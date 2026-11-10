"""Isolated Neo4j working graphs with stable public entity and edge identities."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph
from kgtracevis.kg.import_neo4j import RELATION_PATTERN, resolve_neo4j_config
from kgtracevis.kg.neo4j_repository import Neo4jKGRepository


@dataclass
class WorkingGraphRepository:
    """A graph-scoped repository; writes never merge into legacy KG nodes."""

    repository: Neo4jKGRepository
    graph_id: str

    @classmethod
    def connect(cls, graph_id: str) -> WorkingGraphRepository:
        return cls(Neo4jKGRepository.connect(resolve_neo4j_config()), graph_id)

    def close(self) -> None:
        self.repository.close()

    def write_new(self, graph: KnowledgeGraph) -> None:
        """Create a complete isolated graph in one Neo4j managed transaction."""
        with self.repository.driver.session(database=self.repository.config.database) as session:
            session.execute_write(self._write_transaction, graph)

    def replace(self, graph: KnowledgeGraph) -> None:
        """Replace only this namespace atomically; a failed transaction leaves it unchanged."""

        def replace_transaction(tx):
            tx.run("MATCH (n:KGEntity {graph_id: $id}) DETACH DELETE n", id=self.graph_id).consume()
            self._write_transaction(tx, graph)

        with self.repository.driver.session(database=self.repository.config.database) as session:
            session.execute_write(replace_transaction)

    def _write_transaction(self, tx: Any, graph: KnowledgeGraph) -> None:
        existing = tx.run(
            "MATCH (n:KGEntity {graph_id: $graph_id}) RETURN count(n) AS count",
            graph_id=self.graph_id,
        ).single()
        if existing and existing["count"]:
            raise ValueError(f"working graph already exists: {self.graph_id}")
        rows = [
            {
                "id": self.storage_id(n.id),
                "logical_id": n.id,
                "graph_id": self.graph_id,
                "name": n.name,
                "entity_label": n.label,
                "scenario": n.scenario,
                "aliases": list(n.aliases),
                "description": n.description,
            }
            for n in graph.nodes.values()
        ]
        tx.run("UNWIND $rows AS row CREATE (n:KGEntity) SET n = row", rows=rows).consume()
        for edge in graph.edges:
            if not RELATION_PATTERN.fullmatch(edge.relation):
                raise ValueError(f"invalid Neo4j relation type: {edge.relation}")
            properties = {
                **edge.model_dump(),
                "graph_id": self.graph_id,
                "edge_id": self.storage_id(edge.edge_id),
                "logical_edge_id": edge.edge_id,
            }
            tx.run(
                f"MATCH (h:KGEntity {{id: $head}}), (t:KGEntity {{id: $tail}}) "
                f"CREATE (h)-[r:`{edge.relation}`]->(t) SET r = $properties",
                head=self.storage_id(edge.head),
                tail=self.storage_id(edge.tail),
                properties=properties,
            ).consume()

    def to_knowledge_graph(self, *, scenario: str | None = None) -> KnowledgeGraph:
        """Restore logical IDs and all executable edge metadata from the selected scope."""
        scenarios = ["shared", scenario] if scenario else ["shared", "mvtec", "tep", "wafer"]
        with self.repository.driver.session(database=self.repository.config.database) as session:
            nodes = [
                KGNode(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    label=str(row["label"]),
                    scenario=str(row["scenario"]),
                    aliases=tuple(row["aliases"] or []),
                    description=str(row["description"] or ""),
                )
                for row in session.run(
                    "MATCH (n:KGEntity {graph_id: $graph_id}) WHERE n.scenario IN $scenarios "
                    "RETURN n.logical_id AS id, n.name AS name, n.entity_label AS label, "
                    "n.scenario AS scenario, n.aliases AS aliases, n.description AS description",
                    {"graph_id": self.graph_id, "scenarios": scenarios},
                )
            ]
            edges = []
            allowed = {f.name for f in fields(KGEdge)}
            for row in session.run(
                "MATCH (h:KGEntity {graph_id: $graph_id})-[r]->"
                "(t:KGEntity {graph_id: $graph_id}) "
                "WHERE r.graph_id = $graph_id AND r.scenario IN $scenarios "
                "AND h.scenario IN $scenarios AND t.scenario IN $scenarios "
                "RETURN h.logical_id AS head, t.logical_id AS tail, "
                "type(r) AS relation, properties(r) AS properties",
                {"graph_id": self.graph_id, "scenarios": scenarios},
            ):
                payload = {k: v for k, v in row["properties"].items() if k in allowed}
                payload.update(head=row["head"], tail=row["tail"], relation=row["relation"])
                edges.append(KGEdge(**payload))
        if not nodes:
            raise ValueError(f"working graph has no readable nodes: {self.graph_id}")
        return KnowledgeGraph(nodes, edges)

    def storage_id(self, logical_id: str) -> str:
        """Length-delimited namespace preserves arbitrary logical IDs without collisions."""
        return f"working:{len(self.graph_id)}:{self.graph_id}:{logical_id}"
