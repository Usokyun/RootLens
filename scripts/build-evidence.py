#!/usr/bin/env python3
"""RootLens Module 2: Unified Evidence Construction Pipeline.

Runs upstream evidence generation code from TEP_KG (RBC) and KGTraceVis
(adapters) to produce RootLens-compatible unified Evidence JSON files.
Each file describes one anomaly case with structured observations.

Usage:
    python3 scripts/build-evidence.py
    python3 scripts/build-evidence.py --output-dir public/generated/evidence
    python3 scripts/build-evidence.py --tep-max-cases 10 --skip-mvtec
"""

from __future__ import annotations

import argparse
import builtins
import json
import os as _os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEP_KG_ROOT = Path("/Users/bytedance/my_project/TEP_KG")
MVTEC_KG_ROOT = Path("/Users/bytedance/my_project/MVTec/KGTraceVis")


def _install_zip_strict_compat() -> None:
    """Backport ``zip(..., strict=...)`` for upstream Python 3.10+ code."""
    if sys.version_info >= (3, 10):
        return
    if getattr(builtins.zip, "__name__", "") == "_zip_with_strict":
        return

    original_zip = builtins.zip

    def _zip_with_strict(*iterables, strict: bool = False):
        if not strict:
            yield from original_zip(*iterables)
            return

        iterators = [iter(iterable) for iterable in iterables]
        while True:
            row = []
            exhausted_at = None
            for index, iterator in enumerate(iterators):
                try:
                    row.append(next(iterator))
                except StopIteration:
                    exhausted_at = index
                    break
            if exhausted_at is None:
                yield tuple(row)
                continue
            if row:
                raise ValueError(
                    f"zip() argument {exhausted_at + 1} is shorter than argument 1"
                )
            for index, iterator in enumerate(iterators[exhausted_at + 1 :], start=exhausted_at + 2):
                try:
                    next(iterator)
                except StopIteration:
                    continue
                raise ValueError(
                    f"zip() argument {index} is longer than argument {exhausted_at + 1}"
                )
            return

    builtins.zip = _zip_with_strict


_install_zip_strict_compat()

# ── helpers ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat().replace("+00:00", "Z")
    )

def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _clear_generated_json(output_dir: Path) -> None:
    """Remove stale generated evidence files before rebuilding the sample set."""
    if not output_dir.exists():
        return
    for path in output_dir.glob("*.json"):
        path.unlink()

def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))

def _select_graph_dataset_id(tep: bool, mvtec: bool, wafer: bool) -> str:
    if tep:
        return "tep-kg"
    if wafer:
        return "mvtec-project"  # wafer cases share the MVTec runtime KG
    return "mvtec-project"


def _normalize_evidence_for_rootlens(evidence: dict) -> dict:
    """Ensure every observation has the RootLens contract fields."""
    for obs in evidence.get("observations", []):
        # linked_entity_hints — derived from observation name + any existing hints
        name = str(obs.get("name", ""))
        existing = obs.get("linked_entity_hints", [])
        if isinstance(existing, list):
            hints = [str(h) for h in existing if h]
        else:
            hints = []
        if name and name not in hints:
            hints.append(name)
        obs["linked_entity_hints"] = hints

        # raw_evidence_refs — preserve existing or default to empty
        refs = obs.get("raw_evidence_refs", [])
        if not isinstance(refs, list):
            refs = []
        # normalize each ref to RootLens contract shape if it has data
        normalized_refs = []
        for ref in refs:
            if isinstance(ref, dict):
                normalized_refs.append({
                    "ref_id": str(ref.get("ref_id", ref.get("source_ref", ""))),
                    "label": str(ref.get("label", ref.get("raw_ref", ref.get("ref_id", "")))),
                    "role": str(ref.get("role", "evidence")),
                    "file_path": str(ref.get("file_path", "")),
                    "line": ref.get("line", None),
                })
            else:
                normalized_refs.append({
                    "ref_id": str(ref),
                    "label": str(ref),
                    "role": "evidence",
                    "file_path": "",
                    "line": None,
                })
        obs["raw_evidence_refs"] = normalized_refs

        # remove KGTraceVis-specific legacy observation fields that RootLens contract doesn't use
        for legacy_key in ("raw_ref", "source_ref"):
            obs.pop(legacy_key, None)

    # top-level contract fields
    if not evidence.get("case_label"):
        evidence["case_label"] = evidence.get("case_id", "unknown")
    if not evidence.get("summary"):
        evidence["summary"] = ""
    if not evidence.get("timestamp"):
        evidence["timestamp"] = _now_iso()

    return evidence


