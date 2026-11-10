"""Persistent scoped graph editing and complete package interchange."""

from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage, record_package
from kgtracevis.kg.working_graph_package import (
    ExecutableProfiles,
    WorkingEdge,
    WorkingGraphPackage,
    WorkingNode,
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


def export_working_graph(graph_id: str) -> WorkingGraphPackage | UnifiedWorkingGraphPackage:
    record, graph = load_working_graph(graph_id)
    return record_package(record, graph)


def import_working_graph(
    package: WorkingGraphPackage | UnifiedWorkingGraphPackage,
    *,
    store=None,
    repository_factory=None,
) -> WorkingGraphRecord:
    """Import always creates a new isolated identity; existing graphs are never overwritten."""
    store = store or working_graph_store()
    graph_id = "graph_" + uuid.uuid4().hex
    knowledge = (
        package.knowledge.model_copy(update={"graph_id": graph_id})
        if isinstance(package, UnifiedWorkingGraphPackage)
        else None
    )
    record = WorkingGraphRecord(
        graph_id=graph_id,
        title=package.title,
        build_id=package.build_id,
        dataset=package.dataset,
        status="loading",
        node_count=len(package.nodes),
        edge_count=len(package.edges),
        profiles=package.profiles if isinstance(package, WorkingGraphPackage) else None,
        knowledge=knowledge,
    )
    store.create(record)
    repository = None
    try:
        # Resolve the default at use, so injected repositories and test clients
        # share the same actual runtime path.
        factory = repository_factory or WorkingGraphRepository.connect
        repository = factory(record.graph_id)
        repository.write_new(record_package(record).to_graph() if knowledge else package.to_graph())
        record = record.model_copy(update={"status": "ready"})
        store.update(record)
        return record
    except Exception as exc:
        store.update(record.model_copy(update={"status": "failed", "error": str(exc)}))
        raise
    finally:
        if repository is not None:
            repository.close()


def save_working_graph(
    graph_id: str, package: WorkingGraphPackage | UnifiedWorkingGraphPackage
) -> WorkingGraphRecord:
    if package.graph_id not in {None, graph_id}:
        raise ValueError("package belongs to another graph; import it as a new graph instead")
    store = working_graph_store()
    with graph_operation_lock(graph_id, store):
        record = store.get(graph_id)
        if isinstance(package, UnifiedWorkingGraphPackage):
            package = package.model_copy(
                update={"knowledge": package.knowledge.model_copy(update={"graph_id": graph_id})}
            )
        return _save_locked(record, package, store)


def mutate_working_graph(graph_id: str, request: WorkingGraphMutation) -> WorkingGraphRecord:
    store = working_graph_store()
    with graph_operation_lock(graph_id, store):
        record = store.get(graph_id)
        if record.knowledge is not None:
            return _mutate_unified(record, request, store)
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
    if (record.knowledge is not None) != isinstance(package, UnifiedWorkingGraphPackage):
        raise ValueError("cannot change a working graph's executable contract; import a new graph")
    repository = WorkingGraphRepository.connect(record.graph_id)
    try:
        return _replace_with_backup(repository, record, package, store)
    finally:
        repository.close()


def _replace_with_backup(repository, record, package, store):
    before = repository.to_knowledge_graph(scenario=record.dataset)
    old_package = record_package(record, before)
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_ROOT / f"backup_{uuid.uuid4().hex}.json"
    backup.write_text(old_package.model_dump_json(indent=2), encoding="utf-8")
    updated = record.model_copy(
        update={
            "status": "ready",
            "title": package.title,
            "profiles": package.profiles if isinstance(package, WorkingGraphPackage) else None,
            "knowledge": package.knowledge
            if isinstance(package, UnifiedWorkingGraphPackage)
            else None,
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


def _mutate_unified(record, request, store):
    """Simple entity edits and removal of whole rules; conditions use canonical JSON."""
    from kgtracevis.schema.unified_knowledge import KnowledgePackage

    if request.profiles is not None or request.rebuild_profiles or request.upsert_edges:
        raise ValueError(
            "v2 rules/bindings/conditions must be edited in the complete knowledge JSON"
        )
    data = record.knowledge.model_dump(mode="json")
    entities = {row["entity_id"]: row for row in data["entities"]}
    for node in request.upsert_nodes:
        if node.id not in entities:
            raise ValueError("use knowledge JSON to add or change a non-entity node")
        entities[node.id].update(label=node.name, aliases=node.aliases)
    # Projected edges have canonical Neo4j IDs. Removing either side of an
    # effect/expectation deletes that executable rule, never just its picture.
    graph = record_package(record).to_graph()
    edge_ids = {edge.edge_id: edge.external_edge_id for edge in graph.edges}
    removed_rules = set(request.delete_node_ids)
    removed_relations = set()
    rule_ids = {r["rule_id"] for r in [*data["effect_rules"], *data["expectation_rules"]]}
    relation_ids = {r["relation_id"] for r in data["relations"]}
    for identity in request.delete_edge_ids:
        if identity not in edge_ids:
            raise ValueError(f"unknown edge: {identity}")
        origin = edge_ids[identity]
        if origin in relation_ids:
            removed_relations.add(origin)
        elif origin.rsplit("::", 1)[0] in rule_ids:
            removed_rules.add(origin.rsplit("::", 1)[0])
        else:
            raise ValueError(
                "edit the canonical condition JSON to remove definition/binding/source dependencies"
            )
    if removed_rules - rule_ids:
        raise ValueError(
            "only whole effect/expectation nodes can be deleted here; edit JSON for other nodes"
        )
    data["entities"] = list(entities.values())
    for key in ("effect_rules", "expectation_rules"):
        data[key] = [row for row in data[key] if row["rule_id"] not in removed_rules]
    data["relations"] = [
        row for row in data["relations"] if row["relation_id"] not in removed_relations
    ]
    package = record_package(record).model_copy(
        update={
            "title": request.title or record.title,
            "knowledge": KnowledgePackage.model_validate(data),
        }
    )
    return _save_locked(record, package, store)
