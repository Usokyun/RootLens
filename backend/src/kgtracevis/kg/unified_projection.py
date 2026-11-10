"""The existing studio/Neo4j representation is a projection, never a second IR."""

from __future__ import annotations

import json

from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph
from kgtracevis.kg.unified_compiler import KnowledgeProgram
from kgtracevis.schema.unified_knowledge import KnowledgePackage


def runtime_projection(package: KnowledgePackage, *, scenario: str) -> KnowledgeGraph:
    program = KnowledgeProgram(package)
    entities = program.entities
    nodes = [
        KGNode(
            id=row["node_id"],
            name=row.get("label") or row["node_id"],
            label=row["kind"],
            scenario=scenario,
            aliases=tuple(entities[row["node_id"]].aliases) if row["node_id"] in entities else (),
            description=json.dumps(row, ensure_ascii=False, sort_keys=True),
        )
        for row in program.projection["nodes"]
    ]
    edges = [
        KGEdge(
            head=row["head"],
            relation=row["relation"],
            tail=row["tail"],
            scenario=scenario,
            source="rootlens-knowledge-package.v2",
            evidence=json.dumps(row, ensure_ascii=False),
            confidence=0.0,
            weight=1.0,
            review_status="auto",
            feedback_count=0,
            accepted_count=0,
            rejected_count=0,
            external_edge_id=row["edge_id"],
            confidence_policy="not_a_probability",
        )
        for row in program.projection["edges"]
    ]
    if len({edge.edge_id for edge in edges}) != len(edges):
        raise ValueError("projection has parallel logical edges that the runtime cannot preserve")
    return KnowledgeGraph(nodes, edges)


def validate_runtime_projection(package, graph, *, scenario):
    expected = runtime_projection(package, scenario=scenario)
    if expected.nodes != graph.nodes or {e.edge_id: e.external_edge_id for e in expected.edges} != {
        e.edge_id: e.external_edge_id for e in graph.edges
    }:
        raise ValueError(
            "working graph projection diverged from canonical knowledge; save the package to repair"
        )