def _select_balanced_tep_scenarios(
    scenarios: list[dict],
    max_cases: int | None,
) -> list[dict]:
    """Round-robin across fault numbers so capped TEP samples stay fault-balanced."""
    if max_cases is None or max_cases >= len(scenarios):
        return scenarios

    by_fault: dict[int, list[dict]] = {}
    for scenario in scenarios:
        by_fault.setdefault(int(scenario["fault_number"]), []).append(scenario)

    selected: list[dict] = []
    round_index = 0
    ordered_faults = sorted(by_fault)

    while len(selected) < max_cases:
        added = False
        for fault_number in ordered_faults:
            bucket = by_fault[fault_number]
            if round_index >= len(bucket):
                continue
            selected.append(bucket[round_index])
            added = True
            if len(selected) >= max_cases:
                break
        if not added:
            break
        round_index += 1

    return selected


# =====================================================================
# TEP  evidence construction  (RBC → observations)
# =====================================================================

def _build_tep_evidence(
    output_dir: Path,
    max_cases: int | None = None,
) -> list[dict]:
    """Run TEP_KG RBC pipeline and convert each scenario to unified Evidence JSON."""

    sys.path.insert(0, str(TEP_KG_ROOT / "src"))
    from tep_kg.rbc import build_rbc_scenarios, load_tep_mapping
    from tep_kg.assets import read_jsonl

    precomputed_path = TEP_KG_ROOT / "data" / "processed" / "rca" / "rbc_contributions.jsonl"
    if precomputed_path.exists():
        print("[tep] loading precomputed RBC scenarios …", flush=True)
        scenarios = read_jsonl(precomputed_path)
        fault_count = len({int(row["fault_number"]) for row in scenarios})
        print(
            f"[tep]  done — {len(scenarios)} scenarios across {fault_count} faults",
            flush=True,
        )
    else:
        print("[tep] running RBC pipeline …", flush=True)
        _profile, scenarios, report = build_rbc_scenarios(
            TEP_KG_ROOT,
            row_stride=25,
            window_size=100,
            max_runs_per_fault=500,
        )
        print(
            f"[tep]  done — {len(scenarios)} scenarios across "
            f"{report['fault_count']} faults",
            flush=True,
        )

    mapping = load_tep_mapping(TEP_KG_ROOT)
    channel_info: dict[str, dict] = {}
    for row in mapping:
        ch = str(row["sequence_column"])
        channel_info[ch] = {
            "kg_entity_id": str(row["kg_entity_id"]),
            "display_name": str(row.get("tep_variable_family", "")) + "_"
            + str(row.get("tep_variable_index", "")),
            "alternate_ids": (
                [str(x) for x in row.get("alternate_entity_ids", "").split(",") if x]
                if isinstance(row.get("alternate_entity_ids"), str)
                else row.get("alternate_entity_ids", [])
            ),
        }

    selected = _select_balanced_tep_scenarios(scenarios, max_cases)
    cases: list[dict] = []

    for sc in selected:
        case_id = str(sc["scenario_id"])
        fault_num = int(sc["fault_number"])
        run_num = int(sc["simulation_run"])
        label = f"TEP Fault {fault_num:02d} / Run {run_num}"
        summary = (
            f"TEP process fault #{fault_num}, simulation run {run_num}. "
            f"Window samples {sc['sample_start']}–{sc['sample_end']}."
        )

        observations: list[dict] = []
        channel_contributions = sc.get("channel_contributions", {})
        for ch_name, contrib in sorted(
            channel_contributions.items(),
            key=lambda item: (-float(item[1]), item[0]),
        ):
            contrib_val = float(contrib)
            if contrib_val < 1e-8:
                continue
            info = channel_info.get(ch_name, {})
            obs_id = f"obs_{case_id}_{ch_name}"
            observations.append({
                "obs_id": obs_id,
                "facet": "variable",
                "name": ch_name,
                "variable_name": ch_name,
                "contribution": round(contrib_val, 8),
                "direction": "unknown",
                "confidence": 0.95,
                "linked_entity_hints": [
                    info.get("kg_entity_id", ch_name),
                    *info.get("alternate_ids", []),
                ],
                "raw_evidence_refs": [],
            })

        graph_contributions = sc.get("graph_contributions", {})

        evidence: dict = {
            "case_id": case_id,
            "case_label": label,
            "dataset": "tep",
            "source": "time_series",
            "timestamp": _now_iso(),
            "summary": summary,
            "graph_dataset_id": "tep-kg",
            "observations": observations,
            # extended metadata kept in extra for provenance
            "graph_contributions": {
                k: round(float(v), 8)
                for k, v in graph_contributions.items()
            },
            "fault_number": fault_num,
            "simulation_run": run_num,
        }

        out_path = output_dir / f"{case_id}.json"
        _write_json(out_path, evidence)
        cases.append(evidence)

    print(f"[tep] wrote {len(cases)} evidence files to {output_dir}", flush=True)
    return cases


