"""Focused product API for the material/KG and Evidence/reasoning loops."""

from __future__ import annotations

import copy
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from neo4j.exceptions import DriverError, Neo4jError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kgtracevis.adapters.unified_capabilities import (
    process_capabilities,
    spatial_capabilities,
    visual_capabilities,
)
from kgtracevis.service.kg_materials import (
    get_kg_material,
    save_kg_material_upload,
)
from kgtracevis.service.two_loop_runtime import REASONERS, TASK_ROOT, enable_graph
from kgtracevis.service.two_loop_store import TwoLoopStorageError
from kgtracevis.service.two_loop_tasks import task_manager
from kgtracevis.service.working_graph_editor import export_working_graph
from kgtracevis.service.working_graphs import WorkingGraphStorageError, working_graph_store

router = APIRouter(prefix="/api")
BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEMO_MANIFEST = BACKEND_ROOT / "data/demo/two_loop/manifest.json"
MAX_INPUT_BYTES = 100_000_000


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParseRequest(Request):
    material_ids: list[str] = Field(min_length=1)
    force: bool = False

    @model_validator(mode="after")
    def unique_materials(self):
        if len(self.material_ids) != len(set(self.material_ids)):
            raise ValueError("同一份资料不能重复选择。")
        return self


class BuildRequest(ParseRequest):
    dataset: Literal["mvtec", "tep", "wafer"]
    title: str = Field(min_length=1)
    capability_id: str
    enable_when_ready: bool = False
    max_repairs: int = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def matched_capability(self):
        expected = {
            "mvtec": "visual-region-v2",
            "tep": "process-window-v2",
            "wafer": "spatial-grid-v2",
        }
        if self.capability_id != expected[self.dataset]:
            raise ValueError("制作能力与所选场景不一致。")
        return self


class EnableRequest(Request):
    enabled: bool


class DemoInferenceRequest(Request):
    sample_id: str
    graph_id: str
    reasoner_id: Literal["unified_abduction", "tep_rootkgd"] = "unified_abduction"
    input_variant: Literal["raw", "evidence"] = "raw"
    top_k: int = Field(default=5, ge=1, le=100)


