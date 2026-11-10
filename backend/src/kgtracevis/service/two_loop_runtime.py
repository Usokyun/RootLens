"""The two product loops: source-to-working-knowledge and raw-to-explained-run."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path

from kgtracevis.adapters.batch import evidence_from_records, load_records
from kgtracevis.adapters.unified import evidence_frames
from kgtracevis.core.rootkgd_reasoner import RootKGDReasoner
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.evidence_schema import Evidence
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.service.kg_materials import (
    KGMaterialExtractionRunRequest,
    KGMaterialSelectedBuildRequest,
    extract_kg_material_to_structured_records,
    get_kg_material,
    prepare_kg_material_construction_build,
)
from kgtracevis.service.two_loop_tasks import utc_now
from kgtracevis.service.working_graph_editor import import_working_graph
from kgtracevis.service.working_graphs import graph_operation_lock, working_graph_store

TASK_ROOT = Path("runs/two_loop_tasks")
REASONERS = [
    {
        "reasoner_id": "unified_abduction",
        "title": "统一条件溯因",
        "datasets": ["mvtec", "tep", "wafer"],
        "description": "共同类型契约、联合条件与 U/C/A/J 代价；跨场景使用同一内核。",
    },
    {
        "reasoner_id": "tep_rootkgd",
        "title": "RootKGD 图传播",
        "datasets": ["tep"],
        "description": "TEP 专用：有向关系衰减传播与完整52通道残差贡献向量结构比较。",
    },
]


def enable_graph(graph_id, enabled):
    store = working_graph_store()
    with graph_operation_lock(graph_id, store):
        record = store.get(graph_id)
        if record.status != "ready" or record.knowledge is None:
            raise ValueError("仅可启用校验完成的 v2 工作图。")
        updated = record.model_copy(update={"enabled": enabled})
        store.update(updated)
    return updated


def parse_materials(context, request):
    ids = request["material_ids"]
    context.progress("parsing", completed=0, total=len(ids), unit="份资料")
    for index, identity in enumerate(ids, 1):
        material = get_kg_material(identity).material
        if request.get("force") or material.extraction.status != "extracted":
            extract_kg_material_to_structured_records(
                identity, KGMaterialExtractionRunRequest(overwrite=bool(request.get("force")))
            )
        context.progress(
            "parsing", f"已解析：{material.title}", completed=index, total=len(ids), unit="份资料"
        )
    return {"material_ids": ids}


def build_materials(context, request):
    from kgtracevis.adapters.unified_capabilities import capability_manifest
    from kgtracevis.source_kg_compiler.compiler import load_source_units
    from kgtracevis.source_kg_compiler.llm import OpenAICompatibleSourceKGLLM
    from kgtracevis.source_kg_compiler.unified import compile_unified_knowledge

    parse_materials(context, {"material_ids": request["material_ids"], "force": False})
    sources = prepare_kg_material_construction_build(
        KGMaterialSelectedBuildRequest(
            material_ids=request["material_ids"],
            target_contract="unified-v2",
            capability_id=request["capability_id"],
            output_name=context.task["task_id"],
        )
    )
    units = load_source_units(
        tuple(Path(s.path) for s in sources.sources), default_scenario=request["dataset"]
    )
    page_selection = {
        m.extraction.source_id: m.metadata.get("selected_pages")
        for m in sources.materials
        if m.metadata.get("selected_pages")
    }
    if page_selection:
        units = [
            u
            for u in units
            if u.source_id not in page_selection
            or u.source_span.get("page") in page_selection[u.source_id]
        ]
    output = TASK_ROOT / context.task["task_id"] / "build"
    context.task["request"]["source_snapshot"] = [u.model_dump(mode="json") for u in units]
    context.manager.store.save_task(context.task)
    package = compile_unified_knowledge(
        units,
        capability_manifest(request["capability_id"]),
        llm_client=OpenAICompatibleSourceKGLLM(),
        output_dir=output,
        title=request["title"],
        dataset=request["dataset"],
        max_repairs=request.get("max_repairs", 1),
        progress=context.progress,
    )
    package = package.model_copy(update={"build_id": context.task["task_id"]})
    context.progress("graph_ready", "保存 canonical 知识与隔离 Neo4j 投影")
    record = import_working_graph(package)
    if request.get("enable_when_ready"):
        record = enable_graph(record.graph_id, True)
    return {
        "graph_id": record.graph_id,
        "build_id": context.task["task_id"],
        "graph": record.model_dump(mode="json"),
        "artifacts": {p.name: str(p) for p in output.iterdir() if p.is_file()},
    }


def infer(context, request):
    package = UnifiedWorkingGraphPackage.model_validate(request["graph_snapshot"])
    input_path = Path(request["input_path"])
    run_id = str(uuid.uuid4())
    root = TASK_ROOT / context.task["task_id"] / "analysis"
    root.mkdir(parents=True, exist_ok=True)
    context.progress("upload", "已保存输入与所选工作图快照", completed=1, total=1, unit="份输入")
    groups, records = prepare_inputs(context, request, package, root)
    reasoner = (
        UnifiedReasoner(package.knowledge)
        if request["reasoner_id"] == "unified_abduction"
        else RootKGDReasoner(package.knowledge)
    )
    total = sum(len(g["frames"]) for g in groups)
    context.progress("reasoning", completed=0, total=total, unit="查询")
    cases, completed = [], 0
    for group in groups:
        results = []
        for frame in group["frames"]:
            result = reasoner.analyze(frame, top_k=request.get("top_k", 5))
            result = explain_result(result, frame, package)
            results.append(result)
            completed += 1
            context.progress(
                "reasoning",
                f"已分析：{group['display_name']}",
                completed=completed,
                total=total,
                unit="查询",
            )
        cases.append(
            {
                "case_id": group["case_id"],
                "display_name": group["display_name"],
                "evidence_frames": [f.model_dump(mode="json") for f in group["frames"]],
                "results": results,
                "generated_evidence": group.get("generated_evidence"),
                "visual_evidence": [],
                "observation_locations": [
                    observation_location(f, o) for f in group["frames"] for o in f.observations
                ],
            }
        )
    context.progress("explanation", "整理来源、观测定位、预览与 Evidence 下载")
    all_frames = [frame for case in cases for frame in case["evidence_frames"]]
    frame_path = root / "evidence-frames.json"
    frame_path.write_text(json.dumps({"frames": all_frames}, ensure_ascii=False, indent=2))
    artifacts = {"input": str(input_path), "evidence-frames.json": str(frame_path)}
    graph_path = root / "working-graph-snapshot.json"
    graph_path.write_text(package.model_dump_json(indent=2))
    artifacts[graph_path.name] = str(graph_path)
    if request.get("reference_path"):
        artifacts["normal-reference"] = request["reference_path"]
    media_assets = _resolve_media(context, request, groups, records, root)
    visuals = _visuals(records, groups, run_id, root, media_assets)
    for visual in visuals:
        if visual.get("preview_path"):
            p = Path(visual["preview_path"])
            artifacts[p.name] = str(p)
    for case in cases:
        case["visual_evidence"] = [v for v in visuals if v["case_id"] == case["case_id"]]
        case["media_status"] = (
            "available"
            if any(v.get("available") for v in case["visual_evidence"])
            or any(
                a["uri"] in media_assets and a["asset_id"] in {"window", "image", "grid"}
                for f in case["evidence_frames"]
                for a in f["assets"]
            )
            else "not_attached"
        )
        case["media_note"] = (
            "原始媒体已关联。"
            if case["media_status"] == "available"
            else "只有统计与引用，原始媒体未附带。"
        )
        case.update(_media_payload(case["evidence_frames"], media_assets))
    run = {
        "run_id": run_id,
        "title": request["title"],
        "created_at": utc_now(),
        "status": "completed",
        "dataset": package.dataset,
        "input_mode": request["input_mode"],
        "reasoner_id": request["reasoner_id"],
        "graph_id": package.graph_id,
        "graph_title": package.title,
        "case_count": len(cases),
        "candidate_count": sum(len(r["ranked_root_causes"]) for c in cases for r in c["results"]),
        "cases": cases,
        "working_graph_snapshot": package.model_dump(mode="json"),
        "artifacts": artifacts,
        "source_filename": request.get("source_filename", input_path.name),
        "task_id": context.task["task_id"],
        "media_assets": media_assets,
        "evidence_download_url": f"/api/analyses/{run_id}/evidence",
        "input_snapshot": {k: v for k, v in request.items() if k != "graph_snapshot"},
    }
    (root / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2))
    context.manager.store.save_analysis(run)
    return {"run_id": run_id}


def prepare_inputs(context, request, package, root):
    path, mode = Path(request["input_path"]), request["input_mode"]
    context.progress("adapter", "读取原始输入与测量能力")
    records, evidence_items = [], []
    if mode == "evidence":
        payload = json.loads(path.read_text())
        rows = payload.get("frames", [payload]) if isinstance(payload, dict) else payload
        if not isinstance(rows, list) or not rows:
            raise ValueError("Evidence JSON 需要非空 Frame、Frame 数组或 {frames:[...]}。")
        groups = []
        for index, row in enumerate(rows, 1):
            if isinstance(row, dict) and row.get("schema_version") == "rootlens-evidence.v2":
                frame = EvidenceFrame.model_validate(row)
                groups.append(
                    {
                        "case_id": frame.case_id,
                        "display_name": frame_display_name(frame, index),
                        "frames": [frame],
                    }
                )
            else:
                evidence_items.append(Evidence.model_validate(row))
        if groups and evidence_items:
            raise ValueError("不能在同一上传中混用 Frame 与旧 Evidence。")
        if groups:
            context.progress(
                "measurement",
                "已校验保存的原生 Evidence，不调用模型",
                completed=len(groups),
                total=len(groups),
                unit="Frame",
            )
            return groups, []
    elif mode == "records":
        records = load_records(path)
        evidence_items = evidence_from_records(records, dataset=package.dataset)
    elif mode == "process":
        from kgtracevis.producers.tep_records import build_tep_dat_records

        reference = request.get("reference_path")
        if not reference:
            raise ValueError("过程原始输入必须附带匹配的正常 reference_file。")
        sequence = _process_matrix(path, root / "sequence.dat")
        normal = _process_matrix(Path(reference), root / "normal.dat")
        windows = request.get("windows") or [[1, 100]]
        records = build_tep_dat_records(
            normal,
            sequence,
            output_dir=root / "process",
            windows=windows,
            sampling_interval_seconds=request.get("sampling_seconds", 180.0),
            progress=context.progress,
        )
        context.progress(
            "measurement",
            "已从正常参考拟合 PCA/scaler，生成完整52通道测量",
            completed=len(records),
            total=len(windows),
            unit="窗口",
        )
        evidence_items = evidence_from_records(records, dataset="tep")
    elif mode == "image":
        records = _image_records(context, request, package, root)
        evidence_items = evidence_from_records(records, dataset="mvtec")
    elif mode == "wafer":
        records = _wafer_records(context, request, root)
        evidence_items = evidence_from_records(records, dataset="wafer")
    else:
        raise ValueError(f"unknown input_mode: {mode}")
    groups = []
    for index, evidence in enumerate(evidence_items, 1):
        if evidence.dataset != package.dataset:
            raise ValueError("Evidence 场景与所选工作图不一致。")
        frames = evidence_frames(evidence)
        groups.append(
            {
                "case_id": evidence.case_id,
                "display_name": frame_display_name(frames[0], index),
                "frames": frames,
                "generated_evidence": evidence.model_dump(mode="json"),
            }
        )
        context.progress(
            "measurement",
            f"已生成：{groups[-1]['display_name']}",
            completed=index,
            total=len(evidence_items),
            unit="样本",
        )
    if not groups:
        raise ValueError("没有生成可分析的 Evidence。")
    return groups, records


def _process_matrix(path, destination):
    import numpy as np

    if path.suffix.lower() != ".csv":
        return path
    first = path.open().readline().strip().split(",")
    try:
        [float(x) for x in first]
        skiprows = 0
    except ValueError as exc:
        from kgtracevis.core.rootkgd_reasoner import CHANNELS

        if first != CHANNELS:
            raise ValueError("过程 CSV 标题必须依次为 xmeas_1..41, xmv_1..11。") from exc
        skiprows = 1
    matrix = np.loadtxt(path, delimiter=",", skiprows=skiprows)
    np.savetxt(destination, matrix)
    return destination


def _image_records(context, request, package, root):
    from kgtracevis.kg.unified_semantics import visual_semantic_concepts
    from kgtracevis.producers import build_mvtec_records
    from kgtracevis.producers.mvtec_models import resolve_mvtec_model_selection
    from kgtracevis.producers.visual_semantics import OpenAICompatibleROISemantics
    from kgtracevis.schema.visual_reasoning import VisualRegion
    from kgtracevis.service.runs import _build_mvtec_upload_predictor

    object_name = request.get("object_name") or "bottle"
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", object_name):
        raise ValueError("object_name 必须是已注册的对象名称。")
    selection = resolve_mvtec_model_selection(request.get("model_preset"), object_name=object_name)
    context.progress("adapter", f"加载 {object_name} / {selection.preset} 模型")
    predictor = _build_mvtec_upload_predictor(
        model_backend=selection.backend,
        checkpoint=selection.checkpoint_path,
        device=os.environ.get("KGTRACEVIS_MVTEC_DEVICE", "CPU"),
        model_type=selection.preset,
    )
    image = root / "images" / object_name / "test" / "unknown" / Path(request["input_path"]).name
    image.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(request["input_path"], image)
    context.progress("adapter", "执行图像异常定位模型")
    records = build_mvtec_records(
        root / "images",
        predictor,
        output_dir=root / "image-model",
        model_backend=selection.backend,
        checkpoint=selection.checkpoint_path,
        max_cases=1,
        include_good=True,
    )
    for record in records:
        record["annotation_type"] = "unlabeled"
        if (
            request.get("semantic_mode") == "vlm"
            and record.get("detector", {}).get("raw_pred_label") is not False
        ):
            context.progress("adapter", "ROI 视觉语义模型正在识别实际区域（不传原因候选）")
            semantics = OpenAICompatibleROISemantics()
            regions = semantics.annotate(
                image,
                [VisualRegion.model_validate(r) for r in record["visual_regions"]],
                object_name=object_name,
                concepts=visual_semantic_concepts(package.knowledge.model_dump(mode="json")),
                output_dir=root / "rois",
                normal_reference_path=selection.normal_reference,
            )
            record["visual_regions"] = [r.model_dump(mode="json") for r in regions]
            record["semantic_inference"] = {
                "model": semantics.model,
                "calls": semantics.calls,
                "total_tokens": semantics.tokens,
            }
    (root / "model-records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return records


def _wafer_records(context, request, root):
    from kgtracevis.producers.backends import TorchWM811KBackend
    from kgtracevis.producers.wm811k_records import build_wm811k_records

    checkpoint = Path(
        os.environ.get("KGTRACEVIS_WM811K_CHECKPOINT")
        or "runs/refactor_m2_m6/public/wm811k_resnet.pt"
    )
    if not checkpoint.is_file():
        raise ValueError("缺少已信任的 WM811K ResNet 权重；请配置 KGTRACEVIS_WM811K_CHECKPOINT。")
    path = Path(request["input_path"])
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text())
        if isinstance(payload, list) and payload and isinstance(payload[0], list):
            payload = [{"case_id": "wafer_upload", "waferMap": payload}]
        elif isinstance(payload, dict):
            payload = [payload]
        normalized = root / "raw-wafer.jsonl"
        normalized.write_text("\n".join(json.dumps(p) for p in payload))
        path = normalized
    context.progress("adapter", "加载独立 ResNet 晶圆图案分类器")
    classifier = TorchWM811KBackend(checkpoint=checkpoint, device="cpu")
    records = build_wm811k_records(
        path,
        classifier,
        output_dir=root / "wafer-model",
        model_backend="torch-resnet34",
        checkpoint=checkpoint,
        include_unlabeled=True,
        include_normal=True,
        wafer_map_inline_limit=100000,
    )
    (root / "model-records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return records


def frame_display_name(frame, index):
    scope = next(s for s in frame.scopes if s.scope_id == frame.task.scope_id)
    if scope.kind == "time_window":
        return f"样本 {scope.sample_start}–{scope.sample_end}"
    if scope.kind == "image_region":
        return f"图像区域 {index}"
    if frame.source_dataset == "wafer":
        return f"晶圆网格 {index}"
    return f"样本 {index}"


def observation_location(frame, observation):
    scope = next(s for s in frame.scopes if s.scope_id == observation.scope_id)
    subject = next(s for s in frame.subjects if s.subject_id == observation.subject_id)
    return {
        "obs_id": observation.obs_id,
        "subject_id": observation.subject_id,
        "subject_external_id": subject.external_id,
        "feature_id": observation.feature_id,
        "scope": scope.model_dump(mode="json"),
        "raw_refs": observation.raw_refs,
        "assets": [
            a.model_dump(mode="json") for a in frame.assets if a.asset_id in observation.raw_refs
        ],
        "reference_id": observation.reference_id,
        "procedure_id": observation.procedure_id,
    }


def explain_result(result, frame, package):
    from kgtracevis.kg.unified_compiler import KnowledgeProgram

    program = KnowledgeProgram(package.knowledge)
    labels = {r["node_id"]: r.get("label") or r["node_id"] for r in program.projection["nodes"]}
    fallback_names = {
        "EffectRule": "作用规则",
        "ExpectationRule": "预期表现",
        "DefinitionRule": "联合条件",
        "LogicGate": "条件组合",
        "SourceAssertion": "资料断言",
        "ValueBinding": "取值映射",
    }
    for row in program.projection["nodes"]:
        if not row.get("label"):
            labels[row["node_id"]] = fallback_names.get(row["kind"], row["kind"])
    sources = {
        s.assertion_id: s.model_dump(mode="json") for s in package.knowledge.source_assertions
    }
    locations = {o.obs_id: observation_location(frame, o) for o in frame.observations}
    for row in result.get("grounded_facts", []):
        row["display_name"] = labels.get(row["predicate_id"], row["predicate_id"])
        row["observation_locations"] = [
            locations[i] for i in row["source_obs_ids"] if i in locations
        ]
    for row in result.get("candidate_evaluations", []):
        row["candidate_name"] = labels.get(row["candidate_id"], row.get("candidate_name"))
    for row in result.get("ranked_root_causes", []):
        for path in row.get("explanation_paths", []):
            path["node_names"] = [labels.get(i, i) for i in path["nodes"]]
            path["observation_locations"] = [
                locations[i] for i in path["support_obs_ids"] if i in locations
            ]
            assertion_ids = path.get("source_assertion_ids", [])
            if not assertion_ids:
                identities = set(path["nodes"])
                for collection in (
                    package.knowledge.observable_definitions,
                    package.knowledge.pattern_definitions,
                    package.knowledge.effect_rules,
                    package.knowledge.expectation_rules,
                ):
                    for item in collection:
                        identity = getattr(item, "predicate_id", None) or getattr(
                            item, "rule_id", None
                        )
                        identity = identity or getattr(item, "definition_id", None)
                        if identity in identities:
                            assertion_ids.extend(item.source_assertion_ids)
            path["source_assertion_ids"] = sorted(set(assertion_ids))
            path["source_assertions"] = [sources[i] for i in path["source_assertion_ids"]]
    result["display_labels"] = labels
    result["source_assertions"] = list(sources.values())
    return result


def _resolve_media(context, request, groups, records, root):
    registry = context.manager.store.media_registry()
    registry.update(request.get("media_bindings", {}))
    raw = request["input_mode"] in {"image", "process", "wafer"}
    if request["input_mode"] == "wafer":
        by_case = {r["case_id"]: r for r in records}
        for group in groups:
            record = by_case[group["case_id"]]
            grid = record.get("wafer_map")
            if grid is not None:
                destination = root / ("grid-" + uuid.uuid4().hex + ".json")
                destination.write_text(json.dumps(grid))
                for frame in group["frames"]:
                    for asset in frame.assets:
                        if asset.asset_id == "grid":
                            registry[asset.uri] = str(destination)
    if raw:
        for path in root.rglob("*"):
            if path.is_file():
                registry[str(path)] = str(path)
        for key in ("input_path", "reference_path"):
            if request.get(key):
                registry[request[key]] = request[key]
    attached = {}
    for group in groups:
        for frame in group["frames"]:
            for asset in frame.assets:
                uri = asset.uri
                base = uri.split("#", 1)[0]
                path = registry.get(uri) or registry.get(base)
                if path and Path(path).is_file():
                    attached[uri] = path
    # Preview-producing paths are registered only from this raw run's output tree.
    if raw:
        attached.update({str(p): str(p) for p in root.rglob("*") if p.is_file()})
    return attached


def _visuals(records, groups, run_id, root, media_assets):
    from kgtracevis.service.visual_evidence import build_visual_evidence_artifacts

    allowed_paths = {str(Path(p).resolve()) for p in media_assets.values()}

    def safe_record(value):
        if isinstance(value, list):
            return [safe_record(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if isinstance(item, str) and (key.endswith("_path") or key.endswith("_uri")):
                if str(Path(item).resolve()) not in allowed_paths:
                    continue
            result[key] = safe_record(item)
        return result

    records = [safe_record(record) for record in records]
    if not records:
        for group in groups:
            for frame in group["frames"]:
                for asset in frame.assets:
                    path = media_assets.get(asset.uri)
                    if not path:
                        continue
                    if asset.kind == "image":
                        records.append(
                            {
                                "case_id": group["case_id"],
                                "dataset": frame.source_dataset,
                                "image_path": path,
                            }
                        )
                    elif frame.source_dataset == "wafer" and asset.kind == "typed_array":
                        p = Path(path)
                        if p.suffix.lower() in {".jsonl", ".json"}:
                            grid = json.loads(p.read_text()) if p.suffix == ".json" else None
                            if not (isinstance(grid, list) and grid and isinstance(grid[0], list)):
                                rows = load_records(p)
                                grid = (
                                    rows[0].get("waferMap", rows[0].get("wafer_map"))
                                    if rows
                                    else None
                                )
                            if grid is not None:
                                records.append(
                                    {
                                        "case_id": group["case_id"],
                                        "dataset": "wafer",
                                        "wafer_map": grid,
                                    }
                                )
    items = build_visual_evidence_artifacts(records, run_id=run_id, run_dir=root)
    for item in items:
        if item.get("url"):
            item["url"] = item["url"].replace("/api/runs/", "/api/analyses/")
    return items


def _media_payload(frames, media_assets):
    """Load only registry-resolved data, never the arbitrary URI supplied by a Frame."""
    result = {}
    for frame in frames:
        assets = {a["asset_id"]: a for a in frame["assets"]}
        window = assets.get("window")
        if window and window["uri"] in media_assets:
            path = Path(media_assets[window["uri"]])
            if path.suffix == ".npy":
                import numpy as np

                values = np.load(path, allow_pickle=False)
                columns = window.get("columns") or []
                if values.ndim == 2 and len(columns) == values.shape[1]:
                    result["process_trends"] = [
                        {"channel": channel, "samples": values[:, i].tolist()}
                        for i, channel in enumerate(columns)
                    ]
        grid = assets.get("grid")
        if grid and grid["uri"] in media_assets:
            path = Path(media_assets[grid["uri"]])
            if path.suffix == ".json":
                values = json.loads(path.read_text())
                if isinstance(values, list) and values and isinstance(values[0], list):
                    result["wafer_map"] = values
            elif path.suffix == ".jsonl":
                records = load_records(path)
                if records:
                    result["wafer_map"] = records[0].get("waferMap", records[0].get("wafer_map"))
    return result
