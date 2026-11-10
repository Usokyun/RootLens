SCENARIO: tep

# TEP window diagnosis — reusable numerical knowledge

Reference: Tennessee Eastman benchmark, Braatz closed-loop reference data:
https://github.com/camaramm/tennessee-eastman-profBraatz
52 channels are XMEAS1..41 then XMV1..11; sampling interval 180 seconds.
Testing disturbances start after 160 normal samples (first affected sample 161).
Normal-reference PCA and standardization must be fitted on fault-free data only.
RBC is residual squared energy by channel, normalized over all 52 channels.

Variables (retain IDs and channel aliases):
- ReactorTemperature (Variable), aliases xmeas_9, XMEAS_9
- ReactorCoolingOutletTemperature (Variable), aliases xmeas_21, XMEAS_21
- ReactorCoolingValve (Variable), aliases xmv_10, XMV_10
- AFeedFlow (Variable), aliases xmeas_1, XMEAS_1
- Stream4FeedFlow (Variable), aliases xmeas_4, XMEAS_4
- ReactorCoolingDisturbance (Fault): reactor cooling-water inlet disturbance candidate
- FeedDisturbance (Fault): feed flow/composition disturbance candidate

Physical candidate→response relations (modeling hypotheses, not observed roots):
ReactorCoolingDisturbance AFFECTS_VARIABLE ReactorCoolingOutletTemperature
ReactorCoolingDisturbance AFFECTS_VARIABLE ReactorTemperature
ReactorCoolingDisturbance AFFECTS_VARIABLE ReactorCoolingValve
FeedDisturbance AFFECTS_VARIABLE AFeedFlow
FeedDisturbance AFFECTS_VARIABLE Stream4FeedFlow
FeedDisturbance AFFECTS_VARIABLE ReactorTemperature
All these specified relations enable forward propagation, relation_family
FAULT_SOURCE, attenuation 1.0, edge_weight 0.7. Do not enable unrelated edges.

Executable measured_runtime.tep profiles use registered channels and actual edges.
The following abs(mean_z)>=2 tests are explicit predeclared demo heuristics,
not calibrated confidence and not tuned to this run's fault label:
- ReactorCoolingDisturbance (anchor itself; candidate itself): ANY of
  process.mean_z abs_gte 2 for xmeas_21 or xmv_10 or xmeas_9.
- FeedDisturbance (anchor itself; candidate itself): ANY of
  process.mean_z abs_gte 2 for xmeas_1 or xmeas_4.
Each predicate binds its channel's Variable node and the corresponding actual
candidate AFFECTS_VARIABLE edge. Numerical ranking must multiply the complete
channel contribution vector by the current graph's forward propagation gains.
Never use faultNumber, file name, native fault ID or simulation label as a feature.