def call(action):
    try:
        return action()
    except (TwoLoopStorageError, WorkingGraphStorageError, DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def public_task(task, after_sequence=0):
    result = copy.deepcopy(task)
    result["next_sequence"] = max((e["sequence"] for e in task["events"]), default=0)
    result["events"] = [e for e in task["events"] if e["sequence"] > after_sequence]
    result["request"] = {
        k: v for k, v in result["request"].items() if k not in {"graph_snapshot", "source_snapshot"}
    }
    return result


@router.get("/reasoners")
def reasoners():
    return {"reasoners": REASONERS}


@router.get("/authoring/capabilities")
def authoring_capabilities():
    """One public authoring contract, also supplied to the actual LLM compiler."""
    return {
        "capabilities": {
            dataset: capability.model_dump(mode="json")
            for dataset, capability in (
                ("mvtec", visual_capabilities()),
                ("tep", process_capabilities()),
                ("wafer", spatial_capabilities()),
            )
        }
    }


@router.get("/tasks")
def tasks(limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return call(
        lambda: {"tasks": [public_task(t) for t in task_manager().store.list_tasks(limit=limit)]}
    )


@router.get("/tasks/{task_id}")
def task(task_id: str, after_sequence: Annotated[int, Query(ge=0)] = 0):
    return call(lambda: public_task(task_manager().store.get_task(task_id), after_sequence))


@router.post("/tasks/{task_id}/retry", status_code=202)
def retry_task(task_id: str):
    return call(lambda: public_task(task_manager().retry(task_id)))


@router.post("/tasks/material-parse", status_code=202)
def parse_materials(request: ParseRequest):
    def submit():
        for identity in request.material_ids:
            get_kg_material(identity)
        return public_task(
            task_manager().submit(
                "material_parse", request.model_dump(mode="json"), title="解析原始资料"
            )
        )

    return call(submit)


@router.post("/tasks/material-build", status_code=202)
def build_materials(request: BuildRequest):
    def submit():
        for identity in request.material_ids:
            material = get_kg_material(identity).material
            if material.scenario not in {request.dataset, "shared"}:
                raise ValueError("选中的资料包含其它场景，请分开制作工作图。")
        return public_task(
            task_manager().submit(
                "material_build", request.model_dump(mode="json"), title=request.title
            )
        )

    return call(submit)


@router.post("/kg/working-graphs/{graph_id}/enable")
def graph_enable(graph_id: str, request: EnableRequest):
    return call(lambda: enable_graph(graph_id, request.enabled).model_dump(mode="json"))


def inference_request(graph_id, reasoner_id, **options):
    record = working_graph_store().get(graph_id)
    if record.status != "ready" or not record.enabled or record.knowledge is None:
        raise ValueError("请先在知识图谱页启用一张 v2 工作图。")
    if reasoner_id not in {r["reasoner_id"] for r in REASONERS}:
        raise ValueError("请选择统一条件溯因或 RootKGD 图传播。")
    if reasoner_id == "tep_rootkgd" and record.dataset != "tep":
        raise ValueError("RootKGD 图传播仅适用于 TEP 过程场景。")
    mode = options["input_mode"]
    if (
        mode in {"image", "process", "wafer"}
        and {"image": "mvtec", "process": "tep", "wafer": "wafer"}[mode] != record.dataset
    ):
        raise ValueError("原始输入模式与所选工作图场景不一致。")
    if options.get("dataset") not in {None, record.dataset}:
        raise ValueError("上传场景与所选工作图不一致。")
    if options.get("semantic_mode") == "vlm" and mode != "image":
        raise ValueError("ROI 语义仅用于图像原始输入。")
    package = export_working_graph(graph_id)
    return {
        "graph_id": graph_id,
        "graph_snapshot": package.model_dump(mode="json"),
        "reasoner_id": reasoner_id,
        "dataset": record.dataset,
        **options,
    }


def safe_name(filename):
    value = re.sub(r"[^a-zA-Z0-9_.-]", "_", Path(filename).name).strip(".")
    return value or "input.json"


@router.post("/tasks/inference", status_code=202)
async def inference_upload(
    file: Annotated[UploadFile, File()],
    graph_id: Annotated[str, Form()],
    reasoner_id: Annotated[str, Form()] = "unified_abduction",
    input_mode: Annotated[
        Literal["evidence", "records", "image", "process", "wafer"], Form()
    ] = "evidence",
    reference_file: Annotated[UploadFile | None, File()] = None,
    dataset: Annotated[str | None, Form()] = None,
    object_name: Annotated[str | None, Form()] = None,
    model_preset: Annotated[str | None, Form()] = None,
    semantic_mode: Annotated[Literal["disabled", "vlm"], Form()] = "disabled",
    windows: Annotated[str | None, Form()] = None,
    sampling_seconds: Annotated[float, Form(gt=0)] = 180.0,
    title: Annotated[str | None, Form()] = None,
    top_k: Annotated[int, Form(ge=1, le=100)] = 5,
):
    try:
        parsed_windows = json.loads(windows) if windows else None
        if parsed_windows is not None and (
            not isinstance(parsed_windows, list)
            or not parsed_windows
            or any(
                not isinstance(w, list)
                or len(w) != 2
                or any(type(x) is not int for x in w)
                or w[0] < 1
                or w[1] < w[0]
                for w in parsed_windows
            )
        ):
            raise ValueError("windows 必须是一基闭区间数组，例如 [[1,100],[161,260]]。")
        request = inference_request(
            graph_id,
            reasoner_id,
            input_mode=input_mode,
            dataset=dataset,
            object_name=object_name,
            model_preset=model_preset,
            semantic_mode=semantic_mode,
            windows=parsed_windows,
            sampling_seconds=sampling_seconds,
            title=title or file.filename or "样本分析",
            top_k=top_k,
            source_filename=file.filename or "input.json",
        )
        if input_mode == "process" and reference_file is None:
            raise ValueError("过程原始数据需要 reference_file 正常参考。")
        content = await file.read(MAX_INPUT_BYTES + 1)
        if not content or len(content) > MAX_INPUT_BYTES:
            raise ValueError("输入文件为空或超过100MB。")
        root = TASK_ROOT / "inputs" / uuid.uuid4().hex
        root.mkdir(parents=True)
        path = root / safe_name(file.filename or "input.json")
        path.write_bytes(content)
        request["input_path"] = str(path)
        if reference_file is not None:
            reference = await reference_file.read(MAX_INPUT_BYTES + 1)
            if not reference or len(reference) > MAX_INPUT_BYTES:
                raise ValueError("正常参考为空或超过100MB。")
            reference_path = root / (
                "reference_" + safe_name(reference_file.filename or "normal.dat")
            )
            reference_path.write_bytes(reference)
            request["reference_path"] = str(reference_path)
        return public_task(task_manager().submit("inference", request, title=request["title"]))
    except (TwoLoopStorageError, WorkingGraphStorageError, DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/analyses")
def analyses(limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return call(lambda: {"runs": task_manager().store.list_analyses(limit=limit)})


@router.get("/analyses/{run_id}")
def analysis(run_id: str):
    return call(lambda: task_manager().store.get_analysis(run_id))


@router.get("/analyses/{run_id}/evidence")
def analysis_evidence(run_id: str):
    def artifact():
        run = task_manager().store.get_analysis(run_id)
        path = Path(run["artifacts"]["evidence-frames.json"])
        return FileResponse(path, media_type="application/json", filename="evidence-frames.json")

    return call(artifact)


@router.get("/analyses/{run_id}/artifacts/{name}")
def analysis_artifact(run_id: str, name: str):
    def artifact():
        run = task_manager().store.get_analysis(run_id)
        if name not in run["artifacts"]:
            raise ValueError("找不到该分析附件。")
        path = Path(run["artifacts"][name])
        if not path.is_file():
            raise ValueError("分析附件已不可用。")
        return FileResponse(path)

    return call(artifact)


def read_library():
    if not DEMO_MANIFEST.is_file():
        return {"demos": [], "samples": []}
    manifest = json.loads(DEMO_MANIFEST.read_text())

    def transform(item):
        if isinstance(item, list):
            return [transform(i) for i in item]
        if not isinstance(item, dict):
            return item
        result = {key: transform(value) for key, value in item.items()}
        if "asset_id" in item and "path" in item:
            path = (BACKEND_ROOT / item["path"]).resolve()
            if not path.is_relative_to(BACKEND_ROOT):
                raise ValueError("演示资产路径越出后端目录。")
            result["available"] = path.exists()
            result["download_url"] = "/api/demo-library/assets/" + item["asset_id"]
        if "reasoner_ids" in result:
            result["reasoner_ids"] = [
                "unified_abduction" if r == "unified" else r for r in result["reasoner_ids"]
            ]
        if result.get("input_mode") in {"tep_raw", "wafer_raw"}:
            result["input_mode"] = {"tep_raw": "process", "wafer_raw": "wafer"}[
                result["input_mode"]
            ]
        return result

    manifest = transform(manifest)
    manifest["samples"] = [
        {**s, "demo_id": d["id"]} for d in manifest["demos"] for s in d["samples"]
    ]
    return manifest


def library_assets():
    assets = {}

    def collect(item):
        if isinstance(item, list):
            for value in item:
                collect(value)
        elif isinstance(item, dict):
            if "asset_id" in item and "path" in item:
                assets[item["asset_id"]] = item
            for value in item.values():
                collect(value)

    collect(read_library())
    return assets


def asset_path(asset):
    path = (BACKEND_ROOT / asset["path"]).resolve()
    if not path.is_relative_to(BACKEND_ROOT) or not path.is_file():
        raise ValueError("演示资产不可用，请先运行公开演示准备脚本。")
    return path


@router.get("/demo-library")
def demo_library():
    return call(read_library)


@router.get("/demo-library/assets/{asset_id}")
def demo_asset(asset_id: str):
    def artifact():
        asset = library_assets().get(asset_id)
        if asset is None:
            raise ValueError("找不到演示资产。")
        path = asset_path(asset)
        return FileResponse(path, media_type=asset.get("media_type"), filename=path.name)

    return call(artifact)


@router.post("/demo-library/{demo_id}/materials")
def demo_materials(demo_id: str):
    def register():
        demo = next((d for d in read_library()["demos"] if d["id"] == demo_id), None)
        if demo is None:
            raise ValueError("找不到演示场景。")
        materials = []
        for asset in demo["materials"]:
            identity = safe_name(f"demo_{demo_id}_{asset['asset_id']}")
            try:
                material = get_kg_material(identity).material
            except ValueError:
                path = asset_path(asset)
                kind = {".pdf": "pdf", ".md": "markdown", ".html": "webpage"}.get(
                    path.suffix, "text"
                )
                material = save_kg_material_upload(
                    material_id=identity,
                    title=asset["title"],
                    filename=path.name,
                    content=path.read_bytes(),
                    scenario=demo["dataset"],
                    material_type=kind,
                    content_type=asset.get("media_type"),
                    metadata={
                        "demo_id": demo_id,
                        "source_url": asset.get("source_url"),
                        "selected_pages": demo.get("material_options", {}).get("pages"),
                        "demo_material_import": True,
                    },
                )
            materials.append(material.model_dump(mode="json"))
        return {"materials": materials}

    return call(register)


@router.post("/tasks/inference/demo", status_code=202)
def demo_inference(body: DemoInferenceRequest):
    def submit():
        sample = next(
            (s for s in read_library()["samples"] if s["sample_id"] == body.sample_id), None
        )
        if sample is None:
            raise ValueError("找不到演示样本。")
        asset = sample["evidence"] if body.input_variant == "evidence" else sample["raw_input"]
        options = sample.get("raw_options", {}) if body.input_variant == "raw" else {}
        request = inference_request(
            body.graph_id,
            body.reasoner_id,
            input_mode="evidence" if body.input_variant == "evidence" else sample["input_mode"],
            title=sample["title"],
            top_k=body.top_k,
            source_filename=Path(asset["path"]).name,
            **options,
        )
        path = asset_path(asset)
        root = TASK_ROOT / "inputs" / uuid.uuid4().hex
        root.mkdir(parents=True)
        destination = root / safe_name(path.name)
        shutil.copyfile(path, destination)
        request.update(
            input_path=str(destination), sample_id=body.sample_id, input_variant=body.input_variant
        )
        if body.input_variant == "evidence":
            payload = json.loads(destination.read_text())
            frames = payload.get("frames", [payload]) if isinstance(payload, dict) else payload
            raw_path = asset_path(sample["raw_input"])
            request["media_bindings"] = {
                asset["uri"]: str(raw_path)
                for frame in frames
                for asset in frame.get("assets", [])
                if (
                    asset["kind"] == "image"
                    or (sample["dataset"] == "wafer" and asset["asset_id"] == "grid")
                )
            }
            supporting = {
                a["frame_asset_id"]: str(asset_path(a))
                for a in sample.get("supporting_assets", [])
                if a.get("frame_asset_id")
            }
            for frame in frames:
                for asset in frame.get("assets", []):
                    if asset["asset_id"] in supporting:
                        request["media_bindings"][asset["uri"]] = supporting[asset["asset_id"]]
                    elif asset["uri"].split("#", 1)[0] in supporting.values():
                        request["media_bindings"][asset["uri"]] = asset["uri"].split("#", 1)[0]
        if body.input_variant == "raw" and sample.get("normal_reference"):
            reference = asset_path(sample["normal_reference"])
            reference_path = root / ("reference_" + safe_name(reference.name))
            shutil.copyfile(reference, reference_path)
            request["reference_path"] = str(reference_path)
        return public_task(task_manager().submit("inference", request, title=request["title"]))

    return call(submit)
