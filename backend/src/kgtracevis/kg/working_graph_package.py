"""Complete, validated interchange for a working graph and its executable knowledge."""

from __future__ import annotations

import math
from dataclasses import fields
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph
from kgtracevis.kg.import_neo4j import RELATION_PATTERN
from kgtracevis.kg.visual_profile_compiler import compile_visual_profiles, validate_visual_profiles
from kgtracevis.schema.measured_reasoning import MeasuredProfileBundle, validate_measured_profiles
from kgtracevis.schema.visual_reasoning import VisualProfileBundle

ExecutableProfiles = VisualProfileBundle | MeasuredProfileBundle


def compile_profiles(graph, dataset, domain=None):
    if dataset == "mvtec":
        return compile_visual_profiles(graph, domain)
    payload = (domain or {}).get("measured_runtime", {}).get(dataset)
    if payload:
        result = MeasuredProfileBundle.model_validate(payload)
    else:
        result = MeasuredProfileBundle(
            dataset=dataset,
            issues=[
                "No executable measured profiles; supply graph-bound predicates before analysis."
            ],
        )
    validate_measured_profiles(result, graph)
    return result


def validate_profiles(profiles, graph, dataset):
    if dataset == "mvtec" and isinstance(profiles, VisualProfileBundle):
        validate_visual_profiles(profiles, graph)
    elif isinstance(profiles, MeasuredProfileBundle) and profiles.dataset == dataset:
        validate_measured_profiles(profiles, graph)
    else:
        raise ValueError("profile schema and working graph dataset do not match")


class WorkingNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    scenario: Literal["mvtec", "wafer", "tep", "shared"]
    aliases: list[str] = Field(default_factory=list)
    description: str = ""

    def to_node(self) -> KGNode:
        return KGNode(**{**self.model_dump(), "aliases": tuple(self.aliases)})


def _edge_input(value):
    if not isinstance(value, dict):
        return value
    unknown = set(value) - {f.name for f in fields(KGEdge)} - {"edge_id"}
    if unknown:
        raise ValueError(f"unregistered edge fields: {sorted(unknown)}")
    value = dict(value)
    edge_id = value.pop("edge_id", None)
    if edge_id is not None:
        expected = "|".join(str(value[k]) for k in ("head", "relation", "tail", "scenario"))
        if edge_id != expected:
            raise ValueError("edge_id does not match its logical endpoints/relation/scenario")
    return value


WorkingEdge = Annotated[KGEdge, BeforeValidator(_edge_input)]


class WorkingGraphPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["rootlens-working-graph.v1"] = "rootlens-working-graph.v1"
    graph_id: str | None = None
    title: str = Field(min_length=1)
    dataset: Literal["mvtec", "wafer", "tep"] = "mvtec"
    build_id: str = "import"
    nodes: list[WorkingNode] = Field(min_length=1)
    edges: list[WorkingEdge]
    profiles: ExecutableProfiles | None = None

    @model_validator(mode="after")
    def validate_graph(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("duplicate logical node IDs")
        if len({edge.edge_id for edge in self.edges}) != len(self.edges):
            raise ValueError("duplicate logical edge IDs")
        if any(node.scenario not in {self.dataset, "shared"} for node in self.nodes):
            raise ValueError("node belongs to another scenario")
        for edge in self.edges:
            if edge.head not in ids or edge.tail not in ids:
                raise ValueError(f"dangling edge endpoint: {edge.edge_id}")
            if edge.scenario not in {self.dataset, "shared"}:
                raise ValueError("edge belongs to another scenario")
            if not RELATION_PATTERN.fullmatch(edge.relation):
                raise ValueError("invalid relation type")
            if not 0 <= edge.confidence <= 1:
                raise ValueError("edge confidence must lie in [0, 1]")
            for field in fields(KGEdge):
                value = getattr(edge, field.name)
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"non-finite edge value: {field.name}")
        graph = self.to_graph()
        if self.profiles is None:
            self.profiles = compile_profiles(graph, self.dataset)
        validate_profiles(self.profiles, graph, self.dataset)
        return self

    def to_graph(self) -> KnowledgeGraph:
        return KnowledgeGraph([node.to_node() for node in self.nodes], self.edges)


