"""Closed wafer/process measurements and reusable graph-bound predicates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MeasuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WaferMeasurements(MeasuredModel):
    schema_version: Literal["wafer-measurements.v1"] = "wafer-measurements.v1"
    encoding: Literal["wm811k_012"] = "wm811k_012"
    valid_die_count: int = Field(ge=0)
    failed_die_count: int = Field(ge=0)
    failure_density: float = Field(ge=0, le=1)
    center_density: float | None = Field(default=None, ge=0, le=1)
    edge_density: float | None = Field(default=None, ge=0, le=1)
    middle_density: float | None = Field(default=None, ge=0, le=1)
    largest_component_ratio: float = Field(ge=0, le=1)
    component_count: int = Field(ge=0)
    linearity: float | None = Field(default=None, ge=0, le=1)
    classifier_pattern: str | None = None
    classifier_source: str | None = None
    annotation_state: Literal["normal", "labeled", "unlabeled", "unknown"] = "unknown"


class ProcessChannel(MeasuredModel):
    channel: str = Field(pattern=r"^(xmeas|xmv)_\d+$")
    mean_z: float
    std_z: float = Field(ge=0)
    slope_z: float
    contribution: float = Field(ge=0, le=1)
    samples: list[float] = Field(min_length=2)


class ProcessMeasurements(MeasuredModel):
    schema_version: Literal["process-measurements.v1"] = "process-measurements.v1"
    reference_id: str
    sample_start: int
    sample_end: int
    sampling_interval_seconds: float = Field(gt=0)
    fault_start_sample: int | None = None
    normal_reference_rows: int = Field(ge=2)
    residual_energy: float = Field(ge=0)
    normal_energy_limit: float = Field(ge=0)
    channels: list[ProcessChannel] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_window(self):
        if self.sample_end < self.sample_start:
            raise ValueError("reversed process window")
        ids = [c.channel for c in self.channels]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate process channel")
        lengths = {len(c.samples) for c in self.channels}
        if len(lengths) != 1 or next(iter(lengths)) != self.sample_end - self.sample_start + 1:
            raise ValueError("channel samples must cover the complete contiguous window")
        return self


Metric = Literal[
    "wafer.failure_density",
    "wafer.center_density",
    "wafer.edge_density",
    "wafer.middle_density",
    "wafer.largest_component_ratio",
    "wafer.linearity",
    "wafer.component_count",
    "wafer.classifier_pattern",
    "process.mean_z",
    "process.std_z",
    "process.slope_z",
    "process.contribution",
]


class MeasuredCondition(MeasuredModel):
    feature: Metric
    channel: str | None = Field(default=None, pattern=r"^(xmeas|xmv)_\d+$")
    op: Literal["gte", "lte", "abs_gte", "eq", "in"]
    value: float | str | list[str]
    concept_id: str
    source_edge_id: str
    required: bool = True

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("boolean is not a numeric measurement")
        return value

    @model_validator(mode="after")
    def validate_operand(self):
        if self.feature.startswith("process.") != (self.channel is not None):
            raise ValueError("process predicates require an explicit registered channel")
        if self.channel is not None:
            family, number = self.channel.split("_")
            if not 1 <= int(number) <= (41 if family == "xmeas" else 11):
                raise ValueError("TEP channel is outside XMEAS1..41 / XMV1..11")
        if self.feature == "wafer.classifier_pattern":
            if not (
                (self.op == "eq" and isinstance(self.value, str))
                or (self.op == "in" and isinstance(self.value, list))
            ):
                raise ValueError("classifier predicate requires eq/string or in/string-list")
        elif self.op not in {"gte", "lte", "abs_gte"} or not isinstance(self.value, float):
            raise ValueError("measured predicate requires a numeric comparison")
        return self


class MeasuredProfile(MeasuredModel):
    profile_id: str
    anchor_id: str
    candidate_ids: list[str] = Field(min_length=1)
    conditions: list[MeasuredCondition] = Field(min_length=1)
    conflicts: list[MeasuredCondition] = Field(default_factory=list)
    match_mode: Literal["all", "any"] = "all"


class MeasuredProfileBundle(MeasuredModel):
    schema_version: Literal["rootlens-measured-profiles.v1"] = "rootlens-measured-profiles.v1"
    dataset: Literal["wafer", "tep"]
    profiles: list[MeasuredProfile] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


def validate_measured_profiles(bundle, graph):
    from kgtracevis.kg.visual_profile_compiler import edge_reference_map

    edges = edge_reference_map(graph)
    for p in bundle.profiles:
        for node_id in [p.anchor_id, *p.candidate_ids]:
            if node_id not in graph.nodes:
                raise ValueError(f"profile refers to missing node: {node_id}")
        for c in [*p.conditions, *p.conflicts]:
            if not c.feature.startswith("wafer." if bundle.dataset == "wafer" else "process."):
                raise ValueError("predicate belongs to another dataset")
            edge = edges.get(c.source_edge_id)
            if c.concept_id not in graph.nodes or edge is None:
                raise ValueError(f"invalid measured binding: {c.concept_id} / {c.source_edge_id}")
            if c.concept_id not in {edge.head, edge.tail}:
                raise ValueError("binding concept is not an endpoint of its source edge")
            if bundle.dataset == "tep":
                node = graph.nodes[c.concept_id]
                aliases = {term.lower().replace("_", "") for term in node.searchable_terms}
                if node.label.lower() != "variable" or c.channel.replace("_", "") not in aliases:
                    raise ValueError(f"{c.channel} must bind its Variable node, not {c.concept_id}")
