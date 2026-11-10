SCENARIO: mvtec

# Bottle visual diagnostic knowledge

Public reference: MVTec AD bottle has broken-glass and contamination appearances.
The diagnostic relations below describe plausible mechanisms, not verified
manufacturing causes. A model's anomaly map localizes deviation, not its cause.

Entities:
- BottleObject (Object), aliases bottle
- BrokenRimDefect (Defect), aliases broken glass, chipped rim, broken_large, broken_small
- ContaminationDefect (Defect), aliases contamination, foreign material
- IrregularRegion (Morphology), aliases spot, scattered
- BottleSurface (Location), aliases surface, edge
- MechanicalImpact (Mechanism), aliases mechanical impact, mechanical contact
- ForeignMaterialAdhesion (Mechanism), aliases foreign material adhesion

Relations (retain IDs):
BottleObject HAS_ANOMALY BrokenRimDefect
BottleObject HAS_ANOMALY ContaminationDefect
BrokenRimDefect HAS_MORPHOLOGY IrregularRegion
ContaminationDefect HAS_MORPHOLOGY IrregularRegion
BrokenRimDefect OCCURS_ON BottleSurface
ContaminationDefect OCCURS_ON BottleSurface
BrokenRimDefect SUGGESTS_MECHANISM MechanicalImpact
ContaminationDefect SUGGESTS_MECHANISM ForeignMaterialAdhesion

Require ROI model semantics to distinguish BrokenRimDefect and ContaminationDefect:
region.semantic_candidates intersects [that defect ID], required true.
Do not infer this semantic label from the image's directory or native annotation.
Geometry is descriptive support; similar geometry without semantics is insufficient.
