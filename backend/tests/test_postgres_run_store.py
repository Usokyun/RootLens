"""Tests for Postgres-backed run and feedback persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from kgtracevis.service.handlers import (
    FeedbackRequest,
    ReviewLedgerListRequest,
    ReviewLedgerListResponse,
)
from kgtracevis.service.postgres import PostgresConfig
from kgtracevis.service.postgres_run_payloads import detail_payload
from kgtracevis.service.postgres_run_store import PostgresRunStore


class FakeResult:
    def __init__(
        self,
        *,
        one: dict[str, Any] | None = None,
        rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self._one = one
        self._rows = rows or []

    def fetchone(self) -> dict[str, Any] | None:
        return self._one

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class FakeTransaction:
    def __enter__(self) -> FakeTransaction:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class FakeCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, Any]] = []
        self._next_one: dict[str, Any] | None = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self.executions.append((sql, params))
        if "RETURNING id::text" in sql:
            self._next_one = {"id": "11111111-1111-1111-1111-111111111111"}
        elif "RETURNING feedback_id::text" in sql:
            self._next_one = {
                "feedback_id": "22222222-2222-2222-2222-222222222222",
                "created_at": datetime(2026, 5, 14, tzinfo=timezone.utc),
            }

    def fetchone(self) -> dict[str, Any] | None:
        row = self._next_one
        self._next_one = None
        return row

    def fetchall(self) -> list[dict[str, Any]]:
        return []


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()
        self.committed = False

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    def execute(self, sql: str, params: Any = None) -> FakeResult:
        self.cursor_obj.executions.append((sql, params))
        if "RETURNING id" in sql:
            return FakeResult(one={"id": "11111111-1111-1111-1111-111111111111"})
        if "FROM run_evidence_cases rc" in sql:
            return FakeResult()
        if "SELECT dataset, case_pk FROM analysis_runs" in sql:
            return FakeResult(
                one={
                    "dataset": "wafer",
                    "case_pk": "11111111-1111-1111-1111-111111111111",
                }
            )
        if "RETURNING feedback_id" in sql:
            return FakeResult(
                one={
                    "feedback_id": "22222222-2222-2222-2222-222222222222",
                    "created_at": datetime(2026, 5, 14, tzinfo=timezone.utc),
                }
            )
        return FakeResult()

    def commit(self) -> None:
        self.committed = True


def test_postgres_run_store_persists_run_detail_to_normalized_tables() -> None:
    """Run persistence should fan out detail payloads into structured tables."""
    connection = FakeConnection()
    store = PostgresRunStore(
        PostgresConfig(dsn="postgresql://unit-test"),
        connection_factory=lambda: connection,
    )

    store.persist_run_detail(
        {
            "run": {
                "run_id": "33333333-3333-3333-3333-333333333333",
                "created_at": "2026-05-14T00:00:00+00:00",
                "mode": "evidence",
                "source_filename": "case.json",
                "top_k": 2,
                "run_dir": "runs/rootlens_sessions/33333333-3333-3333-3333-333333333333",
                "status": "completed",
                "dataset": "mvtec",
                "case_count": 1,
                "evidence_count": 1,
                "label": "MVTEC · mvtec_unit",
            },
            "claim_boundary": "candidate/plausible explanation only",
            "evidence": {
                "case_id": "mvtec_unit",
                "dataset": "mvtec",
                "source": "unit",
                "object": "capsule",
                "anomaly_type": "scratch",
                "timestamp": None,
                "raw_evidence": {"field": "value"},
                "normalized_evidence": {},
                "human_feedback": {},
            },
            "analysis": {
                "case_id": "mvtec_unit",
                "linked_entities": [
                    {
                        "link_id": "anomaly_type:scratch",
                        "field": "anomaly_type",
                        "mention": "scratch",
                        "selected_entity_id": "ScratchDefect",
                        "score": 1.0,
                        "match_type": "exact_name",
                    }
                ],
                "consistency_score": 0.75,
                "inconsistent_fields": ["morphology"],
                "correction_candidates": [
                    {
                        "candidate_id": "corr_1",
                        "field": "morphology",
                        "original_value": "spot",
                        "suggested_value": "linear",
                        "score": 0.8,
                    }
                ],
                "top_k_paths": [
                    {
                        "path_id": "path_1",
                        "rank": 1,
                        "nodes": ["ScratchDefect", "MechanicalContact"],
                        "relations": ["HAS_PLAUSIBLE_CAUSE"],
                        "score": 0.9,
                        "source_edges": [
                            {
                                "edge_id": (
                                    "ScratchDefect|HAS_PLAUSIBLE_CAUSE|"
                                    "MechanicalContact|mvtec"
                                ),
                            }
                        ],
                    }
                ],
                "ranked_root_causes": [
                    {
                        "ranking_id": "rca_mvtec_unit_mechanicalcontact",
                        "rank": 1,
                        "candidate_id": "MechanicalContact",
                        "candidate_name": "Mechanical contact",
                        "score": 0.9,
                        "scoring_method": "relation_weighted_path",
                    }
                ],
            },
            "artifacts": {"input_path": "runs/input/case.json"},
        }
    )

    sql_text = "\n".join(sql for sql, _params in connection.cursor_obj.executions)
    assert "INSERT INTO evidence_cases" in sql_text
    assert "INSERT INTO analysis_runs" in sql_text
    assert "INSERT INTO run_evidence_cases" in sql_text
    assert "INSERT INTO linked_entities" in sql_text
    assert "INSERT INTO consistency_checks" in sql_text
    assert "INSERT INTO correction_candidates" in sql_text
    assert "INSERT INTO ranked_paths" in sql_text
    assert "INSERT INTO artifacts" in sql_text

    analysis_params = next(
        params
        for sql, params in connection.cursor_obj.executions
        if "INSERT INTO analysis_runs" in sql
    )
    assert str(analysis_params[0]) == "33333333-3333-3333-3333-333333333333"
    assert analysis_params[2] == "mvtec"
    assert analysis_params[7] == 1
    parameters = _json_obj(analysis_params[16])
    assert parameters["ranked_root_causes_by_case"]["mvtec_unit"][0]["candidate_id"] == (
        "MechanicalContact"
    )


def test_postgres_run_store_records_feedback_with_contract_mapping() -> None:
    """Dashboard feedback names should map to Postgres enum values."""
    connection = FakeConnection()
    store = PostgresRunStore(
        PostgresConfig(dsn="postgresql://unit-test"),
        connection_factory=lambda: connection,
    )

    receipt = store.record_feedback(
        {
            "run_id": "33333333-3333-3333-3333-333333333333",
            "target_type": "path",
            "target_id": "path_1",
            "action": "needs_review",
            "note": "source should be checked",
            "reviewer": "analyst",
            "metadata": {"dataset": "wafer"},
        }
    )

    assert receipt["status"] == "recorded"
    feedback_params = next(
        params
        for sql, params in connection.cursor_obj.executions
        if "INSERT INTO feedback_records" in sql
    )
    assert feedback_params[0] == "wafer"
    assert feedback_params[3] == "ranked_path"
    assert feedback_params[5] == "uncertain"
    assert feedback_params[7] == "source should be checked"
    assert connection.committed is True


@pytest.mark.parametrize(
    ("public_target", "storage_target", "canonical_target"),
    [
        ("path", "ranked_path", "path"),
        ("edge", "kg_edge", "edge"),
        ("correction", "correction_candidate", "correction"),
        ("entity_link", "entity_link", "entity_link"),
        ("link", "entity_link", "entity_link"),
        ("case", "case", "case"),
        ("root_cause_candidate", "root_cause_candidate", "root_cause_candidate"),
    ],
)
def test_postgres_feedback_round_trip_matches_public_ledger_contract(
    public_target: str, storage_target: str, canonical_target: str
) -> None:
    """Stored target aliases must reload as valid, consistently keyed API targets."""

    class FeedbackConnection(FakeConnection):
        def __init__(self) -> None:
            super().__init__()
            self.feedback_rows: list[dict[str, Any]] = []

        def execute(self, sql: str, params: Any = None) -> FakeResult:
            if "SELECT f.feedback_id::text" in sql:
                assert params[4:6] == (storage_target, storage_target)
                self.cursor_obj.executions.append((sql, params))
                return FakeResult(rows=self.feedback_rows)
            if "SELECT count(*) AS total_count" in sql:
                self.cursor_obj.executions.append((sql, params))
                return FakeResult(one={"total_count": len(self.feedback_rows)})
            result = super().execute(sql, params)
            if "INSERT INTO feedback_records" in sql:
                self.feedback_rows.append(
                    {
                        "feedback_id": "22222222-2222-2222-2222-222222222222",
                        "created_at": datetime(2026, 5, 14, tzinfo=timezone.utc),
                        "run_id": params[1],
                        "case_id": "wafer_unit",
                        "target_type": params[3],
                        "target_id": params[4],
                        "feedback": params[5],
                        "corrected_value": _json_obj(params[6]),
                        "comment": params[7],
                        "reviewer": params[8],
                    }
                )
            return result

    connection = FeedbackConnection()
    store = PostgresRunStore(
        PostgresConfig(dsn="postgresql://unit-test"),
        connection_factory=lambda: connection,
    )
    request = FeedbackRequest.model_validate(
        {
            "run_id": "33333333-3333-3333-3333-333333333333",
            "case_id": "wafer_unit",
            "target_type": public_target,
            "target_id": "target_1",
            "action": "needs_review",
            "note": "Check the cited source",
            "reviewer": "analyst",
            "metadata": {"corrected_value": "review proposal"},
        }
    )
    store.record_feedback(request)
    assert connection.feedback_rows[0]["target_type"] == storage_target

    response = ReviewLedgerListResponse.model_validate(
        store.list_feedback(
            ReviewLedgerListRequest.model_validate(
                {
                    "run_id": request.run_id,
                    "target_type": public_target,
                    "target_id": request.target_id,
                }
            )
        )
    )

    assert response.total_count == response.returned_count == 1
    record = response.records[0]
    assert record.target_type == canonical_target
    assert record.target_id == request.target_id
    assert record.target_key == f"{canonical_target}:{request.target_id}"
    assert record.run_id == request.run_id
    assert record.case_id == request.case_id
    assert record.action == request.action
    assert record.note == request.note
    assert record.reviewer == request.reviewer
    assert record.metadata == request.metadata
    assert connection.feedback_rows[0]["target_type"] == storage_target


def test_postgres_detail_payload_preserves_stored_ranked_root_causes() -> None:
    """Loaded Postgres run details should not replace stored RCA rankings with paths."""
    root_cause = {
        "ranking_id": "rca_tep_0001_reactorcoolingfault",
        "rank": 1,
        "candidate_id": "ReactorCoolingFault",
        "candidate_name": "Reactor cooling fault",
        "score": 0.88,
        "scoring_method": "tep_artifact_bridge",
    }

    payload = detail_payload(
        run_row={
            "run_id": "33333333-3333-3333-3333-333333333333",
            "started_at": datetime(2026, 5, 14, tzinfo=timezone.utc),
            "mode": "evidence",
            "source_filename": "tep.json",
            "top_k": 1,
            "run_dir": "runs/unit",
            "status": "completed",
            "dataset": "tep",
            "case_count": 1,
            "evidence_count": 1,
            "label": "TEP · tep_0001",
            "model_preset": None,
            "model_backend": None,
            "claim_boundary": "candidate/plausible explanation only",
            "parameters": {
                "ranked_root_causes_by_case": {"tep_0001": [root_cause]},
                "workflow_steps": [],
            },
            "summary": {},
        },
        case_rows=[
            {
                "case_pk": "11111111-1111-1111-1111-111111111111",
                "case_id": "tep_0001",
                "dataset": "tep",
                "evidence_payload": {
                    "case_id": "tep_0001",
                    "dataset": "tep",
                    "raw_evidence": {},
                    "normalized_evidence": {},
                    "human_feedback": {},
                },
                "generated_evidence_path": None,
            }
        ],
        linked_rows=[],
        consistency_rows=[],
        correction_rows=[],
        path_rows=[
            {
                "case_pk": "11111111-1111-1111-1111-111111111111",
                "path_id": "path_1",
                "rank": 1,
                "source_entity_id": "XMEAS_1",
                "target_entity_id": "FallbackPathCause",
                "node_ids": ["XMEAS_1", "FallbackPathCause"],
                "relation_ids": ["RELATED_TO"],
                "score": 0.5,
                "confidence": 0.5,
                "evidence_match": 0.5,
                "supporting_evidence": [],
                "payload": {},
            }
        ],
        artifact_rows=[],
    )

    assert payload["ranked_root_causes"] == [root_cause]
    assert payload["analysis"]["ranked_root_causes"] == [root_cause]
    assert payload["cases"][0]["ranked_root_causes"] == [root_cause]


def test_postgres_run_store_records_root_cause_feedback() -> None:
    """Unified root-cause candidates should be valid Postgres feedback targets."""
    connection = FakeConnection()
    store = PostgresRunStore(
        PostgresConfig(dsn="postgresql://unit-test"),
        connection_factory=lambda: connection,
    )

    store.record_feedback(
        {
            "run_id": "33333333-3333-3333-3333-333333333333",
            "target_type": "root_cause_candidate",
            "target_id": "rca_tep_0001_reactorcoolingfault",
            "action": "accept",
        }
    )

    feedback_params = next(
        params
        for sql, params in connection.cursor_obj.executions
        if "INSERT INTO feedback_records" in sql
    )
    assert feedback_params[3] == "root_cause_candidate"
    assert feedback_params[4] == "rca_tep_0001_reactorcoolingfault"


def test_postgres_run_store_records_feedback_against_matching_run_case() -> None:
    """Feedback with run and case context should attach to the selected run case."""

    class CaseAwareConnection(FakeConnection):
        def execute(self, sql: str, params: Any = None) -> FakeResult:
            self.cursor_obj.executions.append((sql, params))
            if "FROM run_evidence_cases rc" in sql:
                return FakeResult(
                    one={
                        "dataset": "mvtec",
                        "case_pk": "44444444-4444-4444-4444-444444444444",
                    }
                )
            if "RETURNING feedback_id" in sql:
                return FakeResult(
                    one={
                        "feedback_id": "22222222-2222-2222-2222-222222222222",
                        "created_at": datetime(2026, 5, 14, tzinfo=timezone.utc),
                    }
                )
            return super().execute(sql, params)

    connection = CaseAwareConnection()
    store = PostgresRunStore(
        PostgresConfig(dsn="postgresql://unit-test"),
        connection_factory=lambda: connection,
    )

    store.record_feedback(
        {
            "run_id": "33333333-3333-3333-3333-333333333333",
            "case_id": "mvtec_case_2",
            "target_type": "case",
            "action": "accept",
        }
    )

    sql_text = "\n".join(sql for sql, _params in connection.cursor_obj.executions)
    feedback_params = next(
        params
        for sql, params in connection.cursor_obj.executions
        if "INSERT INTO feedback_records" in sql
    )
    assert "FROM run_evidence_cases rc" in sql_text
    assert feedback_params[0] == "mvtec"
    assert feedback_params[2] == "44444444-4444-4444-4444-444444444444"


def _json_obj(value: Any) -> Any:
    return value.obj if hasattr(value, "obj") else value
