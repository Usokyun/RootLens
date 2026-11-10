"""0/1/2 spatial data and an independent classifier to the frozen common core."""

from __future__ import annotations

import math

from kgtracevis.mask.wafer_map_features import measure_wafer_map
from kgtracevis.schema.measured_reasoning import WaferMeasurements
from kgtracevis.schema.unified_evidence import EvidenceFrame


def spatial_frames(evidence):
    rows = [o for o in evidence.observations if o.value_type == "wafer-measurements.v1"]
    if len(rows) != 1:
        raise ValueError("a spatial query requires one complete grid measurement")
    observation = rows[0]
    measured = WaferMeasurements.model_validate(observation.value)
    extra = evidence.raw_evidence.extra
    grid = extra.get("wm811k", {}).get("wafer_map")
    shape = extra.get("descriptor_stats", {}).get("map_shape")
    uri = extra.get("wafer_map_path")
    if grid is not None:
        if any(type(cell) is bool for row in grid for cell in row):
            raise ValueError("binary boolean masks are not the declared 0/1/2 die encoding")
        actual = measure_wafer_map(grid)
        for field in (
            "valid_die_count",
            "failed_die_count",
            "failure_density",
            "center_density",
            "middle_density",
            "edge_density",
            "largest_component_ratio",
            "component_count",
            "linearity",
        ):
            a, b = getattr(actual, field), getattr(measured, field)
            if (
                (a is None) != (b is None)
                or a is not None
                and not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
            ):
                raise ValueError(f"spatial measurement disagrees with its actual grid: {field}")
        shape = [len(grid), len(grid[0])]
        uri = f"evidence://{evidence.case_id}/raw_evidence.extra.wm811k.wafer_map"
    if not uri or not shape or len(shape) != 2:
        raise ValueError("v2 spatial reasoning needs the actual grid asset and its declared shape")
    subject, parent = "wafer", "scope:grid"
    scopes = [
        {
            "scope_id": parent,
            "kind": "spatial_grid",
            "subject_id": subject,
            "asset_id": "grid",
            "encoding": {"background": 0, "normal": 1, "failed": 2},
        }
    ]
    for zone, interval in (
        ("all_valid", [0.0, 1.0]),
        ("center", [0.0, 0.4]),
        ("middle", [0.4, 0.8]),
        ("edge", [0.8, 1.0]),
    ):
        scopes.append(
            {
                "scope_id": "scope:" + zone,
                "kind": "spatial_zone",
                "subject_id": subject,
                "parent_scope_id": parent,
                "zone": zone,
                "normalized_radius_interval": interval,
            }
        )
    assets = [
        {"asset_id": "grid", "kind": "typed_array", "uri": uri, "dtype": "uint8", "shape": shape},
        {
            "asset_id": "prediction",
            "kind": "json",
            "uri": f"evidence://{evidence.case_id}/classifier",
        },
    ]
    procedures = [
        {
            "procedure_id": "spatial-statistics",
            "kind": "measurement",
            "input_asset_ids": ["grid"],
            "definition": "0=background,1=good,2=failed. Radius about valid bounding-box center, "
            "scaled by its axis half-spans, clipped at 1; center r<=.4, middle .4<r<.8, "
            "edge r>=.8. Eight-neighbor components. Density denominators use valid dies only.",
        },
        {
            "procedure_id": "classifier",
            "kind": "model_estimate",
            "input_asset_ids": ["grid"],
            "model_id": measured.classifier_source or "unavailable",
            "definition": "Independent producer classification, no native labels supplied.",
        },
    ]
    observations = []

    def add(feature, value, zone="all_valid", procedure="spatial-statistics"):
        observations.append(
            {
                "obs_id": observation.obs_id + ":" + zone + ":" + feature,
                "subject_id": subject,
                "feature_id": feature,
                "value": value,
                "status": "observed" if value is not None else "missing",
                "scope_id": "scope:" + zone,
                "procedure_id": procedure,
                "dependency_group": "grid",
                "raw_refs": ["prediction" if procedure == "classifier" else "grid"],
            }
        )

    def number(value):
        return {"kind": "number", "number": value, "unit": "1"} if value is not None else None

    add(
        "detection.anomaly_present",
        {"kind": "boolean", "boolean": measured.failed_die_count > 0}
        if measured.valid_die_count
        else None,
    )
    for name in ("valid_die_count", "failed_die_count", "component_count", "linearity"):
        add("spatial." + name, number(getattr(measured, name)))
    add(
        "spatial.largest_component_ratio",
        number(measured.largest_component_ratio) if measured.failed_die_count else None,
    )
    for zone, value in (
        ("all_valid", measured.failure_density if measured.valid_die_count else None),
        ("center", measured.center_density),
        ("middle", measured.middle_density),
        ("edge", measured.edge_density),
    ):
        add("spatial.failure_density", number(value), zone)
    add("spatial.grid", {"kind": "array_ref", "asset_id": "grid"})
    add(
        "classifier.pattern",
        {"kind": "category", "category": measured.classifier_pattern}
        if measured.classifier_pattern and measured.classifier_source
        else None,
        procedure="classifier",
    )
    return [
        EvidenceFrame.model_validate(
            {
                "case_id": evidence.case_id + "/query/grid",
                "source_dataset": evidence.dataset,
                "task": {
                    "target_role": "pattern_family",
                    "context_subject_id": subject,
                    "focus_subject_ids": [subject],
                    "scope_id": parent,
                },
                "subjects": [
                    {
                        "subject_id": subject,
                        "kind": "spatial_grid",
                        "external_namespace": "industrial.object",
                        "external_id": evidence.object,
                    }
                ],
                "scopes": scopes,
                "assets": assets,
                "procedures": procedures,
                "observations": observations,
            }
        )
    ]
