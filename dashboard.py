import sys
from datetime import datetime
from collections import deque

import numpy as np
import pandas as pd

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSlider,
    QGroupBox,
    QFormLayout,
    QFrame,
    QFileDialog,
    QTextEdit,
    QScrollArea,
)

from PySide6.QtCore import Qt, QTimer

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from sim_engine import PipelineSimulator, PipelineConfig, Scenario
from detector import PipelineDetector


# ================================================================
# STYLE
# ================================================================

QSS = """
QMainWindow {
    background-color: #0b1121;
}

QWidget {
    color: #e2e8f0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    margin-top: 15px;
    padding: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    color: #94a3b8;
    font-weight: bold;
    font-size: 12px;
}

QPushButton {
    background-color: #3b82f6;
    color: white;
    border-radius: 4px;
    padding: 6px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #2563eb;
}

QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #334155;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #38bdf8;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QTextEdit {
    background-color: #0f172a;
    border: 1px solid #334155;
    color: #38bdf8;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}

QLabel#Data {
    font-family: 'Consolas', monospace;
    font-weight: bold;
    color: #f8fafc;
}

/* Custom Scrollbar for smaller screens */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #0b1121;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
"""


# ================================================================
# PLOTTING CANVAS
# ================================================================

class MultiPlotCanvas(FigureCanvas):

    def __init__(self, parent=None, dpi=100):
        self.fig = Figure(
            figsize=(8, 8),
            dpi=dpi
        )

        self.fig.patch.set_facecolor(
            "#1e293b"
        )

        self.ax_sch = self.fig.add_subplot(311)
        self.ax_pres = self.fig.add_subplot(312)
        self.ax_flow = self.fig.add_subplot(313)

        # Secondary axis for flow residual.
        self.ax_flow_res = self.ax_flow.twinx()

        self._style_axes()

        self.fig.subplots_adjust(
            left=0.08,
            right=0.92,
            top=0.95,
            bottom=0.15,
            hspace=0.65
        )

        super().__init__(
            self.fig
        )

    def _style_axes(self):

        for ax in [
            self.ax_sch,
            self.ax_pres,
            self.ax_flow
        ]:

            ax.set_facecolor(
                "#0f172a"
            )

            ax.spines["top"].set_visible(
                False
            )

            ax.spines["right"].set_visible(
                False
            )

            ax.spines["bottom"].set_color(
                "#475569"
            )

            ax.spines["left"].set_color(
                "#475569"
            )

            ax.tick_params(
                colors="#94a3b8",
                labelsize=9
            )

        self.ax_flow_res.set_facecolor(
            "none"
        )

        self.ax_flow_res.spines[
            "top"
        ].set_visible(False)

        self.ax_flow_res.spines[
            "left"
        ].set_visible(False)

        self.ax_flow_res.spines[
            "right"
        ].set_color("#475569")

        self.ax_flow_res.tick_params(
            colors="#fbbf24",
            labelsize=9
        )


# ================================================================
# MAIN DASHBOARD
# ================================================================

