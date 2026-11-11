"""Check the shipped demo catalog and prepare optional local assets.

From backend/: uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec
Add --download to fetch the pinned Bottle PatchCore checkpoint for raw input.
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
EARLIER = ROOT / "runs/unified_reasoning"
PUBLIC = ROOT / "runs/refactor_m2_m6/public"

TEP_BASE = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/"
PREPARATION_ERRORS: list[dict] = []
MVTEC_MODEL_MANIFEST = "runs/two_loop_demo/mvtec-demo-models.json"
WAFER_INPUT_URL = (
    "https://huggingface.co/datasets/lslattery/wafer-defect-detection/resolve/main/test.pkl"
)
WAFER_SAMPLE_IDS = {
    "wafer-nearfull": "248536",
    "wafer-normal": "5",
    "wafer-pattern-disagreement": "31707",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def stage(source: Path, destination: Path, *, url: str | None, download: bool) -> Path:
    """Never replace an existing raw asset or retrieve private/user material."""
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, destination)
    elif download and url:
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as out:
                shutil.copyfileobj(response, out)
            temporary.rename(destination)
        except OSError as exc:
            PREPARATION_ERRORS.append(
                {"asset": str(destination.relative_to(ROOT)), "url": url, "error": str(exc)}
            )
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def hydrate_process_support(frame: dict, sample: dict) -> None:
    """Restore omitted numerical assets from the same public input and matched reference."""
    assets = {a["asset_id"]: a for a in frame["assets"]}
    if sample["dataset"] != "tep" or all(
        (ROOT / assets[name]["uri"]).is_file() for name in ("window", "normal", "scaler")
    ):
        return
    normal, sequence = ROOT / sample["normal_reference"]["path"], ROOT / sample["raw_input"]["path"]
    if not normal.is_file() or not sequence.is_file():
        return
    from kgtracevis.adapters.batch import evidence_from_records
    from kgtracevis.adapters.unified import evidence_frames
    from kgtracevis.producers.tep_records import build_tep_dat_records

    scope = next(s for s in frame["scopes"] if s["scope_id"] == frame["task"]["scope_id"])
    output = RUNTIME / f"prepared_process/{sample['sample_id']}"
    records = build_tep_dat_records(
        normal,
        sequence,
        output_dir=output,
        windows=[(scope["sample_start"], scope["sample_end"])],
        sampling_interval_seconds=180,
    )
    measured = evidence_frames(evidence_from_records(records, dataset="tep")[0])[0]
    actual = {
        (o.subject_id, o.feature_id): o.value
        for o in measured.observations
        if o.status == "observed" and o.value is not None and o.value.kind in {"number", "boolean"}
    }
    for observation in frame["observations"]:
        value = observation.get("value")
        if (
            observation["status"] != "observed"
            or not value
            or value["kind"] not in {"number", "boolean"}
        ):
            continue
        current = actual[(observation["subject_id"], observation["feature_id"])].model_dump(
            mode="json"
        )
        equal = (
            (
                math.isclose(current["number"], value["number"], rel_tol=1e-8, abs_tol=1e-8)
                and current["unit"] == value["unit"]
            )
            if value["kind"] == "number"
            else current == value
        )
        if not equal:
            raise ValueError(
                f"reconstructed normal model differs from saved Evidence: {sample['sample_id']}"
            )
    profile_path = output / "normal_reference_profile.json"
    profile = json.loads(profile_path.read_text())
    profile["reference_id"] = frame["task"]["reference_id"]
    write_json(profile_path, profile)
    sources = {
        "window": output / f"window_{scope['sample_start']}_{scope['sample_end']}.npy",
        "normal": output / "normal_reference.csv",
        "scaler": profile_path,
    }
    for name, source in sources.items():
        destination = ROOT / assets[name]["uri"]
        if not destination.resolve().is_relative_to(RUNTIME):
            raise ValueError("demo numerical support must stay in the managed runtime directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    write_json(
        output / "reconstruction.json",
        {
            "sample_id": sample["sample_id"],
            "reference_id": frame["task"]["reference_id"],
            "source": sample["raw_input"]["path"],
            "normal": sample["normal_reference"]["path"],
            "numeric_observations_matched": len(actual),
            "tolerance": 1e-8,
            "note": (
                "Original scalar Evidence unchanged; "
                "missing arrays/scaler rebuilt from the same public data."
            ),
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


def verified_checkpoint(path: Path, model: dict) -> None:
    # A third-party binary is executable model input: verify the published LFS digest,
    # not only the filename, before making it selectable by the backend.
    if path.stat().st_size == model["size_bytes"]:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() == model["sha256"]:
            return
    raise ValueError(f"PatchCore 权重不符合固定发布版本：{path}；未覆盖现有文件。")


def prepare_bottle_checkpoint(demo: dict) -> None:
    (model,) = demo["models"]
    checkpoint = ROOT / model["local_path"]
    registry = ROOT / MVTEC_MODEL_MANIFEST
    config = {
        "schema_version": "rootlens-mvtec-models.v1",
        "objects": {"bottle": {"patchcore": {"checkpoint": model["local_path"]}}},
    }
    if registry.exists() and json.loads(registry.read_text()) != config:
        raise ValueError(f"演示模型登记已存在且内容不同：{registry}；未覆盖现有登记。")
    if checkpoint.is_file():
        verified_checkpoint(checkpoint, model)
    else:
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        # Publish atomically only after integrity validation; partial downloads are never usable.
        with NamedTemporaryFile(dir=checkpoint.parent, suffix=".part", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with urllib.request.urlopen(model["source_url"], timeout=120) as response:
                with temporary.open("wb") as out:
                    shutil.copyfileobj(response, out)
            verified_checkpoint(temporary, model)
            temporary.replace(checkpoint)
        finally:
            temporary.unlink(missing_ok=True)
    if not registry.exists():
        write_json(registry, config)


def prepare_tep(demo: dict, *, download: bool) -> None:
    for material in demo["materials"]:
        original = material["source_url"].rsplit("/", 1)[-1]
        stage(
            EARLIER / "public" / original,
            ROOT / material["path"],
            url=material["source_url"],
            download=download,
        )
    for sample in demo["samples"]:
        for asset in (sample["raw_input"], sample["normal_reference"]):
            original = asset["source_url"].rsplit("/", 1)[-1]
            source = PUBLIC / f"tep_{original}"
            if not source.is_file():
                source = EARLIER / "public" / f"tep_{original}"
            stage(source, ROOT / asset["path"], url=asset["source_url"], download=download)
        for frame in frames_from_asset(sample["evidence"]):
            hydrate_process_support(frame.model_dump(mode="json"), sample)


def prepare_wafer(demo: dict, *, download: bool) -> None:
    for model in demo["models"]:
        destination = ROOT / model["path"]
        stage(
            PUBLIC / destination.name,
            destination,
            url=model["source_url"],
            download=download,
        )
    excerpt, model_card = demo["materials"]
    stage(
        PUBLIC / "wafer_model_card.md",
        ROOT / model_card["path"],
        url=model_card["source_url"] + "/raw/main/README.md",
        download=download,
    )
    excerpt_path = stage(
        EARLIER / "public/wm811k-paper-p3-p4.txt",
        ROOT / excerpt["path"],
        url=None,
        download=False,
    )
    if download and not excerpt_path.is_file():
        from kgtracevis.source_kg_compiler.material_parser import parse_material

        paper = stage(
            EARLIER / "public/wm811k-original.pdf",
            RUNTIME / "materials/wm811k-original.pdf",
            url=excerpt["source_url"],
            download=True,
        )
        if paper.is_file():
            parsed = parse_material(paper, source_id="wm811k-original-paper", scenario="wafer")
            selected = [u.content_text for u in parsed.units if u.source_span.get("page") in (3, 4)]
            if selected:
                excerpt_path.write_text("\n\n".join(selected))

    needs_raw = [s for s in demo["samples"] if not (ROOT / s["raw_input"]["path"]).is_file()]
    source = PUBLIC / "wafer_samples.jsonl"
    rows = {}
    if needs_raw and source.is_file():
        with source.open() as stream:
            rows = {str(row["wafer_id"]): row["waferMap"] for row in map(json.loads, stream)}
    wanted = {WAFER_SAMPLE_IDS[s["sample_id"]] for s in needs_raw}
    if wanted - rows.keys() and download:
        from scripts.prepare_public_wafer_demo import DataOnlyUnpickler

        table = stage(
            PUBLIC / "wm811k_test.pkl",
            RUNTIME / "sources/wm811k_test.pkl",
            url=WAFER_INPUT_URL,
            download=True,
        )
        if table.is_file():
            with table.open("rb") as handle:
                dataframe = DataOnlyUnpickler(handle).load()
            for index, row in dataframe.iterrows():
                if str(index) in wanted:
                    rows[str(index)] = row["waferMap"].tolist()
    for sample in demo["samples"]:
        sample_id = sample["sample_id"]
        wafer_id = WAFER_SAMPLE_IDS[sample_id]
        raw = ROOT / sample["raw_input"]["path"]
        if not raw.is_file() and wafer_id in rows:
            raw.parent.mkdir(parents=True, exist_ok=True)
            # Original labels stay in the source table, never in model input.
            raw.write_text(
                json.dumps(
                    {
                        "wafer_id": wafer_id,
                        "case_id": f"wm811k_{wafer_id}",
                        "waferMap": rows[wafer_id],
                    }
                )
                + "\n"
            )
        (support,) = sample["supporting_assets"]
        grid_path = ROOT / support["path"]
        if not grid_path.is_file() and raw.is_file():
            payload = json.loads(raw.read_text())
            grid = payload.get("waferMap", payload.get("wafer_map"))
            if grid is not None:
                write_json(grid_path, grid)


def prepare(download: bool = False, dataset: str | None = None) -> dict:
    PREPARATION_ERRORS.clear()
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

    checked, missing, raw_models = [], [], []
    for demo in manifest["demos"]:
        for item in demo["materials"]:
            if not (ROOT / item["path"]).is_file():
                missing.append(item["path"])
        for model in demo["models"]:
            path = model.get("local_path") or model["path"]
            raw_models.append({"path": path, "available": (ROOT / path).is_file()})
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
            for item in inputs + sample.get("supporting_assets", []):
                if not (ROOT / item["path"]).is_file():
                    missing.append(item["path"])
    return {
        "validated": checked,
        "missing_assets": sorted(set(missing)),
        "optional_raw_models": raw_models,
        "preparation_errors": list(PREPARATION_ERRORS),
    }


def build_knowledge(dataset: str, output: Path) -> dict:
    """Call the configured client with original public material, never sample measurements."""
    from kgtracevis.adapters.unified_capabilities import capability_manifest
    from kgtracevis.source_kg_compiler.llm import OpenAICompatibleSourceKGLLM
    from kgtracevis.source_kg_compiler.material_parser import parse_material
    from kgtracevis.source_kg_compiler.unified import compile_unified_knowledge

    capability_id = {
        "bottle": "visual-region-v2",
        "tep": "process-window-v2",
        "wafer": "spatial-grid-v2",
    }[dataset]
    capability = capability_manifest(capability_id)
    scenario = "mvtec" if dataset == "bottle" else dataset
    if dataset == "bottle":
        (source,) = read_manifest("mvtec")["demos"][0]["materials"]
        units = parse_material(
            ROOT / source["path"],
            source_id=source["asset_id"],
            scenario=scenario,
            original_uri=source["source_url"],
        ).units
    elif dataset == "tep":
        units = []
        for file in ("teprob.f", "temain_mod.f"):
            units.extend(
                parse_material(
                    RUNTIME / f"materials/{file}.txt",
                    source_id=f"braatz:{file}",
                    scenario=scenario,
                    original_uri=TEP_BASE + file,
                ).units
            )
        capability = capability.model_copy(
            update={
                "recommended_max_candidates": 8,
                "max_signatures": 16,
                "notes": capability.notes + "\nDemo authoring refinement: use circuit-specific "
                "mechanisms and exact channels from the original equations. Distinguish reactor "
                "and condenser heat-removal circuits rather than merging unrelated circuits. "
                "Retain feed composition, feed thermal boundary, reaction kinetics and valve "
                "actuation alternatives supported by source. Explain paths to multiple source-"
                "connected measured or manipulated channels, including composition analyzers "
                "where the equations support them. Do not require all connected variables to "
                "shift at once: closed-loop compensation may move valves while holding "
                "temperature. "
                "Do not force full 52-channel coverage. Use mean_z abs>=2 as one uniform declared "
                "demo heuristic if no source numeric diagnostic cutoff exists. Never infer a "
                "channel-specific direction or diagnostic threshold from disturbance numbers. "
                "Conditions' numeric-cutoff assertions must be declared_demo_heuristic; the "
                "mechanism/channel association may be llm_proposed when inferred from equations. "
                "Use short Chinese labels with original channel codes retained. The source "
                "controller comments contain copy/paste mislabels: prefer actual assignments, "
                "e.g. CONTRL10 reads XMEAS(21), CONTRL18 reads XMEAS(9) and adjusts SETPT(10).",
            }
        )
    else:
        units = parse_material(
            RUNTIME / "materials/wafer-model-card.md",
            source_id="radai-wm811k-model-card",
            scenario=scenario,
            original_uri="https://huggingface.co/radai-agent/radai-wm811k-defect-detection",
        ).units
    llm = OpenAICompatibleSourceKGLLM(max_tokens=16000)
    package = compile_unified_knowledge(
        units,
        capability,
        llm_client=llm,
        output_dir=output,
        title=f"双闭环演示 · {dataset} · 原始资料LLM构图",
        dataset=scenario,
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
