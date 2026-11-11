"""Run the published graded catalog through the real analysis API.

This is an API client, not a second measurement or reasoning implementation.
Existing output directories require --resume; completed/failed tasks are not resubmitted.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from scripts.prepare_two_loop_demo import read_manifest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


class DemoClient:
    def __init__(self, base_url, output, *, resume=False):
        base_url = base_url.rstrip("/")
        self.output = output
        output.mkdir(parents=True, exist_ok=resume)
        self.client = httpx.Client(base_url=base_url, timeout=120)
        path = output / "state.json"
        self.state = (
            json.loads(path.read_text())
            if resume and path.exists()
            else {"base_url": base_url, "graphs": {}, "tasks": {}, "analyses": {}, "failures": []}
        )
        if self.state["base_url"].rstrip("/") != base_url:
            self.client.close()
            raise ValueError("恢复记录的后端地址不同，请使用原地址或新的输出目录。")

    def save(self):
        write(self.output / "state.json", self.state)

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def task(self, label, endpoint, body, *, files=None):
        if label in self.state["tasks"]:
            task_id = self.state["tasks"][label]
        else:
            task = self.request(
                "POST",
                endpoint,
                **({"data": body, "files": files} if files is not None else {"json": body}),
            )
            task_id = task["task_id"]
            self.state["tasks"][label] = task_id
            self.save()
            write(self.output / f"{label}.request.json", {"endpoint": endpoint, "body": body})
        deadline = time.monotonic() + 1200
        previous_stage = None
        while time.monotonic() < deadline:
            status_url = f"/api/tasks/{task_id}"
            try:
                task = self.request("GET", status_url)
            except httpx.TransportError:
                # Retry the read once; the recorded task ID is never resubmitted.
                time.sleep(2)
                task = self.request("GET", status_url)
            write(self.output / f"{label}.task.json", task)
            if task["stage"] != previous_stage:
                print(
                    json.dumps(
                        {
                            "operation": label,
                            "task_id": task_id,
                            "status": task["status"],
                            "stage": task["stage"],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                previous_stage = task["stage"]
            if task["status"] in {"completed", "failed", "interrupted"}:
                if task["status"] != "completed":
                    failure = {"operation": label, "task_id": task_id, "error": task["error"]}
                    if failure not in self.state["failures"]:
                        self.state["failures"].append(failure)
                    self.save()
                return task
            time.sleep(2)
        raise TimeoutError(f"API task remains unfinished: {task_id}")

    def import_graphs(self, demos):
        for demo in demos:
            identity = demo["id"]
            if identity in self.state["graphs"]:
                continue
            result = self.request("POST", f"/api/demo-library/{identity}/working-graph")
            if result["state"] != "ready" or not result["available"] or not result["graph_id"]:
                raise ValueError(f"{demo['title']}：配套图安装后仍未启用。")
            write(self.output / f"{identity}.working-graph-install.json", result)
            self.state["graphs"][identity] = result["graph_id"]
            self.save()

    def inference(self, sample, graph_id, reasoner_id, variant):
        label = f"{sample['sample_id']}-{variant}-{reasoner_id}"
        task = self.task(
            label,
            "/api/tasks/inference/demo",
            {
                "sample_id": sample["sample_id"],
                "graph_id": graph_id,
                "reasoner_id": reasoner_id,
                "input_variant": variant,
                "top_k": 8,
            },
        )
        if task["status"] != "completed":
            return
        run_id = task["result"]["run_id"]
        run = self.request("GET", f"/api/analyses/{run_id}")
        if (
            run["graph_id"] != graph_id
            or run["reasoner_id"] != reasoner_id
            or run["input_mode"] != (sample["input_mode"] if variant == "raw" else "evidence")
        ):
            raise ValueError("已保存的任务不对应本次图、引擎或入口；请使用新的输出目录。")
        write(self.output / f"{label}.analysis.json", run)
        self.state["analyses"][label] = {
            "run_id": run_id,
            "sample_id": sample["sample_id"],
            "graph_id": graph_id,
            "reasoner_id": reasoner_id,
            "input_variant": variant,
            "cases": [
                {
                    "case_id": c["case_id"],
                    "frame_count": len(c["evidence_frames"]),
                    "media_count": len(c.get("visual_evidence", [])),
                    "results": [
                        {
                            "outcome": r["outcome"],
                            "path_count": len(r.get("top_k_paths", [])),
                            "candidates": [
                                {
                                    k: candidate.get(k)
                                    for k in (
                                        "candidate_id",
                                        "candidate_name",
                                        "status",
                                        "rank",
                                        "score",
                                    )
                                }
                                for candidate in r.get("graded_candidates", r["ranked_root_causes"])
                            ],
                        }
                        for r in c["results"]
                    ],
                }
                for c in run["cases"]
            ],
        }
        self.save()


def catalog_membership(catalog):
    return {
        demo["id"]: {sample["sample_id"]: sample["reasoner_ids"] for sample in demo["samples"]}
        for demo in catalog["demos"]
    }


def select_demos(library, *, selected, all_samples, reasoner):
    if catalog_membership(library) != catalog_membership(read_manifest()):
        raise ValueError("后端尚未加载当前发布的分级演示清单；未提交任务。")
    known = {s["sample_id"] for d in library["demos"] for s in d["samples"]}
    if missing := selected - known:
        raise ValueError("未在当前清单找到样本：" + ", ".join(sorted(missing)))
    demos = []
    for demo in library["demos"]:
        samples = []
        for sample in demo["samples"]:
            identity = sample["sample_id"]
            if not (all_samples or (identity in selected if selected else sample["recommended"])):
                continue
            if reasoner not in sample["reasoner_ids"]:
                if identity in selected:
                    raise ValueError(f"样本 {identity} 不支持推理器 {reasoner}。")
                continue
            samples.append(sample)
        if samples:
            demos.append({**demo, "samples": samples})
    if not demos:
        raise ValueError("当前选择没有适用的发布样本。")
    return demos


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", required=True, help="后端地址（如 http://127.0.0.1:8000）")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    sample_choice = p.add_mutually_exclusive_group()
    sample_choice.add_argument("--sample", action="append", help="发布 sample_id；可重复指定")
    sample_choice.add_argument("--all", action="store_true", help="包含所有发布样本")
    p.add_argument("--variant", choices=("raw", "evidence", "both"), default="evidence")
    p.add_argument("--graph-id", help="仅对单场景明确指定已启用的工作图")
    p.add_argument(
        "--reasoner", choices=("graded_abduction", "tep_rootkgd"), default="graded_abduction"
    )
    args = p.parse_args()
    client = DemoClient(args.base_url, args.output_dir, resume=args.resume)
    try:
        library = client.request("GET", "/api/demo-library")
        try:
            demos = select_demos(
                library,
                selected=set(args.sample or []),
                all_samples=args.all,
                reasoner=args.reasoner,
            )
        except ValueError as error:
            p.error(str(error))
        if args.graph_id and len(demos) != 1:
            p.error("--graph-id 只适用于单场景；请用 --sample 限定。")
        write(args.output_dir / "library.json", library)
        if args.graph_id is None:
            client.import_graphs(demos)
        for demo in demos:
            graph_id = args.graph_id or client.state["graphs"][demo["id"]]
            for sample in demo["samples"]:
                for variant in ["raw", "evidence"] if args.variant == "both" else [args.variant]:
                    client.inference(sample, graph_id, args.reasoner, variant)
        print(
            json.dumps(
                {
                    "state": str(args.output_dir / "state.json"),
                    "graph_ids": client.state["graphs"],
                    "analyses": len(client.state["analyses"]),
                    "failures": client.state["failures"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return int(bool(client.state["failures"]))
    finally:
        client.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
