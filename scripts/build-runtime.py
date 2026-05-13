#!/usr/bin/env python3
"""RootLens Module 3: offline RCA runtime generation with upstream logic.

This script keeps RootLens' browser app on a static runtime file while moving the
actual RCA generation back to the upstream Python implementations:

- route1 uses KGTraceVis entity linking / consistency / correction / path ranking
- route2 uses the exact Root-KGD scenario + ranking artifacts from TEP_KG

The browser still consumes ``public/generated/rootlens-runtime.json``. The
difference is that the file is now built offline from the original reasoning
logic instead of local JS heuristics.
"""

from __future__ import annotations

import argparse
import builtins
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
TEP_KG_ROOT = Path("/Users/bytedance/my_project/TEP_KG")
MVTEC_KG_ROOT = Path("/Users/bytedance/my_project/MVTec/KGTraceVis")


def _install_zip_strict_compat() -> None:
    """Backport ``zip(..., strict=...)`` for upstream Python 3.10+ code."""
    if sys.version_info >= (3, 10):
        return
    if getattr(builtins.zip, "__name__", "") == "_zip_with_strict":
        return

    original_zip = builtins.zip

    def _zip_with_strict(*iterables: Iterable[Any], strict: bool = False):
        if not strict:
            yield from original_zip(*iterables)
            return

        iterators = [iter(iterable) for iterable in iterables]
        while True:
            row = []
            exhausted_at = None
            for index, iterator in enumerate(iterators):
                try:
                    row.append(next(iterator))
                except StopIteration:
                    exhausted_at = index
                    break
            if exhausted_at is None:
                yield tuple(row)
                continue
            if row:
                raise ValueError(
                    f"zip() argument {exhausted_at + 1} is shorter than argument 1"
                )
            for index, iterator in enumerate(iterators[exhausted_at + 1 :], start=exhausted_at + 2):
                try:
                    next(iterator)
                except StopIteration:
                    continue
                raise ValueError(
                    f"zip() argument {index} is longer than argument {exhausted_at + 1}"
                )
            return

    builtins.zip = _zip_with_strict


_install_zip_strict_compat()

sys.path.insert(0, str(TEP_KG_ROOT / "src"))
sys.path.insert(0, str(MVTEC_KG_ROOT / "src"))

from kgtracevis.kg.consistency_checker import check_consistency
from kgtracevis.kg.correction_generator import generate_correction_candidates
from kgtracevis.kg.entity_linker import link_evidence_entities
from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph
from kgtracevis.kg.path_ranker import rank_root_cause_paths
from kgtracevis.schema.evidence_schema import Evidence as KGTraceEvidence
from tep_kg.rca_evaluation import summarize_hit_rate_report

