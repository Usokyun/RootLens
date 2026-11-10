# Capsule visual diagnosis — starter material

SCENARIO: mvtec

## Scope and vocabulary

The object is a capsule (CapsuleObject; alias: capsule). MVTec AD contains
capsule test examples with cracks, scratches, punctures, faulty imprints and
deformation. The dataset supplies visual defect annotations, not per-image
factory cause labels. Dataset source:
https://www.mvtec.com/research-teaching/datasets/mvtec-ad

## Observable appearance

A crack (CrackDefect; alias: crack) is a discontinuity in the capsule shell.
It may appear as an elongated line or a localized irregular mark. A scratch
(ScratchDefect; alias: scratch) is an elongated surface mark. A puncture
(PokeDefect; aliases: poke, puncture) is a localized opening or spot.

LinearMorphology (alias: linear) and SpotMorphology (alias: spot) are observable
image-region concepts. The producer measures area ratio, bounding box, aspect
ratio and eccentricity. Linear geometry can support both cracks and scratches;
ROI semantic recognition is a separate observation used to distinguish them.
Image-grid position does not establish a physical component or factory location.

## Plausible investigation directions

For this starter demo knowledge, a cracked shell can motivate investigating
material-related shell weakness (MaterialDefect) or compression during handling
(PackagingPressure). A scratch can motivate investigating mechanical contact
(MechanicalContact) or surface abrasion (SurfaceWear). A puncture can motivate
investigating mechanical contact. These are reusable plausible explanations,
not observed production events or verified causes for any test image.

Represent appearance relations and plausible-cause relations separately. Do not
infer which machine acted, add event logs, or choose one cause uniquely from a
single image. Do not invent numeric diagnostic thresholds from this material.
