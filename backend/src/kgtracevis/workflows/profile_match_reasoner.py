"""Visual feature/graph matching with an executable, observation-level diagnostic trace."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kgtracevis.core.result import RankedRootCause, RcaReasoningResult
from kgtracevis.kg.graph import KGEdge, KnowledgeGraph, normalize_text
from kgtracevis.kg.visual_profile_compiler import (
    CAUSE_RELATIONS,
    compile_visual_profiles,
    edge_reference_map,
    observation_concept_binding,
    validate_visual_profiles,
)
from kgtracevis.schema.evidence_schema import Evidence
from kgtracevis.schema.visual_reasoning import (
    VisualCondition,
    VisualDiagnosticProfile,
    VisualProfileBundle,
    VisualRegion,
)


class VisualProfileReasoner:
    """Execute graph-bound conditions; empty diagnoses never request a generic fallback."""

    def __init__(
        self,
        profiles: VisualProfileBundle | None = None,
        *,
        graph_id: str | None = None,
    ) -> None:
        self.profiles = profiles
        self.graph_id = graph_id

    def reason_root_causes(
        self,
        evidence: Evidence,
        *,
        graph: KnowledgeGraph,
        linked_entities: list[dict[str, Any]],
        top_k: int = 5,
    ) -> RcaReasoningResult:
        del linked_entities
        if evidence.dataset != "mvtec":
            raise ValueError("visual profile reasoning supports mvtec only")
        bundle = self.profiles or compile_visual_profiles(graph)
        validate_visual_profiles(bundle, graph)
        edge_map = edge_reference_map(graph)
        observations = [
            obs for obs in evidence.observations if obs.value_type == "visual_region.v1"
        ]
        applicable = [
            profile
            for profile in bundle.profiles
            if normalize_text(evidence.object)
            in {normalize_text(term) for term in graph.nodes[profile.object_id].searchable_terms}
        ]
        if not applicable:
            return RcaReasoningResult(
                case_id=evidence.case_id,
                scoring_method="visual_profile_match",
                outcome="not_applicable",
                linked_entities=[],
                metadata={
                    "reasoner": "visual_profile_match",
                    "reasoner_adapter": "visual_profile_match",
                    "reasoning_profile_id": "mvtec_feature_graph_v1",
                    "selection_mode": "explicit",
                    "outcome": "not_applicable",
                    "fallback_applied": False,
                    "trace": [],
                    "graph_id": self.graph_id,
                    "region_count": len(observations),
                    "profile_count": len(bundle.profiles),
                    "profile_issues": bundle.issues,
                    "reason": f"当前工作图没有适用于对象 {evidence.object} 的可执行诊断画像。",
                },
            )
        detector = evidence.raw_evidence.extra.get("detector")
        detector_normal = isinstance(detector, Mapping) and detector.get("raw_pred_label") is False
        if detector_normal:
            return RcaReasoningResult(
                case_id=evidence.case_id,
                scoring_method="visual_profile_match",
                outcome="no_match",
                linked_entities=[],
                metadata={
                    "reasoner": "visual_profile_match",
                    "reasoner_adapter": "visual_profile_match",
                    "reasoning_profile_id": "mvtec_feature_graph_v1",
                    "selection_mode": "explicit",
                    "outcome": "no_match",
                    "detection_status": "normal",
                    "trace": [],
                    "graph_id": self.graph_id,
                    "region_count": len(observations),
                    "profile_count": len(bundle.profiles),
                    "fallback_applied": False,
                },
            )
        traces: list[dict[str, Any]] = []
        links: dict[tuple[str, str], dict[str, Any]] = {}
        candidates: dict[str, dict[str, Any]] = {}
        all_paths: dict[str, dict[str, Any]] = {}
        for observation in observations:
            region = VisualRegion.model_validate(observation.value)
            for profile in bundle.profiles:
                checks = [
                    _check(c, evidence.object, region, observation.obs_id, graph, profile.anchor_id)
                    for c in profile.conditions
                ]
                conflicts = [
                    _check(c, evidence.object, region, observation.obs_id, graph, profile.anchor_id)
                    for c in profile.conflicts
                ]
                failed = [c for c in checks if c["required"] and c["result"] == "not_matched"]
                missing = [c for c in checks if c["required"] and c["result"] == "missing"]
                refuted = [c for c in conflicts if c["result"] == "matched"]
                semantic_conflicts = [
                    c
                    for c in checks
                    if c["feature"] == "region.semantic_candidates" and c["result"] == "not_matched"
                ]
                status = (
                    "not_matched"
                    if failed or refuted or semantic_conflicts
                    else "insufficient_evidence"
                    if missing
                    else "matched"
                )
                if region.semantic_status == "normal":
                    status = "not_matched"
                elif region.semantic_status == "unknown" and region.semantic_source:
                    status = "insufficient_evidence"
                matched = [c for c in checks if c["result"] == "matched"]
                groups = {c["group"] for c in matched if c["feature"] != "object"}
                optional_conflicts = {
                    c["group"] for c in checks if not c["required"] and c["result"] == "not_matched"
                }
                score = float(len(groups)) - 0.5 * len(optional_conflicts)
                trace = {
                    "profile_id": profile.profile_id,
                    "obs_id": observation.obs_id,
                    "region_id": region.region_id,
                    "anchor_id": profile.anchor_id,
                    "status": status,
                    "conditions": checks,
                    "conflicts": conflicts,
                    "support_groups": sorted(groups),
                    "score": score,
                    "semantic_status": region.semantic_status,
                    "semantic_conflict": bool(semantic_conflicts),
                }
                traces.append(trace)
                if status != "matched" or not groups:
                    continue
                for check in matched:
                    if check["concept_id"]:
                        _add_link(
                            links,
                            observation.obs_id,
                            check["concept_id"],
                            check["feature"],
                            check["actual"],
                            graph,
                        )
                _add_link(
                    links,
                    observation.obs_id,
                    profile.anchor_id,
                    "anomaly_type",
                    graph.nodes[profile.anchor_id].name,
                    graph,
                )
                for candidate_id in profile.candidate_ids:
                    paths = _paths_for_match(
                        evidence.case_id,
                        observation.obs_id,
                        profile,
                        matched,
                        candidate_id,
                        graph,
                        edge_map,
                        score,
                    )
                    if not paths:
                        continue
                    row = candidates.setdefault(
                        candidate_id,
                        {
                            "score": score,
                            "obs_ids": set(),
                            "paths": [],
                            "matches": [],
                        },
                    )
                    row["score"] = max(row["score"], score)
                    row["obs_ids"].add(observation.obs_id)
                    row["matches"].append(trace)
                    row["paths"].extend(paths)
                    for path in paths:
                        all_paths[path["path_id"]] = path
        ranked = []
        selected = sorted(candidates, key=lambda c: (-candidates[c]["score"], c))[:top_k]
        for rank, candidate_id in enumerate(selected, start=1):
            row = candidates[candidate_id]
            used_edges = {e["edge_id"]: e for p in row["paths"] for e in p["source_edges"]}
            features = sorted(
                {
                    c["feature"]
                    for t in row["matches"]
                    for c in t["conditions"]
                    if c["result"] == "matched" and c["feature"] != "object"
                }
            )
            tied = any(
                other != candidate_id and candidates[other]["score"] == row["score"]
                for other in selected
            )
            ranked.append(
                RankedRootCause(
                    ranking_id=f"ranking:{evidence.case_id}:{candidate_id}",
                    rank=rank,
                    candidate_id=candidate_id,
                    candidate_name=graph.nodes[candidate_id].name,
                    candidate_label=graph.nodes[candidate_id].label,
                    candidate_role="plausible_mechanism",
                    score=row["score"],
                    explanation_paths=row["paths"],
                    supporting_edges=list(used_edges.values()),
                    support_evidence_ids=sorted(row["obs_ids"]),
                    scoring_method="visual_profile_match",
                    scoring_details={
                        "reason": (
                            f"区域 {', '.join(sorted({t['region_id'] for t in row['matches']}))} "
                            f"的 {', '.join(features)} 与图谱诊断条件相符。"
                            + ("当前观测无法区分同分的机制候选。" if tied else "")
                        ),
                        "score_meaning": "matched feature groups minus optional conflict penalty",
                        "profile_matches": row["matches"],
                    },
                )
            )
        paths = [p for p in all_paths.values() if p["target_entity_id"] in selected]
        outcome = (
            "matched"
            if ranked
            else (
                "insufficient_evidence"
                if not observations or any(t["status"] == "insufficient_evidence" for t in traces)
                else "no_match"
            )
        )
        return RcaReasoningResult(
            case_id=evidence.case_id,
            ranked_root_causes=ranked,
            top_k_paths=paths,
            scoring_method="visual_profile_match",
            outcome=outcome,
            linked_entities=list(links.values()),
            metadata={
                "reasoner": "visual_profile_match",
                "reasoner_adapter": "visual_profile_match",
                "outcome": outcome,
                "region_count": len(observations),
                "profile_count": len(bundle.profiles),
                "profile_issues": bundle.issues,
                "trace": traces,
                "fallback_applied": False,
                "graph_id": self.graph_id,
                "reasoning_profile_id": "mvtec_feature_graph_v1",
                "selection_mode": "explicit",
            },
        )


def _check(
    condition: VisualCondition,
    object_name: str,
    region: VisualRegion,
    obs_id: str,
    graph: KnowledgeGraph,
    anchor_id: str,
) -> dict[str, Any]:
    actual = (
        object_name
        if condition.feature == "object"
        else getattr(
            region,
            condition.feature.removeprefix("region."),
            None,
        )
    )
    if actual is None or actual == [] or actual == "":
        status = "missing"
    else:
        expected = condition.value
        if condition.op in {"gte", "lte"}:
            matched = (
                float(actual) >= float(expected)
                if condition.op == "gte"
                else float(actual) <= float(expected)
            )
        elif condition.op == "intersects":
            matched = bool(
                {normalize_text(str(v)) for v in actual}
                & {normalize_text(str(v)) for v in expected}
            )
        elif condition.op == "in":
            matched = normalize_text(str(actual)) in {normalize_text(str(v)) for v in expected}
        elif isinstance(expected, str):
            matched = normalize_text(str(actual)) == normalize_text(expected)
        else:
            matched = actual == expected
        status = "matched" if matched else "not_matched"
    binding = observation_concept_binding(graph, anchor_id, condition.feature, actual)
    result = {
        **condition.model_dump(mode="json"),
        "actual": actual,
        "result": status,
        "obs_id": obs_id,
        "measurement_source": region.semantic_source
        if condition.group == "semantics"
        else region.source,
        "raw_ref": region.raw_ref,
        "coordinate_space": region.coordinate_space,
        "bbox_xyxy": region.bbox_xyxy,
    }
    if condition.feature in {"region.morphology", "region.location"}:
        result["concept_id"] = binding.tail if binding else None
        result["source_edge_id"] = binding.edge_id if binding else None
    return result


def _add_link(
    links: dict,
    obs_id: str,
    concept_id: str,
    field: str,
    actual: Any,
    graph: KnowledgeGraph,
) -> None:
    links[(obs_id, concept_id)] = {
        "link_id": f"link:{obs_id}:{concept_id}",
        "obs_id": obs_id,
        "field": field,
        "mention": str(actual),
        "selected_entity_id": concept_id,
        "selected_entity_name": graph.nodes[concept_id].name,
        "match_type": "feature_binding",
        "score": 1.0,
        "ambiguous": False,
        "candidates": [],
    }


def _paths_for_match(
    case_id: str,
    obs_id: str,
    profile: VisualDiagnosticProfile,
    checks: list[dict[str, Any]],
    candidate_id: str,
    graph: KnowledgeGraph,
    edge_map: dict[str, KGEdge],
    score: float,
) -> list[dict[str, Any]]:
    cause_edges = [
        e
        for e in graph.edges
        if e.head == profile.anchor_id
        and e.tail == candidate_id
        and e.relation in CAUSE_RELATIONS
        and e.review_status != "rejected"
        and e.scenario in {"mvtec", "shared"}
    ]
    paths: dict[str, dict[str, Any]] = {}
    for cause_edge in cause_edges:
        for check in checks:
            if check["feature"] == "object":
                continue  # Scope constrains applicability; it is not an observed defect feature.
            concept_id = check["concept_id"]
            edge_id = check["source_edge_id"]
            edges = []
            nodes = [profile.anchor_id, candidate_id]
            if concept_id and concept_id != profile.anchor_id and edge_id:
                edge = edge_map[edge_id]
                if edge.head == concept_id and edge.tail == profile.anchor_id:
                    edges.append(edge.model_dump())
                elif edge.head == profile.anchor_id and edge.tail == concept_id:
                    edges.append(
                        {
                            **edge.model_dump(),
                            "head": concept_id,
                            "tail": profile.anchor_id,
                            "relation": "SUPPORTS_DEFECT",
                            "edge_id": f"view:{edge.edge_id}",
                            "origin_edge_id": edge.edge_id,
                            "origin_edge": edge.model_dump(),
                            "interpretation": "diagnostic reverse view; not physical causation",
                        }
                    )
                else:
                    continue
                nodes.insert(0, concept_id)
            edges.append(cause_edge.model_dump())
            path_id = (
                f"path:{case_id}:{obs_id}:{profile.profile_id}:{nodes[0]}:{cause_edge.edge_id}"
            )
            if path_id in paths:
                paths[path_id]["support_conditions"].append(check)
                continue
            paths[path_id] = {
                "path_id": path_id,
                "source_entity_id": nodes[0],
                "target_entity_id": candidate_id,
                "nodes": nodes,
                "node_names": [graph.nodes[n].name for n in nodes],
                "relations": [e["relation"] for e in edges],
                "length": len(edges),
                "score": score,
                "confidence": None,
                "path_strength": score,
                "support_obs_ids": [obs_id],
                "source_edge_ids": [e["edge_id"] for e in edges],
                "source_edges": edges,
                "supporting_evidence": [obs_id],
                "knowledge_evidence": [e["evidence"] for e in edges],
                "support_conditions": [check],
            }
    return list(paths.values())
