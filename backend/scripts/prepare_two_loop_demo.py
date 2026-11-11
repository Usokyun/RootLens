"""Check the graded demo catalog and prepare its optional local raw assets.

From backend/: uv run --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec
Add --download to reuse or obtain the chosen scene's pinned raw assets.
This command never changes the catalog, graph packages, or exported Evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SMALL = ROOT / "data/demo/graded_rca"
RUNTIME = ROOT / "runs/graded_rca_demo"
PUBLIC = ROOT / "runs/refactor_m2_m6/public"
TEP_RAW = ROOT / "runs/two_loop_demo/raw/tep"
MVTEC_MODEL_MANIFEST = "runs/graded_rca_demo/mvtec-models.json"


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(value)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def attachment_targets(sample: dict, expected: set) -> dict:
    targets = {}
    for asset in sample.get("supporting_assets", []):
        case, scoped = asset.get("frame_case_id"), asset.get("case_asset_id")
        global_id = asset.get("frame_asset_id")
        if (case is None) != (scoped is None) or bool(scoped) == bool(global_id):
            raise ValueError("演示附件须明确声明 Frame 对应的资源标识。")
        key = case, scoped or global_id
        if key in targets:
            raise ValueError("不能重复指定同一 Frame 的同一附件。")
        targets[key] = (ROOT / asset["path"]).resolve()
    if (
        set(targets) != expected
        or len(set(targets.values())) != len(expected)
        or any(not p.is_relative_to(RUNTIME.resolve()) for p in targets.values())
    ):
        raise ValueError("附件须完整对应发布 Frame，并使用不同的受管运行路径。")
    return targets


def _tep_window(frame):
    scope = next(s for s in frame.scopes if s.scope_id == frame.task.scope_id)
    return scope.sample_start, scope.sample_end, scope.sampling_seconds


def _tep_archived_sources(frames, ranges, expected, *, normal, sequence):
    """Prefer actual saved producer media, but only when it matches the pinned raw slices."""
    import numpy as np

    by_id = {f.case_id: f for f in frames}
    archives = (ROOT / "runs/two_loop_tasks").resolve()
    sources = {}
    for case, asset_id in expected:
        frame = by_id[case] if case is not None else frames[0]
        asset = next((a for a in frame.assets if a.asset_id == asset_id), None)
        if asset is None:
            return None
        path = (ROOT / asset.uri).resolve()
        if not path.is_relative_to(archives) or not path.is_file():
            return None
        sources[(case, asset_id)] = path
    try:
        raw = np.loadtxt(sequence)
        ref = np.loadtxt(normal)
        if ref.shape[0] == 52:
            ref = ref.T
        for frame, (start, end) in zip(frames, ranges, strict=True):
            saved = np.load(sources[(frame.case_id, "window")], allow_pickle=False)
            if not np.array_equal(saved, raw[start - 1 : end]):
                return None
        profile = json.loads(sources[(None, "scaler")].read_text())
        if profile["reference_id"] != frames[0].task.reference_id or not np.array_equal(
            np.loadtxt(sources[(None, "normal")], delimiter=",", skiprows=1), ref
        ):
            return None
    except (KeyError, OSError, ValueError):
        return None
    return sources


def hydrate_process_support(frames: list, sample: dict) -> None:
    """Rebuild optional arrays into manifest destinations, never saved Frame URIs."""
    from kgtracevis.adapters.batch import evidence_from_records
    from kgtracevis.adapters.unified import evidence_frames
    from kgtracevis.producers.tep_records import build_tep_dat_records

    cases = {frame.case_id for frame in frames}
    expected = {(case_id, "window") for case_id in cases} | {(None, "normal"), (None, "scaler")}
    targets = attachment_targets(sample, expected)
    normal, sequence = ROOT / sample["normal_reference"]["path"], ROOT / sample["raw_input"]["path"]
    windows = [_tep_window(frame) for frame in frames]
    ranges = [(start, end) for start, end, _ in windows]
    intervals = {interval for _, _, interval in windows}
    reference_ids = {frame.task.reference_id for frame in frames}
    if len(intervals) != 1 or len(reference_ids) != 1 or None in intervals | reference_ids:
        raise ValueError("同一 TEP 样例须保存统一采样间隔和正常参考。")
    if (
        len(set(ranges)) != len(frames)
        or [list(pair) for pair in ranges] != sample["raw_options"]["windows"]
        or intervals != {sample["raw_options"]["sampling_seconds"]}
    ):
        raise ValueError("TEP 的原始入口窗口及采样间隔须与发布 Frame 一致。")

    def publish(sources):
        for key, source in sources.items():
            target = targets[key]
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise ValueError(f"已有 TEP 附件不匹配：{target}；未覆盖。")
        for key, source in sources.items():
            target = targets[key]
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    archived = _tep_archived_sources(frames, ranges, expected, normal=normal, sequence=sequence)
    if archived is not None:
        publish(archived)
        return

    with TemporaryDirectory(prefix="rootlens-tep-support-") as staging:
        output = Path(staging)
        records = build_tep_dat_records(
            normal,
            sequence,
            output_dir=output,
            windows=ranges,
            sampling_interval_seconds=intervals.pop(),
        )
        measured = {
            _tep_window(frame): frame
            for evidence in evidence_from_records(records, dataset="tep")
            for frame in evidence_frames(evidence)
        }
        sources = {}
        for frame in frames:
            start, end, _ = _tep_window(frame)
            verify_tep_observations(frame, measured[_tep_window(frame)])
            sources[(frame.case_id, "window")] = output / f"window_{start}_{end}.npy"
        profile_path = output / "normal_reference_profile.json"
        profile = json.loads(profile_path.read_text())
        profile["reference_id"] = reference_ids.pop()
        write_json(profile_path, profile)
        sources[(None, "normal")] = output / "normal_reference.csv"
        sources[(None, "scaler")] = profile_path
        publish(sources)


def verify_tep_observations(frame, measured):
    actual = {
        (o.subject_id, o.feature_id): o.value.model_dump(mode="json")
        for o in measured.observations
        if o.status == "observed" and o.value is not None
    }
    for o in frame.observations:
        if o.status != "observed" or o.value is None or o.value.kind not in {"number", "boolean"}:
            continue
        saved, value = o.value.model_dump(mode="json"), actual.get((o.subject_id, o.feature_id))
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
    if not any(
        destination.resolve().is_relative_to(directory.resolve())
        for directory in (RUNTIME, PUBLIC, TEP_RAW)
    ):
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
    prepare_transfer(model)
    if not registry.exists():
        write_json(registry, config)


def prepare_tep(demo: dict) -> None:
    checked = set()
    for sample in demo["samples"]:
        raw = sample["raw_input"]
        cache = PUBLIC / ("tep_" + raw["source_url"].rsplit("/", 1)[-1])
        prepare_transfer(raw, cached=cache)
        reference = sample["normal_reference"]
        if reference["path"] not in checked:
            prepare_transfer(reference, cached=PUBLIC / "tep_d00.dat")
            checked.add(reference["path"])
        hydrate_process_support(frames_from_asset(sample["evidence"]), sample)


def wafer_rows(sample: dict, frames: list) -> list:
    """A raw row must have exactly the identity and grid shape of its packaged Frame."""
    rows = sample["raw_source"]["rows"]
    if len(rows) != len(frames) or len({row["row_id"] for row in rows}) != len(rows):
        raise ValueError("WM811K 原始行须与发布 Frame 一一对应。")
    for row, frame in zip(rows, frames, strict=True):
        grid = next(a for a in frame.assets if a.asset_id == "grid")
        if (
            row["frame_case_id"] != frame.case_id
            or frame.case_id != f"wm811k_{row['row_id']}/query/grid"
            or tuple(row["shape"]) != tuple(grid.shape)
        ):
            raise ValueError(f"WM811K 原始行与发布 Frame 不匹配：{row['row_id']}")
    return rows


def prepare_wafer(demo: dict) -> None:
    import numpy as np
    import pandas as pd

    from scripts._wm811k_table import DataOnlyUnpickler

    (sample,) = demo["samples"]
    (model,) = demo["models"]
    source = sample["raw_source"]
    rows = wafer_rows(sample, frames_from_asset(sample["evidence"]))
    targets = attachment_targets(sample, {(row["frame_case_id"], "grid") for row in rows})
    table_path = prepare_transfer(source)
    with table_path.open("rb") as handle:
        table = DataOnlyUnpickler(handle).load()
    if not isinstance(table, pd.DataFrame) or not table.index.is_unique:
        raise ValueError("WM811K 公共表须有唯一原始行索引。")
    clean, grids = [], {}
    for row in rows:
        row_id = row["row_id"]
        wafer = np.asarray(table.at[int(row_id), "waferMap"])
        if wafer.shape != tuple(row["shape"]) or not np.isin(wafer, [0, 1, 2]).all():
            raise ValueError(f"WM811K 行 {row_id} 不是预期的原始 0/1/2 网格。")
        cells = wafer.tolist()
        clean.append({"wafer_id": row_id, "case_id": f"wm811k_{row_id}", "waferMap": cells})
        grids[targets[(row["frame_case_id"], "grid")]] = cells
    raw = (ROOT / sample["raw_input"]["path"]).resolve()
    if not raw.resolve().is_relative_to(RUNTIME.resolve()):
        raise ValueError("WM811K 原始样本须位于受管本地运行目录。")
    if raw.exists():
        if [json.loads(line) for line in raw.read_text().splitlines() if line.strip()] != clean:
            raise ValueError(f"已有原始样本与固定上游行不同：{raw}；未覆盖。")
    for path, grid in grids.items():
        if path.exists() and json.loads(path.read_text()) != grid:
            raise ValueError(f"已有 WM811K 附件不是同一片晶圆：{path}；未覆盖。")
    prepare_transfer(model)
    for path, grid in grids.items():
        if not path.exists():
            write_text(path, json.dumps(grid, separators=(",", ":")) + "\n")
    if not raw.exists():
        # Only identities and original cells reach the classifier, never native labels.
        write_text(raw, "".join(json.dumps(row) + "\n" for row in clean))


def prepare(download: bool = False, dataset: str | None = None) -> dict:
    manifest = read_manifest(dataset)
    if download:
        preparers = {"mvtec": prepare_bottle_checkpoint, "tep": prepare_tep, "wafer": prepare_wafer}
        for demo in manifest["demos"]:
            preparers[demo["dataset"]](demo)
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


def recompute(manifest: dict, output: Path) -> list[dict]:
    """Recompute each intermediate input; no database, model, or native label is read."""
    from kgtracevis.core.graded_reasoner import GradedReasoner
    from kgtracevis.core.rootkgd_reasoner import RootKGDReasoner
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
                reasoner = {"graded_abduction": GradedReasoner, "tep_rootkgd": RootKGDReasoner}[
                    reasoner_id
                ]
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="fetch missing public assets only")
    parser.add_argument(
        "--dataset", choices=("mvtec", "tep", "wafer"), help="prepare one scene only"
    )
    parser.add_argument(
        "--recompute-output",
        type=Path,
        help="new directory for all intermediate-Evidence reasoning results",
    )
    args = parser.parse_args()
    manifest = prepare(download=args.download, dataset=args.dataset)
    report = check(manifest)
    print(json.dumps({"manifest": str(SMALL / "manifest.json"), **report}, ensure_ascii=False))
    if report["missing_assets"]:
        raise SystemExit(1)
    if args.recompute_output:
        print(json.dumps(recompute(manifest, args.recompute_output), ensure_ascii=False))


if __name__ == "__main__":
    main()
