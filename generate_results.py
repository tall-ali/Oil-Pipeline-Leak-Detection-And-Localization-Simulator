"""
Generate representative engineering figures for the
Oil Pipeline Leak Detection and Localization Simulator.

The script uses the project's existing simulator and detector
so the figures are generated from the same implementation used
by the dashboard.
"""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from sim_engine import PipelineConfig, PipelineSimulator, Scenario
from detector import PipelineDetector


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

OUTPUT_DIR = Path("results/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Number of simulation samples used for each figure.
NUM_STEPS = 80

# Fault location used for leak scenarios.
FAULT_LOCATION_KM = 25.0

# Fixed random seed so the generated figures are reproducible.
RANDOM_SEED = 42


# ------------------------------------------------------------
# Scenario names
# ------------------------------------------------------------

SCENARIOS = [
    (Scenario.NORMAL, "normal_operation.png", "Normal Operation"),
    (Scenario.SMALL_LEAK, "small_leak.png", "Small Leak"),
    (Scenario.MODERATE_LEAK, "moderate_leak.png", "Moderate Leak"),
    (Scenario.MAJOR_LEAK, "major_leak.png", "Major Leak"),
    (Scenario.BLOCKAGE, "blockage.png", "Blockage"),
    (Scenario.SENSOR_FAULT, "sensor_fault.png", "Sensor Fault"),
]


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def normalize_step_output(data):
    """
    Support both simulator return formats:

        telemetry

    and:

        {
            "telemetry": telemetry,
            "ground_truth": ground_truth
        }
    """
    if isinstance(data, dict) and "telemetry" in data:
        telemetry = data["telemetry"]
        ground_truth = data.get("ground_truth", {})
    else:
        telemetry = data
        ground_truth = {}

    return telemetry, ground_truth


def get_value(data, *names, default=None):
    """Safely retrieve the first available key from a dictionary."""
    for name in names:
        if isinstance(data, dict) and name in data:
            return data[name]
    return default


def make_detector(config, simulator):
    """
    Create the detector using the current detector interface.
    """
    R = getattr(simulator, "hydraulic_resistance", None)

    if R is None:
        raise AttributeError(
            "PipelineSimulator does not expose 'hydraulic_resistance'. "
            "Please check sim_engine.py."
        )

    return PipelineDetector(config.length, R)


def configure_simulator(simulator, scenario):
    """
    Configure the simulator for the requested scenario.
    """

    if scenario == Scenario.NORMAL:
        simulator.set_scenario(
            Scenario.NORMAL,
            location=FAULT_LOCATION_KM,
            p_in=70.0,
            noise=0.2,
            faulty_sensor=5
        )

    elif scenario in (
        Scenario.SMALL_LEAK,
        Scenario.MODERATE_LEAK,
        Scenario.MAJOR_LEAK,
    ):
        simulator.set_scenario(
            scenario,
            location=FAULT_LOCATION_KM,
            p_in=70.0,
            noise=0.2,
            faulty_sensor=5
        )

    elif scenario == Scenario.BLOCKAGE:
        simulator.set_scenario(
            Scenario.BLOCKAGE,
            location=FAULT_LOCATION_KM,
            p_in=70.0,
            noise=0.2,
            faulty_sensor=5
        )

    elif scenario == Scenario.SENSOR_FAULT:
        sensor_positions = np.asarray(simulator.sensor_positions)

        faulty_sensor = int(
            np.argmin(
                np.abs(sensor_positions - FAULT_LOCATION_KM)
            )
        )

        simulator.set_scenario(
            Scenario.SENSOR_FAULT,
            location=FAULT_LOCATION_KM,
            p_in=70.0,
            noise=0.2,
            faulty_sensor=faulty_sensor,
        )


def run_scenario(scenario):
    """
    Run one complete simulation scenario and collect telemetry.
    """

    np.random.seed(RANDOM_SEED)

    config = PipelineConfig()
    simulator = PipelineSimulator(config)
    detector = make_detector(config, simulator)

    configure_simulator(simulator, scenario)

    positions = None

    pressure_history = []
    expected_pressure_history = []
    flow_in_history = []
    flow_out_history = []
    flow_balance_history = []
    detection_scores = []
    estimated_locations = []
    statuses = []

    for _ in range(NUM_STEPS):

        raw_data = simulator.step()

        telemetry, ground_truth = normalize_step_output(raw_data)

        # ----------------------------------------------------
        # Sensor positions
        # ----------------------------------------------------

        sensor_positions = get_value(
            telemetry,
            "sensor_positions",
            default=getattr(
                simulator,
                "sensor_positions",
                None,
            ),
        )

        if sensor_positions is not None:
            positions = np.asarray(sensor_positions)

        # ----------------------------------------------------
        # Pressure
        # ----------------------------------------------------

        pressures = get_value(
            telemetry,
            "pressures",
            "pressure",
        )

        if pressures is not None:
            pressures = np.asarray(pressures, dtype=float)
            pressure_history.append(pressures)

        # ----------------------------------------------------
        # Flow
        # ----------------------------------------------------

        flow_in = get_value(
            telemetry,
            "flow_in",
            "q_in",
        )

        flow_out = get_value(
            telemetry,
            "flow_out",
            "q_out",
        )

        if flow_in is not None:
            flow_in_history.append(float(flow_in))

        if flow_out is not None:
            flow_out_history.append(float(flow_out))

        if flow_in is not None and flow_out is not None:
            flow_balance_history.append(
                float(flow_in) - float(flow_out)
            )

        # ----------------------------------------------------
        # Expected pressure
        # ----------------------------------------------------

        p_in = get_value(
            telemetry,
            "p_in_setpoint",
            "p_in_nominal",
            default=getattr(
                config,
                "p_in_ref",
                None,
            ),
        )

        q_theoretical = get_value(
            telemetry,
            "q_theoretical",
            default=getattr(
                config,
                "q_theoretical",
                getattr(
                    simulator,
                    "q_theoretical",
                    None,
                ),
            ),
        )

        R = getattr(simulator, "hydraulic_resistance", None)

        if (
            positions is not None
            and p_in is not None
            and q_theoretical is not None
            and R is not None
        ):
            expected_pressure = (
                float(p_in)
                - R
                * float(q_theoretical) ** 2
                * positions
            )

            expected_pressure_history.append(
                expected_pressure
            )

        # ----------------------------------------------------
        # Detection
        # ----------------------------------------------------

        try:
            result = detector.detect(telemetry)

            detection_scores.append(
                float(
                    getattr(
                        result,
                        "fused_anomaly_score",
                        np.nan,
                    )
                )
            )

            location = getattr(
                result,
                "estimated_location",
                None,
            )

            if location is None:
                estimated_locations.append(np.nan)
            else:
                estimated_locations.append(
                    float(location)
                )

            statuses.append(
                str(
                    getattr(
                        result,
                        "status",
                        "Unknown",
                    )
                )
            )

        except Exception:
            detection_scores.append(np.nan)
            estimated_locations.append(np.nan)
            statuses.append("Unknown")

    # --------------------------------------------------------
    # Convert collected data
    # --------------------------------------------------------

    pressures = np.asarray(
        pressure_history,
        dtype=float,
    )

    expected_pressures = np.asarray(
        expected_pressure_history,
        dtype=float,
    )

    flow_in = np.asarray(
        flow_in_history,
        dtype=float,
    )

    flow_out = np.asarray(
        flow_out_history,
        dtype=float,
    )

    flow_balance = np.asarray(
        flow_balance_history,
        dtype=float,
    )

    scores = np.asarray(
        detection_scores,
        dtype=float,
    )

    locations = np.asarray(
        estimated_locations,
        dtype=float,
    )

    return {
        "positions": positions,
        "pressures": pressures,
        "expected_pressures": expected_pressures,
        "flow_in": flow_in,
        "flow_out": flow_out,
        "flow_balance": flow_balance,
        "scores": scores,
        "locations": locations,
        "statuses": statuses,
    }


# ------------------------------------------------------------
# Figure generation
# ------------------------------------------------------------

def generate_figure(
    scenario,
    filename,
    title,
):
    """
    Generate one representative engineering figure styled 
    identically to the PySide6 SCADA Dashboard.
    """

    print(f"Generating: {title}")

    data = run_scenario(scenario)

    positions = data["positions"]
    pressures = data["pressures"]
    expected_pressures = data["expected_pressures"]
    flow_in = data["flow_in"]
    flow_out = data["flow_out"]
    flow_balance = data["flow_balance"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), dpi=180)
    fig.patch.set_facecolor('#0b1121')

    # --------------------------------------------------------
    # Main pressure plot
    # --------------------------------------------------------
    ax1.set_facecolor('#1e293b')

    if pressures.size > 0 and positions is not None:
        measured_pressure = np.mean(pressures[-10:], axis=0)  # Use last few stable frames

        if expected_pressures.size > 0:
            expected_pressure = np.mean(expected_pressures[-10:], axis=0)
            ax1.plot(
                positions,
                expected_pressure,
                color='#64748b',
                linestyle="--",
                linewidth=1.5,
                label="Nominal Model",
            )

        ax1.plot(
            positions,
            measured_pressure,
            color='#38bdf8',
            marker="o",
            linewidth=2,
            label="Measured Pressure",
        )

        # Plot Ground Truth Fault Marker
        if scenario in [Scenario.SMALL_LEAK, Scenario.MODERATE_LEAK, Scenario.MAJOR_LEAK]:
            ax1.axvline(x=FAULT_LOCATION_KM, color='#f43f5e', linestyle='--', linewidth=2, label="True Leak Location")
        elif scenario == Scenario.BLOCKAGE:
            ax1.axvline(x=FAULT_LOCATION_KM, color='#fbbf24', linestyle='--', linewidth=2, label="True Blockage Location")
        elif scenario == Scenario.SENSOR_FAULT:
            fault_idx = int(np.argmin(np.abs(positions - FAULT_LOCATION_KM)))
            ax1.plot(positions[fault_idx], measured_pressure[fault_idx], marker='X', color='#f43f5e', markersize=14, linestyle='None', label="Faulty Sensor")

        ax1.set_xlabel("Pipeline Distance (km)", color='#94a3b8')
        ax1.set_ylabel("Pressure (bar)", color='#94a3b8')
        ax1.set_title(f"{title} — Hydraulic Pressure Profile", color='#e2e8f0', fontsize=12, fontweight='bold')
        
        ax1.tick_params(colors='#94a3b8')
        ax1.grid(True, color='#334155', linestyle='-', alpha=0.6)
        
        ax1.spines['bottom'].set_color('#475569')
        ax1.spines['left'].set_color('#475569')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        
        ax1.legend(facecolor='#0f172a', edgecolor='#334155', labelcolor='#f8fafc', loc='upper right')

    # --------------------------------------------------------
    # Flow plot
    # --------------------------------------------------------
    ax2.set_facecolor('#1e293b')

    if len(flow_in) > 0 and len(flow_out) > 0:
        steps_array = np.arange(len(flow_in))

        ax2.plot(steps_array, flow_in, color='#10b981', linewidth=2, label="Inlet Flow")
        ax2.plot(steps_array, flow_out, color='#f43f5e', linewidth=2, label="Outlet Flow")
        
        # Create secondary axis for the residual to match dashboard
        ax2_res = ax2.twinx()
        ax2_res.plot(steps_array, flow_balance, color='#fbbf24', linestyle=":", linewidth=1.5, label="Residual ΔQ")
        
        # Axis 2 Styling
        ax2.set_xlabel("Simulation Step", color='#94a3b8')
        ax2.set_ylabel("Volumetric Flow (m³/h)", color='#94a3b8')
        ax2.set_title(f"{title} — Transient Flow Behavior", color='#e2e8f0', fontsize=12, fontweight='bold')
        
        ax2.tick_params(colors='#94a3b8')
        ax2.grid(True, color='#334155', linestyle='-', alpha=0.6)
        
        ax2.spines['bottom'].set_color('#475569')
        ax2.spines['left'].set_color('#475569')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        
        # Axis 2 Residual Styling
        ax2_res.set_ylabel("Residual (m³/h)", color='#fbbf24')
        ax2_res.tick_params(colors='#fbbf24')
        ax2_res.spines['top'].set_visible(False)
        ax2_res.spines['left'].set_visible(False)
        ax2_res.spines['bottom'].set_visible(False)
        ax2_res.spines['right'].set_color('#475569')

        # Combine legends
        lines_1, labels_1 = ax2.get_legend_handles_labels()
        lines_2, labels_2 = ax2_res.get_legend_handles_labels()
        ax2.legend(lines_1 + lines_2, labels_1 + labels_2, facecolor='#0f172a', edgecolor='#334155', labelcolor='#f8fafc', loc='upper left')

    fig.suptitle(
        "Oil Pipeline Leak Detection & Diagnostics Simulator",
        fontsize=14,
        fontweight="bold",
        color="#f8fafc"
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96], pad=2.0)

    output_path = OUTPUT_DIR / filename

    fig.savefig(
        output_path,
        dpi=180,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )

    plt.close(fig)

    print(f"  Saved: {output_path}")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    print()
    print("=" * 60)
    print("Generating pipeline simulation result figures")
    print("=" * 60)
    print()

    for scenario, filename, title in SCENARIOS:

        try:
            generate_figure(
                scenario,
                filename,
                title,
            )

        except Exception as exc:

            print()
            print(
                f"ERROR while generating {title}:"
            )
            print(exc)
            print()

            raise

    print()
    print("=" * 60)
    print("All figures generated successfully.")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
