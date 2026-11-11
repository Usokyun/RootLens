"""Small durable JSON envelopes for two-loop tasks and complete analysis snapshots."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from kgtracevis.service.postgres import PostgresConfig, resolve_postgres_config


class TwoLoopStorageError(RuntimeError):
    pass


class TwoLoopStore:
    def __init__(self, config: PostgresConfig | None = None):
        self.config = config or resolve_postgres_config()

    @contextmanager
    def connection(self):
        import psycopg
        from psycopg.rows import dict_row

        if not self.config.dsn:
            raise TwoLoopStorageError("异步任务需要已配置的 Postgres。")
        try:
            with psycopg.connect(self.config.dsn, row_factory=dict_row) as connection:
                yield connection
        except psycopg.Error as exc:
            raise TwoLoopStorageError("任务存储不可用，请检查当前 Postgres 连接。") from exc

    def ensure_schema(self):
        sql = Path(__file__).with_name("migrations").joinpath("002_two_loop_tasks.sql")
        with self.connection() as connection:
            connection.execute(sql.read_text())

    def recover_tasks(self):
        """A single API worker owns tasks; a new process never claims old work succeeded."""
        from kgtracevis.service.two_loop_tasks import utc_now

        for task in self.list_tasks(limit=100000):
            if task["status"] not in {"queued", "running"}:
                continue
            now = utc_now()
            task.update(status="interrupted", updated_at=now)
            task["error"] = {
                "stage": task["stage"],
                "type": "WorkerRestarted",
                "message": "服务重启中断了任务。输入已保留；可手动重试。",
            }
            task["events"].append(
                {
                    "sequence": len(task["events"]) + 1,
                    "at": now,
                    "stage": task["stage"],
                    "label": task["error"]["message"],
                    "status": "interrupted",
                }
            )
            self.save_task(task)

    def save_task(self, task: dict[str, Any]):
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute(
                "INSERT INTO rootlens_tasks(task_id,payload) VALUES (%s,%s) "
                "ON CONFLICT(task_id) DO UPDATE SET payload=EXCLUDED.payload,updated_at=now()",
                (task["task_id"], Jsonb(task)),
            )

    def get_task(self, task_id: str):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM rootlens_tasks WHERE task_id=%s", (task_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"找不到任务：{task_id}")
        return row["payload"]

    def list_tasks(self, *, limit=50):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM rootlens_tasks ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        return [r["payload"] for r in rows]

    def material_has_active_task(self, material_id: str) -> bool:
        """Check the full task ledger, including work outside the recent-list limit."""
        with self.connection() as connection:
            if (
                connection.execute("SELECT to_regclass('rootlens_tasks') AS task_table").fetchone()[
                    "task_table"
                ]
                is None
            ):
                return False
            row = connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM rootlens_tasks
                    WHERE payload->>'kind' IN ('material_parse', 'material_build')
                      AND payload->>'status' IN ('queued', 'running')
                      AND (payload->'request'->'material_ids') ? %s
                ) AS in_use
                """,
                (material_id,),
            ).fetchone()
        return bool(row["in_use"])

    def save_analysis(self, run):
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute(
                "INSERT INTO rootlens_analyses(run_id,payload) VALUES (%s,%s)",
                (run["run_id"], Jsonb(run)),
            )

    def get_analysis(self, run_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM rootlens_analyses WHERE run_id=%s", (run_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"找不到分析：{run_id}")
        return row["payload"]

    def list_analyses(self, *, limit=50):
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload - 'cases' - 'working_graph_snapshot' - 'artifacts'
                               - 'media_assets' - 'input_snapshot' AS payload,
                       ARRAY(
                           SELECT ARRAY[result->>'outcome', result->>'reason']
                           FROM jsonb_path_query(payload, '$.cases[*].results[*]') AS saved(result)
                           WHERE jsonb_typeof(result->'outcome') = 'string'
                             AND result->>'outcome' <> ''
                       ) AS saved_outcomes
                FROM rootlens_analyses ORDER BY created_at DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
        summaries = []
        for row in rows:
            counts: Counter[str] = Counter()
            normal_gates = 0
            for outcome, reason in row["saved_outcomes"]:
                if outcome == "no_match" and reason == "normal_reference_gate_is_false":
                    normal_gates += 1
                else:
                    counts[outcome] += 1
            summary = row["payload"]
            if counts or normal_gates:
                summary = {
                    **summary,
                    "outcome_counts": dict(counts),
                    "normal_gate_count": normal_gates,
                }
            summaries.append(summary)
        return summaries

    def media_registry(self):
        """Only paths actually registered by a raw run can resolve native Frame URIs."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT payload->'media_assets' AS assets FROM rootlens_analyses "
                "WHERE payload ? 'media_assets'"
            ).fetchall()
        return {uri: path for row in rows for uri, path in (row["assets"] or {}).items()}
