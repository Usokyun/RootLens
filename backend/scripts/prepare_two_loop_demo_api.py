"""Exercise the real two-loop API and retain inputs, stage events and complete results.

This is an API client, not a second measurement or reasoning implementation.
Existing output directories require --resume; completed/failed tasks are not resubmitted.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


class DemoClient:
    def __init__(self, base_url, output, *, resume=False):
        self.output = output
        output.mkdir(parents=True, exist_ok=resume)
        self.client = httpx.Client(base_url=base_url, timeout=120)
        path = output / "state.json"
        self.state = (
            json.loads(path.read_text())
            if resume and path.exists()
            else {"base_url": base_url, "graphs": {}, "tasks": {}, "analyses": {}, "failures": []}
        )

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
            task = self.request("GET", f"/api/tasks/{task_id}")
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
            url = demo["working_graph"]["download_url"]
            package = self.request("GET", url)
            package["title"] += " · 双闭环实跑"
            record = self.request("POST", "/api/kg/working-graphs/import", json=package)
            graph_id = record["graph_id"]
            self.request(
                "POST", f"/api/kg/working-graphs/{graph_id}/enable", json={"enabled": True}
            )
            self.state["graphs"][identity] = graph_id
            write(self.output / f"{identity}.imported-graph.json", record)
            self.save()

    def build_bottle(self):
        registered = self.request("POST", "/api/demo-library/bottle/materials")
        write(self.output / "bottle.materials.json", registered)
        task = self.task(
            "bottle-source-build",
            "/api/tasks/material-build",
            {
                "material_ids": [m["material_id"] for m in registered["materials"]],
                "dataset": "mvtec",
                "title": "原厂PDF → 真实LLM · 双闭环玻璃缺损知识",
                "capability_id": "visual-region-v2",
                "enable_when_ready": False,
            },
        )
        if task["status"] != "completed":
            return
        graph_id = task["result"]["graph_id"]
        if "bottle-source-built" not in self.state["graphs"]:
            package = self.request("GET", f"/api/kg/working-graphs/{graph_id}/package")
            write(self.output / "bottle.llm-original-package.json", package)
            for entity in package["knowledge"]["entities"]:
                if entity["entity_id"] == "entity:industrial.object:bottle":
                    entity["aliases"] = list(dict.fromkeys(entity.get("aliases", []) + ["玻璃瓶"]))
            package["title"] += " · 已保存中文别名"
            self.request("PUT", f"/api/kg/working-graphs/{graph_id}/package", json=package)
            readback = self.request("GET", f"/api/kg/working-graphs/{graph_id}/package")
            assert any("玻璃瓶" in e.get("aliases", []) for e in readback["knowledge"]["entities"])
            write(self.output / "bottle.edited-package.json", readback)
            self.request(
                "POST", f"/api/kg/working-graphs/{graph_id}/enable", json={"enabled": True}
            )
            self.state["graphs"]["bottle-source-built"] = graph_id
            self.save()

    def inference(self, sample, graph_id, reasoner_id, variant, *, from_raw=False):
        label = f"{sample['sample_id']}-{variant}-{reasoner_id}"
        if variant == "evidence" and from_raw:
            raw = self.state["analyses"].get(f"{sample['sample_id']}-raw-{reasoner_id}")
            if raw is None or raw["graph_id"] != graph_id:
                raise ValueError("重新制作知识后，先完成同图的原始运行，再下载其Frame复算。")
            downloaded = self.client.get(f"/api/analyses/{raw['run_id']}/evidence")
            downloaded.raise_for_status()
            task = self.task(
                label,
                "/api/tasks/inference",
                {
                    "graph_id": graph_id,
                    "reasoner_id": reasoner_id,
                    "input_mode": "evidence",
                    "top_k": "8",
                    "title": sample["title"] + " · 下载Frame复算",
                },
                files={
                    "file": (
                        sample["sample_id"] + "-from-raw.json",
                        downloaded.content,
                        "application/json",
                    )
                },
            )
        else:
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
                                    for k in ("candidate_id", "candidate_name", "rank", "score")
                                }
                                for candidate in r["ranked_root_causes"]
                            ],
                        }
                        for r in c["results"]
                    ],
                }
                for c in run["cases"]
            ],
        }
        self.save()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8012")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--build-bottle", action="store_true", help="actual configured LLM call")
    p.add_argument("--build-only", action="store_true", help="stop after the material/KG loop")
    p.add_argument("--sample", action="append", help="stable sample_id; repeat to select")
    p.add_argument("--all", action="store_true", help="all samples, both entrances and engines")
    p.add_argument("--variant", choices=("raw", "evidence", "both"), default="both")
    p.add_argument("--graph-id", help="use one explicit enabled graph instead of importing seeds")
    p.add_argument(
        "--reasoner",
        choices=("unified_abduction", "tep_rootkgd"),
        help="run only this engine; otherwise use each sample's supported engines",
    )
    args = p.parse_args()
    client = DemoClient(args.base_url, args.output_dir, resume=args.resume)
    library = client.request("GET", "/api/demo-library")
    write(args.output_dir / "library.json", library)
    if args.graph_id is None and not args.build_only:
        client.import_graphs(library["demos"])
    if args.build_bottle:
        client.build_bottle()
    if args.build_only:
        print(json.dumps(client.state, ensure_ascii=False), flush=True)
        return
    selected = set(
        args.sample
        or ([] if args.all else ["bottle-rim-break", "tep-sequence-04", "wafer-nearfull"])
    )
    for demo in library["demos"]:
        for sample in demo["samples"]:
            if not args.all and sample["sample_id"] not in selected:
                continue
            graph_id = args.graph_id or client.state["graphs"].get(
                "bottle-source-built"
                if demo["id"] == "bottle" and args.build_bottle
                else demo["id"]
            )
            if graph_id is None:
                continue
            for reasoner in [args.reasoner] if args.reasoner else sample["reasoner_ids"]:
                if reasoner not in sample["reasoner_ids"]:
                    continue
                for variant in ["raw", "evidence"] if args.variant == "both" else [args.variant]:
                    client.inference(
                        sample,
                        graph_id,
                        reasoner,
                        variant,
                        from_raw=args.build_bottle and demo["id"] == "bottle",
                    )
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


if __name__ == "__main__":
    main()
