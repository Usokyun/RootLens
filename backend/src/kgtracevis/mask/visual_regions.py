"""Compute and adapt region measurements without inferring a physical defect cause."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from kgtracevis.mask.mask_feature_extractor import summarize_mask_features
from kgtracevis.schema.feature_catalog import MORPHOLOGY_LINEAR, MORPHOLOGY_SPOT
from kgtracevis.schema.visual_reasoning import VisualRegion


def regions_from_mask(
    mask: Any,
    *,
    source: str = "detector_mask",
    raw_ref: str | None = None,
    coordinate_space: str = "detector_grid",
) -> list[VisualRegion]:
    """Measure each 4-connected region; IDs follow deterministic raster order."""
    array = np.asarray(mask, dtype=float)
    if array.ndim != 2 or not array.size or not np.isfinite(array).all():
        raise ValueError("mask must be a nonempty finite 2-dimensional array")
    binary = array > 0
    remaining = set(zip(*np.where(binary), strict=True))
    components: list[list[tuple[int, int]]] = []
    # Sorting once avoids quadratic min(remaining) for highly fragmented maps.
    for start in sorted(remaining):
        if start not in remaining:
            continue
        remaining.remove(start)
        queue = [start]
        points = []
        while queue:
            row, col = queue.pop()
            points.append((row, col))
            for p in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if p in remaining:
                    remaining.remove(p)
                    queue.append(p)
        components.append(points)
    regions = []
    for index, points in enumerate(components, start=1):
        coords = np.asarray(points, dtype=float)
        ys, xs = coords[:, 0], coords[:, 1]
        x1, y1, x2, y2 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        eigenvalues = np.linalg.eigvalsh(np.cov(coords.T)) if len(points) > 1 else [0, 0]
        largest, smallest = float(max(eigenvalues)), float(min(eigenvalues))
        eccentricity = (1 - max(0, smallest) / largest) ** 0.5 if largest > 0 else 0
        summary = summarize_mask_features(
            {
                "centroid_norm": [
                    xs.mean() / max(1, binary.shape[1] - 1),
                    ys.mean() / max(1, binary.shape[0] - 1),
                ]
            },
            bbox=[x1, y1, x2, y2],
            centroid=[xs.mean(), ys.mean()],
            area_ratio=len(points) / binary.size,
            eccentricity=eccentricity,
            component_count=1,
            image_shape=list(binary.shape),
        )
        regions.append(
            VisualRegion.model_validate(
                {
                    "region_id": f"region_{index}",
                    "source": source,
                    "coordinate_space": coordinate_space,
                    "image_shape": list(binary.shape),
                    "bbox_xyxy": [x1, y1, x2, y2],
                    "area_ratio": len(points) / binary.size,
                    "aspect_ratio": max(x2 - x1, y2 - y1) / min(x2 - x1, y2 - y1),
                    "eccentricity": eccentricity,
                    "component_count": 1,
                    # Eccentricity .8 still permits a broad 1.67:1 ellipse/crescent.
                    # Reserve "linear" for >=3:1 bounding extent or a thin covariance axis.
                    "morphology": MORPHOLOGY_LINEAR
                    if max(x2 - x1, y2 - y1) / min(x2 - x1, y2 - y1) >= 3 or eccentricity >= 0.95
                    else MORPHOLOGY_SPOT,
                    "location": summary.get("location"),
                    "raw_ref": raw_ref,
                }
            )
        )
    return regions


def regions_from_record(data: Mapping[str, Any]) -> list[VisualRegion]:
    """Read typed regions or adapt supplied geometry; never read files from arbitrary records."""
    if "visual_regions" in data:
        regions = [VisualRegion.model_validate(row) for row in data["visual_regions"]]
        if len({region.region_id for region in regions}) != len(regions):
            raise ValueError("region_id must be unique within a case")
        return regions
    if data.get("predicted_mask") is not None:
        return regions_from_mask(
            data["predicted_mask"],
            source="supplied_mask",
            raw_ref="predicted_mask",
            coordinate_space="image",
        )
    stats = data.get("mask_stats") or data.get("geometry")
    geometry_keys = ("bbox", "bounding_box", "area_ratio", "eccentricity", "image_shape")
    if not isinstance(stats, Mapping) and not any(key in data for key in geometry_keys):
        return []
    summary = summarize_mask_features(
        stats if isinstance(stats, Mapping) else {},
        bbox=data.get("bbox", data.get("bounding_box")),
        area_ratio=data.get("area_ratio"),
        centroid=data.get("centroid"),
        image_shape=data.get("image_shape"),
        eccentricity=data.get("eccentricity"),
        component_count=data.get("component_count"),
    )
    normalized = summary["mask_stats"]
    return [
        VisualRegion.model_validate(
            {
                "region_id": "region_1",
                "source": "supplied_geometry",
                "coordinate_space": "unspecified",
                "image_shape": normalized.get("image_shape"),
                "bbox_xyxy": normalized.get("bbox"),
                "area_ratio": normalized.get("area_ratio"),
                "aspect_ratio": normalized.get("aspect_ratio"),
                "eccentricity": normalized.get("eccentricity"),
                "component_count": normalized.get("component_count"),
                "morphology": summary.get("morphology"),
                "location": summary.get("location"),
                "raw_ref": "raw_evidence.extra.mask_stats",
            }
        )
    ]


def map_regions_to_image(
    regions: list[VisualRegion],
    original_shape: tuple[int, int],
    transform: Mapping[str, Any] | None,
) -> list[VisualRegion]:
    """Invert only the explicitly recorded resize/crop, never infer alignment from size alone."""
    mapped = []
    height, width = original_shape
    for region in regions:
        bbox = region.bbox_xyxy
        if bbox is None:
            mapped.append(region)
            continue
        if region.coordinate_space == "image":
            image_bbox = bbox
        elif transform and transform.get("kind") == "identity":
            if region.image_shape != original_shape:
                raise ValueError("identity mapping requires equal image and detector dimensions")
            image_bbox = bbox
        elif transform and transform.get("kind") in {"resize", "resize_center_crop"}:
            if region.image_shape is None:
                raise ValueError("detector-grid mapping requires its image_shape")
            grid_h, grid_w = region.image_shape
            if transform["kind"] == "resize":
                left, top, crop_w, crop_h = 0, 0, width, height
                resized_w, resized_h = width, height
            else:
                resized_h, resized_w = transform["resized_shape"]
                left, top, crop_w, crop_h = transform["crop_xywh"]
            x1, y1, x2, y2 = bbox
            image_bbox = (
                (left + x1 / grid_w * crop_w) * width / resized_w,
                (top + y1 / grid_h * crop_h) * height / resized_h,
                (left + x2 / grid_w * crop_w) * width / resized_w,
                (top + y2 / grid_h * crop_h) * height / resized_h,
            )
        else:
            mapped.append(region.model_copy(update={"original_image_shape": original_shape}))
            continue
        mapped.append(
            region.model_copy(
                update={
                    "image_bbox_xyxy": image_bbox,
                    "original_image_shape": original_shape,
                }
            )
        )
    return mapped
