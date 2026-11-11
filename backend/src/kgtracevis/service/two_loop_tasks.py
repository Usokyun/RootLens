"""Durable single-worker task state machine with real stage events, never timers."""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from kgtracevis.service.kg_materials import material_operations, require_active_material
from kgtracevis.service.two_loop_store import TwoLoopStore

LOGGER = logging.getLogger(__name__)
STAGES = {
    "queued": "等待执行",
    "parsing": "解析原始资料",
    "llm": "LLM 制作知识",
    "validation": "自动校验",
    "compilation": "编译工作图",
    "graph_ready": "图谱就绪",
    "upload": "接收输入",
    "adapter": "Adapter / 模型",
    "measurement": "测量与 Evidence",
    "reasoning": "知识图谱推理",
    "explanation": "整理解释与数据对应",
    "completed": "完成",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class TaskContext:
    def __init__(self, manager, task):
        self.manager, self.task = manager, task

    def progress(self, stage, label=None, *, completed=None, total=None, unit=None, **details):
        self.task.update(
            status="running",
            stage=stage,
            stage_label=STAGES.get(stage, stage),
            updated_at=utc_now(),
            progress={
                "completed": completed,
                "total": total,
                "unit": unit,
                "indeterminate": total is None,
            },
        )
        event = {
            "sequence": len(self.task["events"]) + 1,
            "at": self.task["updated_at"],
            "stage": stage,
            "label": label or STAGES.get(stage, stage),
            "completed": completed,
            "total": total,
            "unit": unit,
            "status": "running",
        }
        if details:
            event["details"] = details
        self.task["events"].append(event)
        self.manager.store.save_task(self.task)


class TaskManager:
    """One API process owns two bounded workers; Postgres retains every task and input."""

    def __init__(self, store=None, *, recover=True, workers=2):
        self.store = store or TwoLoopStore()
        self.store.ensure_schema()
        if recover:
            self.store.recover_tasks()
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rootlens-task")
        self.handlers = {}
        self.futures = {}

    def submit(self, kind, request, *, title, retry_of=None):
        if kind not in self.handlers:
            raise ValueError(f"unknown task kind: {kind}")
        if kind in {"material_parse", "material_build"}:
            with material_operations(request["material_ids"]) as store:
                materials = [
                    require_active_material(store, identity) for identity in request["material_ids"]
                ]
                ids = [material.material_id for material in materials]
                if len(ids) != len(set(ids)):
                    raise ValueError("同一份资料不能重复选择。")
                if kind == "material_build" and any(
                    material.scenario not in {request["dataset"], "shared"}
                    for material in materials
                ):
                    raise ValueError("选中的资料包含其它场景，请分开制作工作图。")
                # Publish the queued task before releasing the same locks used for archive.
                request = {**request, "material_ids": ids}
                return self._enqueue(kind, request, title=title, retry_of=retry_of)
        return self._enqueue(kind, request, title=title, retry_of=retry_of)

    def _enqueue(self, kind, request, *, title, retry_of):
        now = utc_now()
        task = {
            "task_id": "task_" + uuid.uuid4().hex,
            "kind": kind,
            "title": title,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "stage": "queued",
            "stage_label": STAGES["queued"],
            "progress": {"completed": None, "total": None, "unit": None, "indeterminate": True},
            "events": [],
            "request": request,
            "result": None,
            "error": None,
            "retry_of": retry_of,
        }
        self.store.save_task(task)
        self.futures[task["task_id"]] = self.executor.submit(self._run, task)
        # Return the persisted queued snapshot, not the worker's mutable object.
        return self.store.get_task(task["task_id"])

    def _run(self, task):
        context = TaskContext(self, task)
        try:
            result = self.handlers[task["kind"]](context, task["request"])
            context.progress("completed", completed=1, total=1, unit="任务")
            task.update(status="completed", result=result, updated_at=utc_now())
            task["events"][-1]["status"] = "completed"
            self.store.save_task(task)
        except Exception as exc:
            LOGGER.exception("Task %s failed in %s", task["task_id"], task["stage"])
            task.update(
                status="failed",
                updated_at=utc_now(),
                error={
                    "stage": task["stage"],
                    "message": str(exc),
                    "type": type(exc).__name__,
                },
            )
            task["events"].append(
                {
                    "sequence": len(task["events"]) + 1,
                    "at": task["updated_at"],
                    "stage": task["stage"],
                    "label": str(exc),
                    "status": "failed",
                }
            )
            self.store.save_task(task)

    def retry(self, task_id):
        task = self.store.get_task(task_id)
        if task["status"] not in {"failed", "interrupted"}:
            raise ValueError("仅失败或中断任务可以重试。")
        return self.submit(task["kind"], task["request"], title=task["title"], retry_of=task_id)


_manager = None
_manager_lock = threading.Lock()


def file_material_has_active_task(material_id: str) -> bool:
    """File-backed materials may be used by the current API process's task worker."""
    return _manager is not None and _manager.store.material_has_active_task(material_id)


def task_manager():
    global _manager
    with _manager_lock:
        if _manager is None:
            from kgtracevis.service.two_loop_runtime import build_materials, infer, parse_materials

            _manager = TaskManager()
            _manager.handlers.update(
                material_parse=parse_materials, material_build=build_materials, inference=infer
            )
    return _manager
