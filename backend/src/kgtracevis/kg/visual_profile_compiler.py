"""Compile existing visual graph relations and LLM profile hints into executable predicates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph, normalize_text
from kgtracevis.schema.visual_reasoning import (
    VisualCondition,
    VisualDiagnosticProfile,
    VisualProfileBundle,
)

CAUSE_RELATIONS = {
    "HAS_PLAUSIBLE_CAUSE",
    "POSSIBLY_CAUSES",
    "SUGGESTS_MECHANISM",
    "SUGGESTS_PLAUSIBLE_MECHANISM",
}
FEATURE_TERMS = {
    "region.morphology": ("linear", "spot", "scattered", "dense"),
    "region.location": ("surface", "edge"),
}


def edge_reference_map(graph: KnowledgeGraph) -> dict[str, KGEdge]:
    """Resolve both runtime tuple IDs and retained compiler IDs, rejecting collisions."""
    result: dict[str, KGEdge] = {}
    for edge in graph.edges:
        for reference in (edge.edge_id, edge.external_edge_id):
            if not reference:
                continue
            if reference in result and result[reference].edge_id != edge.edge_id:
                raise ValueError(f"ambiguous source edge ID: {reference}")
            result[reference] = edge
    return result


def compile_visual_profiles(
    graph: KnowledgeGraph,
    domain_profiles: Mapping[str, Any] | None = None,
) -> VisualProfileBundle:
    """Generate only conditions and candidate links supported by this graph."""
    rows = (
        (domain_profiles or {})
        .get("profiles", {})
        .get("mvtec", {})
        .get("object_defect_profiles", [])
    )
    hints = {
        (str(row.get("object_id")), str(row.get("defect_id"))): row
        for row in rows
        if isinstance(row, Mapping)
    }
    edge_map = edge_reference_map(graph)
    output = VisualProfileBundle()
    for object_edge in graph.edges:
        if object_edge.relation not in {"HAS_ANOMALY", "HAS_DEFECT"}:
            continue
        obj, anchor = graph.nodes[object_edge.head], graph.nodes[object_edge.tail]
        if obj.label != "Object" or obj.scenario not in {"mvtec", "shared"}:
            continue
        if (
            anchor.scenario not in {"mvtec", "shared"}
            or object_edge.scenario not in {"mvtec", "shared"}
            or object_edge.review_status == "rejected"
        ):
            continue
        outgoing = [
            e
            for e in graph.edges
            if e.head == anchor.id
            and e.scenario in {"mvtec", "shared"}
            and e.review_status != "rejected"
        ]
        causes = [e for e in outgoing if e.relation in CAUSE_RELATIONS]
        if not causes:
            continue
        conditions = [
            VisualCondition(
                feature="object",
                op="in",
                value=list(obj.searchable_terms),
                concept_id=obj.id,
                source_edge_id=object_edge.edge_id,
                group="object",
            )
        ]
        for relation, feature in (
            ("HAS_MORPHOLOGY", "region.morphology"),
            ("OCCURS_ON", "region.location"),
        ):
            edges = [e for e in outgoing if e.relation == relation]
            # Alternatives in the same family form one set condition, not an impossible AND.
            values = []
            for edge in edges:
                values.extend(_feature_terms(graph.nodes[edge.tail], feature))
            if values:
                conditions.append(
                    VisualCondition.model_validate(
                        {
                            "feature": feature,
                            "op": "in",
                            "value": sorted(set(values)),
                            "concept_id": edges[0].tail if len(edges) == 1 else None,
                            "source_edge_id": edges[0].edge_id if len(edges) == 1 else None,
                            "group": "geometry",
                        }
                    )
                )
        hint = hints.get((obj.id, anchor.id), {})
        try:
            extra = [VisualCondition.model_validate(c) for c in hint.get("evidence_conditions", [])]
            conflicts = [
                VisualCondition.model_validate(c) for c in hint.get("conflict_conditions", [])
            ]
            for condition in [*extra, *conflicts]:
                if condition.feature == "object":
                    values = (
                        condition.value if isinstance(condition.value, list) else [condition.value]
                    )
                    valid_names = {normalize_text(t) for t in obj.searchable_terms}
                    if not all(normalize_text(str(v)) in valid_names for v in values):
                        raise ValueError("object condition does not match its graph scope")
                    condition.op = "in"
                    condition.value = list(obj.searchable_terms)
                if condition.concept_id and condition.concept_id not in graph.nodes:
                    raise ValueError(f"unknown condition concept: {condition.concept_id}")
                if condition.source_edge_id:
                    if condition.source_edge_id not in edge_map:
                        raise ValueError(f"unknown condition edge: {condition.source_edge_id}")
                    condition.source_edge_id = edge_map[condition.source_edge_id].edge_id
            conditions.extend(extra)
            for conflict in conflicts:
                for support in conditions:
                    if support.feature != conflict.feature:
                        continue
                    if support.op in {"eq", "in"} and conflict.op in {"eq", "in"}:
                        positive = (
                            support.value if isinstance(support.value, list) else [support.value]
                        )
                        negative = (
                            conflict.value if isinstance(conflict.value, list) else [conflict.value]
                        )
                        if {normalize_text(str(v)) for v in positive} & {
                            normalize_text(str(v)) for v in negative
                        }:
                            raise ValueError(f"conflict overlaps support for {support.feature}")
            conditions.append(
                VisualCondition(
                    feature="region.semantic_candidates",
                    op="intersects",
                    value=list(anchor.searchable_terms),
                    concept_id=anchor.id,
                    required=len(conditions) == 1,
                    group="semantics",
                )
            )
            output.profiles.append(
                VisualDiagnosticProfile(
                    profile_id=f"mvtec:{obj.id}:{anchor.id}",
                    object_id=obj.id,
                    anchor_id=anchor.id,
                    conditions=conditions,
                    conflicts=conflicts,
                    candidate_ids=sorted({e.tail for e in causes}),
                    source_edge_ids=sorted({object_edge.edge_id, *(e.edge_id for e in outgoing)}),
                )
            )
        except (ValueError, ValidationError) as exc:
            output.issues.append(f"{obj.id}/{anchor.id}: {exc}")
    return output


def validate_visual_profiles(bundle: VisualProfileBundle, graph: KnowledgeGraph) -> None:
    """Fail explicitly if persisted profiles no longer match the current working graph."""
    edges = edge_reference_map(graph)
    seen = set()
    for profile in bundle.profiles:
        if profile.profile_id in seen:
            raise ValueError(f"duplicate visual profile: {profile.profile_id}")
        seen.add(profile.profile_id)
        for node_id in [profile.object_id, profile.anchor_id, *profile.candidate_ids]:
            if node_id not in graph.nodes or graph.nodes[node_id].scenario not in {
                "mvtec",
                "shared",
            }:
                raise ValueError(f"visual profile references absent/out-of-scope node: {node_id}")
        for edge_id in profile.source_edge_ids:
            if edge_id not in edges:
                raise ValueError(f"visual profile references absent edge: {edge_id}")
            if edges[edge_id].review_status == "rejected" or edges[edge_id].scenario not in {
                "mvtec",
                "shared",
            }:
                raise ValueError(f"visual profile references unusable edge: {edge_id}")
        if not any(
            edge.head == profile.object_id
            and edge.tail == profile.anchor_id
            and edge.relation in {"HAS_ANOMALY", "HAS_DEFECT"}
            and edge.review_status != "rejected"
            and edge.scenario in {"mvtec", "shared"}
            for edge in graph.edges
        ):
            raise ValueError(
                f"no usable object/defect edge: {profile.object_id} → {profile.anchor_id}"
            )
        for condition in [*profile.conditions, *profile.conflicts]:
            if condition.concept_id and (
                condition.concept_id not in graph.nodes
                or graph.nodes[condition.concept_id].scenario not in {"mvtec", "shared"}
            ):
                raise ValueError(
                    f"visual condition references absent concept: {condition.concept_id}"
                )
            if condition.source_edge_id and condition.source_edge_id not in edges:
                raise ValueError(
                    f"visual condition references absent edge: {condition.source_edge_id}"
                )
            if condition.source_edge_id and (
                edges[condition.source_edge_id].review_status == "rejected"
                or edges[condition.source_edge_id].scenario not in {"mvtec", "shared"}
            ):
                raise ValueError(
                    f"visual condition references unusable edge: {condition.source_edge_id}"
                )
        for candidate_id in profile.candidate_ids:
            if not any(
                e.head == profile.anchor_id
                and e.tail == candidate_id
                and e.relation in CAUSE_RELATIONS
                and e.review_status != "rejected"
                and e.scenario in {"mvtec", "shared"}
                for e in graph.edges
            ):
                raise ValueError(f"no usable diagnostic edge: {profile.anchor_id} → {candidate_id}")


def _feature_terms(node: KGNode, feature: str) -> list[str]:
    terms = {normalize_text(t) for t in node.searchable_terms}
    allowed = FEATURE_TERMS[feature]
    return [
        term
        for term in allowed
        if any(
            value in {term, f"{term}morphology", f"{term}location", f"{term}pattern"}
            for value in terms
        )
    ]


def observation_concept_binding(
    graph: KnowledgeGraph,
    anchor_id: str,
    feature: str,
    actual: Any,
) -> KGEdge | None:
    """Resolve alternatives using the measured value, not an LLM-supplied representative ID."""
    relation = {"region.morphology": "HAS_MORPHOLOGY", "region.location": "OCCURS_ON"}.get(feature)
    if relation is None:
        return None
    matches = [
        edge
        for edge in graph.edges
        if edge.head == anchor_id
        and edge.relation == relation
        and edge.review_status != "rejected"
        and edge.scenario in {"mvtec", "shared"}
        and normalize_text(str(actual)) in _feature_terms(graph.nodes[edge.tail], feature)
    ]
    return sorted(matches, key=lambda edge: edge.edge_id)[0] if matches else None
