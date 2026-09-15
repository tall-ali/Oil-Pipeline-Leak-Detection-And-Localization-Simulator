# Limitations and Future Work

## Current Limitations

This project is a physics-informed simulation and decision-support prototype. It is not an industrial-grade computational pipeline monitoring system.

The current implementation uses a simplified one-dimensional model rather than a full transient hydraulic solver. Sensor behavior and fault signatures are simulated. Thresholds and confidence calculations are designed for the prototype and have not been calibrated against field data.

Localization is based on the most likely affected sensor interval, so the reported position should not be interpreted as an exact physical leak coordinate.

## Future Work

### Hydraulic Modeling

- Add transient pressure and flow dynamics.
- Model fluid properties, friction, and pipeline characteristics more realistically.
- Investigate negative-pressure-wave behavior.

### Detection

- Add statistical change-point and sequential detection methods.
- Compare rule-based detection with machine-learning models.
- Study adaptive thresholds under changing operating conditions.

### Validation

- Run Monte Carlo experiments over sensor noise and operating conditions.
- Measure detection probability and false-alarm rate.
- Report localization MAE and RMSE.
- Evaluate classification performance with confusion matrices.

### System Design

- Optimize sensor placement.
- Add real-time streaming telemetry interfaces.
- Introduce database-backed event storage.
- Develop a digital-twin architecture.

### Data and Deployment

- Evaluate against public and field-derived datasets where available.
- Calibrate sensor and hydraulic models from real measurements.
- Investigate edge/industrial deployment constraints.

These extensions would move the project from a controlled educational prototype toward a more rigorous research platform.
