"""Executable adapter capabilities sent to the knowledge compiler, not case values."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from kgtracevis.schema.unified_evidence import Identifier, UnifiedModel
from kgtracevis.schema.unified_knowledge import FeatureDefinition


class CapabilityManifest(UnifiedModel):
    capability_id: Identifier
    observation_contract: Identifier
    target_role: Identifier
    context_namespace: Identifier = "industrial.object"
    context_external_ids: list[Identifier] = Field(min_length=1)
    variable_namespace: Identifier | None = None
    variable_external_ids: list[Identifier] = Field(default_factory=list)
    scopes: list[Literal["task_scope", "spatial_zone"]] = Field(min_length=1)
    zones: list[Identifier] = Field(default_factory=list)
    features: list[FeatureDefinition] = Field(min_length=1)
    notes: str


def _feature(identity, kind, definition, unit=None, reference=False):
    return FeatureDefinition(
        feature_id=identity,
        value_kind=kind,
        definition=definition,
        unit=unit,
        requires_reference=reference,
    )


def visual_capabilities(objects=("bottle",)) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="visual-region-v2",
        observation_contract="visual_region.v1",
        target_role="mechanism",
        context_external_ids=list(objects),
        scopes=["task_scope"],
        features=[
            _feature(
                "detection.anomaly_present",
                "boolean",
                "Actual detector boolean; no cause information.",
            ),
            *[
                _feature("geometry." + key, "number", definition, "1")
                for key, definition in [
                    ("area_ratio", "Connected-component pixels / total detector-grid pixels."),
                    ("aspect_ratio", "Axis-aligned bbox longest side / shortest side."),
                    (
                        "eccentricity",
                        "Connected-component coordinate covariance eccentricity in [0,1].",
                    ),
                    ("component_count", "Number of components retained in this region."),
                ]
            ],
            _feature(
                "geometry.morphology",
                "category",
                "Mask-derived coarse morphology: linear, irregular, compact; not a defect class.",
            ),
            _feature(
                "geometry.location",
                "category",
                "Image-grid position: upper, lower, left, right, center; not anatomical parts.",
            ),
            _feature(
                "appearance.semantic_candidates",
                "candidate_set",
                "Open ROI VLM candidates. Labels come from candidate_contains operands; "
                "absence is unknown.",
            ),
            _feature(
                "appearance.defect_present",
                "boolean",
                "VLM explicit normal/defect assessment; uncertain is missing.",
            ),
        ],
        notes=(
            "One frame per ROI; same_subject_same_scope joins. No anatomical location "
            "from image-grid position. No direct force, temperature, contact or material-presence "
            "measurements. Every signature includes explicit detector anomaly=true. "
            "Use plausible competing mechanisms, not asserted unique causes."
        ),
    )


def capability_manifest(identity: str) -> CapabilityManifest:
    if identity == "visual-region-v2":
        return visual_capabilities()
    raise ValueError(f"unknown adapter capability: {identity}")