# =====================================================================
# MVTec / KGTraceVis  evidence construction  (adapters)
# =====================================================================

def _build_kgtracevis_evidence(
    output_dir: Path,
) -> list[dict]:
    """Load KGTraceVis example records and convert via adapters to Evidence JSON."""

    _prev_cwd = _os.getcwd()
    try:
        _os.chdir(str(MVTEC_KG_ROOT))
        sys.path.insert(0, str(MVTEC_KG_ROOT / "src"))

        from kgtracevis.adapters.batch import (  # type: ignore[import-untyped]
            evidence_from_records,
            load_records,
        )
        from kgtracevis.schema.evidence_schema import Evidence  # type: ignore[import-untyped]

        # mvtec example records
        mvtec_path = MVTEC_KG_ROOT / "data" / "examples" / "records" / "mvtec_records.jsonl"
        tep_records_path = MVTEC_KG_ROOT / "data" / "examples" / "records" / "tep_records.jsonl"
        wm811k_path = MVTEC_KG_ROOT / "data" / "examples" / "records" / "wm811k_records.jsonl"

        all_cases: list[dict] = []

        for label, path in [
            ("mvtec", mvtec_path),
            ("tep-kgtracevis", tep_records_path),
            ("wm811k", wm811k_path),
        ]:
            if not path.exists():
                print(f"[{label}] skipping — {path} not found", flush=True)
                continue

            print(f"[{label}] loading records …", flush=True)
            records = load_records(str(path))
            evidence_list: list[Evidence] = evidence_from_records(records)
            print(f"[{label}]  {len(evidence_list)} evidence objects", flush=True)

            for ev in evidence_list:
                case_json = json.loads(ev.model_dump_json())
                case_json = _normalize_evidence_for_rootlens(case_json)
                case_json["case_label"] = f"{ev.dataset.upper()} / {ev.object} / {ev.anomaly_type}"
                case_id = str(case_json.get("case_id", f"{label}_{len(all_cases) + 1:04d}"))
                dataset = str(case_json.get("dataset", ""))
                case_json["graph_dataset_id"] = _select_graph_dataset_id(
                    tep=(dataset == "tep"),
                    mvtec=(dataset == "mvtec"),
                    wafer=(dataset == "wafer"),
                )
                if not case_json.get("summary"):
                    raw_desc = case_json.get("raw_evidence", {})
                    if isinstance(raw_desc, dict):
                        case_json["summary"] = str(raw_desc.get("description", ""))
                    else:
                        case_json["summary"] = ""
                out_path = output_dir / f"{case_id}.json"
                _write_json(out_path, case_json)
                all_cases.append(case_json)

        print(
            f"[kgtracevis] wrote {len(all_cases)} evidence files to {output_dir}",
            flush=True,
        )
        return all_cases

    finally:
        _os.chdir(_prev_cwd)


# =====================================================================
# Seed / demo evidence  (pre-built example files)
# =====================================================================

