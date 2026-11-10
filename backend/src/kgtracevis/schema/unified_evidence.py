"""Typed, modality-independent observation contract for unified reasoning.

The legacy Evidence contract is unchanged. Only this explicit v2 entry point
requires these fields; raw unregistered metadata never becomes executable data.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

Identifier = Annotated[str, Field(min_length=1, strict=True)]
FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class UnifiedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


class NumberValue(UnifiedModel):
    kind: Literal["number"]
    number: FiniteNumber
    unit: Identifier


class BooleanValue(UnifiedModel):
    kind: Literal["boolean"]
    boolean: StrictBool


class CategoryValue(UnifiedModel):
    kind: Literal["category"]
    category: Identifier


class CandidateSetValue(UnifiedModel):
    kind: Literal["candidate_set"]
    items: list[Identifier]
    exhaustive: StrictBool = False

    @model_validator(mode="after")
    def unique_items(self):
        if len(self.items) != len(set(self.items)):
            raise ValueError("candidate_set contains duplicate labels")
        return self


class IntervalValue(UnifiedModel):
    kind: Literal["interval"]
    lower: FiniteNumber
    upper: FiniteNumber
    unit: Identifier

    @model_validator(mode="after")
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError("interval lower exceeds upper")
        return self


class ArrayRefValue(UnifiedModel):
    kind: Literal["array_ref"]
    asset_id: Identifier


ObservationValue = Annotated[
    NumberValue | BooleanValue | CategoryValue | CandidateSetValue | IntervalValue | ArrayRefValue,
    Field(discriminator="kind"),
]


class Subject(UnifiedModel):
    subject_id: Identifier
    kind: Literal["object", "image_region", "equipment", "variable", "spatial_grid", "event"]
    external_namespace: Identifier | None = None
    external_id: Identifier | None = None
    parent_id: Identifier | None = None
    context_subject_id: Identifier | None = None

    @model_validator(mode="after")
    def external_identity(self):
        if (self.external_namespace is None) != (self.external_id is None):
            raise ValueError("external identity needs namespace and id together")
        return self


class ImageRegionScope(UnifiedModel):
    scope_id: Identifier
    kind: Literal["image_region"]
    subject_id: Identifier
    asset_id: Identifier
    image_shape_hw: tuple[Annotated[int, Field(strict=True, gt=0)], ...]
    coordinate_space: Literal["original_image_pixels", "detector_grid_pixels"]
    bbox_xyxy: tuple[FiniteNumber, FiniteNumber, FiniteNumber, FiniteNumber]

    @model_validator(mode="after")
    def geometry(self):
        if len(self.image_shape_hw) != 2:
            raise ValueError("image_shape_hw needs height and width")
        h, w = self.image_shape_hw
        x1, y1, x2, y2 = self.bbox_xyxy
        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
            raise ValueError("bbox exceeds its declared coordinate plane")
        return self


class TimeWindowScope(UnifiedModel):
    scope_id: Identifier
    kind: Literal["time_window"]
    context_subject_id: Identifier
    sample_start: Annotated[int, Field(strict=True, ge=0)]
    sample_end: Annotated[int, Field(strict=True, ge=0)]
    index_base: Literal[0, 1]
    end_inclusive: StrictBool
    sampling_seconds: Annotated[FiniteNumber, Field(gt=0)]

    @model_validator(mode="before")
    @classmethod
    def integer_index_base(cls, value):
        if isinstance(value, dict) and "index_base" in value:
            if type(value["index_base"]) is not int:
                raise ValueError("index_base must be an integer, not a boolean or float")
        return value

    @model_validator(mode="after")
    def time_axis(self):
        count = self.sample_end - self.sample_start + int(self.end_inclusive)
        if self.sample_start < self.index_base or count <= 0:
            raise ValueError("empty or reversed time window")
        return self


class DieEncoding(UnifiedModel):
    background: Literal[0] = 0
    normal: Literal[1] = 1
    failed: Literal[2] = 2


class SpatialGridScope(UnifiedModel):
    scope_id: Identifier
    kind: Literal["wafer_grid", "spatial_grid"]
    subject_id: Identifier
    asset_id: Identifier
    encoding: DieEncoding


class SpatialZoneScope(UnifiedModel):
    scope_id: Identifier
    kind: Literal["wafer_zone", "spatial_zone"]
    subject_id: Identifier
    parent_scope_id: Identifier
    zone: Identifier
    normalized_radius_interval: tuple[FiniteNumber, FiniteNumber]
    valid_die_only: StrictBool = True

    @model_validator(mode="after")
    def radius(self):
        lo, hi = self.normalized_radius_interval
        if not 0 <= lo < hi <= 1:
            raise ValueError("invalid normalized radius interval")
        return self


class EventScope(UnifiedModel):
    scope_id: Identifier
    kind: Literal["event"]
    subject_id: Identifier
    context_subject_id: Identifier | None = None


Scope = Annotated[
    ImageRegionScope | TimeWindowScope | SpatialGridScope | SpatialZoneScope | EventScope,
    Field(discriminator="kind"),
]


class FileAsset(UnifiedModel):
    asset_id: Identifier
    kind: Literal["image", "mask", "json", "numeric_model", "text"]
    uri: Identifier


class TypedArrayAsset(UnifiedModel):
    asset_id: Identifier
    kind: Literal["typed_array"]
    uri: Identifier
    dtype: Literal["float32", "float64", "uint8", "int32", "int64"]
    shape: list[Annotated[int, Field(strict=True, gt=0)]] = Field(min_length=1)
    columns: list[Identifier] | None = None

    @model_validator(mode="after")
    def array_layout(self):
        if self.columns is not None and (
            len(self.shape) != 2
            or len(self.columns) != self.shape[1]
            or len(set(self.columns)) != len(self.columns)
        ):
            raise ValueError("array columns must uniquely describe its second axis")
        return self


Asset = Annotated[FileAsset | TypedArrayAsset, Field(discriminator="kind")]


class Procedure(UnifiedModel):
    procedure_id: Identifier
    kind: Literal["measurement", "model_estimate", "operator_assertion"]
    input_asset_ids: list[Identifier] = Field(default_factory=list)
    reference_id: Identifier | None = None
    definition: str = ""
    model_id: str | None = None
    version: str | None = None


class Reference(UnifiedModel):
    reference_id: Identifier
    kind: Literal["normal_standardization", "normal_image"]
    normal_asset_id: Identifier
    scaler_asset_id: Identifier | None = None

    @model_validator(mode="after")
    def scaler_required(self):
        if self.kind == "normal_standardization" and self.scaler_asset_id is None:
            raise ValueError("normal standardization requires its fitted scaler asset")
        return self


class UnifiedObservation(UnifiedModel):
    obs_id: Identifier
    subject_id: Identifier
    feature_id: Identifier
    value: ObservationValue | None = None
    status: Literal["observed", "missing", "invalid", "not_applicable"]
    scope_id: Identifier
    procedure_id: Identifier
    reference_id: Identifier | None = None
    dependency_group: Identifier
    raw_refs: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def observation_state(self):
        if self.status == "observed" and (self.value is None or not self.raw_refs):
            raise ValueError("observed values need a typed value and raw references")
        if self.status != "observed" and self.value is not None:
            raise ValueError("unobserved/invalid values belong in raw assets, not executable value")
        return self


class DiagnosticTask(UnifiedModel):
    target_role: Identifier
    context_subject_id: Identifier
    focus_subject_ids: list[Identifier] = Field(min_length=1)
    scope_id: Identifier
    reference_id: Identifier | None = None


def indexed(rows, key: str):
    """Build an identity index, refusing ambiguous identity instead of overwriting."""
    result = {getattr(row, key): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate {key}")
    return result


class EvidenceFrame(UnifiedModel):
    schema_version: Literal["rootlens-evidence.v2"] = "rootlens-evidence.v2"
    example_kind: Literal["synthetic_design"] | None = None
    case_id: Identifier
    source_dataset: Identifier = "unknown"
    task: DiagnosticTask
    subjects: list[Subject] = Field(min_length=1)
    scopes: list[Scope] = Field(min_length=1)
    assets: list[Asset] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    observations: list[UnifiedObservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def reference_integrity(self):
        subjects = indexed(self.subjects, "subject_id")
        scopes = indexed(self.scopes, "scope_id")
        assets = indexed(self.assets, "asset_id")
        procedures = indexed(self.procedures, "procedure_id")
        refs = indexed(self.references, "reference_id")
        indexed(self.observations, "obs_id")

        def require(value, values, description):
            if value is not None and value not in values:
                raise ValueError(f"unknown {description}: {value}")

        for subject in self.subjects:
            require(subject.parent_id, subjects, "parent subject")
            require(subject.context_subject_id, subjects, "context subject")
            seen = {subject.subject_id}
            parent = subject.parent_id
            while parent:
                if parent in seen:
                    raise ValueError("cyclic subject hierarchy")
                seen.add(parent)
                require(parent, subjects, "ancestor subject")
                parent = subjects[parent].parent_id
        for scope in self.scopes:
            require(getattr(scope, "subject_id", None), subjects, "scope subject")
            require(getattr(scope, "context_subject_id", None), subjects, "scope context")
            require(getattr(scope, "asset_id", None), assets, "scope asset")
            if isinstance(scope, SpatialZoneScope):
                parent = scopes.get(scope.parent_scope_id)
                if (
                    not isinstance(parent, SpatialGridScope)
                    or parent.subject_id != scope.subject_id
                ):
                    raise ValueError("spatial zone must belong to the same subject's grid")
        for reference in self.references:
            require(reference.normal_asset_id, assets, "normal asset")
            require(reference.scaler_asset_id, assets, "scaler asset")
            if reference.kind == "normal_standardization":
                if not isinstance(assets[reference.normal_asset_id], TypedArrayAsset):
                    raise ValueError("normal standardization needs a typed normal-data array")
                if assets[reference.scaler_asset_id].kind != "numeric_model":
                    raise ValueError("standardization scaler must be a numeric model asset")
            elif assets[reference.normal_asset_id].kind != "image":
                raise ValueError("normal image reference must point to an image")
        for procedure in self.procedures:
            for asset_id in procedure.input_asset_ids:
                require(asset_id, assets, "procedure input asset")
            require(procedure.reference_id, refs, "procedure reference")
        for obs in self.observations:
            require(obs.subject_id, subjects, "observation subject")
            require(obs.scope_id, scopes, "observation scope")
            require(obs.procedure_id, procedures, "observation procedure")
            require(obs.reference_id, refs, "observation reference")
            for asset_id in obs.raw_refs:
                require(asset_id, assets, "observation raw asset")
            if isinstance(obs.value, ArrayRefValue):
                require(obs.value.asset_id, assets, "observation array")
                if not isinstance(assets[obs.value.asset_id], TypedArrayAsset):
                    raise ValueError("array_ref must reference a typed array")
            scope = scopes[obs.scope_id]
            if getattr(scope, "subject_id", obs.subject_id) != obs.subject_id:
                raise ValueError("observation and scope subjects differ")
            if isinstance(scope, TimeWindowScope):
                context = subjects[obs.subject_id].context_subject_id
                if (
                    context != scope.context_subject_id
                    and obs.subject_id != scope.context_subject_id
                ):
                    raise ValueError("observation and time-window contexts differ")
            procedure = procedures[obs.procedure_id]
            if obs.reference_id != procedure.reference_id and procedure.reference_id is not None:
                raise ValueError("observation uses a different reference from its procedure")
        task = self.task
        require(task.context_subject_id, subjects, "task context")
        require(task.scope_id, scopes, "task scope")
        require(task.reference_id, refs, "task reference")
        for subject_id in task.focus_subject_ids:
            require(subject_id, subjects, "task focus")
        if len(set(task.focus_subject_ids)) != len(task.focus_subject_ids):
            raise ValueError("duplicate task focus")
        return self
