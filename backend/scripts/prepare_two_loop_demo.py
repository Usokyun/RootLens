"""Prepare the three public-data demos without touching databases or model outputs.

Run from backend/: uv run --offline --no-sync python scripts/prepare_two_loop_demo.py
Existing source assets are reused; --download retrieves missing public files only.
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMALL = ROOT / "data/demo/two_loop"
RUNTIME = ROOT / "runs/two_loop_demo"
EARLIER = ROOT / "runs/unified_reasoning"
PUBLIC = ROOT / "runs/refactor_m2_m6/public"

EMHART = (
    "https://www.emhartglass.com/sites/default/files/publications/2024-07/"
    "BEG_BR0060RevA-Defect_Guide-WEB.pdf"
)
TEP_BASE = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/"
DS_BASE = "https://huggingface.co/datasets/DefectSpectrum/Defect_Spectrum/resolve/main/"
HF_BOTTLE = "https://huggingface.co/datasets/foersben/mvtec-ad/resolve/main/"
PREPARATION_ERRORS: list[dict] = []


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


def asset(
    asset_id: str,
    path: Path,
    title: str,
    *,
    url: str | None = None,
    redistribution: str = "derived_public_measurements",
    media_type: str | None = None,
) -> dict:
    return {
        "asset_id": asset_id,
        "title": title,
        "path": path.relative_to(ROOT).as_posix(),
        "media_type": media_type or mimetypes.guess_type(path.name)[0] or "text/plain",
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "available": path.is_file(),
        "source_url": url,
        "redistribution": redistribution,
        "storage_scope": "repository" if path.is_relative_to(SMALL) else "local_runtime",
    }


def frozen(index: int, name: str) -> Path:
    source = EARLIER / f"u5_frozen/{index:03d}-evidence.json"
    destination = SMALL / f"evidence/{name}.json"
    # Keep the prior generation in history; defaults come from this round's raw runs.
    if source.exists():
        write_json(SMALL / f"history/u5-{name}.json", json.loads(source.read_text()))
    current = {
        0: ("bottle-insufficient", 0),
        1: ("bottle-normal", 0),
        2: ("bottle-chipped", 0),
        3: ("bottle-chipped-second", 0),
        4: ("bottle-semantic-miss", 0),
        5: ("tep-normal-window", 0),
        6: ("tep-sequence-04", 1),
        9: ("tep-sequence-01", 1),
        12: ("tep-sequence-05", 1),
        17: ("wafer-nearfull", 0),
        23: ("wafer-normal", 0),
        20: ("wafer-pattern-disagreement", 0),
    }
    if index in current:
        sample_id, case_index = current[index]
        batch = "api-final" if sample_id.startswith("wafer-") else "api-e2e-002"
        run = RUNTIME / f"{batch}/{sample_id}-raw-unified_abduction.analysis.json"
        if run.is_file():
            payload = json.loads(run.read_text())
            write_json(destination, payload["cases"][case_index]["evidence_frames"][0])
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


def prepare(download: bool = False) -> dict:
    PREPARATION_ERRORS.clear()
    SMALL.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    bottle_model_url = "https://huggingface.co/micguida1/mvtec-anomaly-checkpoints/resolve/main/Patchcore/MVTecAD/bottle/latest/weights/lightning/model.ckpt"
    wafer_model_url = "https://huggingface.co/radai-agent/radai-wm811k-defect-detection/resolve/main/best_radai_resnet.pt"
    bottle_model = PUBLIC / "bottle_patchcore.ckpt"
    if not bottle_model.is_file():
        bottle_model = stage(
            bottle_model,
            RUNTIME / "models/bottle_patchcore.ckpt",
            url=bottle_model_url,
            download=download,
        )
    wafer_model = PUBLIC / "wm811k_resnet.pt"
    if not wafer_model.is_file():
        wafer_model = stage(
            wafer_model, RUNTIME / "models/wm811k_resnet.pt", url=wafer_model_url, download=download
        )
    graph_assets = {}
    for name in ("bottle", "tep", "wafer"):
        source = ROOT / f"data/kg/unified/{name}-working-graph.v2.json"
        destination = SMALL / f"knowledge/{name}-working-graph.v2.json"
        if not destination.exists():
            package = json.loads(source.read_text())
            package["title"] = {
                "bottle": "玻璃边缘缺损 · 厂家资料候选图",
                "tep": "TEP 过程异常 · 程序来源候选图",
                "wafer": "晶圆失效空间图案 · 联合特征图",
            }[name]
            write_json(destination, package)
        graph_assets[name] = asset(f"{name}-working-graph", destination, "可编辑演示工作图")

    pdf = stage(
        EARLIER / "public/emhart-defect-guide.pdf",
        RUNTIME / "materials/emhart-defect-guide.pdf",
        url=EMHART,
        download=download,
    )
    bottle_images = {}
    for name, original, url in (
        (
            "sample_001",
            EARLIER / "public/bottle-additional/001.png",
            DS_BASE + "DS-MVTec/bottle/image/broken_large/001.png",
        ),
        (
            "sample_002",
            EARLIER / "public/bottle-additional/002.png",
            DS_BASE + "DS-MVTec/bottle/image/broken_large/002.png",
        ),
        (
            "sample_003",
            EARLIER / "public/bottle-additional/003.png",
            DS_BASE + "DS-MVTec/bottle/image/broken_large/003.png",
        ),
        (
            "sample_006",
            RUNTIME / "candidate-images/broken_large-006.png",
            DS_BASE + "DS-MVTec/bottle/image/broken_large/006.png",
        ),
        ("normal_001", PUBLIC / "bottle/input_1.png", HF_BOTTLE + "bottle/test/good/000.png"),
        (
            "sample_000",
            PUBLIC / "bottle/input_0.png",
            HF_BOTTLE + "bottle/test/broken_large/000.png",
        ),
    ):
        destination = stage(
            original, RUNTIME / f"raw/bottle/{name}.png", url=url, download=download
        )
        bottle_images[name] = asset(
            f"bottle-{name}-raw",
            destination,
            "公开原始玻璃边缘图像",
            url=url,
            redistribution="MVTec_AD_CC_BY_NC_SA_4.0_local_only",
        )
    bottle_samples = []
    for sample_id, title, image, index, expected in (
        (
            "bottle-chipped",
            "局部缺损A · 本轮语义漏检",
            "sample_001",
            2,
            "本轮ROI把原生异常判正常，当前测量与中间Evidence均无匹配，保留真实感知失败。",
        ),
        (
            "bottle-chipped-second",
            "局部缺损B · 本轮语义漏检",
            "sample_002",
            3,
            "本轮ROI判正常；不替换模型观测，不强配原因。",
        ),
        ("bottle-normal", "正常玻璃图 · 阴性对照", "normal_001", 1, "异常门控不成立，无支持候选。"),
        (
            "bottle-semantic-miss",
            "语义漏检 · 真实失败",
            "sample_003",
            4,
            "原生异常图曾被ROI模型判正常，冻结结果无匹配；保留该失败。",
        ),
    ):
        frame = frozen(index, sample_id)
        bottle_samples.append(
            {
                "sample_id": sample_id,
                "title": title,
                "dataset": "mvtec",
                "input_mode": "image",
                "expectation": expected,
                "raw_input": bottle_images[image],
                "evidence": asset(
                    f"{sample_id}-evidence", frame, "实际模型产出的冻结EvidenceFrame"
                ),
                "raw_options": {
                    "object_name": "bottle",
                    "model_preset": "patchcore",
                    "semantic_mode": "vlm",
                },
                "reasoner_ids": ["unified_abduction"],
            }
        )
    current_frame = SMALL / "evidence/bottle-rim-break.json"
    if current_frame.is_file():
        bottle_samples.insert(
            0,
            {
                "sample_id": "bottle-rim-break",
                "title": "玻璃边缘缺损 · 本轮实测",
                "dataset": "mvtec",
                "input_mode": "image",
                "expectation": (
                    "本轮真实PatchCore/ROI语义支持可见缺损；"
                    "多个制造原因仍并列，不把外观当唯一根因。"
                ),
                "raw_input": bottle_images["sample_006"],
                "evidence": asset(
                    "bottle-rim-break-evidence",
                    current_frame,
                    "本轮真实原图运行导出的EvidenceFrame",
                ),
                "raw_options": {
                    "object_name": "bottle",
                    "model_preset": "patchcore",
                    "semantic_mode": "vlm",
                },
                "reasoner_ids": ["unified_abduction"],
                "origin_run_id": "1d116c71-d461-4d9a-852f-eb7f243534c0",
                "suitability_checks": {
                    "raw_run_ids": [
                        "bde29798-db9a-4eb6-aa6a-439125ac88d1",
                        "1d116c71-d461-4d9a-852f-eb7f243534c0",
                    ],
                    "result": "同一图两次真实模型均给出玻璃开裂/缺失外观；不是留出集或准确率估计。",
                },
            },
        )
    bottle_samples.append(
        {
            "sample_id": "bottle-geometry-only",
            "title": "关闭ROI语义 · 证据不足对照",
            "dataset": "mvtec",
            "input_mode": "image",
            "expectation": (
                "只运行真实PatchCore定位和几何，不提供外观语义；缺失不是正常，应显示证据不足。"
            ),
            "raw_input": bottle_images["sample_000"],
            "evidence": asset(
                "bottle-geometry-only-evidence",
                SMALL / "evidence/bottle-geometry-only.json",
                "关闭语义后由真实adapter生成的EvidenceFrame",
            ),
            "raw_options": {
                "object_name": "bottle",
                "model_preset": "patchcore",
                "semantic_mode": "disabled",
            },
            "reasoner_ids": ["unified_abduction"],
        }
    )

    normal = stage(
        PUBLIC / "tep_d00.dat",
        RUNTIME / "raw/tep/normal_reference.dat",
        url=TEP_BASE + "d00.dat",
        download=download,
    )
    normal_asset = asset(
        "tep-normal-reference",
        normal,
        "正常参考 · 500行/52通道",
        url=TEP_BASE + "d00.dat",
        redistribution="Illinois_NCSA_style_license",
    )
    tep_samples = []
    for serial, original, index, title in (
        ("04", PUBLIC / "tep_d04_te.dat", 6, "过程序列A · 冷却扰动对照"),
        ("01", EARLIER / "public/tep_d01_te.dat", 9, "过程序列B · 进料扰动对照"),
        ("05", EARLIER / "public/tep_d05_te.dat", 12, "过程序列C · 另一冷却边界对照"),
    ):
        raw = stage(
            original,
            RUNTIME / f"raw/tep/sequence_{serial}.dat",
            url=TEP_BASE + f"d{serial}_te.dat",
            download=download,
        )
        sample_id = f"tep-sequence-{serial}"
        tep_samples.append(
            {
                "sample_id": sample_id,
                "title": title,
                "dataset": "tep",
                "input_mode": "process",
                "expectation": (
                    "原始52通道经正常scaler/PCA；比较正常与异常窗口、两引擎及图中可达通道。"
                    "原图统一内核首位曾错误。"
                ),
                "raw_input": asset(
                    f"{sample_id}-raw",
                    raw,
                    "公开52通道过程序列",
                    url=TEP_BASE + f"d{serial}_te.dat",
                    redistribution="Illinois_NCSA_style_license",
                ),
                "normal_reference": normal_asset,
                "evidence": asset(
                    f"{sample_id}-evidence",
                    frozen(index, sample_id),
                    "实际窗口161–260的完整EvidenceFrame",
                ),
                "raw_options": {
                    "windows": [[1, 100], [161, 260], [261, 360]],
                    "sampling_seconds": 180,
                },
                "reasoner_ids": ["unified_abduction", "tep_rootkgd"],
            }
        )
    tep_samples.append(
        {
            "sample_id": "tep-normal-window",
            "title": "过程正常窗口 · 阴性对照",
            "dataset": "tep",
            "input_mode": "process",
            "expectation": "同一序列1–100窗口正常门控不成立。",
            "raw_input": tep_samples[0]["raw_input"],
            "normal_reference": normal_asset,
            "evidence": asset(
                "tep-normal-evidence", frozen(5, "tep-normal-window"), "实际正常窗口EvidenceFrame"
            ),
            "raw_options": {"windows": [[1, 100]], "sampling_seconds": 180},
            "reasoner_ids": ["unified_abduction", "tep_rootkgd"],
        }
    )
    tep_materials = []
    for file, title in (
        ("teprob.f", "TEP原始过程方程与通道定义"),
        ("temain_mod.f", "TEP闭环控制示例"),
    ):
        path = stage(
            EARLIER / f"public/{file}",
            RUNTIME / f"materials/{file}.txt",
            url=TEP_BASE + file,
            download=download,
        )
        tep_materials.append(
            asset(
                f"tep-material-{file}",
                path,
                title,
                url=TEP_BASE + file,
                redistribution="Illinois_NCSA_style_license",
            )
        )

    wafer_samples = []
    source_wafer = PUBLIC / "wafer_samples.jsonl"
    rows = (
        [json.loads(line) for line in source_wafer.read_text().splitlines()]
        if source_wafer.exists()
        else []
    )
    if not rows and download:
        from scripts.prepare_public_wafer_demo import DataOnlyUnpickler

        table = stage(
            PUBLIC / "wm811k_test.pkl",
            RUNTIME / "sources/wm811k_test.pkl",
            url="https://huggingface.co/datasets/lslattery/wafer-defect-detection/resolve/main/test.pkl",
            download=True,
        )
        if table.is_file():
            with table.open("rb") as handle:
                dataframe = DataOnlyUnpickler(handle).load()
            # Original source row IDs identify the examples; no label is passed on.
            for index, row in dataframe.iterrows():
                if str(index) in {"248536", "5", "31707"}:
                    rows.append({"wafer_id": str(index), "waferMap": row["waferMap"].tolist()})
    for wafer_id, index, sample_id, title, expectation in (
        (
            "248536",
            17,
            "wafer-nearfull",
            "近全片失效 · 空间联合条件",
            "独立ResNet分类与实际高失效率共同支持近全片图案；不把图案当成制造原因。",
        ),
        (
            "5",
            23,
            "wafer-normal",
            "正常晶圆 · 阴性对照",
            "原生None仍可能有少量失败die；八类分类器没有正常类，须结合实际空间统计，不把分类输出直接当诊断。",
        ),
        (
            "31707",
            20,
            "wafer-pattern-disagreement",
            "图案分歧 · 真实失败",
            "原生Donut和模型Edge-Ring分歧；原生标签不进入分类器。",
        ),
    ):
        row = next((r for r in rows if str(r["wafer_id"]) == wafer_id), None)
        path = RUNTIME / f"raw/wafer/{sample_id}-{wafer_id}.jsonl"
        if row and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            # Only cells and identity enter the model. Native labels remain in the original source.
            clean = {
                "wafer_id": wafer_id,
                "case_id": f"wm811k_{wafer_id}",
                "waferMap": row["waferMap"],
            }
            path.write_text(json.dumps(clean) + "\n")
        wafer_samples.append(
            {
                "sample_id": sample_id,
                "title": title,
                "dataset": "wafer",
                "input_mode": "wafer",
                "expectation": expectation,
                "raw_input": asset(
                    f"{sample_id}-raw",
                    path,
                    "无原生标签的公开晶圆网格",
                    url="https://huggingface.co/datasets/lslattery/wafer-defect-detection",
                    redistribution="upstream_dataset_license_unspecified_local_only",
                    media_type="application/x-ndjson",
                ),
                "evidence": asset(
                    f"{sample_id}-evidence",
                    frozen(index, sample_id),
                    "实际独立分类与空间测量EvidenceFrame",
                ),
                "raw_options": {},
                "reasoner_ids": ["unified_abduction"],
            }
        )
    wafer_card = stage(
        PUBLIC / "wafer_model_card.md",
        RUNTIME / "materials/wafer-model-card.md",
        url="https://huggingface.co/radai-agent/radai-wm811k-defect-detection/raw/main/README.md",
        download=download,
    )
    wafer_paper_excerpt = stage(
        EARLIER / "public/wm811k-paper-p3-p4.txt",
        RUNTIME / "materials/wm811k-paper-p3-p4.txt",
        url=None,
        download=False,
    )
    if download and not wafer_paper_excerpt.is_file():
        from kgtracevis.source_kg_compiler.material_parser import parse_material

        paper = stage(
            EARLIER / "public/wm811k-original.pdf",
            RUNTIME / "materials/wm811k-original.pdf",
            url="https://outlook.stpi.niar.org.tw/pdfview/tdop/1601",
            download=True,
        )
        if paper.is_file():
            parsed = parse_material(paper, source_id="wm811k-original-paper", scenario="wafer")
            selected = [u.content_text for u in parsed.units if u.source_span.get("page") in (3, 4)]
            if selected:
                wafer_paper_excerpt.write_text("\n\n".join(selected))
    manifest = {
        "schema_version": "rootlens-demo-manifest.v1",
        "title": "RootLens · 资料到知识、样本到解释的双闭环",
        "path_base": "backend",
        "prepared_by": "scripts/prepare_two_loop_demo.py",
        "demos": [
            {
                "id": "bottle",
                "dataset": "mvtec",
                "title": "玻璃边缘 · 原图到候选原因",
                "purpose": "原厂家资料→LLM知识图→人工修改→PatchCore/ROI语义→可追溯候选",
                "capability_id": "visual-region-v2",
                "working_graph": graph_assets["bottle"],
                "materials": [
                    asset(
                        "bottle-manufacturer-pdf",
                        pdf,
                        "Emhart原厂缺陷指南 · PDF",
                        url=EMHART,
                        redistribution="copyrighted_public_pdf_local_only",
                    ),
                ],
                "material_options": {
                    "pages": [13, 20],
                    "note": "选取Broken/Chipped Finish的原始PDF页；不是手写诊断规则。",
                },
                "samples": bottle_samples,
                "models": [
                    asset(
                        "bottle-patchcore",
                        bottle_model,
                        "Bottle PatchCore",
                        url=bottle_model_url,
                        redistribution="model_card_missing_local_only",
                    )
                ],
                "sources": [
                    {
                        "title": "MVTec AD许可",
                        "url": "https://www.mvtec.com/research-teaching/datasets/mvtec-ad",
                        "license": "CC BY-NC-SA 4.0；非商业。镜像标签不覆盖原始数据许可。",
                    }
                ],
            },
            {
                "id": "tep",
                "dataset": "tep",
                "title": "TEP过程 · 全通道与双引擎",
                "purpose": "原过程/控制程序→可编辑通道知识→正常参考/PCA→统一约束与RootKGD图传播",
                "capability_id": "process-window-v2",
                "working_graph": graph_assets["tep"],
                "materials": tep_materials,
                "samples": tep_samples,
                "models": [],
                "sources": [
                    {
                        "title": "Braatz TEP原程序与参考数据",
                        "url": "https://github.com/camaramm/tennessee-eastman-profBraatz",
                        "license": "Illinois/Braatz permissive notice；保留版权和免责声明。",
                    }
                ],
            },
            {
                "id": "wafer",
                "dataset": "wafer",
                "title": "晶圆网格 · 空间图案解释",
                "purpose": "原始网格→独立ResNet+空间统计→图案联合条件与原始die对应",
                "capability_id": "spatial-grid-v2",
                "working_graph": graph_assets["wafer"],
                "materials": [
                    asset(
                        "wafer-original-paper-excerpt",
                        wafer_paper_excerpt,
                        "WM-811K原论文 · 第3–4页定位正文（非完整PDF）",
                        url="https://outlook.stpi.niar.org.tw/pdfview/tdop/1601",
                        redistribution="copyrighted_paper_excerpt_local_only",
                    ),
                    asset(
                        "wafer-model-card",
                        wafer_card,
                        "RadAI模型作者原始模型卡",
                        url="https://huggingface.co/radai-agent/radai-wm811k-defect-detection",
                        redistribution="MIT_model_card",
                    ),
                ],
                "samples": wafer_samples,
                "models": [
                    asset(
                        "wafer-resnet",
                        wafer_model,
                        "WM811K ResNet34",
                        url=wafer_model_url,
                        redistribution="MIT_model",
                    )
                ],
                "sources": [
                    {
                        "title": "WM-811K数据镜像",
                        "url": "https://huggingface.co/datasets/lslattery/wafer-defect-detection",
                        "license": (
                            "数据镜像未明示许可；原网格仅本机使用、不随仓库分发。"
                            "模型MIT不自动覆盖数据。"
                        ),
                    },
                    {
                        "title": "WM-811K原论文",
                        "url": "https://ieeexplore.ieee.org/document/6932449/",
                    },
                ],
            },
        ],
        "interpretation": (
            "expectation是演示对照说明，不输入模型/adapter/推理；原生标签不冒充测量。"
            "原始LLM产物和演示适配分别保存。"
        ),
        "preparation_errors": list(PREPARATION_ERRORS),
    }
    for demo in manifest["demos"]:
        for sample in demo["samples"]:
            sample["recommended"] = sample["sample_id"] in {
                "bottle-rim-break",
                "tep-sequence-04",
                "wafer-nearfull",
            }
            frame_path = ROOT / sample["evidence"]["path"]
            if not frame_path.is_file():
                continue
            frame = json.loads(frame_path.read_text())
            hydrate_process_support(frame, sample)
            supporting = []
            uri_rewrites = {}
            for item in frame["assets"]:
                source = Path(item["uri"])
                source = source if source.is_absolute() else ROOT / source
                if item["asset_id"] == "image" and not source.is_file():
                    source = ROOT / sample["raw_input"]["path"]
                if (
                    sample["dataset"] == "wafer"
                    and item["asset_id"] == "grid"
                    and not source.is_file()
                ):
                    raw_path = ROOT / sample["raw_input"]["path"]
                    if raw_path.is_file():
                        raw = json.loads(raw_path.read_text())
                        grid = raw.get("waferMap", raw.get("wafer_map"))
                        if grid is not None:
                            source = RUNTIME / f"frozen/{sample['sample_id']}/grid.json"
                            write_json(source, grid)
                if not source.is_file():
                    continue
                safe_id = item["asset_id"].replace(":", "_").replace("/", "_")
                destination = RUNTIME / f"frozen/{sample['sample_id']}/{safe_id}{source.suffix}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != destination.resolve():
                    # Derived support copies track the current Frame. Original raw outputs remain.
                    shutil.copy2(source, destination)
                uri_rewrites[item["uri"]] = destination.relative_to(ROOT).as_posix()
                item["uri"] = destination.relative_to(ROOT).as_posix()
                support = asset(
                    f"{sample['sample_id']}-support-{safe_id}",
                    destination,
                    {
                        "window": "完整52通道原始窗口",
                        "normal": "匹配正常参考矩阵",
                        "scaler": "正常scaler/PCA参数",
                    }.get(item["asset_id"], "原始测量配套资产"),
                    redistribution="derived_public_measurements_local_assets",
                )
                support["frame_asset_id"] = item["asset_id"]
                support["kind"] = item["kind"]
                supporting.append(support)
            for item in frame["assets"]:
                base, separator, fragment = item["uri"].partition("#")
                if base in uri_rewrites:
                    item["uri"] = uri_rewrites[base] + (separator + fragment if separator else "")
            write_json(frame_path, frame)
            sample["evidence"]["size_bytes"] = frame_path.stat().st_size
            sample["supporting_assets"] = supporting
    write_json(
        RUNTIME / "mvtec-models.json",
        {
            "schema_version": "rootlens-mvtec-models.v1",
            "objects": {
                "bottle": {
                    "patchcore": {
                        "checkpoint": str(bottle_model.relative_to(ROOT)),
                        "normal_reference": bottle_images["normal_001"]["path"],
                    }
                }
            },
        },
    )
    write_json(SMALL / "manifest.json", manifest)
    return manifest


def check(manifest: dict) -> dict:
    from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
    from kgtracevis.schema.unified_evidence import EvidenceFrame

    checked, missing = [], []
    for demo in manifest["demos"]:
        for item in demo["materials"] + demo["models"]:
            if not (ROOT / item["path"]).is_file():
                missing.append(item["path"])
        graph = ROOT / demo["working_graph"]["path"]
        package = UnifiedWorkingGraphPackage.model_validate_json(graph.read_text())
        for sample in demo["samples"]:
            evidence = ROOT / sample["evidence"]["path"]
            if evidence.exists():
                frame = EvidenceFrame.model_validate_json(evidence.read_text())
                checked.append(
                    {
                        "sample_id": sample["sample_id"],
                        "observations": len(frame.observations),
                        "graph_nodes": len(package.nodes),
                        "graph_edges": len(package.edges),
                    }
                )
            else:
                missing.append(str(evidence.relative_to(ROOT)))
            for key in ("raw_input", "normal_reference"):
                if key in sample and not (ROOT / sample[key]["path"]).is_file():
                    missing.append(sample[key]["path"])
    return {"validated": checked, "missing_assets": sorted(set(missing))}


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
        parsed = parse_material(
            RUNTIME / "materials/emhart-defect-guide.pdf",
            source_id="emhart-glass-defects-2024",
            scenario=scenario,
            original_uri=EMHART,
        )
        units = [u for u in parsed.units if u.source_span.get("page") in (13, 20)]
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
                "max_candidates": 8,
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
    from kgtracevis.schema.unified_evidence import EvidenceFrame

    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for demo in manifest["demos"]:
        package = UnifiedWorkingGraphPackage.model_validate_json(
            (ROOT / demo["working_graph"]["path"]).read_text()
        )
        for sample in demo["samples"]:
            frame = EvidenceFrame.model_validate_json(
                (ROOT / sample["evidence"]["path"]).read_text()
            )
            for reasoner_id in sample["reasoner_ids"]:
                reasoner = RootKGDReasoner if reasoner_id == "tep_rootkgd" else UnifiedReasoner
                result = reasoner(package.knowledge).analyze(frame, top_k=8)
                filename = f"{sample['sample_id']}-{reasoner_id}.json"
                write_json(output / filename, result)
                row = {
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
                rows.append(row)
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
        update={"max_candidates": 8, "max_signatures": 16}
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
    manifest = prepare(download=args.download)
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