def _copy_seed_evidence(output_dir: Path) -> list[dict]:
    """Copy and normalize KGTraceVis pre-built example evidence files."""
    examples_dir = MVTEC_KG_ROOT / "data" / "examples"
    seed_files = [
        "tep_example.json",
        "ds_mvtec_example.json",
        "wafer_example.json",
    ]

    cases: list[dict] = []
    for filename in seed_files:
        path = examples_dir / filename
        if not path.exists():
            print(f"[seed] skipping {filename} — not found", flush=True)
            continue

        data = json.loads(path.read_text(encoding="utf-8"))

        # normalize observations and add RootLens contract fields
        data = _normalize_evidence_for_rootlens(data)
        case_id = str(data.get("case_id", filename.replace(".json", "")))
        dataset = str(data.get("dataset", ""))

        data["case_label"] = data.get(
            "case_label",
            f"{dataset.upper()} Demo / {data.get('object', 'unknown')}",
        )
        data["graph_dataset_id"] = _select_graph_dataset_id(
            tep=(dataset == "tep"),
            mvtec=(dataset == "mvtec"),
            wafer=(dataset == "wafer"),
        )
        if not data.get("summary"):
            raw_desc = data.get("raw_evidence", {})
            if isinstance(raw_desc, dict):
                data["summary"] = raw_desc.get("description", "")
            else:
                data["summary"] = ""

        out_path = output_dir / f"{case_id}.json"
        _write_json(out_path, data)
        cases.append(data)

    print(f"[seed] wrote {len(cases)} seed evidence files", flush=True)
    return cases


# =====================================================================
# orchestrator
# =====================================================================

def build_all(
    *,
    output_dir: Path | None = None,
    tep_max_cases: int | None = None,
    skip_tep: bool = False,
    skip_mvtec: bool = False,
    skip_seed: bool = False,
) -> dict:
    started_at = _now_iso()
    all_cases: list[dict] = []
    errors: list[str] = []

    if output_dir is None:
        output_dir = REPO_ROOT / "public" / "generated" / "evidence"

    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_generated_json(output_dir)

    # ── TEP RBC evidence ───────────────────────────────────────────
    if not skip_tep:
        try:
            tep_cases = _build_tep_evidence(output_dir, max_cases=tep_max_cases)
            all_cases.extend(tep_cases)
        except Exception as exc:
            errors.append(f"TEP evidence build failed: {exc}")

    # ── MVTec / KGTraceVis adapters ─────────────────────────────────
    if not skip_mvtec:
        try:
            mvtec_cases = _build_kgtracevis_evidence(output_dir)
            all_cases.extend(mvtec_cases)
        except Exception as exc:
            errors.append(f"KGTraceVis evidence build failed: {exc}")

    # ── Seed / demo evidence ────────────────────────────────────────
    if not skip_seed:
        try:
            seed_cases = _copy_seed_evidence(output_dir)
            all_cases.extend(seed_cases)
        except Exception as exc:
            errors.append(f"Seed evidence copy failed: {exc}")

    if not all_cases:
        raise RuntimeError(
            "No evidence cases were built. Errors:\n" + "\n".join(errors)
        )

    by_dataset: dict[str, int] = {}
    for c in all_cases:
        ds = str(c.get("dataset", "unknown"))
        by_dataset[ds] = by_dataset.get(ds, 0) + 1

    return {
        "ok": len(errors) == 0,
        "generatedAt": _now_iso(),
        "startedAt": started_at,
        "caseCount": len(all_cases),
        "byDataset": by_dataset,
        "outputDir": str(output_dir),
        "errors": errors,
    }


# =====================================================================
# CLI
# =====================================================================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RootLens Module 2 — Unified Evidence Construction Pipeline"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "public" / "generated" / "evidence",
        help="Output directory for evidence JSON files",
    )
    parser.add_argument(
        "--tep-max-cases",
        type=int,
        default=None,
        help="Limit TEP RBC scenarios (default: all 1000)",
    )
    parser.add_argument(
        "--skip-tep", action="store_true", help="Skip TEP RBC evidence"
    )
    parser.add_argument(
        "--skip-mvtec", action="store_true", help="Skip KGTraceVis adapter evidence"
    )
    parser.add_argument(
        "--skip-seed", action="store_true",
        help="Skip KGTraceVis pre-built example evidence",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Print summary as JSON to stdout",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = build_all(
        output_dir=args.output_dir,
        tep_max_cases=args.tep_max_cases,
        skip_tep=args.skip_tep,
        skip_mvtec=args.skip_mvtec,
        skip_seed=args.skip_seed,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    elif not summary["ok"]:
        print("[FAIL] evidence construction completed with errors:", file=sys.stderr)
        for err in summary["errors"]:
            print(f"  - {err}", file=sys.stderr)
        return 1
    else:
        print(f"[OK] {summary['caseCount']} evidence cases built", flush=True)
        for ds, count in sorted(summary["byDataset"].items()):
            print(f"  {ds}: {count} cases", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
