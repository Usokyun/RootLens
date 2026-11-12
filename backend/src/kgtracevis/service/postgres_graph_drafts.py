"""Append-only graph-workspace versions in the existing kg_edit_drafts table."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from kgtracevis.service.postgres import PostgresConfig, resolve_postgres_config

OPERATION = "rootlens-graph-workspace-v1"


@dataclass(frozen=True)
class PostgresGraphDraftStore:
    config: PostgresConfig
    connection_factory: Any | None = None

    @classmethod
    def from_environment(cls) -> PostgresGraphDraftStore:
        return cls(resolve_postgres_config())

    def _connection(self) -> Any:
        if self.connection_factory is not None:
            return self.connection_factory()
        if not self.config.dsn:
            raise RuntimeError("Postgres is required to save graph workspace drafts")
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.config.dsn, row_factory=dict_row)

    def append(self, payload: dict[str, Any]) -> dict[str, object]:
        from psycopg.types.json import Jsonb

        dataset = payload.get("metadata", {}).get("dataset")
        if dataset not in {"mvtec", "wafer", "tep"}:
            raise ValueError("graph workspace drafts require an explicit dataset")
        draft_id = uuid.uuid4()
        with self._connection() as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    INSERT INTO kg_edit_drafts
                        (draft_id, dataset, operation, target_type, target_id,
                         draft_payload, status, created_by)
                    VALUES (%s, %s, %s, 'graph_workspace', %s, %s, 'draft', %s)
                    RETURNING draft_id::text, created_at
                    """,
                    (
                        draft_id,
                        dataset,
                        OPERATION,
                        payload["target_id"],
                        Jsonb(payload),
                        payload.get("reviewer"),
                    ),
                ).fetchone()
        record = {
            **payload,
            "draft_id": str(row["draft_id"]),
            "recorded_at": row["created_at"].isoformat(),
        }
        return {"status": "recorded", "record": record}

    def list(self, request: Any) -> dict[str, object]:
        filters = (
            OPERATION,
            request.target_id,
            request.target_id,
            request.target_key,
            request.target_key,
            request.source,
            request.source,
            request.reviewer,
            request.reviewer,
        )
        where = """
            FROM kg_edit_drafts WHERE operation = %s AND target_type = 'graph_workspace'
              AND (%s::text IS NULL OR target_id = %s)
              AND (%s::text IS NULL OR draft_payload->>'target_key' = %s)
              AND (%s::text IS NULL OR draft_payload->>'source' = %s)
              AND (%s::text IS NULL OR created_by = %s)
        """
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT draft_id::text, draft_payload, created_at "
                + where
                + " ORDER BY created_at DESC, draft_id DESC OFFSET %s LIMIT %s",
                (*filters, request.offset, request.limit),
            ).fetchall()
            count = connection.execute(
                "SELECT count(*) AS total_count " + where, filters
            ).fetchone()
        records = [
            {
                **row["draft_payload"],
                "draft_id": row["draft_id"],
                "recorded_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
        return {
            "records": records,
            "total_count": int(count["total_count"]),
            "returned_count": len(records),
            "offset": request.offset,
            "limit": request.limit,
        }
