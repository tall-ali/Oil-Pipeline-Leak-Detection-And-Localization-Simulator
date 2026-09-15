"""
Pipeline Leak Detection and Localization Engine

Transparent, physics-informed detector for the Oil Pipeline Leak
Detection & Localization Simulator.

The detector receives telemetry only. Ground-truth scenario/location
information must never be passed into this class.

Detection architecture:

    Raw telemetry
        ↓
    Temporal EMA filtering
        ↓
    Hydraulic pressure residual
        ↓
    Flow-balance analysis
        ↓
    Spatial consistency analysis
        ↓
    Evidence fusion
        ↓
    Fault classification
        ↓
    Leak localization + confidence
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class DetectionResult:
    status: str
    severity: str
    estimated_location: Optional[float]
    affected_indices: Optional[Tuple[int, int]]
    leak_rate: float
    fused_anomaly_score: float
    detection_confidence: float
    localization_confidence: float
    flow_score: float
    pressure_score: float
    primary_evidence: str


class PipelineDetector:
    """
    Physics-informed pipeline fault detector.

    The detector uses:
        1. EMA temporal filtering
        2. Flow imbalance
        3. Hydraulic pressure residuals
        4. Spatial consistency
        5. Evidence fusion

    Fault classes:
        NORMAL
        LEAK
        BLOCKAGE
        SENSOR_FAULT
    """

    def __init__(self, length: float, R: float):
        self.length = float(length)
        self.R = float(R)

        # Last localization result.
        self.last_location = None
        self.last_indices = None

        # --------------------------------------------------------------
        # TEMPORAL EMA FILTER STATE
        # --------------------------------------------------------------

        self.filtered_flow_in = None
        self.filtered_flow_out = None
        self.filtered_pressure = None

        # EMA smoothing factor.
        #
        # 1.0  = no smoothing
        # 0.20 = moderate smoothing
        # Lower values = stronger smoothing but more detection lag.
        self.alpha = 0.20

    # ------------------------------------------------------------------
    # RESET
    # ------------------------------------------------------------------

    def reset(self):
        """Reset detector state and clear all EMA filters."""

        self.last_location = None
        self.last_indices = None

        self.filtered_flow_in = None
        self.filtered_flow_out = None
        self.filtered_pressure = None

    # ------------------------------------------------------------------
    # MAIN DETECTION
    # ------------------------------------------------------------------

    def detect(self, telemetry: dict) -> DetectionResult:
        """
        Analyze pipeline telemetry.

        Expected telemetry keys:

            sensor_positions
            pressures
            flow_in
            flow_out
            p_in_setpoint
            q_theoretical
            pressure_noise_std
            flow_noise_std
            dt_seconds

        Ground truth is intentionally not used.
        """

        # --------------------------------------------------------------
        # 1. EXTRACT TELEMETRY
        # --------------------------------------------------------------

        positions = np.asarray(
            telemetry["sensor_positions"],
            dtype=float
        )

        raw_pressure = np.asarray(
            telemetry["pressures"],
            dtype=float
        )

        raw_flow_in = float(
            telemetry["flow_in"]
        )

        raw_flow_out = float(
            telemetry["flow_out"]
        )

        p_in = float(
            telemetry["p_in_setpoint"]
        )

        q_theoretical = float(
            telemetry.get(
                "q_theoretical",
                raw_flow_in
            )
        )

        pressure_noise = max(
            float(
                telemetry.get(
                    "pressure_noise_std",
                    0.2
                )
            ),
            1e-6
        )

        flow_noise = max(
            float(
                telemetry.get(
                    "flow_noise_std",
                    5.0
                )
            ),
            1e-6
        )

        # --------------------------------------------------------------
        # 2. TEMPORAL EMA FILTER
        # --------------------------------------------------------------

        if self.filtered_flow_in is None:

            # First sample initializes the filter.
            self.filtered_flow_in = raw_flow_in
            self.filtered_flow_out = raw_flow_out
            self.filtered_pressure = raw_pressure.copy()

        else:

            alpha = self.alpha

            self.filtered_flow_in = (
                (1.0 - alpha)
                * self.filtered_flow_in
                + alpha
                * raw_flow_in
            )

            self.filtered_flow_out = (
                (1.0 - alpha)
                * self.filtered_flow_out
                + alpha
                * raw_flow_out
            )

            self.filtered_pressure = (
                (1.0 - alpha)
                * self.filtered_pressure
                + alpha
                * raw_pressure
            )

        # Use filtered measurements for detection.
        flow_in = float(
            self.filtered_flow_in
        )

        flow_out = float(
            self.filtered_flow_out
        )

        pressure = np.asarray(
            self.filtered_pressure,
            dtype=float
        )

        # --------------------------------------------------------------
        # 3. EFFECTIVE SENSOR NOISE
        # --------------------------------------------------------------

        # The theoretical steady-state standard deviation of an EMA
        # filtered white-noise signal is:
        #
        # sigma_filtered =
        #     sigma * sqrt(alpha / (2 - alpha))
        #
        # A conservative noise floor is retained so that the detector
        # does not become unrealistically sensitive simply because the
        # signal has been smoothed.

        alpha = self.alpha

        effective_flow_noise = max(
            flow_noise
            * np.sqrt(
                alpha
                / (2.0 - alpha)
            ),
            flow_noise * 0.50
        )

        effective_pressure_noise = max(
            pressure_noise
            * np.sqrt(
                alpha
                / (2.0 - alpha)
            ),
            pressure_noise * 0.50
        )

        # --------------------------------------------------------------
        # 4. FLOW BALANCE
        # --------------------------------------------------------------

        # For a leak:
        #
        # Q_in - Q_out ≈ Q_leak
        #
        # Both flow measurements are volumetric flow rates in m³/h.

        delta_q = (
            flow_in
            - flow_out
        )

        flow_sigma = (
            np.sqrt(2.0)
            * max(
                effective_flow_noise,
                1e-6
            )
        )

        flow_z = (
            abs(delta_q)
            / max(
                flow_sigma,
                1e-9
            )
        )

        flow_score = float(
            np.clip(
                flow_z / 3.0,
                0.0,
                1.0
            )
        )

        # --------------------------------------------------------------
        # 5. EXPECTED PRESSURE PROFILE
        # --------------------------------------------------------------

        # Nominal hydraulic model:
        #
        # P(x) = P_in - R * Q² * x
        #
        # The detector compares measured pressure against the expected
        # pressure profile.

        expected_pressure = (
            p_in
            - self.R
            * (q_theoretical ** 2)
            * positions
        )

        pressure_residual = (
            pressure
            - expected_pressure
        )

        pressure_sigma = max(
            effective_pressure_noise * 3.0,
            1e-6
        )

        max_pressure_residual = float(
            np.max(
                np.abs(
                    pressure_residual
                )
            )
        )

        pressure_score = float(
            np.clip(
                max_pressure_residual
                / pressure_sigma,
                0.0,
                1.0
            )
        )

        # --------------------------------------------------------------
        # 6. SPATIAL CONSISTENCY
        # --------------------------------------------------------------

        residual_sigma = max(
            effective_pressure_noise,
            1e-6
        )

        anomalous = (
            np.abs(
                pressure_residual
            )
            > 2.0 * residual_sigma
        )

        spatial_score = (
            self._spatial_consistency(
                anomalous
            )
        )

        # --------------------------------------------------------------
        # 7. EVIDENCE FUSION
        # --------------------------------------------------------------

        fused_score = (
            0.45 * flow_score
            + 0.35 * pressure_score
            + 0.20 * spatial_score
        )

        fused_score = float(
            np.clip(
                fused_score,
                0.0,
                1.0
            )
        )

        # --------------------------------------------------------------
        # 8. BLOCKAGE DETECTION
        # --------------------------------------------------------------

        blockage_threshold = max(
            0.20 * q_theoretical,
            1e-6
        )

        blockage_condition = (
            flow_in < blockage_threshold
            and flow_out < blockage_threshold
            and q_theoretical > 1e-6
        )

        if blockage_condition:

            (
                location,
                indices,
                loc_conf
            ) = self._locate_blockage(
                positions,
                pressure
            )

            self._remember_location(
                location,
                indices
            )

            return self._build_result(
                status="BLOCKAGE",
                severity="MAJOR",
                estimated_location=location,
                affected_indices=indices,
                leak_rate=0.0,
                fused_anomaly_score=fused_score,
                detection_confidence=float(
                    np.clip(
                        0.50
                        + 0.50 * fused_score,
                        0.0,
                        1.0
                    )
                ),
                localization_confidence=loc_conf,
                flow_score=flow_score,
                pressure_score=pressure_score,
                primary_evidence=(
                    "Very low flow through pipeline"
                ),
            )

        # --------------------------------------------------------------
        # 9. SENSOR FAULT DETECTION
        # --------------------------------------------------------------

        sensor_fault_indices = np.where(
            np.abs(
                pressure_residual
            )
            > 5.0 * residual_sigma
        )[0]

        sensor_fault_condition = (
            len(sensor_fault_indices) == 1
            and flow_z < 2.0
        )

        if sensor_fault_condition:

            faulty_index = int(
                sensor_fault_indices[0]
            )

            location = float(
                positions[faulty_index]
            )

            indices = (
                faulty_index,
                faulty_index
            )

            self._remember_location(
                location,
                indices
            )

            return self._build_result(
                status="SENSOR_FAULT",
                severity="WARNING",
                estimated_location=location,
                affected_indices=indices,
                leak_rate=0.0,
                fused_anomaly_score=fused_score,
                detection_confidence=float(
                    np.clip(
                        0.55
                        + 0.35 * pressure_score,
                        0.0,
                        1.0
                    )
                ),
                localization_confidence=0.95,
                flow_score=flow_score,
                pressure_score=pressure_score,
                primary_evidence=(
                    "Isolated pressure sensor anomaly"
                ),
            )

        # --------------------------------------------------------------
        # 10. LEAK DETECTION
        # --------------------------------------------------------------

        leak_condition = (
            fused_score >= 0.40
            and flow_score >= 0.30
        )

        if leak_condition:

            (
                location,
                indices,
                localization_confidence
            ) = self._locate_leak(
                positions,
                pressure_residual
            )

            # Volumetric leak rate.
            #
            # Units:
            #     m³/h

            leak_rate = max(
                0.0,
                delta_q
            )

            # ----------------------------------------------------------
            # LEAK SEVERITY
            # ----------------------------------------------------------

            if q_theoretical > 1e-9:

                leak_percentage = (
                    leak_rate
                    / q_theoretical
                    * 100.0
                )

            else:

                leak_percentage = 0.0

            if leak_percentage < 10.0:

                severity = "SMALL"

            elif leak_percentage < 25.0:

                severity = "MODERATE"

            else:

                severity = "MAJOR"

            # ----------------------------------------------------------
            # DETECTION CONFIDENCE
            # ----------------------------------------------------------

            detection_confidence = float(
                np.clip(
                    0.45
                    + 0.55 * fused_score,
                    0.0,
                    1.0
                )
            )

            self._remember_location(
                location,
                indices
            )

            return self._build_result(
                status="LEAK",
                severity=severity,
                estimated_location=location,
                affected_indices=indices,
                leak_rate=leak_rate,
                fused_anomaly_score=fused_score,
                detection_confidence=detection_confidence,
                localization_confidence=(
                    localization_confidence
                ),
                flow_score=flow_score,
                pressure_score=pressure_score,
                primary_evidence=(
                    self._primary_evidence(
                        flow_score,
                        pressure_score,
                        spatial_score
                    )
                ),
            )

        # --------------------------------------------------------------
        # 11. NORMAL OPERATION
        # --------------------------------------------------------------

        self._remember_location(
            None,
            None
        )

        return self._build_result(
            status="NORMAL",
            severity="NONE",
            estimated_location=None,
            affected_indices=None,
            leak_rate=0.0,
            fused_anomaly_score=fused_score,
            detection_confidence=float(
                np.clip(
                    1.0 - fused_score,
                    0.0,
                    1.0
                )
            ),
            localization_confidence=0.0,
            flow_score=flow_score,
            pressure_score=pressure_score,
            primary_evidence=(
                "No significant anomaly detected"
            ),
        )

    # ------------------------------------------------------------------
    # SPATIAL CONSISTENCY
    # ------------------------------------------------------------------

    def _spatial_consistency(
        self,
        anomalous: np.ndarray
    ) -> float:
        """
        Determine whether anomalous pressure sensors form a
        spatially consistent cluster.
        """

        n = len(anomalous)

        if n == 0:
            return 0.0

        if n == 1:
            return 0.25

        longest_cluster = 0
        current_cluster = 0

        for value in anomalous:

            if value:

                current_cluster += 1

                longest_cluster = max(
                    longest_cluster,
                    current_cluster
                )

            else:

                current_cluster = 0

        return float(
            np.clip(
                longest_cluster
                / max(n - 1, 1),
                0.0,
                1.0
            )
        )

    # ------------------------------------------------------------------
    # LEAK LOCALIZATION
    # ------------------------------------------------------------------

    def _locate_leak(
        self,
        positions: np.ndarray,
        residual: np.ndarray
    ):
        """
        Estimate leak location from the spatial pressure residual.

        Method:

            1. Absolute pressure residual
            2. Spatial smoothing
            3. Spatial gradient
            4. Strongest transition
            5. Candidate sensor interval
            6. Interval midpoint

        The result represents the most likely affected pipeline
        segment rather than pretending that the exact physical leak
        point is directly observable between sensors.
        """

        n = len(positions)

        if n < 2:

            location = (
                float(positions[0])
                if n
                else None
            )

            indices = (
                (0, 0)
                if n
                else None
            )

            return (
                location,
                indices,
                0.0
            )

        # --------------------------------------------------------------
        # SPATIAL RESIDUAL MAGNITUDE
        # --------------------------------------------------------------

        abs_residual = np.abs(
            residual
        )

        # --------------------------------------------------------------
        # LIGHT SPATIAL SMOOTHING
        # --------------------------------------------------------------

        if n >= 3:

            smoothed = (
                abs_residual.copy()
            )

            for i in range(
                1,
                n - 1
            ):

                smoothed[i] = (
                    0.25
                    * abs_residual[i - 1]
                    + 0.50
                    * abs_residual[i]
                    + 0.25
                    * abs_residual[i + 1]
                )

        else:

            smoothed = abs_residual

        # --------------------------------------------------------------
        # SPATIAL GRADIENT
        # --------------------------------------------------------------

        gradient = np.gradient(
            smoothed,
            positions
        )

        gradient_abs = np.abs(
            gradient
        )

        # --------------------------------------------------------------
        # FIND STRONGEST INTERNAL TRANSITION
        # --------------------------------------------------------------

        if n > 2:

            candidate_gradient = (
                gradient_abs.copy()
            )

            candidate_gradient[0] = -np.inf
            candidate_gradient[-1] = -np.inf

            pivot = int(
                np.argmax(
                    candidate_gradient
                )
            )

        else:

            pivot = int(
                np.argmax(
                    gradient_abs
                )
            )

        # Convert sensor pivot into an interval.
        left_index = max(
            0,
            min(
                pivot - 1,
                n - 2
            )
        )

        right_index = (
            left_index + 1
        )

        # --------------------------------------------------------------
        # RESIDUAL-STRENGTH INTERVAL
        # --------------------------------------------------------------

        interval_strength = (
            smoothed[:-1]
            + smoothed[1:]
        ) / 2.0

        strongest_interval = int(
            np.argmax(
                interval_strength
            )
        )

        # If another interval is substantially stronger,
        # use that interval instead.
        if (
            interval_strength[
                strongest_interval
            ]
            >=
            interval_strength[
                left_index
            ] * 1.15
        ):

            left_index = (
                strongest_interval
            )

            right_index = (
                left_index + 1
            )

        # --------------------------------------------------------------
        # LOCALIZATION = SENSOR INTERVAL MIDPOINT
        # --------------------------------------------------------------

        location = (
            self._interval_midpoint(
                positions,
                left_index,
                right_index
            )
        )

        # Guarantee the location remains inside the selected segment.
        location = float(
            np.clip(
                location,
                float(
                    positions[left_index]
                ),
                float(
                    positions[right_index]
                )
            )
        )

        # --------------------------------------------------------------
        # LOCALIZATION CONFIDENCE
        # --------------------------------------------------------------

        local_signal = float(
            interval_strength[
                left_index
            ]
        )

        global_signal = float(
            np.max(
                smoothed
            )
        )

        if global_signal > 1e-9:

            relative_strength = (
                local_signal
                / global_signal
            )

        else:

            relative_strength = 0.0

        mean_gradient = float(
            np.mean(
                gradient_abs
            )
        )

        gradient_strength = float(
            np.clip(
                gradient_abs[pivot]
                / max(
                    mean_gradient * 3.0,
                    1e-9
                ),
                0.0,
                1.0
            )
        )

        localization_confidence = float(
            np.clip(
                0.45
                * relative_strength
                + 0.55
                * gradient_strength,
                0.0,
                1.0
            )
        )

        return (
            location,
            (
                left_index,
                right_index
            ),
            localization_confidence
        )

    # ------------------------------------------------------------------
    # INTERVAL MIDPOINT
    # ------------------------------------------------------------------

    def _interval_midpoint(
        self,
        positions: np.ndarray,
        left_index: int,
        right_index: int
    ) -> float:
        """
        Return the midpoint of the selected sensor interval.

        Example:

            S1 = 5 km
            S2 = 10 km

            estimated location = 7.5 km
        """

        return float(
            (
                positions[left_index]
                + positions[right_index]
            ) / 2.0
        )

    # ------------------------------------------------------------------
    # BLOCKAGE LOCALIZATION
    # ------------------------------------------------------------------

    def _locate_blockage(
        self,
        positions: np.ndarray,
        pressure: np.ndarray
    ):
        """
        Estimate blockage location from the largest neighboring
        pressure drop.
        """

        n = len(positions)

        if n < 2:

            location = (
                float(positions[0])
                if n
                else None
            )

            indices = (
                (0, 0)
                if n
                else None
            )

            return (
                location,
                indices,
                0.0
            )

        pressure_drop = np.abs(
            np.diff(
                pressure
            )
        )

        index = int(
            np.argmax(
                pressure_drop
            )
        )

        location = (
            float(
                positions[index]
            )
            + float(
                positions[index + 1]
            )
        ) / 2.0

        max_drop = float(
            pressure_drop[index]
        )

        average_drop = float(
            np.mean(
                pressure_drop
            )
        )

        if average_drop > 1e-9:

            confidence = float(
                np.clip(
                    max_drop
                    / (
                        3.0
                        * average_drop
                    ),
                    0.0,
                    1.0
                )
            )

        else:

            confidence = 0.0

        return (
            location,
            (
                index,
                index + 1
            ),
            confidence
        )

    # ------------------------------------------------------------------
    # PRIMARY EVIDENCE
    # ------------------------------------------------------------------

    def _primary_evidence(
        self,
        flow_score: float,
        pressure_score: float,
        spatial_score: float
    ) -> str:

        scores = {
            "Flow imbalance": flow_score,
            "Pressure anomaly": pressure_score,
            "Spatial pressure consistency": spatial_score,
        }

        return max(
            scores,
            key=scores.get
        )

    # ------------------------------------------------------------------
    # STATE
    # ------------------------------------------------------------------

    def _remember_location(
        self,
        location,
        indices
    ):

        self.last_location = location
        self.last_indices = indices

    # ------------------------------------------------------------------
    # RESULT BUILDER
    # ------------------------------------------------------------------

    def _build_result(
        self,
        status,
        severity,
        estimated_location,
        affected_indices,
        leak_rate,
        fused_anomaly_score,
        detection_confidence,
        localization_confidence,
        flow_score,
        pressure_score,
        primary_evidence
    ) -> DetectionResult:

        return DetectionResult(
            status=status,
            severity=severity,
            estimated_location=estimated_location,
            affected_indices=affected_indices,
            leak_rate=float(
                leak_rate
            ),
            fused_anomaly_score=float(
                fused_anomaly_score
            ),
            detection_confidence=float(
                detection_confidence
            ),
            localization_confidence=float(
                localization_confidence
            ),
            flow_score=float(
                flow_score
            ),
            pressure_score=float(
                pressure_score
            ),
            primary_evidence=(
                primary_evidence
            ),
        )
