"""Full mutable working knowledge interchange, reusing the existing registry."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kgtracevis.kg.unified_projection import runtime_projection
from kgtracevis.schema.unified_knowledge import KnowledgePackage


class UnifiedWorkingGraphPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["rootlens-working-graph.v2"] = "rootlens-working-graph.v2"
    graph_id: str | None = None
    title: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    build_id: str = "unified-import"
    knowledge: KnowledgePackage

    @model_validator(mode="after")
    def valid_projection(self):
        self.to_graph()
        return self

    def to_graph(self):
        return runtime_projection(self.knowledge, scenario=self.dataset)

    @property
    def nodes(self):
        return list(self.to_graph().nodes.values())

    @property
    def edges(self):
        return self.to_graph().edges


def record_package(record, graph=None):
    if record.knowledge is not None:
        return UnifiedWorkingGraphPackage(
            graph_id=record.graph_id,
            title=record.title,
            dataset=record.dataset,
            build_id=record.build_id,
            knowledge=record.knowledge,
        )
    from kgtracevis.kg.working_graph_package import graph_package

    return graph_package(
        graph,
        graph_id=record.graph_id,
        title=record.title,
        dataset=record.dataset,
        build_id=record.build_id,
        profiles=record.profiles,
    )