class PipelineDashboard(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Pipeline Diagnostics & Validation Simulator"
        )

        self.resize(
            1400,
            900
        )

        # ------------------------------------------------------------
        # Core simulation
        # ------------------------------------------------------------

        self.config = PipelineConfig()

        self.sim = PipelineSimulator(
            self.config
        )

        self.detector = PipelineDetector(
            self.config.length,
            self.sim.hydraulic_resistance
        )

        # ------------------------------------------------------------
        # Logging
        # ------------------------------------------------------------

        self.logged_data = []

        self.cumulative_volume_lost = 0.0

        # ------------------------------------------------------------
        # History
        # ------------------------------------------------------------

        self.hist_len = 60

        self.f_in_hist = deque(
            [self.config.q_ref] * self.hist_len,
            maxlen=self.hist_len
        )

        self.f_out_hist = deque(
            [self.config.q_ref] * self.hist_len,
            maxlen=self.hist_len
        )

        self.f_diff_hist = deque(
            [0.0] * self.hist_len,
            maxlen=self.hist_len
        )

        dt = self.config.dt_seconds

        self.time_hist = deque(
            [
                i * dt
                for i in range(
                    -self.hist_len + 1,
                    1
                )
            ],
            maxlen=self.hist_len
        )

        # ------------------------------------------------------------
        # Timer
        # ------------------------------------------------------------

        self.timer = QTimer()

        self.timer.timeout.connect(
            self.run_step
        )

        self.is_running = False

        # ------------------------------------------------------------
        # UI
        # ------------------------------------------------------------

        self.init_ui()

        self.reset_simulation()

    # ================================================================
    # UI
    # ================================================================

    def init_ui(self):

        main_widget = QWidget()

        self.setCentralWidget(
            main_widget
        )

        main_layout = QVBoxLayout(
            main_widget
        )

        # ============================================================
        # KPI HEADER
        # ============================================================

        kpi_layout = QHBoxLayout()

        card_status, self.lbl_status = (
            self.make_kpi_card(
                "SYSTEM STATUS",
                "NORMAL",
                "#10b981"
            )
        )

        card_pressure, self.lbl_pressure = (
            self.make_kpi_card(
                "INLET PRESSURE",
                "70.0 bar",
                "#38bdf8"
            )
        )

        card_vol, self.lbl_vol_loss = (
            self.make_kpi_card(
                "TOTAL VOLUME LOST",
                "0.000 m³",
                "#f43f5e"
            )
        )

        kpi_layout.addWidget(
            card_status
        )

        kpi_layout.addWidget(
            card_pressure
        )

        kpi_layout.addWidget(
            card_vol
        )

        main_layout.addLayout(
            kpi_layout
        )

        # ============================================================
        # BODY
        # ============================================================

        body_layout = QHBoxLayout()

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(380)

        left_widget = QWidget()
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(0, 0, 10, 0)

        # ============================================================
        # OPERATIONS COMMAND
        # ============================================================

        ctrl_group = QGroupBox(
            "OPERATIONS COMMAND"
        )

        ctrl_layout = QFormLayout()

        self.combo_scenario = QComboBox()

        self.combo_scenario.addItems(
            [
                s.value
                for s in Scenario
            ]
        )

        self.combo_scenario.currentTextChanged.connect(
            self.update_params
        )

        self.sld_loc, self.lbl_loc = (
            self.make_slider(
                1,
                int(self.config.length - 1),
                25,
                "km"
            )
        )

        self.sld_pump, self.lbl_pump = (
            self.make_slider(
                40,
                100,
                70,
                "bar"
            )
        )

        self.sld_noise, self.lbl_noise = (
            self.make_slider(
                0,
                10,
                2,
                "bar",
                scale=10.0
            )
        )

        ctrl_layout.addRow(
            "SCENARIO:",
            self.combo_scenario
        )

        ctrl_layout.addRow(
            "FAULT LOCATION:",
            self.wrap_slider(
                self.sld_loc,
                self.lbl_loc
            )
        )

        ctrl_layout.addRow(
            "INLET PRESSURE:",
            self.wrap_slider(
                self.sld_pump,
                self.lbl_pump
            )
        )

        ctrl_layout.addRow(
            "SENSOR NOISE:",
            self.wrap_slider(
                self.sld_noise,
                self.lbl_noise
            )
        )

        ctrl_group.setLayout(
            ctrl_layout
        )

        left_panel.addWidget(
            ctrl_group
        )

        # ============================================================
        # BUTTONS
        # ============================================================

        btn_layout = QHBoxLayout()

        self.btn_run = QPushButton(
            "▶ RUN SIMULATION"
        )

        self.btn_run.clicked.connect(
            self.toggle_sim
        )

        self.btn_reset = QPushButton(
            "⟳ RESET"
        )

        self.btn_reset.clicked.connect(
            self.reset_simulation
        )

        self.btn_csv = QPushButton(
            "↓ EXPORT CSV"
        )

        self.btn_csv.clicked.connect(
            self.export_csv
        )

        btn_layout.addWidget(
            self.btn_run
        )

        btn_layout.addWidget(
            self.btn_reset
        )

        btn_layout.addWidget(
            self.btn_csv
        )

        left_panel.addLayout(
            btn_layout
        )

        # ============================================================
        # SYSTEM DIAGNOSIS
        # ============================================================

        diag_group = QGroupBox(
            "SYSTEM DIAGNOSIS"
        )

        diag_layout = QFormLayout()

        self.lbl_diag_type = QLabel("-")
        self.lbl_diag_type.setObjectName("Data")

        self.lbl_diag_sev = QLabel("-")
        self.lbl_diag_sev.setObjectName("Data")

        self.lbl_diag_loc = QLabel("-")
        self.lbl_diag_loc.setObjectName("Data")

        self.lbl_diag_seg = QLabel("-")
        self.lbl_diag_seg.setObjectName("Data")

        self.lbl_diag_rate = QLabel("-")
        self.lbl_diag_rate.setObjectName("Data")

        self.lbl_diag_ano = QLabel("-")
        self.lbl_diag_ano.setObjectName("Data")

        self.lbl_diag_dconf = QLabel("-")
        self.lbl_diag_dconf.setObjectName("Data")

        self.lbl_diag_lconf = QLabel("-")
        self.lbl_diag_lconf.setObjectName("Data")

        diag_layout.addRow(
            "FAULT TYPE:",
            self.lbl_diag_type
        )

        diag_layout.addRow(
            "SEVERITY:",
            self.lbl_diag_sev
        )

        diag_layout.addRow(
            "EST. LOCATION:",
            self.lbl_diag_loc
        )

        diag_layout.addRow(
            "AFFECTED SEGMENT:",
            self.lbl_diag_seg
        )

        diag_layout.addRow(
            "EST. LEAK RATE:",
            self.lbl_diag_rate
        )

        diag_layout.addRow(
            "ANOMALY SCORE:",
            self.lbl_diag_ano
        )

        diag_layout.addRow(
            "DETECTION CONFIDENCE:",
            self.lbl_diag_dconf
        )

        diag_layout.addRow(
            "LOCALIZATION CONFIDENCE:",
            self.lbl_diag_lconf
        )

        diag_group.setLayout(
            diag_layout
        )

        left_panel.addWidget(
            diag_group
        )

        # ============================================================
        # VALIDATION
        # ============================================================

        valid_group = QGroupBox(
            "VALIDATION / GROUND TRUTH"
        )

        valid_layout = QFormLayout()

        self.lbl_val_true = QLabel("-")
        self.lbl_val_true.setObjectName(
            "Data"
        )

        self.lbl_val_est = QLabel("-")
        self.lbl_val_est.setObjectName(
            "Data"
        )

        self.lbl_val_err = QLabel("-")
        self.lbl_val_err.setObjectName(
            "Data"
        )

        valid_layout.addRow(
            "TRUE FAULT LOCATION:",
            self.lbl_val_true
        )

        valid_layout.addRow(
            "ESTIMATED LOCATION:",
            self.lbl_val_est
        )

        valid_layout.addRow(
            "LOCALIZATION ERROR:",
            self.lbl_val_err
        )

        valid_group.setLayout(
            valid_layout
        )

        left_panel.addWidget(
            valid_group
        )

        # ============================================================
        # EVENT LOG
        # ============================================================

        left_panel.addWidget(
            QLabel("EVENT LOG")
        )

        self.event_log = QTextEdit()

        self.event_log.setReadOnly(
            True
        )

        self.event_log.setMinimumHeight(
            80
        )

        left_panel.addWidget(
            self.event_log
        )

        # Set the fully built left panel into the Scroll Area
        left_scroll.setWidget(
            left_widget
        )

        # ============================================================
        # CANVAS
        # ============================================================

        self.canvas = MultiPlotCanvas(
            self
        )

        body_layout.addWidget(
            left_scroll,
            1
        )

        body_layout.addWidget(
            self.canvas,
            3
        )

        main_layout.addLayout(
            body_layout
        )

    # ================================================================
    # KPI CARD
    # ================================================================

    def make_kpi_card(
        self,
        title,
        value,
        color
    ):

        frame = QFrame()

        frame.setStyleSheet(
            f"""
            background-color: #1e293b;
            border-left: 4px solid {color};
            border-radius: 4px;
            """
        )

        layout = QVBoxLayout(
            frame
        )

        lbl_title = QLabel(
            title
        )

        lbl_title.setStyleSheet(
            """
            color: #94a3b8;
            font-size: 10px;
            font-weight: bold;
            """
        )

        lbl_value = QLabel(
            value
        )

        lbl_value.setStyleSheet(
            f"""
            color: {color};
            font-size: 20px;
            font-weight: bold;
            font-family: 'Consolas', monospace;
            """
        )

        layout.addWidget(
            lbl_title
        )

        layout.addWidget(
            lbl_value
        )

        return (
            frame,
            lbl_value
        )

    # ================================================================
    # SLIDER
    # ================================================================

    def make_slider(
        self,
        v_min,
        v_max,
        start,
        unit,
        scale=1.0
    ):

        slider = QSlider(
            Qt.Horizontal
        )

        slider.setRange(
            v_min,
            v_max
        )

        slider.setValue(
            start
        )

        label = QLabel(
            f"{start / scale:.1f} {unit}"
        )

        label.setObjectName(
            "Data"
        )

        slider.valueChanged.connect(
            self.update_params
        )

        return (
            slider,
            label
        )

    def wrap_slider(
        self,
        slider,
        label
    ):

        layout = QHBoxLayout()

        layout.addWidget(
            slider
        )

        layout.addWidget(
            label
        )

        return layout

    # ================================================================
    # PARAMETERS
    # ================================================================

    def update_params(self):

        scenario = next(
            s
            for s in Scenario
            if s.value
            == self.combo_scenario.currentText()
        )

        location = self.sld_loc.value()

        pump = self.sld_pump.value()

        noise = (
            self.sld_noise.value()
            / 10.0
        )

        self.lbl_loc.setText(
            f"{location:.1f} km"
        )

        self.lbl_pump.setText(
            f"{pump} bar"
        )

        self.lbl_noise.setText(
            f"{noise:.1f} bar"
        )

        closest_sensor = int(
            np.argmin(
                np.abs(
                    self.sim.sensor_positions
                    - location
                )
            )
        )

        self.sim.set_scenario(
            scenario,
            float(location),
            float(pump),
            float(noise),
            closest_sensor
        )

        # VERY IMPORTANT:
        # Parameter changes represent a new simulation condition.
        # Clear detector memory so the old leak signature cannot
        # influence the new scenario.
        self.detector.reset()

    # ================================================================
    # RUN / PAUSE
    # ================================================================

    def toggle_sim(self):

        if self.is_running:

            self.timer.stop()

            self.btn_run.setText(
                "▶ RUN SIMULATION"
            )

            self.btn_run.setStyleSheet(
                ""
            )

            self.log_event(
                "Simulation paused."
            )

            self.is_running = False

        else:

            self.timer.start(
                int(
                    self.config.dt_seconds
                    * 1000
                )
            )

            self.btn_run.setText(
                "⏸ PAUSE"
            )

            self.btn_run.setStyleSheet(
                """
                background-color: #0f172a;
                border: 1px solid #3b82f6;
                """
            )

            self.log_event(
                "Simulation started."
            )

            self.is_running = True

    # ================================================================
    # RESET
    # ================================================================

    def reset_simulation(self):

        self.timer.stop()

        self.is_running = False

        self.btn_run.setText(
            "▶ RUN SIMULATION"
        )

        self.btn_run.setStyleSheet(
            ""
        )

        self.sim.time_step = 0

        self.cumulative_volume_lost = 0.0

        self.logged_data.clear()

        self.event_log.clear()

        self.detector.reset()

        self.time_hist.clear()

        dt = self.config.dt_seconds

        self.time_hist.extend(
            [
                i * dt
                for i in range(
                    -self.hist_len + 1,
                    1
                )
            ]
        )

        self.f_in_hist.clear()

        self.f_in_hist.extend(
            [
                self.config.q_ref
            ] * self.hist_len
        )

        self.f_out_hist.clear()

        self.f_out_hist.extend(
            [
                self.config.q_ref
            ] * self.hist_len
        )

        self.f_diff_hist.clear()

        self.f_diff_hist.extend(
            [
                0.0
            ] * self.hist_len
        )

        self.log_event(
            "System initialized. Nominal state configured."
        )

        # Apply current GUI settings.
        self.update_params()

        # Generate one initial sample.
        self.run_step()

    # ================================================================
    # EVENT LOG
    # ================================================================

    def log_event(
        self,
        message: str
    ):

        timestamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        self.event_log.append(
            f"[{timestamp}] {message}"
        )

        scrollbar = (
            self.event_log.verticalScrollBar()
        )

        scrollbar.setValue(
            scrollbar.maximum()
        )

    # ================================================================
    # MAIN SIMULATION STEP
    # ================================================================

    def run_step(self):

        data = self.sim.step()

        telemetry = data[
            "telemetry"
        ]

        ground_truth = data[
            "ground_truth"
        ]

        result = self.detector.detect(
            telemetry
        )

        # ------------------------------------------------------------
        # Localization validation
        # ------------------------------------------------------------

        loc_error = None

        if (
            result.estimated_location
            is not None
            and ground_truth["scenario"]
            != Scenario.NORMAL.value
        ):

            loc_error = abs(
                result.estimated_location
                - ground_truth[
                    "true_location"
                ]
            )

        # ------------------------------------------------------------
        # Event logging
        # ------------------------------------------------------------

        if not hasattr(
            self,
            "last_status"
        ):
            self.last_status = (
                result.status
            )

        if result.status != self.last_status:

            self.log_event(
                f"Diagnostic state changed: "
                f"{result.status}"
            )

            if result.status != "NORMAL":

                self.log_event(
                    "Evidence: "
                    + result.primary_evidence
                )

                if (
                    result.estimated_location
                    is not None
                ):

                    self.log_event(
                        f"Estimated location: "
                        f"{result.estimated_location:.1f} km"
                    )

                    self.log_event(
                        f"Severity: "
                        f"{result.severity}"
                    )

            self.last_status = (
                result.status
            )

        # ------------------------------------------------------------
        # VOLUME LOSS
        # ------------------------------------------------------------
        #
        # Detector leak_rate is m³/h.
        #
        # m³ = (m³/h) × seconds / 3600
        # ------------------------------------------------------------

        if result.status == "LEAK":

            volumetric_leak_rate = max(
                0.0,
                result.leak_rate
            )

            dt = float(
                telemetry.get(
                    "dt_seconds",
                    self.config.dt_seconds
                )
            )

            volume_increment = (
                volumetric_leak_rate
                * dt
                / 3600.0
            )

            self.cumulative_volume_lost += (
                volume_increment
            )

            self.lbl_vol_loss.setText(
                f"{self.cumulative_volume_lost:.3f} m³"
            )

        # ------------------------------------------------------------
        # UI
        # ------------------------------------------------------------

        self.update_ui(
            telemetry,
            ground_truth,
            result,
            loc_error
        )

        # ------------------------------------------------------------
        # CSV logging
        # ------------------------------------------------------------

        self.log_data(
            telemetry,
            ground_truth,
            result,
            loc_error
        )

    # ================================================================
    # UPDATE UI
    # ================================================================

    def update_ui(
        self,
        telemetry,
        ground_truth,
        result,
        loc_error
    ):

        # ------------------------------------------------------------
        # Status
        # ------------------------------------------------------------

        if result.status == "NORMAL":
            status_color = "#10b981"
        else:
            status_color = "#e11d48"

        self.lbl_status.setText(
            "SIMULATION - "
            + result.status
        )

        self.lbl_status.setStyleSheet(
            f"""
            color: {status_color};
            font-size: 20px;
            font-weight: bold;
            font-family: 'Consolas', monospace;
            """
        )

        # ------------------------------------------------------------
        # Pressure
        # ------------------------------------------------------------

        self.lbl_pressure.setText(
            f"{telemetry['pressures'][0]:.1f} bar"
        )

        # ------------------------------------------------------------
        # Diagnosis
        # ------------------------------------------------------------

        self.lbl_diag_type.setText(
            result.status
        )

        self.lbl_diag_sev.setText(
            result.severity
        )

        if (
            result.estimated_location
            is not None
        ):

            self.lbl_diag_loc.setText(
                f"{result.estimated_location:.1f} km"
            )

        else:

            self.lbl_diag_loc.setText(
                "N/A"
            )

        # ------------------------------------------------------------
        # Affected segment
        # ------------------------------------------------------------

        if result.affected_indices:

            i1, i2 = (
                result.affected_indices
            )

            self.lbl_diag_seg.setText(
                f"S{i1} → S{i2}"
            )

        else:

            self.lbl_diag_seg.setText(
                "N/A"
            )

        # ------------------------------------------------------------
        # Leak rate
        # ------------------------------------------------------------

        if result.status == "LEAK":

            volumetric_rate = (
                result.leak_rate
            )

            self.lbl_diag_rate.setText(
                f"{volumetric_rate:,.2f} m³/h"
            )

        else:

            self.lbl_diag_rate.setText(
                "N/A"
            )

        # ------------------------------------------------------------
        # Scores
        # ------------------------------------------------------------

        self.lbl_diag_ano.setText(
            f"{result.fused_anomaly_score:.2f} / 1.00"
        )

        self.lbl_diag_dconf.setText(
            f"{result.detection_confidence * 100:.1f} %"
        )

        if result.status != "NORMAL":

            self.lbl_diag_lconf.setText(
                f"{result.localization_confidence * 100:.1f} %"
            )

        else:

            self.lbl_diag_lconf.setText(
                "N/A"
            )

        # ------------------------------------------------------------
        # Validation
        # ------------------------------------------------------------

        if (
            ground_truth["scenario"]
            != Scenario.NORMAL.value
        ):

            self.lbl_val_true.setText(
                f"{ground_truth['true_location']:.1f} km"
            )

        else:

            self.lbl_val_true.setText(
                "N/A"
            )

        if (
            result.estimated_location
            is not None
        ):

            self.lbl_val_est.setText(
                f"{result.estimated_location:.1f} km"
            )

        else:

            self.lbl_val_est.setText(
                "N/A"
            )

        if loc_error is not None:

            self.lbl_val_err.setText(
                f"{loc_error:.2f} km"
            )

        else:

            self.lbl_val_err.setText(
                "N/A"
            )

        # ------------------------------------------------------------
        # History
        # ------------------------------------------------------------

        timestamp_seconds = (
            telemetry["timestamp"]
            * telemetry.get(
                "dt_seconds",
                self.config.dt_seconds
            )
        )

        self.time_hist.append(
            timestamp_seconds
        )

        self.f_in_hist.append(
            telemetry["flow_in"]
        )

        self.f_out_hist.append(
            telemetry["flow_out"]
        )

        self.f_diff_hist.append(
            telemetry["flow_in"]
            - telemetry["flow_out"]
        )

        # ------------------------------------------------------------
        # Draw plots
        # ------------------------------------------------------------

        self.update_plots(
            telemetry,
            result
        )

    # ================================================================
    # PLOTS
    # ================================================================

    def update_plots(
        self,
        telemetry,
        result
    ):

        positions = np.asarray(
            telemetry["sensor_positions"]
        )

        pressures = np.asarray(
            telemetry["pressures"]
        )

        # ============================================================
        # PIPELINE SCHEMATIC
        # ============================================================

        ax = self.canvas.ax_sch

        ax.cla()

        ax.set_facecolor(
            "#0f172a"
        )

        ax.set_title(
            "PIPELINE SCHEMATIC",
            color="#94a3b8",
            fontsize=10,
            loc="left"
        )

        ax.plot(
            [
                0,
                self.config.length
            ],
            [0, 0],
            color="#475569",
            linewidth=5,
            zorder=1
        )

        ax.scatter(
            positions,
            np.zeros_like(positions),
            color="#38bdf8",
            s=80,
            zorder=2,
            label="Sensors"
        )

        # Sensor labels
        for i, x in enumerate(
            positions
        ):

            ax.text(
                x,
                -0.35,
                f"S{i}",
                color="#94a3b8",
                fontsize=8,
                ha="center"
            )

        ax.text(
            0,
            0.30,
            "[PUMP]",
            color="#10b981",
            fontweight="bold",
            ha="center"
        )

        ax.text(
            self.config.length,
            0.30,
            "[OUTLET]",
            color="#10b981",
            fontweight="bold",
            ha="center"
        )

        # ------------------------------------------------------------
        # Fault marker
        # ------------------------------------------------------------

        if (
            result.status != "NORMAL"
            and result.estimated_location
            is not None
        ):

            fault_x = (
                result.estimated_location
            )

            ax.scatter(
                [fault_x],
                [0],
                color="#f43f5e",
                marker="X",
                s=180,
                zorder=4,
                label="Estimated Fault"
            )

            if result.affected_indices:

                i1, i2 = (
                    result.affected_indices
                )

                x1 = positions[i1]
                x2 = positions[i2]

                ax.plot(
                    [x1, x2],
                    [0, 0],
                    color="#f43f5e",
                    linewidth=10,
                    alpha=0.25,
                    zorder=1
                )

                ax.text(
                    fault_x,
                    0.45,
                    f"{fault_x:.1f} km",
                    color="#f43f5e",
                    fontweight="bold",
                    ha="center"
                )

        ax.set_xlim(
            -3,
            self.config.length + 3
        )

        ax.set_ylim(
            -0.8,
            0.9
        )

        ax.set_yticks([])

        ax.set_xticks(
            positions
        )

        ax.tick_params(
            colors="#94a3b8",
            labelsize=8
        )

        ax.spines[
            "top"
        ].set_visible(False)

        ax.spines[
            "right"
        ].set_visible(False)

        ax.spines[
            "left"
        ].set_visible(False)

        ax.spines[
            "bottom"
        ].set_color("#475569")

        ax.legend(
            loc="upper right",
            facecolor="#0f172a",
            edgecolor="#334155",
            labelcolor="#f8fafc"
        )

        # ============================================================
        # PRESSURE PROFILE
        # ============================================================

        ax = self.canvas.ax_pres

        ax.cla()

        ax.set_facecolor(
            "#0f172a"
        )

        ax.set_title(
            "PIPELINE PRESSURE PROFILE",
            color="#94a3b8",
            fontsize=10,
            loc="left"
        )

        q_theoretical = (
            telemetry["q_theoretical"]
        )

        expected_pressures = (
            telemetry["p_in_setpoint"]
            - self.sim.hydraulic_resistance
            * q_theoretical ** 2
            * positions
        )

        ax.plot(
            positions,
            expected_pressures,
            color="#64748b",
            linestyle="--",
            linewidth=1.5,
            label="Nominal Model"
        )

        ax.plot(
            positions,
            pressures,
            color="#38bdf8",
            marker="o",
            linewidth=2,
            label="Measured"
        )

        if (
            result.estimated_location
            is not None
            and result.status != "NORMAL"
        ):

            ax.axvline(
                x=result.estimated_location,
                color="#f43f5e",
                linestyle="--",
                linewidth=2,
                label="Estimated Fault"
            )

        ax.set_ylabel(
            "Pressure (bar)",
            color="#94a3b8"
        )

        ax.set_xlabel(
            "Distance (km)",
            color="#94a3b8"
        )

        pressure_max = max(
            100.0,
            telemetry["p_in_setpoint"]
            + 10.0
        )

        ax.set_ylim(
            0,
            pressure_max
        )

        ax.grid(
            True,
            color="#334155",
            linestyle="-",
            alpha=0.6
        )

        ax.legend(
            loc="upper right",
            facecolor="#0f172a",
            edgecolor="#334155",
            labelcolor="#f8fafc"
        )

        # ============================================================
        # FLOW BALANCE
        # ============================================================

        ax = self.canvas.ax_flow

        ax.cla()

        ax.set_facecolor(
            "#0f172a"
        )

        ax.set_title(
            "REAL-TIME FLOW BALANCE",
            color="#94a3b8",
            fontsize=10,
            loc="left"
        )

        time_values = list(
            self.time_hist
        )

        flow_in_values = list(
            self.f_in_hist
        )

        flow_out_values = list(
            self.f_out_hist
        )

        residual_values = list(
            self.f_diff_hist
        )

        ax.plot(
            time_values,
            flow_in_values,
            color="#10b981",
            linewidth=2,
            label="Flow In (m³/h)"
        )

        ax.plot(
            time_values,
            flow_out_values,
            color="#f43f5e",
            linewidth=2,
            label="Flow Out (m³/h)"
        )

        # ------------------------------------------------------------
        # Secondary residual axis
        # ------------------------------------------------------------

        self.canvas.ax_flow_res.cla()

        ax_res = (
            self.canvas.ax_flow_res
        )

        ax_res.set_facecolor(
            "none"
        )

        ax_res.plot(
            time_values,
            residual_values,
            color="#fbbf24",
            linewidth=1.5,
            linestyle=":",
            label="Residual ΔQ"
        )

        ax_res.set_ylabel(
            "Residual (m³/h)",
            color="#fbbf24"
        )

        ax_res.tick_params(
            colors="#fbbf24",
            labelsize=9
        )

        ax_res.spines[
            "top"
        ].set_visible(False)

        ax_res.spines[
            "left"
        ].set_visible(False)

        ax_res.spines[
            "right"
        ].set_color("#475569")

        # ------------------------------------------------------------
        # Dynamic axis ranges
        # ------------------------------------------------------------

        q_max = max(
            max(flow_in_values),
            max(flow_out_values),
            telemetry["q_theoretical"]
        )

        ax.set_ylim(
            0,
            max(
                100.0,
                q_max * 1.25
            )
        )

        max_residual = max(
            50.0,
            max(
                abs(x)
                for x in residual_values
            ) * 1.5
        )

        ax_res.set_ylim(
            -max_residual,
            max_residual
        )

        ax.set_xlabel(
            "Time (s)",
            color="#94a3b8"
        )

        ax.set_ylabel(
            "Flow (m³/h)",
            color="#94a3b8"
        )

        ax.grid(
            True,
            color="#334155",
            linestyle="-",
            alpha=0.6
        )

        lines_1, labels_1 = (
            ax.get_legend_handles_labels()
        )

        lines_2, labels_2 = (
            ax_res.get_legend_handles_labels()
        )

        ax.legend(
            lines_1 + lines_2,
            labels_1 + labels_2,
            loc="upper left",
            facecolor="#0f172a",
            edgecolor="#334155",
            labelcolor="#f8fafc"
        )

        self.canvas.draw_idle()

    # ================================================================
    # CSV LOGGING
    # ================================================================

    def log_data(
        self,
        telemetry,
        ground_truth,
        result,
        loc_error
    ):

        volumetric_leak_rate = (
            result.leak_rate
        )

        timestamp_seconds = (
            telemetry["timestamp"]
            * telemetry.get(
                "dt_seconds",
                self.config.dt_seconds
            )
        )

        entry = {
            "Time_s":
                timestamp_seconds,

            "Scenario":
                ground_truth["scenario"],

            "Flow_In_m3_h":
                telemetry["flow_in"],

            "Flow_Out_m3_h":
                telemetry["flow_out"],

            "Flow_Residual_m3_h":
                (
                    telemetry["flow_in"]
                    - telemetry["flow_out"]
                ),

            "Detector_Status":
                result.status,

            "Severity":
                result.severity,

            "Volumetric_Leak_Rate_m3_h":
                volumetric_leak_rate,

            "Cumulative_Volume_Lost_m3":
                self.cumulative_volume_lost,

            "Flow_Score":
                result.flow_score,

            "Pressure_Score":
                result.pressure_score,

            "Fused_Anomaly_Score":
                result.fused_anomaly_score,

            "Detection_Confidence":
                result.detection_confidence,

            "Localization_Confidence":
                result.localization_confidence,

            "Est_Location_km":
                result.estimated_location,

            "True_Location_km":
                (
                    ground_truth["true_location"]
                    if ground_truth["scenario"]
                    != Scenario.NORMAL.value
                    else None
                ),

            "Localization_Error_km":
                loc_error,
        }

        if result.affected_indices:

            entry[
                "Affected_Sensor_1"
            ] = result.affected_indices[0]

            entry[
                "Affected_Sensor_2"
            ] = result.affected_indices[1]

        else:

            entry[
                "Affected_Sensor_1"
            ] = None

            entry[
                "Affected_Sensor_2"
            ] = None

        for i, pressure in enumerate(
            telemetry["pressures"]
        ):

            entry[
                f"S{i}_Pressure_bar"
            ] = pressure

        self.logged_data.append(
            entry
        )

    # ================================================================
    # EXPORT
    # ================================================================

    def export_csv(self):

        if not self.logged_data:

            self.log_event(
                "No telemetry data available for export."
            )

            return

        file_name, _ = (
            QFileDialog.getSaveFileName(
                self,
                "Export Telemetry",
                "pipeline_validation_data.csv",
                "CSV Files (*.csv)"
            )
        )

        if file_name:

            dataframe = pd.DataFrame(
                self.logged_data
            )

            dataframe.to_csv(
                file_name,
                index=False
            )

            self.log_event(
                f"Validation data exported: {file_name}"
            )


# ================================================================
# APPLICATION ENTRY POINT
# ================================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    app.setStyleSheet(
        QSS
    )

    window = PipelineDashboard()
    window.showMaximized()

    sys.exit(
        app.exec()
    )
