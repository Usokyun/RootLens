"""Executable adapter capabilities sent to the knowledge compiler, not case values."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from kgtracevis.schema.feature_catalog import (
    PROCESS_FEATURE_IDS,
    SPATIAL_FEATURE_IDS,
    VISUAL_FEATURE_IDS,
    feature_definitions,
)
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
    max_candidates: int = Field(default=6, ge=1, le=32)
    max_signatures: int = Field(default=4, ge=1, le=16)
    max_hypotheses_per_signature: int = Field(default=6, ge=1, le=32)


def visual_capabilities(objects=("bottle",)) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="visual-region-v2",
        observation_contract="visual_region.v1",
        target_role="mechanism",
        context_external_ids=list(objects),
        scopes=["task_scope"],
        max_candidates=16,
        max_signatures=8,
        max_hypotheses_per_signature=16,
        features=feature_definitions(VISUAL_FEATURE_IDS),
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
    if identity == "process-window-v2":
        return process_capabilities()
    if identity == "spatial-grid-v2":
        return spatial_capabilities()
    raise ValueError(f"unknown adapter capability: {identity}")


def process_capabilities() -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="process-window-v2",
        observation_contract="process-measurements.v1",
        target_role="mechanism",
        context_external_ids=["Tennessee Eastman Process"],
        variable_namespace="tep_braatz.channel",
        variable_external_ids=[f"xmeas_{i}" for i in range(1, 42)]
        + [f"xmv_{i}" for i in range(1, 12)],
        scopes=["task_scope"],
        max_candidates=16,
        max_signatures=12,
        max_hypotheses_per_signature=16,
        features=feature_definitions(PROCESS_FEATURE_IDS),
        notes=(
            "One equipment/window query, all channels retained. Fit on separate normal data. "
            "All statistics require that actual reference. Unspecified thresholds are heuristics. "
            "Closed-loop control may maintain temperature while an actuator changes; do not demand "
            "every connected mean must shift. Compare source-supported mechanism families, "
            "not fault IDs. No case fault label or test values are provided to construction."
        ),
    )


def spatial_capabilities() -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="spatial-grid-v2",
        observation_contract="wafer-measurements.v1",
        target_role="pattern_family",
        context_external_ids=["wafer"],
        scopes=["spatial_zone"],
        zones=["all_valid", "center", "middle", "edge"],
        max_candidates=8,
        max_signatures=8,
        max_hypotheses_per_signature=1,
        features=feature_definitions(SPATIAL_FEATURE_IDS),
        notes=(
            "Task is PATTERN FAMILY comparison, not manufacturing-cause identification. "
            "Candidates are the eight named patterns in classifier.pattern, not factory causes. "
            "Each signature belongs to ONE target pattern; competing classes belong to other "
            "signatures, not neighboring causes of this signature. "
            "Mechanisms are intermediate spatial states. Every feature is scoped to a zone; "
            "use all_valid for classifier and global statistics. Radius is the clipped "
            "elliptical distance about valid-die bounding-box center: center r<=.4, "
            "middle .4<r<.8, edge r>=.8. Only valid dies contribute to density. "
            "The numeric cutoffs are declared heuristics unless supplied by sources. "
            "Use spatial measurements to test the model label, not label-only signatures; "
            "a wrong classifier may conflict with spatial data. No process-cause observations."
        ),
    )
