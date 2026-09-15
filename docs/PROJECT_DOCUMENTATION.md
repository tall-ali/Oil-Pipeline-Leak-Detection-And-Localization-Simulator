# Project Documentation

## Oil Pipeline Leak Detection and Localization Simulator

### 1. Abstract

This project presents a physics-informed simulation and decision-support prototype for detecting, classifying, and localizing anomalies in a pressurized oil pipeline. A simplified one-dimensional pipeline model generates pressure and flow telemetry from normal and faulted operating conditions. Measurement noise is introduced to represent imperfect sensors.

The detection engine combines flow-balance analysis, pressure-residual analysis, and spatial consistency into a transparent evidence-fusion framework. The system classifies operating conditions as normal operation, leak, blockage, or sensor fault, and estimates the most likely affected pipeline segment together with severity and confidence indicators.

An operator dashboard provides real-time telemetry visualization, alarm information, validation against ground truth, event logging, and CSV export.

### 2. Introduction

Pipeline integrity monitoring requires reliable detection of abnormal operating conditions and, where possible, rapid localization of the affected section. Different physical signals can provide complementary evidence: changes in inlet/outlet flow, pressure deviations, and spatial patterns across distributed sensors.

This project demonstrates these principles using a controlled simulation environment. The focus is not on reproducing a complete industrial computational pipeline monitoring system, but on building an understandable engineering pipeline from physical modeling to automated detection and operator visualization.

### 3. Problem Statement

Develop a software system capable of simulating pipeline operation, generating noisy sensor measurements, detecting abnormal conditions, estimating their severity, and identifying the most likely affected pipeline segment through a graphical operator interface.

### 4. Project Objectives

- Build a simplified pressurized pipeline simulator.
- Generate distributed pressure and flow telemetry.
- Model sensor noise and operating faults.
- Detect unexplained flow imbalance.
- Detect pressure-profile anomalies.
- Use spatial information to improve localization.
- Fuse multiple evidence sources into a transparent anomaly score.
- Classify normal operation, leaks, blockages, and sensor faults.
- Estimate leak severity and detection confidence.
- Compare estimated location with simulated ground truth.
- Provide an operator-oriented GUI.
- Export simulation telemetry for further analysis.

### 5. System Overview

The complete processing chain is:

```text
Pipeline Configuration
        ↓
Pipeline Simulator
        ↓
Noisy Sensor Telemetry
        ↓
Temporal Filtering
        ↓
Flow-Balance Analysis
        ↓
Pressure-Residual Analysis
        ↓
Spatial Consistency Analysis
        ↓
Evidence Fusion
        ↓
Fault Classification
        ↓
Localization / Severity / Confidence
        ↓
Operator Dashboard
```

### 6. System Architecture

The architecture separates physical simulation from diagnostic logic and visualization. The simulator is responsible for generating the operating state and measurements. The detector consumes telemetry and produces a structured detection result. The dashboard presents the result and retains event and validation information.

### 7. Pipeline Simulation Model

#### 7.1 Pipeline Geometry

The prototype represents the pipeline as a one-dimensional line with a total length of approximately 50 km. Distributed sensors are positioned along the pipeline, allowing pressure behavior to be examined spatially.

The model is intentionally one-dimensional and simplified. It is designed to support algorithm development and visualization without requiring a full computational fluid dynamics model.

#### 7.2 Pressure Model

A nominal pressure profile is represented by a decreasing function of pipeline distance. In the simplified model, the expected pressure is expressed conceptually as:

`P(x) = P_in - R q² x`

where `P_in` is the inlet pressure, `q` is the theoretical flow, `R` represents the simplified hydraulic resistance parameter, and `x` is the normalized/represented pipeline position used by the simulator.

A fault modifies the expected profile, producing pressure residuals that can be analyzed by the detector.

#### 7.3 Flow Model

The simulator provides theoretical and measured inlet/outlet flow. Under normal operation, inlet and outlet flow should remain approximately balanced. A leak introduces a difference between the two measurements.

The simplified flow-loss estimate is based on the measured difference:

`ΔQ = Q_in - Q_out`

This quantity is interpreted as unexplained volumetric flow loss within the simulated pipeline.

#### 7.4 Sensor Noise

Random measurement noise is added to pressure and flow measurements. Noise level can be adjusted through the dashboard, allowing the robustness of the detection logic to be explored.

The detector applies exponential moving-average filtering to reduce short-term measurement fluctuations before evaluating anomalies.

#### 7.5 Fault Injection

The simulator supports multiple scenarios, including normal operation, small/moderate/major leaks, blockage, and sensor fault. A leak location can be selected through the interface so that estimated and ground-truth locations can be compared.

### 8. Leak Detection Methodology

#### 8.1 Flow-Balance Analysis

The detector compares inlet and outlet flow after temporal filtering. A statistically scaled flow imbalance is converted into a normalized anomaly score. A large unexplained imbalance provides direct evidence of a leak or other loss mechanism.

#### 8.2 Pressure Residual Analysis

The detector calculates the expected pressure profile from the nominal operating condition and compares it with measured pressure. The difference is the pressure residual:

`r_i = P_measured,i - P_expected,i`

Residual magnitude is evaluated relative to the effective sensor noise level.

#### 8.3 Spatial Consistency

Pressure anomalies are evaluated across sensor positions rather than treating every sensor independently. Spatially coherent deviations provide stronger evidence of a pipeline event than an isolated sensor spike.

