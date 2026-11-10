"""Evaluate frozen JSON frames/knowledge with same-input references and ablations."""

import argparse
import json
from pathlib import Path

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.experiments.unified_diagnosis import (
    atom_path_reference,
    flat_reference,
    flattened_knowledge,
)
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    cases = json.loads(args.manifest.read_text())["cases"]
    if args.output_dir.exists():
        raise ValueError("use a new output directory; existing evaluations are immutable")
    args.output_dir.mkdir(parents=True)
    report = []
    for i, case in enumerate(cases):
        k = KnowledgePackage.model_validate_json(Path(case["knowledge"]).read_text())
        frame = EvidenceFrame.model_validate_json(Path(case["evidence"]).read_text())
        actual = UnifiedReasoner(k).analyze(frame, top_k=128)
        flat = flat_reference(k, frame)
        costs = {
            r["candidate_id"]: (r["scoring_details"]["total_cost"], r["eligible_for_ranking"])
            for r in actual["candidate_evaluations"]
        }
        equivalent = all(
            r["candidate_id"] in costs
            and abs(costs[r["candidate_id"]][0] - r["cost"]) < 1e-9
            and costs[r["candidate_id"]][1] == r["eligible"]
            for r in flat
        ) and len(flat) == len(costs)
        lifted = UnifiedReasoner(flattened_knowledge(k)).analyze(frame, top_k=128)
        lifted_costs = {
            r["candidate_id"]: (r["scoring_details"]["total_cost"], r["eligible_for_ranking"])
            for r in lifted["candidate_evaluations"]
        }
        no_conflict = k.model_dump(mode="json")
        no_conflict["execution_policy"]["conflict_weight"] = 0.0
        ablation = UnifiedReasoner(no_conflict).analyze(frame, top_k=128)
        path = atom_path_reference(k, frame)
        row = {
            **case,
            "outcome": actual["outcome"],
            "flat_equivalent": equivalent,
            "intermediate_removal_equivalent": costs == lifted_costs,
            "candidates": [
                (r["candidate_id"], r["rank"], r["score"]) for r in actual["ranked_root_causes"]
            ],
            "atom_path_candidates": [r["candidate_id"] for r in path],
            "no_conflict_candidates": [
                (r["candidate_id"], r["rank"], r["score"]) for r in ablation["ranked_root_causes"]
            ],
            "path_count": len(actual["top_k_paths"]),
        }
        report.append(row)
        (args.output_dir / f"{i:03d}.json").write_text(
            json.dumps(
                {"comparison": row, "flat": flat, "unified": actual, "no_conflict": ablation},
                ensure_ascii=False,
                indent=2,
            )
        )
    summary = {
        "case_count": len(report),
        "flat_equivalent_count": sum(r["flat_equivalent"] for r in report),
        "intermediate_removal_equivalent_count": sum(
            r["intermediate_removal_equivalent"] for r in report
        ),
        "cases": report,
    }
    (args.output_dir / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}))
    if not all(r["flat_equivalent"] and r["intermediate_removal_equivalent"] for r in report):
        raise SystemExit("reference mismatch: inspect per-case reports before making a claim")


if __name__ == "__main__":
    main()
