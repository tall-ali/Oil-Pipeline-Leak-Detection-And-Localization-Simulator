# Methodology

## 1. Simulation

The simulator represents a pressurized pipeline as a simplified one-dimensional system with distributed pressure sensors and inlet/outlet flow measurements. It generates a theoretical operating state, applies scenario-specific disturbances, and adds configurable measurement noise.

## 2. Pressure Residual

For each pressure sensor, the detector calculates an expected pressure from the nominal operating condition and compares it with the filtered measurement:

`r_i = P_measured,i - P_expected,i`

The residual magnitude is normalized against an effective noise estimate.

## 3. Flow Balance

The primary flow consistency quantity is:

`ΔQ = Q_in - Q_out`

The flow imbalance is scaled relative to the expected measurement uncertainty and converted into a bounded anomaly score.

## 4. Temporal Filtering

The detector uses an exponential moving average to reduce short-term sensor fluctuations. The filter coefficient is selected to provide smoothing while retaining changes relevant to fault detection.

## 5. Spatial Consistency

Pressure residuals are evaluated as a spatial pattern. Smoothing and spatial-gradient information help identify a transition between less-affected and more-affected pipeline regions.

## 6. Evidence Fusion

The current fused score is:

`S = 0.45 S_flow + 0.35 S_pressure + 0.20 S_spatial`

The weighting gives the flow balance the strongest contribution because an unexplained inlet/outlet flow difference is direct evidence of a loss mechanism, while pressure and spatial evidence provide complementary confirmation and localization information.

## 7. Classification Logic

The detector applies transparent rules to distinguish:

- Normal operation
- Leak
- Blockage
- Sensor fault

A leak requires sufficient fused anomaly evidence together with meaningful flow evidence. A blockage is associated with severe flow reduction. An isolated pressure anomaly without strong flow evidence can indicate a sensor fault.

## 8. Localization

The detector identifies the most likely affected sensor interval using the spatial pressure-residual pattern. The reported location is the interval midpoint. This avoids claiming a precision that the current sensor spacing and simplified model cannot support.

## 9. Severity

Severity is estimated from relative flow loss. The prototype uses small, moderate, and major categories with simulation-oriented thresholds.

## 10. Confidence

Detection confidence represents the strength and consistency of the available evidence. Localization confidence represents the clarity of the spatial anomaly pattern. These values are decision-support indicators and are not calibrated probabilities.
