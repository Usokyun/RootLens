"""Executable visual observations and diagnostic conditions, independent of the UI."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VisualFeature = Literal[
    "object",
    "region.area_ratio",
    "region.aspect_ratio",
    "region.eccentricity",
    "region.component_count",
    "region.morphology",
    "region.location",
    "region.semantic_candidates",
]
ConditionValue = str | float | list[str]


class VisualRegion(BaseModel):
    """Measurements in one explicitly identified image or detector coordinate plane."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    region_id: str = Field(min_length=1)
    source: Literal["detector_mask", "supplied_mask", "supplied_geometry"]
    coordinate_space: Literal["image", "detector_grid", "unspecified"] = "unspecified"
    image_shape: tuple[int, int] | None = None
    bbox_xyxy: tuple[float, float, float, float] | None = None
    image_bbox_xyxy: tuple[float, float, float, float] | None = None
    original_image_shape: tuple[int, int] | None = None
    area_ratio: float | None = Field(default=None, ge=0, le=1)
    aspect_ratio: float | None = Field(default=None, ge=1)
    eccentricity: float | None = Field(default=None, ge=0, le=1)
    component_count: int | None = Field(default=None, ge=0)
    morphology: str | None = None
    location: str | None = None
    semantic_candidates: list[str] = Field(default_factory=list)
    semantic_source: str | None = None
    semantic_status: Literal[
        "not_requested",
        "predicted",
        "normal",
        "unknown",
        "unaligned",
        "not_evaluated_budget",
    ] = "not_requested"
    semantic_description: str | None = None
    roi_path: str | None = None
    roi_bbox_xyxy: tuple[float, float, float, float] | None = None
    raw_ref: str | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> VisualRegion:
        if self.image_shape is not None and min(self.image_shape) <= 0:
            raise ValueError("image_shape must have positive height and width")
        if self.bbox_xyxy is not None:
            x1, y1, x2, y2 = self.bbox_xyxy
            if min(x1, y1) < 0 or x2 <= x1 or y2 <= y1:
                raise ValueError("bbox must be a positive xyxy extent")
            if self.image_shape and (x2 > self.image_shape[1] or y2 > self.image_shape[0]):
                raise ValueError("bbox lies outside its coordinate plane")
        if self.original_image_shape is not None and min(self.original_image_shape) <= 0:
            raise ValueError("original_image_shape must have positive height and width")
        for image_bbox in (self.image_bbox_xyxy, self.roi_bbox_xyxy):
            if image_bbox is None:
                continue
            if self.original_image_shape is None:
                raise ValueError("image bbox requires the original image dimensions")
            x1, y1, x2, y2 = image_bbox
            height, width = self.original_image_shape
            if min(x1, y1) < 0 or x2 <= x1 or y2 <= y1 or x2 > width or y2 > height:
                raise ValueError("image bbox lies outside the original image")
        if self.semantic_candidates and not self.semantic_source:
            raise ValueError("semantic candidates require their actual source")
        if self.semantic_status == "normal" and (
            self.semantic_candidates or not self.semantic_source
        ):
            raise ValueError("normal semantics require a source and no defect candidates")
        return self


class VisualCondition(BaseModel):
    """A registered feature predicate, optionally bound to a graph concept and edge."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    feature: VisualFeature
    op: Literal["eq", "in", "gte", "lte", "intersects"] = "in"
    value: ConditionValue
    concept_id: str | None = None
    source_edge_id: str | None = None
    required: bool = True
    group: Literal["object", "geometry", "semantics"] = "geometry"

    @model_validator(mode="before")
    @classmethod
    def derive_dependency_group(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            feature = value.get("feature")
            value["group"] = (
                "object"
                if feature == "object"
                else "semantics"
                if feature == "region.semantic_candidates"
                else "geometry"
            )
        return value

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean_operand(cls, value):
        if isinstance(value, bool):
            raise ValueError("boolean is not a numeric measurement")
        return value

    @model_validator(mode="after")
    def validate_operand(self) -> VisualCondition:
        numeric = self.feature in {
            "region.area_ratio",
            "region.aspect_ratio",
            "region.eccentricity",
            "region.component_count",
        }
        if numeric and (
            self.op not in {"eq", "gte", "lte"} or not isinstance(self.value, (int, float))
        ):
            raise ValueError("numeric feature requires a numeric comparison")
        if self.feature == "region.semantic_candidates" and self.op != "intersects":
            raise ValueError("semantic candidates require intersects")
        if not numeric and self.feature != "region.semantic_candidates":
            if self.op not in {"eq", "in"}:
                raise ValueError("scalar labels require eq/in")
            if self.op == "eq" and not isinstance(self.value, str):
                raise ValueError("label equality requires one string")
        if self.op in {"gte", "lte"}:
            if isinstance(self.value, (str, list, bool)):
                raise ValueError("numeric comparison requires a number")
        if self.op in {"in", "intersects"} and not isinstance(self.value, list):
            raise ValueError("set comparison requires a list of strings")
        return self


class VisualDiagnosticProfile(BaseModel):
    """Reusable graph knowledge; no sample-specific observation or final answer."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    object_id: str
    anchor_id: str
    conditions: list[VisualCondition] = Field(min_length=1)
    conflicts: list[VisualCondition] = Field(default_factory=list)
    candidate_ids: list[str] = Field(min_length=1)
    source_edge_ids: list[str] = Field(default_factory=list)


class VisualProfileBundle(BaseModel):
    """Compiler-to-runtime contract with inspectable rejected compilation entries."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rootlens-visual-profiles.v1"] = "rootlens-visual-profiles.v1"
    profiles: list[VisualDiagnosticProfile] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