SUPPORTED_RUNTIME_FACETS = {"variable", "image_defect", "log_event"}
ROOTLENS_RUNTIME_VERSION = "rootlens-runtime.v1"
ROUTE1_TOP_K = 5
ROUTE2_TOP_KS = (1, 3, 5)


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _coerce_float(value: object, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stable_token(value: object) -> str:
    text = str(value or "")
    token = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
    token = "_".join(part for part in token.split("_") if part)
    return token or "unknown"


def _dedupe_text(values: Iterable[object]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _normalize_raw_evidence_refs(value: object) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    if isinstance(value, list):
        items = value
    elif value in ("", None):
        items = []
    else:
        items = [value]

    for item in items:
        if isinstance(item, dict):
            line = item.get("line")
            refs.append(
                {
                    "ref_id": str(item.get("ref_id", item.get("source_ref", ""))),
                    "label": str(item.get("label", item.get("raw_ref", item.get("ref_id", "")))),
                    "role": str(item.get("role", "evidence")),
                    "file_path": str(item.get("file_path", "")),
                    "line": line if isinstance(line, int) else None,
                }
            )
            continue
        text = str(item).strip()
        if not text:
            continue
        refs.append(
            {
                "ref_id": text,
                "label": text,
                "role": "evidence",
                "file_path": "",
                "line": None,
            }
        )
    return refs


def _first_ref(observation: dict[str, Any]) -> tuple[str | None, str | None]:
    refs = observation.get("raw_evidence_refs")
    if isinstance(refs, list) and refs:
        first = refs[0]
        if isinstance(first, dict):
            ref_id = first.get("ref_id")
            label = first.get("label")
            return (
                str(ref_id) if isinstance(ref_id, str) else None,
                str(label) if isinstance(label, str) else None,
            )

    source_ref = observation.get("source_ref")
    raw_ref = observation.get("raw_ref")
    return (
        str(source_ref) if isinstance(source_ref, str) and source_ref else None,
        str(raw_ref) if isinstance(raw_ref, str) and raw_ref else None,
    )


def _select_graph_dataset_id(dataset: str) -> str:
    if dataset == "tep":
        return "tep-kg"
    return "mvtec-project"


def _normalize_morphology(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {
            str(key): entry
            for key, entry in value.items()
            if entry is None or isinstance(entry, (str, int, float, bool, list, dict))
        }
    if isinstance(value, str) and value.strip():
        return {"canonical": value.strip()}
    if value is None:
        return {}
    return {"canonical": str(value)}


def _morphology_mention(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("canonical", "label", "name"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _runtime_obs_from_supported_contract(observation: dict[str, Any]) -> dict[str, Any]:
    facet = str(observation.get("facet", "")).strip()
    confidence = _coerce_float(observation.get("confidence"), 0.5)
    linked_entity_hints = observation.get("linked_entity_hints")
    if isinstance(linked_entity_hints, list):
        hints = _dedupe_text(linked_entity_hints)
    else:
        hints = []
    refs = _normalize_raw_evidence_refs(observation.get("raw_evidence_refs"))
    base: dict[str, Any] = {
        "obs_id": str(observation.get("obs_id", f"obs_{_stable_token(facet)}")),
        "facet": facet,
        "confidence": confidence,
        "linked_entity_hints": hints,
        "raw_evidence_refs": refs,
    }
    attributes = observation.get("attributes")
    if isinstance(attributes, dict) and attributes:
        base["attributes"] = attributes

    if facet == "variable":
        base.update(
            {
                "variable_name": str(observation.get("variable_name", observation.get("name", ""))),
                "contribution": _coerce_float(observation.get("contribution")),
                "direction": str(observation.get("direction", "unknown")) or "unknown",
            }
        )
        time_window = observation.get("time_window")
        if isinstance(time_window, dict):
            start = time_window.get("start")
            end = time_window.get("end")
            if isinstance(start, str) and isinstance(end, str):
                base["time_window"] = {"start": start, "end": end}
        if not base["linked_entity_hints"]:
            base["linked_entity_hints"] = _dedupe_text([base["variable_name"]])
        return base

    if facet == "image_defect":
        base.update(
            {
                "object": str(observation.get("object", "")),
                "anomaly_type": str(observation.get("anomaly_type", "")),
                "location": str(observation.get("location", "")),
                "morphology": _normalize_morphology(observation.get("morphology")),
                "severity": _coerce_float(observation.get("severity")),
            }
        )
        image_region = observation.get("image_region")
        if isinstance(image_region, dict):
            coords = {
                "x": _coerce_float(image_region.get("x")),
                "y": _coerce_float(image_region.get("y")),
                "w": _coerce_float(image_region.get("w")),
                "h": _coerce_float(image_region.get("h")),
            }
            base["image_region"] = coords
        if not base["linked_entity_hints"]:
            base["linked_entity_hints"] = _dedupe_text(
                [
                    base["object"],
                    base["anomaly_type"],
                    base["location"],
                    _morphology_mention(base["morphology"]),
                ]
            )
        return base

    if facet == "log_event":
        base.update(
            {
                "event_type": str(observation.get("event_type", "log_event")),
                "event_code": str(observation.get("event_code", "")),
                "message": str(observation.get("message", observation.get("name", ""))),
                "equipment": str(observation.get("equipment", "")),
            }
        )
        if not base["linked_entity_hints"]:
            base["linked_entity_hints"] = _dedupe_text([base["message"], base["equipment"]])
        return base

    raise ValueError(f"unsupported runtime observation facet: {facet}")


def _runtime_variable_observations_from_kgtracevis(
    raw_case: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_evidence = raw_case.get("raw_evidence", {})
    variable_contributions = {}
    if isinstance(raw_evidence, dict):
        contributions = raw_evidence.get("variable_contributions", {})
        if isinstance(contributions, dict):
            variable_contributions = {
                str(key): _coerce_float(value)
                for key, value in contributions.items()
            }

    observations = raw_case.get("observations", [])
    rows: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    if isinstance(observations, list):
        for observation in observations:
            if not isinstance(observation, dict) or observation.get("facet") != "variable":
                continue
            name = str(observation.get("name", "")).strip()
            if not name:
                continue
            seen_names.add(name)
            refs = _normalize_raw_evidence_refs(
                observation.get("raw_evidence_refs")
                or [
                    {
                        "source_ref": observation.get("source_ref"),
                        "raw_ref": observation.get("raw_ref"),
                    }
                ]
            )
            linked_entity_hints = observation.get("linked_entity_hints")
            hints = linked_entity_hints if isinstance(linked_entity_hints, list) else [name]
            row = {
                "obs_id": str(
                    observation.get(
                        "obs_id",
                        f"obs_{raw_case.get('case_id', 'unknown')}_variable_{_stable_token(name)}",
                    )
                ),
                "facet": "variable",
                "variable_name": name,
                "contribution": variable_contributions.get(
                    name,
                    _coerce_float(observation.get("value")),
                ),
                "direction": str(observation.get("direction", "unknown")) or "unknown",
                "confidence": _coerce_float(
                    observation.get("confidence"),
                    _coerce_float(raw_case.get("confidence"), 0.5),
                ),
                "linked_entity_hints": _dedupe_text(hints),
                "raw_evidence_refs": refs,
            }
            time_window = observation.get("time_window")
            if isinstance(time_window, dict):
                start = time_window.get("start")
                end = time_window.get("end")
                if isinstance(start, str) and isinstance(end, str):
                    row["time_window"] = {"start": start, "end": end}
            metadata = observation.get("metadata")
            if isinstance(metadata, dict) and metadata:
                row["attributes"] = metadata
            rows.append(row)

    raw_variables = []
    if isinstance(raw_evidence, dict):
        variables = raw_evidence.get("variables", [])
        if isinstance(variables, list):
            raw_variables = [str(item).strip() for item in variables if str(item).strip()]

    for name in raw_variables:
        if name in seen_names:
            continue
        rows.append(
            {
                "obs_id": f"obs_{raw_case.get('case_id', 'unknown')}_variable_{_stable_token(name)}",
                "facet": "variable",
                "variable_name": name,
                "contribution": variable_contributions.get(name, 0.0),
                "direction": "unknown",
                "confidence": _coerce_float(raw_case.get("confidence"), 0.5),
                "linked_entity_hints": [name],
                "raw_evidence_refs": [],
            }
        )

    return rows


def _runtime_log_observations_from_kgtracevis(
    raw_case: dict[str, Any],
) -> list[dict[str, Any]]:
    observations = raw_case.get("observations", [])
    rows: list[dict[str, Any]] = []
    seen_messages: set[str] = set()
    if isinstance(observations, list):
        for observation in observations:
            if not isinstance(observation, dict) or observation.get("facet") != "log_event":
                continue
            message = str(observation.get("name", "")).strip()
            if not message:
                continue
            seen_messages.add(message)
            refs = _normalize_raw_evidence_refs(
                observation.get("raw_evidence_refs")
                or [
                    {
                        "source_ref": observation.get("source_ref"),
                        "raw_ref": observation.get("raw_ref"),
                    }
                ]
            )
            metadata = observation.get("metadata")
            metadata_dict = metadata if isinstance(metadata, dict) else {}
            rows.append(
                {
                    "obs_id": str(
                        observation.get(
                            "obs_id",
                            f"obs_{raw_case.get('case_id', 'unknown')}_log_{_stable_token(message)}",
                        )
                    ),
                    "facet": "log_event",
                    "event_type": str(metadata_dict.get("event_type", "log_event")),
                    "event_code": str(metadata_dict.get("event_code", "")),
                    "message": message,
                    "equipment": str(metadata_dict.get("equipment", "")),
                    "confidence": _coerce_float(
                        observation.get("confidence"),
                        _coerce_float(raw_case.get("confidence"), 0.5),
                    ),
                    "linked_entity_hints": _dedupe_text(
                        observation.get("linked_entity_hints", [message])
                    ),
                    "raw_evidence_refs": refs,
                    "attributes": metadata_dict or None,
                }
            )

    raw_evidence = raw_case.get("raw_evidence", {})
    raw_events = []
    if isinstance(raw_evidence, dict):
        log_events = raw_evidence.get("log_events", [])
        if isinstance(log_events, list):
            raw_events = [str(item).strip() for item in log_events if str(item).strip()]

    for message in raw_events:
        if message in seen_messages:
            continue
        rows.append(
            {
                "obs_id": f"obs_{raw_case.get('case_id', 'unknown')}_log_{_stable_token(message)}",
                "facet": "log_event",
                "event_type": "log_event",
                "event_code": "",
                "message": message,
                "equipment": "",
                "confidence": _coerce_float(raw_case.get("confidence"), 0.5),
                "linked_entity_hints": [message],
                "raw_evidence_refs": [],
            }
        )

    normalized: list[dict[str, Any]] = []
    for row in rows:
        attributes = row.get("attributes")
        if attributes:
            normalized.append(row)
        else:
            row.pop("attributes", None)
            normalized.append(row)
    return normalized


def _field_observation_lookup(raw_case: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    observations = raw_case.get("observations", [])
    if not isinstance(observations, list):
        return lookup
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        facet = str(observation.get("facet", "")).strip()
        if facet:
            lookup[facet].append(observation)
    return lookup


def _runtime_image_observation_from_kgtracevis(
    raw_case: dict[str, Any],
) -> dict[str, Any] | None:
    by_facet = _field_observation_lookup(raw_case)
    object_value = raw_case.get("object")
    anomaly_type = raw_case.get("anomaly_type")
    location = raw_case.get("location")
    morphology = raw_case.get("morphology")
    severity = raw_case.get("severity")

    if not object_value and by_facet["object"]:
        object_value = by_facet["object"][0].get("name")
    if not anomaly_type and by_facet["anomaly_type"]:
        anomaly_type = by_facet["anomaly_type"][0].get("name")
    if not location and by_facet["location"]:
        location = by_facet["location"][0].get("name")
    if not morphology and by_facet["morphology"]:
        morphology = by_facet["morphology"][0].get("name")
    if severity in ("", None) and by_facet["severity"]:
        severity = by_facet["severity"][0].get("value", by_facet["severity"][0].get("name"))

    if not any([object_value, anomaly_type, location, morphology]):
        return None

    refs: list[dict[str, object]] = []
    hints: list[object] = []
    for facet in ("object", "anomaly_type", "location", "morphology"):
        for observation in by_facet.get(facet, []):
            refs.extend(
                _normalize_raw_evidence_refs(
                    observation.get("raw_evidence_refs")
                    or [
                        {
                            "source_ref": observation.get("source_ref"),
                            "raw_ref": observation.get("raw_ref"),
                        }
                    ]
                )
            )
            linked_entity_hints = observation.get("linked_entity_hints")
            if isinstance(linked_entity_hints, list):
                hints.extend(linked_entity_hints)
            else:
                hints.append(observation.get("name"))

    raw_evidence = raw_case.get("raw_evidence", {})
    image_region = None
    if isinstance(raw_evidence, dict):
        candidate = raw_evidence.get("image_region")
        if isinstance(candidate, dict):
            image_region = {
                "x": _coerce_float(candidate.get("x")),
                "y": _coerce_float(candidate.get("y")),
                "w": _coerce_float(candidate.get("w")),
                "h": _coerce_float(candidate.get("h")),
            }

    attributes: dict[str, Any] = {"source_format": "kgtracevis-evidence"}
    normalized_evidence = raw_case.get("normalized_evidence")
    if isinstance(normalized_evidence, dict) and normalized_evidence:
        attributes["normalized_evidence"] = normalized_evidence

    return {
        "obs_id": f"obs_{raw_case.get('case_id', 'unknown')}_image_defect_01",
        "facet": "image_defect",
        "object": str(object_value or raw_case.get("dataset", "unknown")),
        "anomaly_type": str(anomaly_type or "unknown"),
        "location": str(location or ""),
        "morphology": _normalize_morphology(morphology),
        "severity": _coerce_float(severity),
        "confidence": _coerce_float(raw_case.get("confidence"), 0.5),
        "linked_entity_hints": _dedupe_text(
            [
                *hints,
                object_value,
                anomaly_type,
                location,
                _morphology_mention(morphology),
            ]
        ),
        "raw_evidence_refs": refs,
        "attributes": attributes,
        **({"image_region": image_region} if image_region else {}),
    }


def _normalize_runtime_evidence(raw_case: dict[str, Any]) -> dict[str, Any]:
    observations = raw_case.get("observations", [])
    dataset = str(raw_case.get("dataset", "unknown"))
    runtime_observations: list[dict[str, Any]] = []

    if isinstance(observations, list) and all(
        isinstance(observation, dict)
        and str(observation.get("facet", "")).strip() in SUPPORTED_RUNTIME_FACETS
        for observation in observations
    ):
        runtime_observations = [
            _runtime_obs_from_supported_contract(observation)
            for observation in observations
            if isinstance(observation, dict)
        ]
    else:
        runtime_observations.extend(_runtime_variable_observations_from_kgtracevis(raw_case))
        image_observation = _runtime_image_observation_from_kgtracevis(raw_case)
        if image_observation is not None:
            runtime_observations.append(image_observation)
        runtime_observations.extend(_runtime_log_observations_from_kgtracevis(raw_case))

    if not runtime_observations:
        raise ValueError(f"unable to normalize evidence for case {raw_case.get('case_id')}")

    return {
        "case_id": str(raw_case.get("case_id", "unknown")),
        "case_label": str(raw_case.get("case_label", raw_case.get("case_id", "unknown"))),
        "dataset": dataset,
        "source": str(raw_case.get("source", "unknown")),
        "timestamp": str(raw_case.get("timestamp", _now_iso())),
        "summary": str(raw_case.get("summary", "")),
        "graph_dataset_id": str(
            raw_case.get("graph_dataset_id", _select_graph_dataset_id(dataset))
        ),
        "observations": runtime_observations,
    }


def _runtime_obs_to_kgtracevis_observations(
    observation: dict[str, Any],
) -> list[dict[str, Any]]:
    source_ref, raw_ref = _first_ref(observation)
    attributes = observation.get("attributes")
    metadata = attributes if isinstance(attributes, dict) else {}

    if observation["facet"] == "variable":
        return [
            {
                "obs_id": observation["obs_id"],
                "facet": "variable",
                "name": observation["variable_name"],
                "display_name": observation["variable_name"],
                "value": observation["contribution"],
                "value_type": "number",
                "direction": observation["direction"],
                "confidence": observation["confidence"],
                "source_ref": source_ref,
                "raw_ref": raw_ref,
                "time_window": observation.get("time_window"),
                "metadata": metadata,
            }
        ]

    if observation["facet"] == "image_defect":
        rows = [
            {
                "obs_id": f"{observation['obs_id']}_object",
                "facet": "object",
                "name": observation["object"],
                "confidence": observation["confidence"],
                "source_ref": source_ref,
                "raw_ref": raw_ref,
                "metadata": metadata,
            },
            {
                "obs_id": f"{observation['obs_id']}_anomaly_type",
                "facet": "anomaly_type",
                "name": observation["anomaly_type"],
                "confidence": observation["confidence"],
                "source_ref": source_ref,
                "raw_ref": raw_ref,
                "metadata": metadata,
            },
        ]
        if observation.get("location"):
            rows.append(
                {
                    "obs_id": f"{observation['obs_id']}_location",
                    "facet": "location",
                    "name": observation["location"],
                    "confidence": observation["confidence"],
                    "source_ref": source_ref,
                    "raw_ref": raw_ref,
                    "metadata": metadata,
                }
            )
        morphology = _morphology_mention(observation.get("morphology"))
        if morphology:
            rows.append(
                {
                    "obs_id": f"{observation['obs_id']}_morphology",
                    "facet": "morphology",
                    "name": morphology,
                    "confidence": observation["confidence"],
                    "source_ref": source_ref,
                    "raw_ref": raw_ref,
                    "metadata": metadata,
                }
            )
        rows.append(
            {
                "obs_id": f"{observation['obs_id']}_severity",
                "facet": "severity",
                "name": str(observation["severity"]),
                "value": observation["severity"],
                "value_type": "number",
                "confidence": observation["confidence"],
                "source_ref": source_ref,
                "raw_ref": raw_ref,
                "metadata": metadata,
            }
        )
        return rows

    if observation["facet"] == "log_event":
        return [
            {
                "obs_id": observation["obs_id"],
                "facet": "log_event",
                "name": observation["message"] or observation["event_code"] or observation["event_type"],
                "display_name": observation["message"],
                "confidence": observation["confidence"],
                "source_ref": source_ref,
                "raw_ref": raw_ref,
                "metadata": {
                    **metadata,
                    "event_type": observation["event_type"],
                    "event_code": observation["event_code"],
                    "equipment": observation["equipment"],
                },
            }
        ]

    return []


def _build_kgtracevis_evidence(
    raw_case: dict[str, Any],
    runtime_evidence: dict[str, Any],
) -> KGTraceEvidence:
    try:
        if "raw_evidence" in raw_case and "object" in raw_case and "anomaly_type" in raw_case:
            return KGTraceEvidence.model_validate(raw_case)
    except Exception:
        pass

    image_observation = next(
        (
            observation
            for observation in runtime_evidence["observations"]
            if observation["facet"] == "image_defect"
        ),
        None,
    )
    kg_observations = [
        row
        for observation in runtime_evidence["observations"]
        for row in _runtime_obs_to_kgtracevis_observations(observation)
    ]
    variable_rows = [
        observation
        for observation in runtime_evidence["observations"]
        if observation["facet"] == "variable"
    ]
    log_rows = [
        observation
        for observation in runtime_evidence["observations"]
        if observation["facet"] == "log_event"
    ]
    payload = {
        "case_id": runtime_evidence["case_id"],
        "dataset": runtime_evidence["dataset"],
        "source": runtime_evidence["source"],
        "object": image_observation["object"] if image_observation else "",
        "anomaly_type": image_observation["anomaly_type"] if image_observation else "",
        "location": image_observation["location"] if image_observation else None,
        "morphology": (
            _morphology_mention(image_observation["morphology"])
            if image_observation
            else None
        ),
        "severity": image_observation["severity"] if image_observation else None,
        "confidence": max(
            _coerce_float(observation.get("confidence"), 0.0)
            for observation in runtime_evidence["observations"]
        ),
        "timestamp": runtime_evidence["timestamp"],
        "raw_evidence": {
            "variables": [observation["variable_name"] for observation in variable_rows],
            "variable_contributions": {
                observation["variable_name"]: observation["contribution"]
                for observation in variable_rows
            },
            "log_events": [observation["message"] for observation in log_rows],
            "description": runtime_evidence["summary"],
            "extra": {
                "graph_dataset_id": runtime_evidence["graph_dataset_id"],
            },
        },
        "observations": kg_observations,
        "adapter": {
            "name": "rootlens-runtime",
            "produces_root_cause": False,
            "metadata": {"source_format": "rootlens-unified-evidence"},
        },
        "normalized_evidence": {},
        "human_feedback": raw_case.get("human_feedback"),
    }
    return KGTraceEvidence.model_validate(payload)


def _route1_node_label(node: dict[str, Any], dataset_id: str) -> str:
    if dataset_id == "tep-kg":
        attributes = node.get("attributes", {})
        candidate_role = str(attributes.get("candidate_role", ""))
        if candidate_role == "root_cause_anchor" or str(node["id"]).startswith("faultanchor:"):
            return "RootCause"
    return str(node.get("category") or node.get("kind") or "Entity")


def _project_route1_graph(dataset: dict[str, Any]) -> KnowledgeGraph:
    dataset_id = str(dataset["id"])
    default_scenario = "tep" if dataset_id == "tep-kg" else "shared"
    reverse_edges = dataset_id == "tep-kg"

    nodes = [
        KGNode(
            id=str(node["id"]),
            name=str(node["name"]),
            label=_route1_node_label(node, dataset_id),
            scenario=str(node.get("attributes", {}).get("scenario", default_scenario)),
            aliases=tuple(_dedupe_text(node.get("aliases", []))),
            description=str(node.get("description", "")),
        )
        for node in dataset["nodes"]
    ]

    deduped_edges: dict[tuple[str, str, str, str], KGEdge] = {}
    for edge in dataset["edges"]:
        head = str(edge["target"] if reverse_edges else edge["source"])
        tail = str(edge["source"] if reverse_edges else edge["target"])
        relation = str(edge["relation"])
        scenario = str(edge.get("attributes", {}).get("scenario", default_scenario))
        confidence = _coerce_float(edge.get("confidence"), _coerce_float(edge.get("weight"), 0.75))
        weight = _coerce_float(edge.get("weight"), confidence)
        evidence = str(
            edge.get("attributes", {}).get(
                "evidence",
                edge.get("origin", {}).get("filePath", edge["id"]),
            )
        )
        candidate = KGEdge(
            head=head,
            relation=relation,
            tail=tail,
            scenario=scenario,
            source=str(
                edge.get("attributes", {}).get(
                    "source",
                    edge.get("origin", {}).get("layer", dataset_id),
                )
            ),
            evidence=evidence,
            confidence=confidence,
            weight=weight,
            review_status=str(edge.get("attributes", {}).get("review_status", "accept")),
            feedback_count=_coerce_int(edge.get("attributes", {}).get("feedback_count"), 0),
            accepted_count=_coerce_int(edge.get("attributes", {}).get("accepted_count"), 0),
            rejected_count=_coerce_int(edge.get("attributes", {}).get("rejected_count"), 0),
        )
        key = (candidate.head, candidate.relation, candidate.tail, candidate.scenario)
        previous = deduped_edges.get(key)
        if previous is None or candidate.confidence > previous.confidence:
            deduped_edges[key] = candidate

    return KnowledgeGraph(nodes, deduped_edges.values())


def _correction_target_meta(
    runtime_evidence: dict[str, Any],
    field: str,
) -> tuple[str | None, str | None]:
    image_defect_obs = [
        observation
        for observation in runtime_evidence["observations"]
        if observation["facet"] == "image_defect"
    ]
    variable_obs = [
        observation
        for observation in runtime_evidence["observations"]
        if observation["facet"] == "variable"
    ]
    log_obs = [
        observation
        for observation in runtime_evidence["observations"]
        if observation["facet"] == "log_event"
    ]

    if field in {"object", "anomaly_type", "location", "morphology"} and image_defect_obs:
        return image_defect_obs[0]["obs_id"], "image_defect"
    if field == "variable" and len(variable_obs) == 1:
        return variable_obs[0]["obs_id"], "variable"
    if field == "log_event" and len(log_obs) == 1:
        return log_obs[0]["obs_id"], "log_event"
    return None, None


def _map_route1_link(
    link: dict[str, Any],
    graph: KnowledgeGraph,
) -> dict[str, Any]:
    selected_entity_id = link.get("selected_entity_id")
    selected_entity_name = None
    if isinstance(selected_entity_id, str) and selected_entity_id in graph.nodes:
        selected_entity_name = graph.nodes[selected_entity_id].name

    candidates = []
    for candidate in link.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        candidates.append(
            {
                "entity_id": str(candidate.get("entity_id", "")),
                "entity_name": str(candidate.get("name", candidate.get("entity_id", ""))),
                "entity_type": str(candidate.get("label", "")),
                "score": _coerce_float(candidate.get("score")),
            }
        )

    payload = {
        "link_id": str(link.get("link_id", "")),
        "field": str(link.get("field", "")),
        "mention": str(link.get("mention", "")),
        "selected_entity_id": selected_entity_id if isinstance(selected_entity_id, str) else None,
        "selected_entity_name": selected_entity_name,
        "score": _coerce_float(link.get("score")),
        "match_type": str(link.get("match_type", "unmatched")),
        "ambiguous": bool(link.get("ambiguous", False)),
        "candidates": candidates,
    }
    if isinstance(link.get("obs_id"), str):
        payload["obs_id"] = str(link["obs_id"])
    if isinstance(link.get("facet"), str):
        payload["facet"] = str(link["facet"])
    return payload


def _support_obs_ids_for_path(
    mapped_links: list[dict[str, Any]],
    path_nodes: Iterable[str],
) -> list[str]:
    node_ids = set(path_nodes)
    return sorted(
        {
            str(link["obs_id"])
            for link in mapped_links
            if isinstance(link.get("obs_id"), str)
            and isinstance(link.get("selected_entity_id"), str)
            and link["selected_entity_id"] in node_ids
        }
    )


def _build_route1_result(
    raw_case: dict[str, Any],
    runtime_evidence: dict[str, Any],
    graph: KnowledgeGraph,
) -> dict[str, Any]:
    kg_evidence = _build_kgtracevis_evidence(raw_case, runtime_evidence)
    linked_entities = link_evidence_entities(kg_evidence, graph)
    consistency = check_consistency(kg_evidence, graph, linked_entities)
    correction_candidates = generate_correction_candidates(
        kg_evidence,
        graph,
        linked_entities,
        consistency,
    )
    ranked_paths = rank_root_cause_paths(kg_evidence, graph, linked_entities, top_k=ROUTE1_TOP_K)

    mapped_links = [_map_route1_link(link, graph) for link in linked_entities]
    mapped_corrections = []
    for candidate in correction_candidates:
        target_obs_id, target_facet = _correction_target_meta(
            runtime_evidence,
            str(candidate.get("target_field", "")),
        )
        payload = {
            "candidate_id": str(candidate.get("candidate_id", "")),
            "source_field": str(candidate.get("source_field", "")),
            "source_entity_id": str(candidate.get("source_entity_id", "")),
            "target_field": str(candidate.get("target_field", "")),
            "original_value": candidate.get("original_value", candidate.get("original")),
            "suggested_entity_id": str(candidate.get("suggested_entity_id", "")),
            "suggested_value": str(candidate.get("suggested_value", candidate.get("suggested", ""))),
            "score": _coerce_float(candidate.get("score")),
            "reason": str(candidate.get("reason", "")),
            "supporting_edge_ids": [
                str(edge_id) for edge_id in candidate.get("supporting_edge_ids", [])
            ],
        }
        if target_obs_id is not None:
            payload["target_obs_id"] = target_obs_id
        if target_facet is not None:
            payload["target_facet"] = target_facet
        mapped_corrections.append(payload)

    mapped_paths = []
    for path in ranked_paths:
        source_edges = []
        for edge in path.get("source_edges", []):
            if not isinstance(edge, dict):
                continue
            source_edges.append(
                {
                    "edge_id": str(edge.get("edge_id", "")),
                    "source": str(edge.get("head", "")),
                    "target": str(edge.get("tail", "")),
                    "relation": str(edge.get("relation", "")),
                    "confidence": _coerce_float(edge.get("confidence")),
                }
            )
        target_entity_id = str(path.get("target_entity_id", ""))
        target_entity_name = (
            graph.nodes.get(target_entity_id).name
            if target_entity_id in graph.nodes
            else target_entity_id
        )
        mapped_paths.append(
            {
                "path_id": str(path.get("path_id", "")),
                "source_entity_id": str(path.get("source_entity_id", "")),
                "target_entity_id": target_entity_id,
                "target_entity_name": target_entity_name,
                "nodes": [str(node_id) for node_id in path.get("nodes", [])],
                "node_names": [str(name) for name in path.get("node_names", [])],
                "relations": [str(relation) for relation in path.get("relations", [])],
                "score": _coerce_float(path.get("score")),
                "confidence": _coerce_float(path.get("confidence")),
                "evidence_match": _coerce_float(path.get("evidence_match")),
                "length": _coerce_int(path.get("length")),
                "source_edges": source_edges,
                "support_obs_ids": _support_obs_ids_for_path(
                    mapped_links,
                    [str(node_id) for node_id in path.get("nodes", [])],
                ),
            }
        )

    return {
        "linked_entities": mapped_links,
        "consistency_score": _coerce_float(consistency.get("consistency_score")),
        "inconsistent_fields": [
            str(field) for field in consistency.get("inconsistent_fields", [])
        ],
        "consistency_checks": [
            {
                "source_field": str(check.get("source_field", "")),
                "target_field": str(check.get("target_field", "")),
                "source_entity_id": str(check.get("source_entity_id", "")),
                "target_entity_id": str(check.get("target_entity_id", "")),
                "relations": [str(relation) for relation in check.get("relations", [])],
                "passed": bool(check.get("passed", False)),
                "matched_relation": (
                    str(check.get("matched_relation"))
                    if isinstance(check.get("matched_relation"), str)
                    else None
                ),
            }
            for check in consistency.get("checks", [])
            if isinstance(check, dict)
        ],
        "correction_candidates": mapped_corrections,
        "ranked_paths": mapped_paths,
    }


def _build_route2_indexes() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    scenarios = {
        str(row["scenario_id"]): row
        for row in _read_jsonl(TEP_KG_ROOT / "data/processed/rca/rbc_contributions.jsonl")
    }
    rankings_by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _read_jsonl(TEP_KG_ROOT / "data/processed/models/root_kgd_rankings.jsonl"):
        rankings_by_scenario[str(row["scenario_id"])].append(row)
    for rows in rankings_by_scenario.values():
        rows.sort(
            key=lambda row: (
                _coerce_int(row.get("rank"), 999),
                str(row.get("candidate_id", "")),
            )
        )
    return scenarios, dict(rankings_by_scenario)


def _top_channel_rows(
    scenario: dict[str, Any],
    graph_nodes: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    graph_contributions = {
        str(entity_id): _coerce_float(value)
        for entity_id, value in scenario.get("graph_contributions", {}).items()
    }
    top_variable_rows = [
        row
        for row in scenario.get("top_variables", [])
        if isinstance(row, dict) and row.get("entity_id")
    ]
    ordered_variables = _dedupe_text(
        [
            *(str(row["entity_id"]) for row in top_variable_rows),
            *(
                entity_id
                for entity_id, _ in sorted(
                    graph_contributions.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
        ]
    )
    top_channels = []
    for rank, entity_id in enumerate(ordered_variables[:8], start=1):
        node = graph_nodes.get(entity_id, {})
        top_channels.append(
            {
                "entity_id": entity_id,
                "name": str(node.get("name", entity_id)),
                "contribution": graph_contributions.get(entity_id, 0.0),
                "rank": rank,
            }
        )
    return ordered_variables, top_channels


def _map_route2_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": str(row.get("scenario_id", "")),
        "fault_number": _coerce_int(row.get("fault_number")),
        "simulation_run": _coerce_int(row.get("simulation_run")),
        "rank": _coerce_int(row.get("rank")),
        "candidate_id": str(row.get("candidate_id", "")),
        "candidate_name": str(row.get("candidate_name", "")),
        "candidate_type": str(row.get("candidate_type", "")),
        "candidate_role": str(row.get("candidate_role", "")),
        "priority_level": _coerce_int(row.get("priority_level")),
        "seed_variable_id": str(row.get("seed_variable_id", "")),
        "seed_score": _coerce_float(row.get("seed_score")),
        "root_score": _coerce_float(row.get("root_score")),
        "ranking_score": _coerce_float(row.get("ranking_score")),
        "structural_ranking_score": _coerce_float(row.get("structural_ranking_score")),
        "ranking_adjustment": _coerce_float(row.get("ranking_adjustment")),
        "covered_contribution_mass": _coerce_float(row.get("covered_contribution_mass")),
        "active_variable_count": _coerce_int(row.get("active_variable_count")),
        "pattern_entropy": _coerce_float(row.get("pattern_entropy")),
        "discriminator_alignment": _coerce_float(row.get("discriminator_alignment")),
        "anchor_contribution_alignment": _coerce_float(row.get("anchor_contribution_alignment")),
        "anchor_dynamic_alignment": _coerce_float(row.get("anchor_dynamic_alignment")),
        "anchor_unique_contribution_alignment": _coerce_float(
            row.get("anchor_unique_contribution_alignment")
        ),
        "anchor_memory_bonus": _coerce_float(row.get("anchor_memory_bonus")),
        "anchor_memory_scenario_count": _coerce_int(row.get("anchor_memory_scenario_count")),
        "top_affected_variables": [
            {
                "entity_id": str(item.get("entity_id", "")),
                "name": str(item.get("name", item.get("entity_id", ""))),
                "propagated_score": _coerce_float(item.get("propagated_score")),
                "rbc_contribution": _coerce_float(item.get("rbc_contribution")),
            }
            for item in row.get("top_affected_variables", [])
            if isinstance(item, dict)
        ],
        "top_support_paths": [
            [str(node_id) for node_id in path]
            for path in row.get("top_support_paths", [])
            if isinstance(path, list)
        ],
        "support_evidence_ids": [
            str(item) for item in row.get("support_evidence_ids", [])
        ],
    }


def _build_route2_result(
    runtime_evidence: dict[str, Any],
    route2_scenarios: dict[str, dict[str, Any]],
    rankings_by_scenario: dict[str, list[dict[str, Any]]],
    graph_nodes: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if runtime_evidence["graph_dataset_id"] != "tep-kg":
        return None

    scenario_id = runtime_evidence["case_id"]
    scenario = route2_scenarios.get(scenario_id)
    ranking_rows = rankings_by_scenario.get(scenario_id)
    if scenario is None or not ranking_rows:
        return None

    graph_contributions = {
        str(entity_id): _coerce_float(value)
        for entity_id, value in scenario.get("graph_contributions", {}).items()
    }
    ordered_variables, top_channels = _top_channel_rows(scenario, graph_nodes)
    return {
        "fault_signature": {
            "contribution_vector": dict(graph_contributions),
            "ordered_variables": ordered_variables,
            "top_channels": top_channels,
            "graph_contributions": dict(graph_contributions),
        },
        "ranked_candidates": [
            _map_route2_candidate(row)
            for row in ranking_rows
        ],
    }


def _variable_observation_index(runtime_evidence: dict[str, Any]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for observation in runtime_evidence["observations"]:
        if observation["facet"] != "variable":
            continue
        candidate_ids = _dedupe_text(
            [
                *observation.get("linked_entity_hints", []),
                observation.get("variable_name"),
            ]
        )
        for candidate_id in candidate_ids:
            index[candidate_id].add(observation["obs_id"])
    return dict(index)


def _route2_support_obs_ids(
    route2_result: dict[str, Any],
    runtime_evidence: dict[str, Any],
) -> dict[str, set[str]]:
    variable_obs_index = _variable_observation_index(runtime_evidence)
    mapping: dict[str, set[str]] = {}
    for candidate in route2_result["ranked_candidates"]:
        obs_ids: set[str] = set()
        for affected in candidate["top_affected_variables"]:
            obs_ids.update(variable_obs_index.get(affected["entity_id"], set()))
        for path in candidate["top_support_paths"]:
            for node_id in path:
                obs_ids.update(variable_obs_index.get(node_id, set()))
        mapping[candidate["candidate_id"]] = obs_ids
    return mapping


def _build_cross_route_signals(
    route1_result: dict[str, Any] | None,
    route2_result: dict[str, Any] | None,
    runtime_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    if route1_result is None or route2_result is None:
        return []

    route1_paths_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in route1_result["ranked_paths"]:
        route1_paths_by_target[path["target_entity_id"]].append(path)

    route2_rank_by_candidate = {
        candidate["candidate_id"]: candidate["rank"]
        for candidate in route2_result["ranked_candidates"]
    }
    route2_name_by_candidate = {
        candidate["candidate_id"]: candidate["candidate_name"]
        for candidate in route2_result["ranked_candidates"]
    }
    route2_obs_ids = _route2_support_obs_ids(route2_result, runtime_evidence)

    shared_candidate_ids = sorted(
        set(route1_paths_by_target) & set(route2_rank_by_candidate),
        key=lambda candidate_id: (
            route2_rank_by_candidate[candidate_id],
            candidate_id,
        ),
    )

    signals = []
    for candidate_id in shared_candidate_ids:
        route1_paths = route1_paths_by_target[candidate_id]
        shared_obs_ids = sorted(
            set().union(*(set(path["support_obs_ids"]) for path in route1_paths))
            & route2_obs_ids.get(candidate_id, set())
        )
        signals.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": route2_name_by_candidate.get(candidate_id, candidate_id),
                "route1_path_ids": [path["path_id"] for path in route1_paths],
                "route2_rank": route2_rank_by_candidate[candidate_id],
                "shared_obs_ids": shared_obs_ids,
            }
        )
    return signals


def _build_analysis_notes(
    runtime_evidence: dict[str, Any],
    route1_result: dict[str, Any] | None,
    route2_result: dict[str, Any] | None,
) -> list[str]:
    dataset_id = runtime_evidence["graph_dataset_id"]
    notes = [
        f"route1_source=kgtracevis.entity_linker+consistency_checker+correction_generator+path_ranker@{dataset_id}",
    ]
    if dataset_id == "tep-kg":
        notes.append("route1_projection=reverse explanatory traversal over the TEP RCA graph")
    if route1_result is not None:
        notes.append(f"route1_path_count={len(route1_result['ranked_paths'])}")

    if route2_result is not None:
        notes.append(
            "route2_source=tep_kg/data/processed/rca/rbc_contributions.jsonl + "
            "data/processed/models/root_kgd_rankings.jsonl"
        )
        notes.append(
            f"route2_candidate_count={len(route2_result['ranked_candidates'])}"
        )
    else:
        notes.append("route2_source=not_applicable_for_this_case")
    return notes


def _graph_snapshot(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": dataset["id"],
        "label": dataset["label"],
        "graph_kind": dataset["graphKind"],
        "description": dataset["description"],
    }


def _runtime_case_from_raw(
    raw_case: dict[str, Any],
    datasets_by_id: dict[str, dict[str, Any]],
    route1_graphs: dict[str, KnowledgeGraph],
    route2_scenarios: dict[str, dict[str, Any]],
    rankings_by_scenario: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    runtime_evidence = _normalize_runtime_evidence(raw_case)
    dataset_id = runtime_evidence["graph_dataset_id"]
    dataset = datasets_by_id.get(dataset_id)
    if dataset is None:
        raise KeyError(f"graph dataset not found for case {runtime_evidence['case_id']}: {dataset_id}")

    route1_result = _build_route1_result(
        raw_case,
        runtime_evidence,
        route1_graphs[dataset_id],
    )
    graph_nodes = {str(node["id"]): node for node in dataset["nodes"]}
    route2_result = _build_route2_result(
        runtime_evidence,
        route2_scenarios,
        rankings_by_scenario,
        graph_nodes,
    )
    return {
        "case_id": runtime_evidence["case_id"],
        "case_label": runtime_evidence["case_label"],
        "dataset": runtime_evidence["dataset"],
        "source": runtime_evidence["source"],
        "summary": runtime_evidence["summary"],
        "graph_snapshot": _graph_snapshot(dataset),
        "evidence": runtime_evidence,
        "analysis": {
            "case_id": runtime_evidence["case_id"],
            "timestamp": runtime_evidence["timestamp"],
            "graph_dataset_id": runtime_evidence["graph_dataset_id"],
            "route1": route1_result,
            "route2": route2_result,
            "cross_route_signals": _build_cross_route_signals(
                route1_result,
                route2_result,
                runtime_evidence,
            ),
            "notes": _build_analysis_notes(runtime_evidence, route1_result, route2_result),
        },
    }


def _select_runtime_evidence_paths(evidence_dir: Path) -> list[Path]:
    return sorted(evidence_dir.glob("*.json"), key=lambda path: path.name)


def _route2_runtime_rows(runtime_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in runtime_cases:
        route2 = case["analysis"]["route2"]
        if route2 is None:
            continue
        rows.extend(route2["ranked_candidates"])
    return rows


def _exact_ranking_parity(
    runtime_cases: list[dict[str, Any]],
    rankings_by_scenario: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    compared_cases = 0
    top1_matches = 0
    top5_prefix_matches = 0
    candidate_count_matches = 0

    for case in runtime_cases:
        route2 = case["analysis"]["route2"]
        if route2 is None:
            continue
        compared_cases += 1
        scenario_id = case["case_id"]
        upstream_rows = rankings_by_scenario.get(scenario_id, [])
        runtime_rows = route2["ranked_candidates"]

        if len(runtime_rows) == len(upstream_rows):
            candidate_count_matches += 1

        upstream_top1 = upstream_rows[0]["candidate_id"] if upstream_rows else None
        runtime_top1 = runtime_rows[0]["candidate_id"] if runtime_rows else None
        if upstream_top1 == runtime_top1:
            top1_matches += 1

        upstream_top5 = [str(row["candidate_id"]) for row in upstream_rows[:5]]
        runtime_top5 = [str(row["candidate_id"]) for row in runtime_rows[:5]]
        if upstream_top5 == runtime_top5:
            top5_prefix_matches += 1

    denominator = max(1, compared_cases)
    return {
        "scenario_count": compared_cases,
        "top1_candidate_match_rate": round(top1_matches / denominator, 8),
        "top5_prefix_match_rate": round(top5_prefix_matches / denominator, 8),
        "candidate_count_match_rate": round(candidate_count_matches / denominator, 8),
    }


def _build_runtime_report(
    runtime_cases: list[dict[str, Any]],
    rankings_by_scenario: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_dataset = Counter(case["dataset"] for case in runtime_cases)
    route2_case_ids = [
        case["case_id"]
        for case in runtime_cases
        if case["analysis"]["route2"] is not None
    ]
    route2_rows = _route2_runtime_rows(runtime_cases)
    route2_report = (
        summarize_hit_rate_report(
            TEP_KG_ROOT,
            route2_rows,
            top_ks=ROUTE2_TOP_KS,
            ranking_reference="RootLens runtime subset",
        )
        if route2_rows
        else None
    )
    fault_distribution = Counter(
        int(row["fault_number"])
        for row in route2_rows
        if int(row.get("rank", 0)) == 1
    )
    return {
        "generated_at": _now_iso(),
        "runtime_case_count": len(runtime_cases),
        "case_count_by_dataset": dict(sorted(by_dataset.items())),
        "route1_case_count": sum(
            1
            for case in runtime_cases
            if case["analysis"]["route1"] is not None
        ),
        "route2_case_count": len(route2_case_ids),
        "route2_case_ids": route2_case_ids,
        "route2_fault_distribution": dict(sorted(fault_distribution.items())),
        "route2_exact_parity": _exact_ranking_parity(runtime_cases, rankings_by_scenario),
        "route2_hit_rate_report": route2_report,
        "sources": {
            "route1": [
                "KGTraceVis/src/kgtracevis/kg/entity_linker.py",
                "KGTraceVis/src/kgtracevis/kg/consistency_checker.py",
                "KGTraceVis/src/kgtracevis/kg/correction_generator.py",
                "KGTraceVis/src/kgtracevis/kg/path_ranker.py",
            ],
            "route2": [
                "TEP_KG/data/processed/rca/rbc_contributions.jsonl",
                "TEP_KG/data/processed/models/root_kgd_rankings.jsonl",
                "TEP_KG/data/processed/rca/fault_root_cause_labels.json",
            ],
        },
    }


def build_runtime(
    *,
    graphs_path: Path,
    evidence_dir: Path,
    output_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    graphs_payload = _read_json(graphs_path)
    datasets = graphs_payload.get("datasets", [])
    if not isinstance(datasets, list):
        raise ValueError("unified graphs payload is missing datasets")

    datasets_by_id = {
        str(dataset["id"]): dataset
        for dataset in datasets
        if isinstance(dataset, dict) and "id" in dataset
    }
    route1_graphs = {
        dataset_id: _project_route1_graph(dataset)
        for dataset_id, dataset in datasets_by_id.items()
    }
    route2_scenarios, rankings_by_scenario = _build_route2_indexes()

    runtime_cases = []
    for evidence_path in _select_runtime_evidence_paths(evidence_dir):
        raw_case = _read_json(evidence_path)
        runtime_cases.append(
            _runtime_case_from_raw(
                raw_case,
                datasets_by_id,
                route1_graphs,
                route2_scenarios,
                rankings_by_scenario,
            )
        )

    runtime_payload = {
        "schema_version": ROOTLENS_RUNTIME_VERSION,
        "generated_at": _now_iso(),
        "generator": "scripts/build-runtime.py",
        "cases": runtime_cases,
    }
    report_payload = _build_runtime_report(runtime_cases, rankings_by_scenario)

    _write_json(output_path, runtime_payload)
    _write_json(report_path, report_payload)
    return {
        "ok": True,
        "runtime_case_count": len(runtime_cases),
        "route2_case_count": report_payload["route2_case_count"],
        "output_path": str(output_path),
        "report_path": str(report_path),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RootLens Module 3 — build offline runtime from upstream RCA logic"
    )
    parser.add_argument(
        "--graphs",
        type=Path,
        default=REPO_ROOT / "public" / "generated" / "unified-graphs.json",
        help="Path to unified-graphs.json",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=REPO_ROOT / "public" / "generated" / "evidence",
        help="Directory containing generated evidence JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "public" / "generated" / "rootlens-runtime.json",
        help="Output path for rootlens-runtime.json",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=REPO_ROOT / "public" / "generated" / "rootlens-runtime-report.json",
        help="Output path for the runtime evaluation report",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the build summary as JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = build_runtime(
        graphs_path=args.graphs,
        evidence_dir=args.evidence_dir,
        output_path=args.output,
        report_path=args.report_output,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            f"[OK] built runtime with {summary['runtime_case_count']} cases "
            f"({summary['route2_case_count']} route2-enabled)",
            flush=True,
        )
        print(f"  runtime: {summary['output_path']}", flush=True)
        print(f"  report:  {summary['report_path']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
