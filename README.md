# Oil Pipeline Leak Detection and Localization Simulator

A physics-informed simulation and decision-support prototype for detecting, classifying, and localizing oil pipeline anomalies from simulated pressure and flow telemetry.

## Overview

The project models a simplified 1-D pressurized pipeline and a distributed sensor network. It injects operating conditions and faults, generates noisy telemetry, and processes the measurements through a transparent detection pipeline.

The system is designed as an engineering prototype rather than an industrial-grade pipeline monitoring system. Its purpose is to demonstrate how physical consistency checks, anomaly scoring, and spatial reasoning can be combined into an operator-facing monitoring tool.

## System Architecture

```text
Pipeline Configuration
        |
        v
Pipeline Simulator
(hydraulic model, noise, fault injection)
        |
        v
Sensor Telemetry
(pressure, inlet flow, outlet flow)
        |
        v
Detection Engine
(flow balance + pressure residual + spatial consistency)
        |
        v
Evidence Fusion
        |
        v
Fault Classification
(normal / leak / blockage / sensor fault)
        |
        v
Localization + Severity + Confidence
        |
        v
Operator Dashboard
(live plots, alarms, validation, event log, CSV export)
```

## Key Features

- Simplified 50 km pipeline simulation
- Distributed pressure sensors along the pipeline
- Simulated inlet and outlet flow measurements
- Configurable sensor noise
- Normal operation, leak, blockage, and sensor-fault scenarios
- Flow-balance anomaly detection
- Pressure-residual analysis
- Spatial consistency analysis
- Evidence fusion for transparent decisions
- Estimated affected pipeline segment
- Leak severity classification
- Detection and localization confidence
- Ground-truth comparison and localization error
- Real-time operator dashboard
- Event logging
- CSV export

## Detection Method

The detector combines three complementary signals:

1. **Flow balance:** compares simulated inlet and outlet flow to identify unexplained mass/volume loss.
2. **Pressure residual:** compares measured pressure against the expected pressure profile.
3. **Spatial consistency:** checks whether pressure anomalies form a physically meaningful spatial pattern.

The resulting evidence is fused into an anomaly score. The detector then classifies the operating condition and estimates the most likely affected sensor interval.

For the current prototype, the localization output represents the **most likely affected pipeline segment**, not an exact physical leak coordinate.

## Scenarios

- Normal Operation
- Small Leak
- Moderate Leak
- Major Leak
- Blockage
- Sensor Fault

## Project Documentation

- [Project Documentation](docs/PROJECT_DOCUMENTATION.md) — complete technical description
- [Methodology](docs/METHODOLOGY.md) — simulation and detection methodology
- [Validation](docs/VALIDATION.md) — validation strategy and evaluation criteria
- [Limitations and Future Work](docs/LIMITATIONS_AND_FUTURE_WORK.md) — current limitations and planned improvements

## Installation

Python 3.10+ is recommended.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python3 dashboard.py
```

## Technologies

- Python
- NumPy
- Pandas
- PySide6
- Matplotlib

## Repository Structure

```text
.
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
├── dashboard.py
├── sim_engine.py
├── detector.py
├── docs/
│   ├── PROJECT_DOCUMENTATION.md
│   ├── METHODOLOGY.md
│   ├── VALIDATION.md
│   └── LIMITATIONS_AND_FUTURE_WORK.md
├── results/
│   ├── figures/
│   └── sample_telemetry.csv
├── screenshots/
└── assets/
    └── system_architecture.png
```

## Limitations

This prototype uses a simplified steady-state 1-D model and simulated telemetry. It does not represent a certified computational pipeline monitoring system and should not be used for operational safety decisions.

## Future Development

Potential extensions include transient hydraulic modeling, negative-pressure-wave detection, Monte Carlo robustness analysis, detection/false-alarm statistics, localization RMSE, sensor-placement optimization, digital-twin integration, and evaluation using real pipeline datasets.

## Author

Boureima Tall Ali Sagaidou

Electronics and Electrical Engineering student | Control Systems | Autonomous Systems | Energy and Infrastructure
