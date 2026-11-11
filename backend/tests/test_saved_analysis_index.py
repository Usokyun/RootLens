"""The native analysis list summarizes saved outcomes without copying the trace."""

from contextlib import nullcontext
from unittest.mock import Mock

from fastapi.testclient import TestClient

from kgtracevis.service import two_loop_api
from kgtracevis.service.api import create_app
from kgtracevis.service.postgres import PostgresConfig
from kgtracevis.service.two_loop_store import TwoLoopStore


def test_current_loop_routes_replace_retired_creation_without_losing_history():
    paths = create_app().openapi()["paths"]
    assert not any(
        path.startswith(
            (
                "/api/kg/construction/",
                "/api/runs",
                "/api/cases",
                "/api/kg/runtime/",
                "/api/reasoning/",
            )
        )
        for path in paths
    )
    assert (
        not {
            "/api/feedback",
            "/api/analyze",
            "/api/what-if",
            "/api/dashboard/bootstrap",
            "/api/kg/working-graphs/{graph_id}/candidate-conditions",
            "/api/kg/working-graphs/{graph_id}/candidate-conditions/{condition_id}",
            "/api/model-assets/download",
            "/api/kg/drafts",
            "/api/kg/source-draft",
            "/api/kg/materials/{material_id}/extract",
            "/api/kg/materials/build-sources",
            "/api/kg/materials/build",
            "/api/kg/materials/register",
        }
        & paths.keys()
    )
    assert all(
        "post" in paths[path]
        for path in (
            "/api/tasks/material-parse",
            "/api/tasks/material-build",
            "/api/tasks/inference",
            "/api/tasks/inference/demo",
            "/api/demo-library/{demo_id}/working-graph",
            "/api/kg/working-graphs/import",
            "/api/kg/working-graphs/{graph_id}/enable",
        )
    )
    assert all(
        "get" in paths[path]
        for path in (
            "/api/analyses",
            "/api/analyses/{run_id}",
            "/api/kg/studio",
            "/api/kg/working-graphs/{graph_id}/package",
            "/api/analyses/{run_id}/evidence",
            "/api/analyses/{run_id}/artifacts/{name}",
        )
    )
    assert set(paths["/api/kg/working-graphs/{graph_id}/package"]) == {"get", "put"}


def test_analysis_index_separates_normal_gate_from_unmatched_and_preserves_unknown(monkeypatch):
    connection = Mock()
    rows = [
        {
            "payload": {"run_id": "mixed", "candidate_count": 8},
            "saved_outcomes": [
                ["no_match", "normal_reference_gate_is_false"],
                ["no_match", "anomaly_gate_is_false"],
                ["no_match", None],
                ["ambiguous", None],
                ["ambiguous", None],
                ["insufficient_evidence", "missing_observations"],
            ],
        },
        {
            "payload": {"run_id": "normal-only", "candidate_count": 0},
            "saved_outcomes": [["no_match", "normal_reference_gate_is_false"]],
        },
        {"payload": {"run_id": "before-outcomes", "candidate_count": 0}, "saved_outcomes": []},
    ]
    connection.execute.return_value.fetchall.return_value = rows
    store = TwoLoopStore(PostgresConfig(dsn=""))
    monkeypatch.setattr(store, "connection", lambda: nullcontext(connection))
    monkeypatch.setattr(two_loop_api, "task_manager", lambda: Mock(store=store))

    response = TestClient(create_app()).get("/api/analyses?limit=3")

    assert response.status_code == 200
    assert response.json() == {
        "runs": [
            {
                "run_id": "mixed",
                "candidate_count": 8,
                "outcome_counts": {"no_match": 1, "ambiguous": 2, "insufficient_evidence": 1},
                "normal_gate_count": 2,
            },
            {
                "run_id": "normal-only",
                "candidate_count": 0,
                "outcome_counts": {},
                "normal_gate_count": 1,
            },
            {"run_id": "before-outcomes", "candidate_count": 0},
        ]
    }
    assert connection.execute.call_args.args[1] == (3,)
    assert all("outcome_counts" not in row["payload"] for row in rows)
