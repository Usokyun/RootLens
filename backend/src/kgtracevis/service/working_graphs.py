"""Activate compiler knowledge in Neo4j and persist its executable profile in Postgres."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kgtracevis.kg.graph import KnowledgeGraph
from kgtracevis.kg.working_graph_package import (
    ExecutableProfiles,
    compile_profiles,
    validate_profiles,
)
from kgtracevis.kg.working_graph_repository import WorkingGraphRepository
from kgtracevis.schema.unified_knowledge import KnowledgePackage
from kgtracevis.schema.visual_reasoning import VisualProfileBundle
from kgtracevis.service.kg_construction import get_kg_construction_build_artifact_path
from kgtracevis.service.postgres import PostgresConfig, resolve_postgres_config


class WorkingGraphRecord(BaseModel):
    """One mutable working graph identity, not a reviewed release."""

    model_config = ConfigDict(extra="forbid")
    graph_id: str
    title: str
    dataset: str = "mvtec"
    build_id: str
    status: Literal["loading", "ready", "failed"]
    node_count: int
    edge_count: int
    profiles: ExecutableProfiles | None
    knowledge: KnowledgePackage | None = None
    error: str = ""
    last_backup_path: str | None = None

    @model_validator(mode="after")
    def one_executable_contract(self):
        if (self.profiles is None) == (self.knowledge is None):
            raise ValueError("working graph requires exactly one executable contract")
        return self


class ActivateWorkingGraphRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Working graph", min_length=1)
    dataset: Literal["mvtec", "wafer", "tep"] = "mvtec"
    compact_runtime: bool = False


class WorkingGraphStore(Protocol):
    def create(self, record: WorkingGraphRecord) -> None: ...
    def update(self, record: WorkingGraphRecord) -> None: ...
    def get(self, graph_id: str) -> WorkingGraphRecord: ...
    def list_ready(self) -> list[WorkingGraphRecord]: ...


class WorkingGraphStorageError(RuntimeError):
    """Only the new working-graph capability is unavailable."""


@dataclass
class PostgresWorkingGraphStore:
    config: PostgresConfig
    connection_factory: Callable | None = None

    @contextmanager
    def _connection(self) -> Any:
        if self.connection_factory:
            with self.connection_factory() as connection:
                yield connection
            return
        if not self.config.dsn:
            raise WorkingGraphStorageError("工作图需要配置 Postgres。")
        import psycopg
        from psycopg.rows import dict_row

        try:
            with psycopg.connect(self.config.dsn, row_factory=dict_row) as connection:
                yield connection
        except psycopg.Error as exc:
            raise WorkingGraphStorageError(
                "工作图存储不可用，请检查 Postgres 并执行 migrate_working_graphs.py --apply。"
            ) from exc

    def create(self, record: WorkingGraphRecord) -> None:
        from psycopg.types.json import Jsonb

        with self._connection() as connection:
            connection.execute(
                "INSERT INTO working_graphs (graph_id, payload) VALUES (%s, %s)",
                (record.graph_id, Jsonb(record.model_dump(mode="json"))),
            )

    def update(self, record: WorkingGraphRecord) -> None:
        from psycopg.types.json import Jsonb

        with self._connection() as connection:
            connection.execute(
                "UPDATE working_graphs SET payload = %s, updated_at = now() WHERE graph_id = %s",
                (Jsonb(record.model_dump(mode="json")), record.graph_id),
            )

    def get(self, graph_id: str) -> WorkingGraphRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM working_graphs WHERE graph_id = %s",
                (graph_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown working graph: {graph_id}")
        return WorkingGraphRecord.model_validate(row["payload"])

    def list_ready(self) -> list[WorkingGraphRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM working_graphs WHERE payload->>'status' = 'ready' "
                "ORDER BY created_at DESC",
            ).fetchall()
        return [WorkingGraphRecord.model_validate(row["payload"]) for row in rows]


_test_store: WorkingGraphStore | None = None


def configure_working_graph_store_for_testing(store: WorkingGraphStore | None) -> None:
    global _test_store
    _test_store = store


def working_graph_store() -> WorkingGraphStore:
    return _test_store or PostgresWorkingGraphStore(resolve_postgres_config())


_GRAPH_LOCKS: dict[str, threading.RLock] = {}


@contextmanager
def graph_operation_lock(graph_id: str, store: WorkingGraphStore):
    """Serialize graph/profile snapshots and edits, including across API processes."""
    if isinstance(store, PostgresWorkingGraphStore):
        with store._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (graph_id,))
            yield
    else:
        with _GRAPH_LOCKS.setdefault(graph_id, threading.RLock()):
            yield


def activate_compiler_build(
    build_id: str,
    request: ActivateWorkingGraphRequest,
    *,
    store: WorkingGraphStore | None = None,
    repository_factory: Callable[[str], Any] = WorkingGraphRepository.connect,
) -> WorkingGraphRecord:
    """Validate first; expose a graph as ready only after its isolated write succeeds."""
    graph = KnowledgeGraph.from_csv(
        get_kg_construction_build_artifact_path(build_id, "nodes"),
        get_kg_construction_build_artifact_path(build_id, "edges"),
    )
    graph = KnowledgeGraph(
        [node for node in graph.nodes.values() if node.scenario in {request.dataset, "shared"}],
        [
            edge
            for edge in graph.edges
            if edge.scenario in {request.dataset, "shared"}
            and graph.nodes[edge.head].scenario in {request.dataset, "shared"}
            and graph.nodes[edge.tail].scenario in {request.dataset, "shared"}
        ],
    )
    domain = json.loads(
        get_kg_construction_build_artifact_path(
            build_id,
            "domain_profiles",
        ).read_text(encoding="utf-8")
    )
    profiles = (
        VisualProfileBundle.model_validate(domain["visual_runtime"])
        if request.dataset == "mvtec" and "visual_runtime" in domain
        else compile_profiles(graph, request.dataset, domain)
    )
    validate_profiles(profiles, graph, request.dataset)
    if not profiles.profiles:
        raise ValueError(f"build has no executable {request.dataset} diagnostic profiles")
    if request.compact_runtime:
        from kgtracevis.kg.working_graph_package import executable_subgraph

        graph = executable_subgraph(graph, profiles)
    record = WorkingGraphRecord(
        graph_id=f"graph_{uuid.uuid4().hex}",
        title=request.title,
        dataset=request.dataset,
        build_id=build_id,
        status="loading",
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        profiles=profiles,
    )
    active_store = store or working_graph_store()
    active_store.create(record)
    repository = None
    try:
        repository = repository_factory(record.graph_id)
        repository.write_new(graph)
        record = record.model_copy(update={"status": "ready"})
        active_store.update(record)
    except Exception as exc:
        active_store.update(record.model_copy(update={"status": "failed", "error": str(exc)}))
        raise
    finally:
        if repository is not None:
            repository.close()
    return record


def load_working_graph(graph_id: str) -> tuple[WorkingGraphRecord, KnowledgeGraph]:
    """Take one consistent graph/profile snapshot for a new analysis run."""
    store = working_graph_store()
    with graph_operation_lock(graph_id, store):
        record = store.get(graph_id)
        if record.status != "ready":
            raise ValueError(f"working graph is not ready: {record.status}")
        repository = WorkingGraphRepository.connect(graph_id)
        try:
            graph = repository.to_knowledge_graph(scenario=record.dataset)
        finally:
            repository.close()
        if record.knowledge is not None:
            from kgtracevis.kg.unified_projection import validate_runtime_projection

            validate_runtime_projection(record.knowledge, graph, scenario=record.dataset)
        else:
            validate_profiles(record.profiles, graph, record.dataset)
        return record, graph
