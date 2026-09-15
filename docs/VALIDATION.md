# Validation

## Purpose

Validation checks whether the detection and localization logic behaves consistently under the simulated operating conditions for which the prototype was designed.

## Ground Truth

The simulator provides the injected scenario and, where applicable, the injected fault location. These values are retained as ground truth for comparison with detector output.

## Core Metrics

### Detection

- Detection rate / recall
- False-alarm rate
- Missed-detection rate
- Classification accuracy by scenario

### Localization

`Localization Error = |Estimated Location - Ground Truth Location|`

For a larger experiment, report mean absolute localization error and RMSE across multiple fault locations.

### Robustness

Repeat experiments across multiple sensor-noise levels and operating conditions to determine whether detection remains stable as measurement uncertainty increases.

## Scenario Matrix

| Scenario | Expected Detector Behavior |
|---|---|
| Normal Operation | Normal |
| Small Leak | Leak / small |
| Moderate Leak | Leak / moderate |
| Major Leak | Leak / major |
| Blockage | Blockage |
| Sensor Fault | Sensor Fault |

## Recommended Test Procedure

1. Start from normal operation and confirm stable baseline telemetry.
2. Inject each fault scenario separately.
3. Repeat each scenario at several pipeline locations.
4. Repeat the tests at several sensor-noise levels.
5. Record detector classification, severity, confidence, and estimated location.
6. Compare the result with simulator ground truth.
7. Calculate detection and localization metrics.
8. Export representative telemetry for reproducibility.

## Interpretation

The current validation demonstrates software behavior within the assumptions of the simulator. It does not establish field-level performance or safety certification. A production evaluation would require validated hydraulic models, calibrated sensors, representative historical events, and independent field or benchmark datasets.
