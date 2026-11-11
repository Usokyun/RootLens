"""Check the shipped demo catalog and prepare optional local assets.

From backend/: uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec
Add --download for the chosen scene’s pinned optional raw assets.
This command never regenerates the catalog, graph packages, or exported Evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
SMALL = ROOT / "data/demo/two_loop"
RUNTIME = ROOT / "runs/two_loop_demo"
PUBLIC = ROOT / "runs/refactor_m2_m6/public"
MVTEC_MODEL_MANIFEST = "runs/two_loop_demo/mvtec-demo-models.json"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def hydrate_process_support(frames: list, sample: dict) -> None:
    """Rebuild optional arrays into manifest destinations, never saved Frame URIs."""
    from kgtracevis.adapters.batch import evidence_from_records
    from kgtracevis.adapters.unified import evidence_frames
    from kgtracevis.producers.tep_records import build_tep_dat_records

    def window(frame):
        scope = next(s for s in frame.scopes if s.scope_id == frame.task.scope_id)
        return scope.sample_start, scope.sample_end, scope.sampling_seconds

    targets = {
        (asset.get("frame_case_id"), asset.get("case_asset_id") or asset["frame_asset_id"]): ROOT
        / asset["path"]
        for asset in sample["supporting_assets"]
    }
    cases = {frame.case_id for frame in frames}
    expected = {(case_id, "window") for case_id in cases} | {(None, "normal"), (None, "scaler")}
    if (
        set(targets) != expected
        or len(set(targets.values())) != len(expected)
        or any(not path.resolve().is_relative_to(RUNTIME.resolve()) for path in targets.values())
    ):
        raise ValueError("TEP 配套文件须按 Frame ID 绑定各窗口和一组受管正常参考。")
    normal, sequence = ROOT / sample["normal_reference"]["path"], ROOT / sample["raw_input"]["path"]
    if all(path.is_file() for path in targets.values()) or not all(
        path.is_file() for path in (normal, sequence)
    ):
        return

    windows = [window(frame) for frame in frames]
    ranges = [(start, end) for start, end, _ in windows]
    intervals = {interval for _, _, interval in windows}
    reference_ids = {frame.task.reference_id for frame in frames}
    if len(intervals) != 1 or len(reference_ids) != 1 or None in intervals | reference_ids:
        raise ValueError("同一 TEP 样例须保存统一采样间隔和正常参考。")
    if len(set(ranges)) != len(frames):
        raise ValueError("同一 TEP 样例的时间窗口不能重复。")
    output = targets[(frames[0].case_id, "window")].parent / "reconstructed"
    records = build_tep_dat_records(
        normal,
        sequence,
        output_dir=output,
        windows=ranges,
        sampling_interval_seconds=intervals.pop(),
    )
    measured = {
        window(frame): frame
        for evidence in evidence_from_records(records, dataset="tep")
        for frame in evidence_frames(evidence)
    }
    numeric_observations = 0
    sources = {}
    for frame in frames:
        start, end, _ = window(frame)
        actual = {
            (o.subject_id, o.feature_id): o.value.model_dump(mode="json")
            for o in measured[window(frame)].observations
            if o.status == "observed" and o.value is not None
        }
        for o in frame.observations:
            if (
                o.status != "observed"
                or o.value is None
                or o.value.kind not in {"number", "boolean"}
            ):
                continue
            saved = o.value.model_dump(mode="json")
            value = actual.get((o.subject_id, o.feature_id))
            equal = value is not None and (
                (
                    value["kind"] == "number"
                    and value["unit"] == saved["unit"]
                    and math.isclose(value["number"], saved["number"], rel_tol=1e-8, abs_tol=1e-8)
                )
                if o.value.kind == "number"
                else value == saved
            )
            if not equal:
                raise ValueError(f"重建的 TEP 观测与保存值不同：{frame.case_id} / {o.obs_id}")
            numeric_observations += 1
        sources[(frame.case_id, "window")] = output / f"window_{start}_{end}.npy"
    profile_path = output / "normal_reference_profile.json"
    profile = json.loads(profile_path.read_text())
    profile["reference_id"] = reference_ids.pop()
    write_json(profile_path, profile)
    sources[(None, "normal")] = output / "normal_reference.csv"
    sources[(None, "scaler")] = profile_path
    for key, source in sources.items():
        target = targets[key]
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    write_json(
        output / "reconstruction.json",
        {
            "sample_id": sample["sample_id"],
            "frame_cases": [frame.case_id for frame in frames],
            "reference_id": profile["reference_id"],
            "source": sample["raw_input"]["path"],
            "normal": sample["normal_reference"]["path"],
            "numeric_observations_matched": numeric_observations,
            "tolerance": 1e-8,
        },
    )


def read_manifest(dataset: str | None = None) -> dict:
    manifest = json.loads((SMALL / "manifest.json").read_text())
    if dataset is not None:
        manifest["demos"] = [demo for demo in manifest["demos"] if demo["dataset"] == dataset]
    return manifest


def frames_from_asset(asset: dict) -> list:
    from kgtracevis.schema.unified_evidence import EvidenceFrame

    payload = json.loads((ROOT / asset["path"]).read_text())
    frames = payload.get("frames", [payload]) if isinstance(payload, dict) else payload
    if not isinstance(frames, list) or not frames:
        raise ValueError(f"没有可复算的 EvidenceFrame：{asset['path']}")
    return [EvidenceFrame.model_validate(frame) for frame in frames]


def verify_transfer(path: Path, asset: dict) -> None:
    """Check explicit integrity pins for downloaded model and data files."""
    if path.stat().st_size == asset["size_bytes"]:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() == asset["sha256"]:
            return
    raise ValueError(f"文件不符合固定发布版本：{path}；未覆盖现有文件。")


def prepare_transfer(asset: dict, *, cached: Path | None = None) -> Path:
    destination = ROOT / (asset.get("local_path") or asset["path"])
    if not destination.resolve().is_relative_to(RUNTIME.resolve()):
        raise ValueError(f"不能在受管运行目录之外写入演示文件：{destination}")
    if destination.is_file():
        verify_transfer(destination, asset)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Partial or mismatched downloads are never published, even for a cached local source.
    with NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        if cached is not None and cached.is_file():
            shutil.copyfile(cached, temporary)
        else:
            with urllib.request.urlopen(asset["source_url"], timeout=120) as response:
                with temporary.open("wb") as out:
                    shutil.copyfileobj(response, out)
        verify_transfer(temporary, asset)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def prepare_bottle_checkpoint(demo: dict) -> None:
    (model,) = demo["models"]
    registry = ROOT / MVTEC_MODEL_MANIFEST
    config = {
        "schema_version": "rootlens-mvtec-models.v1",
        "objects": {"bottle": {"patchcore": {"checkpoint": model["local_path"]}}},
    }
    if registry.exists() and json.loads(registry.read_text()) != config:
        raise ValueError(f"演示模型登记已存在且内容不同：{registry}；未覆盖现有登记。")
    prepare_transfer(model, cached=PUBLIC / "bottle_patchcore.ckpt")
    if not registry.exists():
        write_json(registry, config)


def prepare_tep(demo: dict, *, download: bool) -> None:
    (sample,) = demo["samples"]
    if download:
        prepare_transfer(sample["raw_input"], cached=PUBLIC / "tep_d04_te.dat")
        prepare_transfer(sample["normal_reference"], cached=PUBLIC / "tep_d00.dat")
    hydrate_process_support(frames_from_asset(sample["evidence"]), sample)


def prepare_wafer(demo: dict, *, download: bool) -> None:
    if not download:
        return
    import numpy as np
    import pandas as pd

    from scripts.prepare_public_wafer_demo import DataOnlyUnpickler

    (sample,) = demo["samples"]
    (model,) = demo["models"]
    source = sample["raw_source"]
    row_id = source["row_id"]
    table_path = prepare_transfer(source, cached=PUBLIC / "wm811k_test.pkl")
    with table_path.open("rb") as handle:
        table = DataOnlyUnpickler(handle).load()
    if not isinstance(table, pd.DataFrame) or not table.index.is_unique:
        raise ValueError("WM811K 公共表须有唯一原始行索引。")
    row = np.asarray(table.at[int(row_id), "waferMap"])
    if row.shape != tuple(source["shape"]) or not np.isin(row, [0, 1, 2]).all():
        raise ValueError(f"WM811K 行 {row_id} 不是预期的原始 0/1/2 网格。")
    clean = {"wafer_id": row_id, "case_id": f"wm811k_{row_id}", "waferMap": row.tolist()}
    raw = ROOT / sample["raw_input"]["path"]
    if not raw.resolve().is_relative_to(RUNTIME.resolve()):
        raise ValueError("WM811K 原始样本须位于受管本地运行目录。")
    if raw.exists():
        if json.loads(raw.read_text()) != clean:
            raise ValueError(f"已有原始样本与固定上游行不同：{raw}；未覆盖。")
    else:
        # Only identity and original cells reach the classifier; never copy native labels.
        raw.parent.mkdir(parents=True, exist_ok=True)
        temporary = raw.with_suffix(".jsonl.tmp")
        temporary.write_text(json.dumps(clean) + "\n")
        temporary.replace(raw)
    prepare_transfer(model, cached=PUBLIC / "wm811k_resnet.pt")


def prepare(download: bool = False, dataset: str | None = None) -> dict:
    manifest = read_manifest(dataset)
    for demo in manifest["demos"]:
        if demo["dataset"] == "mvtec" and download:
            prepare_bottle_checkpoint(demo)
        elif demo["dataset"] == "tep":
            prepare_tep(demo, download=download)
        elif demo["dataset"] == "wafer":
            prepare_wafer(demo, download=download)
    return manifest


def check(manifest: dict) -> dict:
    from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage

    checked, missing, raw_models, raw_inputs, media = [], [], [], [], []

    def status(asset):
        path = asset.get("local_path") or asset["path"]
        return {"path": path, "available": (ROOT / path).is_file()}

    for demo in manifest["demos"]:
        for item in demo["materials"] + demo.get("authoring_notes", []):
            if not (ROOT / item["path"]).is_file():
                missing.append(item["path"])
        raw_models.extend(status(model) for model in demo["models"])
        graph = ROOT / demo["working_graph"]["path"]
        package = UnifiedWorkingGraphPackage.model_validate_json(graph.read_text())
        for sample in demo["samples"]:
            frame_asset = sample["evidence"]
            if (ROOT / frame_asset["path"]).is_file():
                frames = frames_from_asset(frame_asset)
                checked.append(
                    {
                        "sample_id": sample["sample_id"],
                        "frames": len(frames),
                        "observations": sum(len(frame.observations) for frame in frames),
                        "graph_nodes": len(package.nodes),
                        "graph_edges": len(package.edges),
                    }
                )
            else:
                missing.append(frame_asset["path"])
            inputs = [sample[k] for k in ("raw_input", "normal_reference") if k in sample]
            for asset in inputs:
                availability = status(asset)
                raw_inputs.append(availability)
                if asset.get("storage_scope") == "repository" and not availability["available"]:
                    missing.append(asset["path"])
            media.extend(status(asset) for asset in sample.get("supporting_assets", []))
    return {
        "validated": checked,
        "missing_assets": sorted(set(missing)),
        "raw_inputs": raw_inputs,
        "optional_raw_models": raw_models,
        "optional_media": media,
    }


def build_knowledge(dataset: str, output: Path) -> dict:
    """Call the configured client with original public material, never sample measurements."""
    from kgtracevis.adapters.unified_capabilities import capability_manifest
    from kgtracevis.source_kg_compiler.llm import OpenAICompatibleSourceKGLLM
    from kgtracevis.source_kg_compiler.material_parser import parse_material
    from kgtracevis.source_kg_compiler.unified import compile_unified_knowledge

    scenario = "mvtec" if dataset == "bottle" else dataset
    (demo,) = read_manifest(scenario)["demos"]
    capability = capability_manifest(demo["capability_id"])
    units = [
        unit
        for source in demo["materials"]
        for unit in parse_material(
            ROOT / source["path"],
            source_id=source["asset_id"],
            scenario=scenario,
            original_uri=source.get("source_url"),
        ).units
    ]
    llm = OpenAICompatibleSourceKGLLM(max_tokens=16000)
    package = compile_unified_knowledge(
        units,
        capability,
        llm_client=llm,
        output_dir=output,
        title=f"双闭环演示 · {dataset} · 原始资料LLM构图",
        dataset=scenario,
        max_repairs=1,
        progress=lambda stage, message, **details: print(
            json.dumps({"stage": stage, "message": message, **details}, ensure_ascii=False),
            flush=True,
        ),
    )
    return {
        "package": str(output / "working-graph.v2.json"),
        "nodes": len(package.nodes),
        "edges": len(package.edges),
        "llm_calls": llm.calls,
        "llm_tokens": llm.total_tokens,
    }


def recompute(manifest: dict, output: Path) -> list[dict]:
    """Recompute each intermediate input; no database, model, or native label is read."""
    from kgtracevis.core.rootkgd_reasoner import RootKGDReasoner
    from kgtracevis.core.unified_reasoner import UnifiedReasoner
    from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage

    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for demo in manifest["demos"]:
        package = UnifiedWorkingGraphPackage.model_validate_json(
            (ROOT / demo["working_graph"]["path"]).read_text()
        )
        for sample in demo["samples"]:
            frames = frames_from_asset(sample["evidence"])
            for reasoner_id in sample["reasoner_ids"]:
                reasoner = RootKGDReasoner if reasoner_id == "tep_rootkgd" else UnifiedReasoner
                engine = reasoner(package.knowledge)
                for index, frame in enumerate(frames, start=1):
                    result = engine.analyze(frame, top_k=8)
                    suffix = f"-frame-{index}" if len(frames) > 1 else ""
                    filename = f"{sample['sample_id']}-{reasoner_id}{suffix}.json"
                    write_json(output / filename, result)
                    rows.append(
                        {
                            "sample_id": sample["sample_id"],
                            "reasoner_id": reasoner_id,
                            "outcome": result["outcome"],
                            "result": filename,
                            "path_count": len(result.get("top_k_paths", [])),
                            "candidates": [
                                {k: r[k] for k in ("candidate_id", "rank", "score")}
                                for r in result["ranked_root_causes"]
                            ],
                        }
                    )
    write_json(output / "summary.json", {"cases": rows})
    return rows


def refine_tep(original: Path, output: Path) -> dict:
    """Curate a source-only LLM proposal; no sample, fault label, or model result is read."""
    from kgtracevis.adapters.unified_capabilities import process_capabilities
    from kgtracevis.source_kg_compiler.material_parser import ParsedSourceBundle
    from kgtracevis.source_kg_compiler.unified import compile_unified_knowledge
    from kgtracevis.source_kg_compiler.unified_blueprint import KnowledgeBlueprint

    original = original.resolve()
    blueprint = KnowledgeBlueprint.model_validate_json((original / "proposal-1.txt").read_text())
    units = ParsedSourceBundle.model_validate_json(
        (original / "source_units.json").read_text()
    ).units
    before = blueprint.model_dump(mode="json")
    # Unknown disturbance names are not diagnoses. Their unsupported observations stay available.
    blueprint.signatures = [
        s for s in blueprint.signatures if s.signature_key != "sig_valve_actuation_unknown"
    ]
    notes = [
        {
            "change": "remove_uninterpretable_generic_unknown_candidates",
            "reason": "原程序把这些扰动标为Unknown；没有明确可诊断机理，不生成兜底原因。",
        }
    ]

    def unit_with(marker):
        return next(u.unit_id for u in units if marker in u.content_text)

    # The original inlet mass-flow formula has no direct temperature factor.
    # Keep source-supported energy-balance effects instead of a speculative D-feed mass effect.
    for signature in blueprint.signatures:
        if signature.signature_key == "sig_feed_thermal_boundary":
            conditions = []
            for channel, label in (("xmeas_9", "反应器温度"), ("xmeas_6", "反应器进料速率")):
                from kgtracevis.source_kg_compiler.unified_blueprint import ConditionDraft

                conditions.append(
                    ConditionDraft.model_validate(
                        {
                            "label": f"{label} {channel.upper()} 标准化均值偏移",
                            "feature_id": "statistics.mean_z",
                            "op": "abs_gte",
                            "operand": {"kind": "number", "number": 2.0, "unit": "1"},
                            "subject_external_id": channel,
                            "assertion": {
                                "text": (
                                    "进料热边界通过焓/流量与反应器能量平衡相关；"
                                    "2 z为声明的演示阈值，不是原程序诊断阈值。"
                                ),
                                "origin": "declared_demo_heuristic",
                                "source_unit_id": unit_with("YP(9)=HST(7)*FTM(7)"),
                                "parameter_origin": "declared_demo_heuristic",
                            },
                        }
                    )
                )
            signature.conditions = conditions
            notes.append(
                {
                    "change": "replace_feed_thermal_mass_flow_shortcut",
                    "reason": (
                        "删除原LLM对D进料质量流量的过强解释；"
                        "改用能量平衡与反应器进料关联，仍是可检验的推断。"
                    ),
                }
            )
        if signature.signature_key == "sig_feed_composition_shift":
            # Feed composition is explicitly measured by the stream-6 gas analyzer.
            signature.conditions = [
                c for c in signature.conditions if c.subject_external_id == "xmeas_23"
            ]
            prototype = signature.conditions[0]
            for channel, component in (("xmeas_24", "B"), ("xmeas_25", "C")):
                signature.conditions.append(
                    prototype.model_copy(
                        deep=True,
                        update={
                            "label": f"反应器进料组分{component} {channel.upper()} 标准化均值偏移",
                            "subject_external_id": channel,
                            "assertion": prototype.assertion.model_copy(
                                update={
                                    "text": (
                                        f"原程序进料分析包含组分{component}；2 z为演示阈值，"
                                        "组成扰动不要求全部组分同时变化。"
                                    ),
                                }
                            ),
                        },
                    )
                )
            notes.append(
                {
                    "change": "bind_feed_composition_to_measured_composition_channels",
                    "reason": "流量不是组成；使用原程序明确列出的进料A/B/C组分测量，并保留ANY。",
                }
            )
        for condition in signature.conditions:
            if condition.feature_id == "statistics.slope_z":
                condition.feature_id = "statistics.mean_z"
                condition.operand = condition.operand.model_copy(
                    update={"number": 2.0, "unit": "1"}
                )
                condition.label = condition.label.replace("斜率", "均值")
                notes.append(
                    {
                        "change": "uniform_standardized_shift_heuristic",
                        "reason": (
                            "不新增任意0.05斜率门槛；各回路统一采用2 z偏移，"
                            "回路差异来自图的变量可达性。"
                        ),
                    }
                )
            # Numerical association cutoffs are never represented as program constants.
            condition.assertion.origin = "declared_demo_heuristic"
            condition.assertion.parameter_origin = "declared_demo_heuristic"
    blueprint.title = "TEP原程序来源 · 分回路知识（LLM蓝图演示适配）"
    capability = process_capabilities().model_copy(
        update={"recommended_max_candidates": 8, "max_signatures": 16}
    )
    package = compile_unified_knowledge(
        units,
        capability,
        llm_client=None,
        stored_blueprint=blueprint,
        output_dir=output,
        title=blueprint.title,
        dataset="tep",
    )
    refinement = {
        "original_directory": str(original.relative_to(ROOT)),
        "original_proposal": "proposal-1.txt",
        "no_sample_inputs_read": True,
        "basis": "原始程序/控制资料与可测能力；不按故障ID或测试数值选择阈值。",
        "changes": notes,
        "before": before,
        "after": blueprint.model_dump(mode="json"),
    }
    write_json(output / "demo-refinement.json", refinement)
    return {
        "package": str(output / "working-graph.v2.json"),
        "nodes": len(package.nodes),
        "edges": len(package.edges),
        "candidates": len(package.knowledge.hypotheses),
        "predicates": len(package.knowledge.observable_definitions),
        "refinement": str(output / "demo-refinement.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="fetch missing public assets only")
    parser.add_argument(
        "--dataset", choices=("mvtec", "tep", "wafer"), help="prepare one scene only"
    )
    parser.add_argument(
        "--build",
        choices=("bottle", "tep", "wafer"),
        help="actually call configured LLM with original public material",
    )
    parser.add_argument(
        "--build-output", type=Path, help="new output directory for the actual LLM build"
    )
    parser.add_argument(
        "--recompute-output",
        type=Path,
        help="new directory for all intermediate-Evidence reasoning results",
    )
    parser.add_argument("--refine-tep", type=Path, help="source-only LLM build directory to curate")
    args = parser.parse_args()
    manifest = prepare(download=args.download, dataset=args.dataset)
    report = check(manifest)
    write_json(RUNTIME / "preparation-report.json", report)
    print(json.dumps({"manifest": str(SMALL / "manifest.json"), **report}, ensure_ascii=False))
    if args.build:
        if not args.build_output:
            parser.error("--build requires a new --build-output directory")
        print(json.dumps(build_knowledge(args.build, args.build_output), ensure_ascii=False))
    if args.recompute_output:
        print(json.dumps(recompute(manifest, args.recompute_output), ensure_ascii=False))
    if args.refine_tep:
        if not args.build_output:
            parser.error("--refine-tep requires a new --build-output directory")
        print(json.dumps(refine_tep(args.refine_tep, args.build_output), ensure_ascii=False))


if __name__ == "__main__":
    main()
