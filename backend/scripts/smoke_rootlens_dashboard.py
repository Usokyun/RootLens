"""Read the current RootLens material, task, and analysis contracts on a running API."""

from __future__ import annotations

import argparse
import json
from urllib.parse import quote
from urllib.request import urlopen


def _read(base: str, path: str):
    with urlopen(base + path, timeout=15) as response:
        return json.load(response)


def smoke(base: str, *, task_id: str | None = None, run_id: str | None = None):
    """Read existing records; do not submit a task or change the database."""
    base = base.rstrip("/")
    if _read(base, "/api/health")["status"] != "ok":
        raise RuntimeError("RootLens API is not healthy")
    active = _read(base, "/api/kg/materials")["materials"]
    archived = _read(base, "/api/kg/materials?archived=true")["materials"]
    if any(row["archived_at"] for row in active) or any(not row["archived_at"] for row in archived):
        raise RuntimeError("Active and archived material lists were mixed")
    tasks = _read(base, "/api/tasks")["tasks"]
    analyses = _read(base, "/api/analyses")["runs"]
    summary = {
        "status": "ok",
        "api": base,
        "active_materials": len(active),
        "archived_materials": len(archived),
        "recent_tasks": len(tasks),
        "recent_analyses": len(analyses),
    }
    if task_id:
        task = _read(base, "/api/tasks/" + quote(task_id, safe=""))
        if task["task_id"] != task_id:
            raise RuntimeError("Task identity changed on read")
        summary["task"] = {
            "task_id": task_id,
            "status": task["status"],
            "events": len(task["events"]),
        }
    if run_id:
        path = "/api/analyses/" + quote(run_id, safe="")
        run = _read(base, path)
        if run["run_id"] != run_id or run["evidence_download_url"] != path + "/evidence":
            raise RuntimeError("Run or Evidence download identity changed on read")
        frames = [frame for case in run["cases"] for frame in case["evidence_frames"]]
        if not frames or _read(base, path + "/evidence")["frames"] != frames:
            raise RuntimeError("The download is not the Evidence saved in the Run")
        summary["analysis"] = {"run_id": run_id, "frames": len(frames)}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8012")
    parser.add_argument("--task-id", help="Inspect one already saved task.")
    parser.add_argument("--run-id", help="Compare one saved analysis and its Evidence download.")
    args = parser.parse_args()
    result = smoke(args.api_url, task_id=args.task_id, run_id=args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
