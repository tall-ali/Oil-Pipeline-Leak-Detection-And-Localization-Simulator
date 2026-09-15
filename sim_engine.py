import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Dict


class Scenario(Enum):
    NORMAL = "Normal Operation"
    SMALL_LEAK = "Small Leak"
    MODERATE_LEAK = "Moderate Leak"
    MAJOR_LEAK = "Major Leak"
    BLOCKAGE = "Blockage"
    SENSOR_FAULT = "Sensor Fault"


@dataclass
class PipelineConfig:
    length: float = 50.0
    num_sensors: int = 11

    p_in_ref: float = 70.0
    p_out_ref: float = 20.0

    q_ref: float = 500.0

    pressure_noise_std: float = 0.2
    flow_noise_std: float = 5.0

    # Simulation time represented by each generated telemetry sample.
    dt_seconds: float = 0.5


class PipelineSimulator:
    """
    Simplified steady-state 1-D pipeline simulator.

    Model:
        Pump -> pipeline -> outlet

    The simulator generates virtual pressure and flow sensors for:
        - Normal operation
        - Small leak
        - Moderate leak
        - Major leak
        - Blockage
        - Sensor fault

    Important:
        This is NOT a CFD model or a full transient pipeline model.
        It is intentionally simplified for an undergraduate diagnostic
        and visualization project.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config

        # Sensor positions along the pipeline.
        self.sensor_positions = np.linspace(
            0.0,
            config.length,
            config.num_sensors
        )

        # Simplified hydraulic resistance:
        #
        #     ΔP = R * Q² * L
        #
        # Therefore:
        #
        #     R = ΔP / (Q² L)
        #
        delta_p_ref = (
            config.p_in_ref
            - config.p_out_ref
        )

        self.hydraulic_resistance = (
            delta_p_ref
            / (
                config.length
                * config.q_ref ** 2
            )
        )

        self.current_scenario = Scenario.NORMAL

        # Ground-truth parameters belong only to the simulator.
        # They are never passed to the detector.
        self.true_location = config.length / 2.0
        self.faulty_sensor_index = config.num_sensors // 2

        self.p_in_actual = config.p_in_ref

        # Runtime sensor-noise setting.
        self.pressure_noise_std = (
            config.pressure_noise_std
        )

        self.time_step = 0

    # ================================================================
    # CONFIGURATION
    # ================================================================

    def set_scenario(
        self,
        scenario: Scenario,
        location: float,
        p_in: float,
        noise: float,
        faulty_sensor: int
    ):
        """
        Configure the current simulation scenario.

        Ground truth is maintained internally by the simulator.
        """

        self.current_scenario = scenario

        self.true_location = float(
            np.clip(
                location,
                0.1,
                self.config.length - 0.1
            )
        )

        self.p_in_actual = float(
            p_in
        )

        self.pressure_noise_std = max(
            0.0,
            float(noise)
        )

        self.faulty_sensor_index = int(
            np.clip(
                faulty_sensor,
                0,
                self.config.num_sensors - 1
            )
        )

    # ================================================================
    # NOMINAL FLOW
    # ================================================================

    def _get_theoretical_nominal_flow(self) -> float:
        """
        Calculate nominal pipeline flow from the current inlet
        pressure and fixed outlet pressure.
        """

        delta_p = max(
            0.0,
            self.p_in_actual
            - self.config.p_out_ref
        )

        q = np.sqrt(
            delta_p
            / (
                self.hydraulic_resistance
                * self.config.length
            )
        )

        return float(q)

    # ================================================================
    # LEAK FLOW SOLVER
    # ================================================================

    def _solve_leak_flows(
        self,
        q_nominal: float,
        leak_rate: float,
        leak_location: float
    ):
        """
        Estimate upstream and downstream pipeline flow for a leak.

        Conditions:

            Q_in - Q_out = Q_leak

        and the simplified pressure-drop relationship is maintained
        on both sides of the leak.

        This is more physically consistent than simply adding and
        subtracting half the leak rate from the nominal flow.
        """

        if leak_rate <= 0.0:
            return (
                q_nominal,
                q_nominal
            )

        L = self.config.length
        x = float(
            np.clip(
                leak_location,
                0.1,
                L - 0.1
            )
        )

        R = self.hydraulic_resistance

        delta_p = max(
            0.0,
            self.p_in_actual
            - self.config.p_out_ref
        )

        # Let:
        #
        #     Q_out = q
        #     Q_in  = q + Q_leak
        #
        # From:
        #
        # ΔP =
        # R[(Q_out + Q_leak)^2 x
        #  + Q_out^2(L-x)]
        #
        # we obtain:
        #
        # A q² + B q + C = 0
        #
        A = L

        B = (
            2.0
            * leak_rate
            * x
        )

        C = (
            leak_rate ** 2
            * x
            - delta_p / R
        )

        discriminant = (
            B ** 2
            - 4.0 * A * C
        )

        if discriminant > 0.0:
            q_out = (
                -B
                + np.sqrt(discriminant)
            ) / (
                2.0 * A
            )

            q_out = max(
                0.0,
                q_out
            )

            q_in = (
                q_out
                + leak_rate
            )

            return (
                float(q_in),
                float(q_out)
            )

        # Safety fallback for an extreme parameter combination.
        q_out = max(
            0.0,
            q_nominal
            - 0.5 * leak_rate
        )

        q_in = (
            q_out
            + leak_rate
        )

        return (
            float(q_in),
            float(q_out)
        )

    # ================================================================
    # PRESSURE PROFILE
    # ================================================================

    def _generate_normal_pressure_profile(
        self,
        p_in_noisy: float,
        q: float
    ) -> np.ndarray:
        """
        Generate the nominal pressure profile.
        """

        pressures = (
            p_in_noisy
            - (
                self.hydraulic_resistance
                * q ** 2
                * self.sensor_positions
            )
        )

        return pressures

    # ================================================================
    # LEAK PRESSURE PROFILE
    # ================================================================

    def _generate_leak_pressure_profile(
        self,
        p_in_noisy: float,
        q_in: float,
        q_out: float,
        leak_rate: float
    ) -> np.ndarray:
        """
        Generate a continuous pressure profile with a hydraulic
        slope change around the leak location.

        Upstream:
            P(x) = P_in - R Q_in² x

        Downstream:
            P(x) = P_leak - R Q_out² (x-x_leak)
        """

        x_leak = self.true_location

        p_leak = (
            p_in_noisy
            - (
                self.hydraulic_resistance
                * q_in ** 2
                * x_leak
            )
        )

        pressures = np.zeros_like(
            self.sensor_positions,
            dtype=float
        )

        for i, x in enumerate(
            self.sensor_positions
        ):

            if x <= x_leak:
                pressures[i] = (
                    p_in_noisy
                    - (
                        self.hydraulic_resistance
                        * q_in ** 2
                        * x
                    )
                )

            else:
                pressures[i] = (
                    p_leak
                    - (
                        self.hydraulic_resistance
                        * q_out ** 2
                        * (x - x_leak)
                    )
                )

        return pressures

    # ================================================================
    # BLOCKAGE PROFILE
    # ================================================================

    def _generate_blockage_pressure_profile(
        self,
        p_in_noisy: float,
        q_theoretical: float
    ):
        """
        Simplified blockage model.

        A blockage drastically reduces flow and creates a large
        pressure discontinuity around the blockage location.

        This intentionally remains a simple diagnostic model rather
        than attempting a detailed valve/pipe-resistance model.
        """

        blockage_flow_factor = 0.05

        q_blocked = (
            q_theoretical
            * blockage_flow_factor
        )

        x_block = self.true_location

        pressures = np.zeros_like(
            self.sensor_positions,
            dtype=float
        )

        for i, x in enumerate(
            self.sensor_positions
        ):

            if x <= x_block:

                pressures[i] = (
                    p_in_noisy
                    - (
                        self.hydraulic_resistance
                        * q_blocked ** 2
                        * x
                    )
                )

            else:

                pressures[i] = (
                    self.config.p_out_ref
                    + (
                        self.hydraulic_resistance
                        * q_blocked ** 2
                        * (
                            self.config.length
                            - x
                        )
                    )
                )

        return (
            pressures,
            q_blocked
        )

    # ================================================================
    # MAIN SIMULATION STEP
    # ================================================================

    def step(self) -> Dict[str, Dict]:
        """
        Generate one telemetry sample.

        Returns two separate dictionaries:

            telemetry
                What a real monitoring system would receive.

            ground_truth
                Hidden simulator information used only for validation.
        """

        self.time_step += 1

        q_theoretical = (
            self._get_theoretical_nominal_flow()
        )

        # ------------------------------------------------------------
        # Leak magnitude
        # ------------------------------------------------------------

        leak_rates = {
            Scenario.NORMAL:
                0.0,

            Scenario.SMALL_LEAK:
                q_theoretical * 0.05,

            Scenario.MODERATE_LEAK:
                q_theoretical * 0.15,

            Scenario.MAJOR_LEAK:
                q_theoretical * 0.30,

            Scenario.BLOCKAGE:
                0.0,

            Scenario.SENSOR_FAULT:
                0.0
        }

        true_leak_rate = float(
            leak_rates.get(
                self.current_scenario,
                0.0
            )
        )

        # Small pump-pressure uncertainty.
        p_in_noisy = (
            self.p_in_actual
            + np.random.normal(
                0.0,
                self.pressure_noise_std * 0.2
            )
        )

        # ============================================================
        # NORMAL / SENSOR FAULT
        # ============================================================

        if self.current_scenario in (
            Scenario.NORMAL,
            Scenario.SENSOR_FAULT
        ):

            q_in = q_theoretical
            q_out = q_theoretical

            pressures = (
                self._generate_normal_pressure_profile(
                    p_in_noisy,
                    q_theoretical
                )
            )

        # ============================================================
        # LEAK
        # ============================================================

        elif self.current_scenario in (
            Scenario.SMALL_LEAK,
            Scenario.MODERATE_LEAK,
            Scenario.MAJOR_LEAK
        ):

            q_in, q_out = (
                self._solve_leak_flows(
                    q_theoretical,
                    true_leak_rate,
                    self.true_location
                )
            )

            pressures = (
                self._generate_leak_pressure_profile(
                    p_in_noisy,
                    q_in,
                    q_out,
                    true_leak_rate
                )
            )

        # ============================================================
        # BLOCKAGE
        # ============================================================

        elif self.current_scenario == Scenario.BLOCKAGE:

            pressures, q_blocked = (
                self._generate_blockage_pressure_profile(
                    p_in_noisy,
                    q_theoretical
                )
            )

            q_in = q_blocked
            q_out = q_blocked

        else:

            q_in = q_theoretical
            q_out = q_theoretical

            pressures = (
                self._generate_normal_pressure_profile(
                    p_in_noisy,
                    q_theoretical
                )
            )

        # ------------------------------------------------------------
        # Pressure sensor noise
        # ------------------------------------------------------------

        pressures = (
            pressures
            + np.random.normal(
                0.0,
                self.pressure_noise_std,
                size=pressures.shape
            )
        )

        # ------------------------------------------------------------
        # Flow sensor noise
        # ------------------------------------------------------------

        measured_q_in = (
            q_in
            + np.random.normal(
                0.0,
                self.config.flow_noise_std
            )
        )

        measured_q_out = (
            q_out
            + np.random.normal(
                0.0,
                self.config.flow_noise_std
            )
        )

        # ------------------------------------------------------------
        # Inject sensor fault AFTER normal hydraulic simulation.
        #
        # This ensures the fault represents a measurement problem,
        # not a physical pipeline change.
        # ------------------------------------------------------------

        if self.current_scenario == Scenario.SENSOR_FAULT:

            pressures[
                self.faulty_sensor_index
            ] = 0.0

        # ============================================================
        # TELEMETRY
        # ============================================================

        telemetry = {
            "timestamp":
                self.time_step,

            "flow_in":
                float(measured_q_in),

            "flow_out":
                float(measured_q_out),

            "sensor_positions":
                self.sensor_positions.copy(),

            "pressures":
                pressures.copy(),

            "q_theoretical":
                float(q_theoretical),

            "p_in_setpoint":
                float(self.p_in_actual),

            "pressure_noise_std":
                float(self.pressure_noise_std),

            "flow_noise_std":
                float(
                    self.config.flow_noise_std
                ),

            "dt_seconds":
                float(
                    self.config.dt_seconds
                )
        }

        # ============================================================
        # GROUND TRUTH
        # ============================================================
        #
        # IMPORTANT:
        # This information is NOT included in telemetry.
        # The detector cannot see it.
        #
        # It exists only so the dashboard can calculate:
        #
        #     estimated location
        #     true location
        #     localization error
        #
        # during validation.
        # ============================================================

        ground_truth = {
            "scenario":
                self.current_scenario.value,

            "true_location":
                float(self.true_location),

            "true_leak_rate":
                float(true_leak_rate)
        }

        return {
            "telemetry":
                telemetry,

            "ground_truth":
                ground_truth
        }
