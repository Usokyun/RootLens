"""Explicit small dependencies shared by unit tests; no runtime-store overrides."""

from pathlib import Path

import pytest

from kgtracevis.kg.graph import DEFAULT_EDGE_PATHS, DEFAULT_NODE_PATHS, KnowledgeGraph
from kgtracevis.workflows.root_cause_provider_selection import build_pipeline

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def seed_graph():
    """Load only checked-in CSV knowledge, never a running Neo4j database."""
    return KnowledgeGraph.from_paths(
        [BACKEND_ROOT / path for path in DEFAULT_NODE_PATHS],
        [BACKEND_ROOT / path for path in DEFAULT_EDGE_PATHS],
    )


@pytest.fixture
def seed_pipeline(seed_graph):
    """Exercise the real profile resolver and algorithms with an explicit graph."""
    return build_pipeline(graph=seed_graph)
