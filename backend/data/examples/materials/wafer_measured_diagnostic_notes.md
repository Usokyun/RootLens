SCENARIO: wafer

# Wafer pattern diagnosis — reusable demo knowledge

Source: WM-811K encoding and the public RadAI classifier model card.
The map contains 0=background, 1=passing die, 2=failing die. All spatial statistics
must use valid die (1 or 2) as denominator, never image pixels. An eight-way
classifier cannot recognize normal or unknown by itself. Its predicted pattern
is independent of map statistics, not an observation of contamination.

Demo predicates below are explicit descriptive heuristics, not calibrated fab limits.
They are specified before evaluating cases. Mechanisms below are hypotheses;
they are not factory-verified root causes.

Entities:
- WaferObject (Object), aliases wafer
- NearFullPattern (Pattern), aliases nearfull, Near-full
- CenterPattern (Pattern), aliases center, Center
- EdgeRingPattern (Pattern), aliases edge_ring, Edge-Ring
- ScratchPattern (Pattern), aliases scratch, Scratch
- WidespreadYieldLoss (Mechanism): widespread die failure, mechanism unresolved
- CentralProcessNonuniformity (Mechanism): candidate spatial process nonuniformity
- EdgeProcessNonuniformity (Mechanism): candidate edge process nonuniformity
- LinearSurfaceDisturbance (Mechanism): candidate linear disturbance

Relations (retain these IDs):
WaferObject HAS_PATTERN NearFullPattern
WaferObject HAS_PATTERN CenterPattern
WaferObject HAS_PATTERN EdgeRingPattern
WaferObject HAS_PATTERN ScratchPattern
NearFullPattern SUGGESTS_MECHANISM WidespreadYieldLoss
CenterPattern SUGGESTS_MECHANISM CentralProcessNonuniformity
EdgeRingPattern SUGGESTS_MECHANISM EdgeProcessNonuniformity
ScratchPattern SUGGESTS_MECHANISM LinearSurfaceDisturbance

Executable measured_runtime.wafer profiles (match_mode all):
- NearFullPattern: wafer.failure_density >= 0.75 AND wafer.classifier_pattern == nearfull.
- CenterPattern: wafer.center_density >= 0.35 AND wafer.edge_density <= 0.15 AND classifier_pattern == center.
- EdgeRingPattern: wafer.edge_density >= 0.30 AND wafer.center_density <= 0.15 AND classifier_pattern == edge_ring.
- ScratchPattern: wafer.linearity >= 0.90 AND wafer.failure_density <= 0.25 AND classifier_pattern == scratch.
For each predicate bind concept_id to its Pattern, and source_edge_id to the
actual Pattern→Mechanism edge (or the WaferObject→Pattern edge). Missing map
measurements or a disagreeing classifier must not create a supported candidate.