def graph_package(
    graph: KnowledgeGraph,
    *,
    graph_id: str,
    title: str,
    build_id: str,
    profiles: ExecutableProfiles,
    dataset: str = "mvtec",
) -> WorkingGraphPackage:
    from dataclasses import asdict

    return WorkingGraphPackage(
        graph_id=graph_id,
        title=title,
        build_id=build_id,
        dataset=dataset,
        nodes=[
            WorkingNode.model_validate(asdict(node))
            for node in sorted(graph.nodes.values(), key=lambda node: node.id)
        ],
        edges=sorted(graph.edges, key=lambda edge: edge.edge_id),
        profiles=profiles,
    )


def executable_subgraph(graph: KnowledgeGraph, profiles: ExecutableProfiles) -> KnowledgeGraph:
    """Reusable runtime view: profile dependencies, not case-specific answers or schema prose.

    The full LLM extraction remains in compiler artifacts. Runtime editing/export
    operates on this explicit domain view; no observation values select its nodes.
    """
    from kgtracevis.kg.visual_profile_compiler import edge_reference_map

    edge_map = edge_reference_map(graph)
    keep = set()
    for profile in profiles.profiles:
        keep.update([profile.anchor_id, *profile.candidate_ids])
        if hasattr(profile, "object_id"):
            keep.add(profile.object_id)
        refs = set(getattr(profile, "source_edge_ids", []))
        for condition in [*profile.conditions, *profile.conflicts]:
            if condition.concept_id:
                keep.add(condition.concept_id)
            if condition.source_edge_id:
                refs.add(condition.source_edge_id)
        for ref in refs:
            edge = edge_map[ref]
            keep.update([edge.head, edge.tail])
    # Preserve physical paths from every declared candidate, including variable
    # contributors not used as threshold predicates, up to the reasoner's horizon.
    frontier = {cid for profile in profiles.profiles for cid in profile.candidate_ids}
    for _ in range(4):
        following = set()
        for edge in graph.edges:
            if not edge.propagation_enabled or edge.review_status == "rejected":
                continue
            pairs = (
                [(edge.head, edge.tail)]
                if edge.propagation_direction == "forward"
                else (
                    [(edge.tail, edge.head)]
                    if edge.propagation_direction == "reverse"
                    else [(edge.head, edge.tail), (edge.tail, edge.head)]
                )
            )
            following.update(t for h, t in pairs if h in frontier)
        frontier = following - keep
        keep.update(following)
    if not keep:
        raise ValueError("no executable knowledge to project")
    return KnowledgeGraph(
        [node for node in graph.nodes.values() if node.id in keep],
        [edge for edge in graph.edges if edge.head in keep and edge.tail in keep],
    )


def refresh_visual_profiles(
    previous_graph: KnowledgeGraph,
    graph: KnowledgeGraph,
    previous: VisualProfileBundle,
) -> VisualProfileBundle:
    """Refresh graph-derived bindings while retaining custom thresholds and constraints."""
    before = {
        (p.object_id, p.anchor_id): p for p in compile_visual_profiles(previous_graph).profiles
    }
    old = {(p.object_id, p.anchor_id): p for p in previous.profiles}
    result = compile_visual_profiles(graph)

    def signature(condition):
        value = condition.value
        if isinstance(value, list):
            value = tuple(sorted(set(value)))
        elif isinstance(value, str) and condition.op == "eq":
            value = (value,)
        op = "in" if condition.op == "eq" and isinstance(condition.value, str) else condition.op
        return condition.feature, op, value, condition.required

    for profile in result.profiles:
        key = profile.object_id, profile.anchor_id
        if key not in old:
            continue
        original = old[key]
        derived = {signature(c) for c in before[key].conditions} if key in before else set()
        current = {signature(c) for c in profile.conditions}
        for condition in original.conditions:
            if signature(condition) not in derived and signature(condition) not in current:
                profile.conditions.append(condition)
                current.add(signature(condition))
        profile.profile_id = original.profile_id
        profile.conflicts = original.conflicts
        profile.source_edge_ids = sorted(
            set(profile.source_edge_ids)
            | {
                c.source_edge_id
                for c in [*profile.conditions, *profile.conflicts]
                if c.source_edge_id
            }
        )
    validate_visual_profiles(result, graph)
    return result
