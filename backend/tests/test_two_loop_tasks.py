"""The task state machine uses persisted transitions, including explicit recovery/retry."""

import copy

import pytest

from kgtracevis.service.two_loop_api import public_task
from kgtracevis.service.two_loop_store import TwoLoopStore
from kgtracevis.service.two_loop_tasks import TaskManager, utc_now


class MemoryStore:
    def __init__(self):
        self.tasks = {}
        self.analyses = {}

    def ensure_schema(self):
        pass

    def recover_tasks(self):
        TwoLoopStore.recover_tasks(self)

    def save_task(self, task):
        self.tasks[task["task_id"]] = copy.deepcopy(task)

    def get_task(self, identity):
        return copy.deepcopy(self.tasks[identity])

    def list_tasks(self, *, limit=50):
        return list(copy.deepcopy(self.tasks).values())[:limit]

    def save_analysis(self, run):
        self.analyses[run["run_id"]] = copy.deepcopy(run)

    def get_analysis(self, identity):
        return copy.deepcopy(self.analyses[identity])

    def list_analyses(self, *, limit=50):
        return [
            {k: v for k, v in run.items() if k not in {"cases", "working_graph_snapshot"}}
            for run in list(copy.deepcopy(self.analyses).values())[:limit]
        ]

    def media_registry(self):
        return {
            uri: path
            for r in self.analyses.values()
            for uri, path in r.get("media_assets", {}).items()
        }


def finish(manager, task):
    manager.futures[task["task_id"]].result(timeout=5)
    return manager.store.get_task(task["task_id"])


def test_real_progress_events_have_actual_counts_and_no_timer():
    store = MemoryStore()
    manager = TaskManager(store)

    def parse(context, request):
        context.progress("parsing", completed=0, total=2, unit="份资料")
        context.progress("parsing", "已解析A", completed=1, total=2, unit="份资料")
        context.progress("llm", "等待实际模型返回")
        return {"graph_id": "saved_graph"}

    manager.handlers["build"] = parse
    task = finish(manager, manager.submit("build", {"ids": [1, 2]}, title="制作"))
    assert task["status"] == "completed"
    assert task["result"] == {"graph_id": "saved_graph"}
    assert [(e["stage"], e["completed"]) for e in task["events"]] == [
        ("parsing", 0),
        ("parsing", 1),
        ("llm", None),
        ("completed", 1),
    ]
    assert task["events"][2]["total"] is None
    response = public_task(task, after_sequence=2)
    assert [e["sequence"] for e in response["events"]] == [3, 4]
    assert response["next_sequence"] == 4
    manager.executor.shutdown()


def test_failure_retains_stage_and_input_manual_retry_creates_new_task():
    manager = TaskManager(MemoryStore())
    attempts = []

    def failing(context, request):
        context.progress("llm", "实际模型调用")
        attempts.append(request["input_path"])
        raise ValueError("provider response incomplete")

    manager.handlers["build"] = failing
    task = finish(manager, manager.submit("build", {"input_path": "kept.pdf"}, title="制作"))
    assert task["status"] == "failed"
    assert task["error"]["stage"] == "llm"
    assert task["error"]["message"] == "provider response incomplete"
    assert attempts == ["kept.pdf"]  # no implicit or paid retry
    retried = finish(manager, manager.retry(task["task_id"]))
    assert retried["task_id"] != task["task_id"]
    assert retried["retry_of"] == task["task_id"]
    assert retried["request"] == task["request"]
    assert manager.store.get_task(task["task_id"])["status"] == "failed"
    assert attempts == ["kept.pdf", "kept.pdf"]
    manager.executor.shutdown()


def test_restart_marks_queued_and_running_interrupted_not_completed():
    store = MemoryStore()
    for status in ("queued", "running", "completed"):
        store.save_task(
            {
                "task_id": status,
                "kind": "inference",
                "status": status,
                "stage": "reasoning",
                "events": [],
                "updated_at": utc_now(),
                "request": {"input_path": "kept.json"},
                "result": None,
            }
        )
    manager = TaskManager(store)
    assert store.get_task("queued")["status"] == "interrupted"
    assert store.get_task("running")["error"]["type"] == "WorkerRestarted"
    assert store.get_task("completed")["status"] == "completed"
    assert store.get_task("running")["request"]["input_path"] == "kept.json"
    with pytest.raises(ValueError, match="失败或中断"):
        manager.retry("completed")
    manager.executor.shutdown()


def test_public_task_omits_internal_full_snapshots_but_keeps_input_identity():
    task = {
        "events": [],
        "request": {
            "graph_snapshot": {"huge": True},
            "source_snapshot": [],
            "graph_id": "g",
            "input_path": "p",
        },
    }
    assert public_task(task)["request"] == {"graph_id": "g", "input_path": "p"}
    assert "graph_snapshot" in task["request"]
