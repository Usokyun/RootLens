"""Closed producer-output adapters; no defect/cause ranking lives at this boundary.

Dispatch is by declared observation contract, not by dataset. Each image ROI is
one query. Unregistered metadata and native dataset labels are never features.
"""

from __future__ import annotations

from kgtracevis.schema.evidence_schema import Evidence
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.visual_reasoning import VisualRegion


def _number(value, unit="1"):
    return {"kind": "number", "number": value, "unit": unit}


def visual_frames(evidence: Evidence) -> list[EvidenceFrame]:
    extra = evidence.raw_evidence.extra
    regions = [
        (obs, VisualRegion.model_validate(obs.value))
        for obs in evidence.observations
        if obs.value_type == "visual_region.v1"
    ]
    detector = extra.get("detector", {})
    detector = detector if isinstance(detector, dict) else {}
    anomaly = detector.get("raw_pred_label")
    if type(anomaly) is not bool:
        anomaly = None
    # A detector-normal or empty mask must not invent a bounding box. An event
    # query retains the actual detection result and leaves morphology missing.
    queries = regions or [(None, None)]
    frames = []
    for index, (observation, region) in enumerate(queries, start=1):
        subject, scope = "roi:" + str(index), "scope:" + str(index)
        image_uri = extra.get("image_path") or f"evidence://{evidence.case_id}/image"
        assets = [
            {"asset_id": "image", "kind": "image", "uri": image_uri},
            {"asset_id": "raw", "kind": "json", "uri": f"evidence://{evidence.case_id}"},
        ]
        scopes = [{"scope_id": scope, "kind": "event", "subject_id": subject}]
        if region:
            original = region.image_bbox_xyxy is not None
            shape = region.original_image_shape if original else region.image_shape
            bbox = region.image_bbox_xyxy if original else region.bbox_xyxy
            if shape and bbox and region.coordinate_space != "unspecified":
                scopes = [
                    {
                        "scope_id": scope,
                        "kind": "image_region",
                        "subject_id": subject,
                        "asset_id": "image",
                        "image_shape_hw": shape,
                        "coordinate_space": "original_image_pixels"
                        if original
                        else "detector_grid_pixels",
                        "bbox_xyxy": bbox,
                    }
                ]
            if region.raw_ref:
                assets.append({"asset_id": "mask", "kind": "json", "uri": region.raw_ref})
        procedures = [
            {
                "procedure_id": "detector",
                "kind": "model_estimate",
                "input_asset_ids": ["image"],
                "model_id": str(detector.get("name", "unknown")),
                "definition": "Explicit detector boolean, not semantic class or probability.",
            },
            {
                "procedure_id": "geometry",
                "kind": "measurement",
                "input_asset_ids": ["raw"],
                "definition": "Connected-component geometry in the declared mask plane.",
            },
        ]
        observations = []

        def add(
            feature,
            value,
            procedure,
            raw="raw",
            *,
            observations=observations,
            observation=observation,
            subject=subject,
            scope=scope,
        ):
            observations.append(
                {
                    "obs_id": (observation.obs_id if observation else evidence.case_id)
                    + ":" + feature,
                    "subject_id": subject,
                    "feature_id": feature,
                    "value": value,
                    "status": "observed" if value is not None else "missing",
                    "scope_id": scope,
                    "procedure_id": procedure,
                    "dependency_group": f"image/{subject}",
                    "raw_refs": [raw],
                }
            )

        add(
            "detection.anomaly_present",
            {"kind": "boolean", "boolean": anomaly} if anomaly is not None else None,
            "detector",
        )
        if region:
            for name in ("area_ratio", "aspect_ratio", "eccentricity", "component_count"):
                value = getattr(region, name)
                add("geometry." + name, _number(value) if value is not None else None, "geometry")
            for name in ("morphology", "location"):
                value = getattr(region, name)
                add(
                    "geometry." + name,
                    {"kind": "category", "category": value} if value else None,
                    "geometry",
                )
            source = region.semantic_source or "not_requested"
            procedures.append(
                {
                    "procedure_id": "semantics",
                    "kind": "model_estimate" if source.startswith("vlm:") else "operator_assertion",
                    "input_asset_ids": ["image", "raw"],
                    "model_id": source,
                    "definition": "Open appearance candidates; absent labels are not negative.",
                }
            )
            semantic_value = None
            if region.semantic_status in {"predicted", "normal"}:
                semantic_value = {
                    "kind": "candidate_set",
                    "items": region.semantic_candidates,
                    "exhaustive": False,
                }
            add("appearance.semantic_candidates", semantic_value, "semantics")
            add(
                "appearance.defect_present",
                {"kind": "boolean", "boolean": False}
                if region.semantic_status == "normal"
                else {"kind": "boolean", "boolean": True}
                if region.semantic_status == "predicted"
                else None,
                "semantics",
            )
        frames.append(
            EvidenceFrame.model_validate(
                {
                    "case_id": f"{evidence.case_id}/query/{index}",
                    "source_dataset": evidence.dataset,
                    "task": {
                        "target_role": "mechanism",
                        "context_subject_id": "object",
                        "focus_subject_ids": [subject],
                        "scope_id": scope,
                    },
                    "subjects": [
                        {
                            "subject_id": "object",
                            "kind": "object",
                            "external_namespace": "industrial.object",
                            "external_id": evidence.object,
                        },
                        {"subject_id": subject, "kind": "image_region", "parent_id": "object"},
                    ],
                    "scopes": scopes,
                    "assets": assets,
                    "procedures": procedures,
                    "observations": observations,
                }
            )
        )
    return frames


def evidence_frames(evidence: Evidence) -> list[EvidenceFrame]:
    contracts = {obs.value_type for obs in evidence.observations}
    if (
        "visual_region.v1" in contracts
        or evidence.source == "image"
        and "detector" in evidence.raw_evidence.extra
    ):
        return visual_frames(evidence)
    raise ValueError(
        "No registered v2 adapter for this producer contract; legacy entries are unchanged"
    )
