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
    max_candidates: int = Field(default=6, ge=1, le=32)
    max_signatures: int = Field(default=4, ge=1, le=16)
    max_hypotheses_per_signature: int = Field(default=6, ge=1, le=32)


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
        max_candidates=16,
        max_signatures=8,
        max_hypotheses_per_signature=16,
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
        features=[
            _feature(
                "detection.anomaly_present",
                "boolean",
                "Window PCA residual energy exceeds matched normal-data 99th-percentile limit.",
            ),
            _feature(
                "statistics.mean_z",
                "number",
                "Window mean of (x-normal_mean)/normal_scale.",
                "1",
                True,
            ),
            _feature(
                "statistics.std_z",
                "number",
                "Population std(ddof=0) of standardized samples in the window.",
                "1",
                True,
            ),
            _feature(
                "statistics.slope_z",
                "number",
                "OLS slope of standardized samples against sample index.",
                "1/sample",
                True,
            ),
            _feature(
                "residual.contribution",
                "number",
                "Normalized squared PCA residual share; complete vector retained, "
                "not a cause probability.",
                "1",
                True,
            ),
            _feature(
                "residual.energy",
                "number",
                "Mean squared PCA reconstruction residual energy in this window.",
                "1",
                True,
            ),
            _feature(
                "residual.normal_limit",
                "number",
                "Matched normal-data 99th-percentile residual energy limit.",
                "1",
                True,
            ),
            _feature(
                "series.raw_values",
                "array_ref",
                "Raw physical-unit channel samples; supporting asset, not a final-rank feature.",
            ),
        ],
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
        features=[
            _feature(
                "detection.anomaly_present",
                "boolean",
                "At least one failed die in a nonempty valid grid.",
            ),
            _feature(
                "spatial.failure_density",
                "number",
                "Failed die / valid die in the declared zone; empty zones are missing.",
                "1",
            ),
            _feature("spatial.valid_die_count", "number", "Number of code-1 or code-2 cells.", "1"),
            _feature("spatial.failed_die_count", "number", "Number of code-2 cells.", "1"),
            _feature(
                "spatial.component_count",
                "number",
                "Eight-neighbor failed-die component count.",
                "1",
            ),
            _feature(
                "spatial.largest_component_ratio",
                "number",
                "Largest eight-neighbor component / failed dies; missing without failures.",
                "1",
            ),
            _feature(
                "spatial.linearity",
                "number",
                "1 - min/max coordinate covariance eigenvalue; missing with <3 failed dies.",
                "1",
            ),
            _feature(
                "classifier.pattern",
                "category",
                "Independent ResNet output, not native labels: center, donut, edge_loc, "
                "edge_ring, loc, random, scratch, nearfull.",
            ),
            _feature(
                "spatial.grid", "array_ref", "Actual grid asset: 0 background, 1 good, 2 failed."
            ),
        ],
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
