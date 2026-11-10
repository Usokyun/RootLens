"""Persistent scoped graph editing and complete package interchange."""

from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kgtracevis.kg.working_graph_package import (
    ExecutableProfiles,
    WorkingEdge,
    WorkingGraphPackage,
    WorkingNode,
    graph_package,
    refresh_visual_profiles,
)
from kgtracevis.kg.working_graph_repository import WorkingGraphRepository
from kgtracevis.schema.visual_reasoning import VisualProfileBundle
from kgtracevis.service.working_graphs import (
    WorkingGraphRecord,
    WorkingGraphStorageError,
    graph_operation_lock,
    load_working_graph,
    working_graph_store,
)

BACKUP_ROOT = Path("runs/working_graph_backups")


class WorkingGraphMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    upsert_nodes: list[WorkingNode] = Field(default_factory=list)
    upsert_edges: list[WorkingEdge] = Field(default_factory=list)
    delete_node_ids: list[str] = Field(default_factory=list)
    delete_edge_ids: list[str] = Field(default_factory=list)
    cascade: bool = False
    profiles: ExecutableProfiles | None = None
    rebuild_profiles: bool = False


def export_working_graph(graph_id: str) -> WorkingGraphPackage:
    record, graph = load_working_graph(graph_id)
    return graph_package(
        graph,
        graph_id=graph_id,
        title=record.title,
        build_id=record.build_id,
        profiles=record.profiles,
        dataset=record.dataset,
    )


def import_working_graph(package: WorkingGraphPackage) -> WorkingGraphRecord:
    """Import always creates a new isolated identity; existing graphs are never overwritten."""
    store = working_graph_store()
    record = WorkingGraphRecord(
        graph_id="graph_" + uuid.uuid4().hex,
        title=package.title,
        build_id=package.build_id,
        dataset=package.dataset,
        status="loading",
        node_count=len(package.nodes),
        edge_count=len(package.edges),
        profiles=package.profiles,
    )
    store.create(record)
    repository = WorkingGraphRepository.connect(record.graph_id)
    try:
        repository.write_new(package.to_graph())
        record = record.model_copy(update={"status": "ready"})
        store.update(record)
        return record
    except Exception as exc:
        store.update(record.model_copy(update={"status": "failed", "error": str(exc)}))
        raise
    finally:
        repository.close()


def save_working_graph(graph_id: str, package: WorkingGraphPackage) -> WorkingGraphRecord:
    if package.graph_id not in {None, graph_id}:
        raise ValueError("package belongs to another graph; import it as a new graph instead")
    store = working_graph_store()
    with graph_operation_lock(graph_id, store):
        record = store.get(graph_id)
        return _save_locked(record, package, store)


def mutate_working_graph(graph_id: str, request: WorkingGraphMutation) -> WorkingGraphRecord:
    store = working_graph_store()
    with graph_operation_lock(graph_id, store):
        record = store.get(graph_id)
        if request.rebuild_profiles and record.dataset != "mvtec":
            raise ValueError(
                "数值/空间画像包含阈值和通道绑定，不能仅凭关系重建；请编辑 profiles 或重新构图。"
            )
        repository = WorkingGraphRepository.connect(graph_id)
        try:
            before = repository.to_knowledge_graph(scenario=record.dataset)
        finally:
            repository.close()
        nodes = dict(before.nodes)
        edges = {edge.edge_id: edge for edge in before.edges}
        for node_id in request.delete_node_ids:
            if node_id not in nodes:
                raise ValueError(f"unknown node: {node_id}")
            incident = [e.edge_id for e in edges.values() if node_id in {e.head, e.tail}]
            if incident and not request.cascade:
                raise ValueError(f"node {node_id} has {len(incident)} dependent edges; use cascade")
            del nodes[node_id]
            edges = {key: edge for key, edge in edges.items() if key not in incident}
        for edge_id in request.delete_edge_ids:
            if edge_id not in edges:
                raise ValueError(f"unknown edge: {edge_id}")
            del edges[edge_id]
        for node in request.upsert_nodes:
            nodes[node.id] = node.to_node()
        for edge in request.upsert_edges:
            edges[edge.edge_id] = edge
        # Reuse package validation for complete edge metadata and logical IDs.
        provisional = WorkingGraphPackage(
            graph_id=graph_id,
            title=request.title or record.title,
            build_id=record.build_id,
            dataset=record.dataset,
            nodes=[
                WorkingNode(
                    id=n.id,
                    name=n.name,
                    label=n.label,
                    scenario=n.scenario,
                    aliases=list(n.aliases),
                    description=n.description,
                )
                for n in nodes.values()
            ],
            edges=list(edges.values()),
        )
        after = provisional.to_graph()
        profiles = request.profiles
        if profiles is None and not request.rebuild_profiles:
            profiles = (
                refresh_visual_profiles(before, after, record.profiles)
                if isinstance(record.profiles, VisualProfileBundle)
                else record.profiles
            )
        package = WorkingGraphPackage(
            **{**provisional.model_dump(), "profiles": profiles},
        )
        return _save_locked(record, package, store)


def _save_locked(record, package, store):
    if record.status != "ready":
        raise ValueError(f"working graph is not ready: {record.status}")
    if package.dataset != record.dataset:
        raise ValueError("cannot change a working graph's dataset; import a new graph")
    repository = WorkingGraphRepository.connect(record.graph_id)
    try:
        return _replace_with_backup(repository, record, package, store)
    finally:
        repository.close()


def _replace_with_backup(repository, record, package, store):
    before = repository.to_knowledge_graph(scenario=record.dataset)
    old_package = graph_package(
        before,
        graph_id=record.graph_id,
        title=record.title,
        build_id=record.build_id,
        profiles=record.profiles,
        dataset=record.dataset,
    )
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_ROOT / f"backup_{uuid.uuid4().hex}.json"
    backup.write_text(old_package.model_dump_json(indent=2), encoding="utf-8")
    updated = record.model_copy(
        update={
            "status": "ready",
            "title": package.title,
            "profiles": package.profiles,
            "node_count": len(package.nodes),
            "edge_count": len(package.edges),
            "last_backup_path": str(backup),
            "error": "",
        }
    )
    try:
        store.update(record.model_copy(update={"status": "loading"}))
        repository.replace(package.to_graph())
        store.update(updated)
        return updated
    except Exception as exc:
        try:
            repository.replace(before)
            store.update(record)
        except Exception as recovery_error:
            raise WorkingGraphStorageError(
                f"工作图保存失败，恢复未完成；请从 {backup} 恢复：{recovery_error}"
            ) from exc
        raise