#### 8.4 Evidence Fusion

The prototype combines three normalized evidence components:

- Flow-balance score: 45%
- Pressure score: 35%
- Spatial-consistency score: 20%

The fused anomaly score is therefore conceptually:

`S = 0.45 S_flow + 0.35 S_pressure + 0.20 S_spatial`

A leak is reported when the fused score and flow evidence satisfy the detector thresholds. This transparent approach makes the decision process easier to inspect than a black-box classifier.

### 9. Leak Localization

Localization is performed using the spatial pattern of pressure residuals. The detector smooths the residual pattern, examines spatial changes, and identifies the strongest transition associated with the abnormal region.

The final estimate is reported as the midpoint of the most likely affected sensor interval. Therefore, the output should be interpreted as an estimated pipeline segment rather than an exact leak coordinate.

### 10. Fault Classification

#### 10.1 Normal Operation

The system reports normal operation when anomaly evidence remains below the detection criteria.

#### 10.2 Leak

A leak is reported when the fused anomaly evidence is sufficiently strong and the flow imbalance provides supporting evidence.

#### 10.3 Blockage

A severe reduction in both inlet and outlet flow is treated as a blockage-type condition in the simplified model. The location estimate is based on the strongest neighboring pressure drop.

#### 10.4 Sensor Fault

An isolated pressure anomaly without corresponding strong flow evidence can be classified as a sensor-fault condition. This prevents a single abnormal measurement from automatically being interpreted as a pipeline leak.

### 11. Severity Estimation

Leak severity is estimated from the relative flow loss compared with theoretical flow. The current prototype uses three qualitative levels:

- Small: less than approximately 10% flow loss
- Moderate: approximately 10–25% flow loss
- Major: above approximately 25% flow loss

These thresholds are simulation-oriented and are not operational safety limits.

### 12. Confidence Estimation

Detection confidence reflects the strength and consistency of the evidence supporting the classification. Localization confidence reflects how clearly the spatial pressure pattern identifies an affected sensor interval.

Confidence values are intended as decision-support indicators rather than certified probabilities of failure.

### 13. Operator Dashboard

The PySide6 dashboard provides:

- Operating scenario selection
- Pump/inlet pressure control
- Sensor-noise control
- Fault-location control
- Detection status
- Severity
- Estimated location
- Detection and localization confidence
- Flow balance visualization
- Pressure-profile visualization
- Ground-truth validation
- Localization error
- Event log
- CSV export
- Reset and simulation controls

The dashboard is designed to expose the reasoning of the detector rather than only displaying a final alarm.

### 14. Validation and Ground Truth

Because the simulator knows the injected scenario and location, the system can compare its estimate with ground truth. For localization, the principal error measure is:

`Localization Error = |Estimated Location - Ground Truth Location|`

Validation should be repeated for multiple fault locations and sensor-noise levels. A stronger future evaluation should report detection rate, false-alarm rate, missed-detection rate, and localization RMSE.

### 15. Experimental Scenarios

The project includes the following operating scenarios:

| Scenario | Purpose |
|---|---|
| Normal Operation | Establish baseline behavior |
| Small Leak | Test low-severity anomaly detection |
| Moderate Leak | Test intermediate flow loss |
| Major Leak | Test strong anomaly detection |
| Blockage | Distinguish loss-of-flow behavior from leakage |
| Sensor Fault | Test resistance to isolated measurement anomalies |

### 16. Results

The dashboard provides real-time qualitative and quantitative results for each simulated scenario. The recommended repository results section should contain representative screenshots, selected telemetry exports, and scenario figures generated from the final implementation.

Results should be interpreted as simulation results. They demonstrate algorithm behavior under the implemented assumptions rather than field performance.

### 17. Limitations

The current prototype has several important limitations:

- It uses a simplified one-dimensional pipeline model.
- It does not solve full transient hydraulic equations.
- It does not model fluid properties in full detail.
- Sensor behavior is simplified.
- Fault signatures are simulated rather than obtained from field measurements.
- Detection thresholds are heuristic and simulation-oriented.
- Localization is interval-based rather than exact.
- Confidence values are not calibrated probabilities.
- The system has not been validated against an industrial pipeline monitoring benchmark.

### 18. Future Development

Potential next stages include:

- Transient hydraulic modeling
- Negative pressure wave detection
- Statistical change-point detection
- Monte Carlo robustness testing
- Detection probability and false-alarm analysis
- Localization RMSE evaluation
- Sensor-placement optimization
- More realistic leak hydraulics
- Digital-twin integration
- Real pipeline datasets
- Machine-learning comparison models
- Real-time streaming telemetry interfaces

### 19. Technologies Used

- Python
- NumPy
- Pandas
- PySide6
- Matplotlib

### 20. Conclusion

The Oil Pipeline Leak Detection and Localization Simulator demonstrates a complete engineering workflow from physical-system simulation to automated anomaly detection and operator visualization. By combining flow balance, pressure residuals, spatial consistency, and evidence fusion, the prototype provides an interpretable approach to pipeline monitoring.

The project is intentionally structured so that the current transparent simulation can later be extended toward more advanced transient models, statistical validation, digital-twin methods, and real-world data evaluation.

### 21. References

The methodology is informed by established pipeline leak-detection concepts including mass/volume balance, pressure-based analysis, negative pressure waves, statistical methods, and computational pipeline monitoring. Representative review literature should be recorded in the repository with complete bibliographic details before final submission.
