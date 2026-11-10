"""Perturb frozen actual observations/knowledge without rerunning perception."""

import argparse
import copy
import json
from pathlib import Path

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.experiments.unified_diagnosis import flat_reference
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


def signature(result):
    return {
        "outcome": result["outcome"],
        "costs": {
            r["candidate_id"]: [r["score"], r["eligible_for_ranking"]]
            for r in result["candidate_evaluations"]
        },
        "paths": [p["nodes"] for p in result["top_k_paths"]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for item in json.loads(args.manifest.read_text())["cases"]:
        knowledge = KnowledgePackage.model_validate_json(Path(item["knowledge"]).read_text())
        frame = json.loads(Path(item["evidence"]).read_text())
        engine = UnifiedReasoner(knowledge)
        original = engine.analyze(frame, top_k=128)
        baseline = signature(original)
        duplicate = copy.deepcopy(frame)
        # Duplicate an actually referenced source row, including explicit counterevidence.
        fact = next((f for f in original["grounded_facts"] if f["source_obs_ids"]), None)
        obs_id = fact["source_obs_ids"][0] if fact else frame["observations"][0]["obs_id"]
        row = copy.deepcopy(next(o for o in frame["observations"] if o["obs_id"] == obs_id))
        row["obs_id"] += ":repeated-source-row"
        duplicate["observations"].append(row)
        duplicate["observations"].reverse()
        duplicate["source_dataset"] = "unseen_dataset_name_no_rank_dispatch"
        altered = engine.analyze(duplicate, top_k=128)
        output = {**item, "duplicate_reorder_dataset_invariant": baseline == signature(altered)}
        original_flat = flat_reference(knowledge, EvidenceFrame.model_validate(frame))
        naive = flat_reference(
            knowledge, EvidenceFrame.model_validate(duplicate), count_source_rows=True
        )
        output["naive_source_counting_changed"] = original_flat != naive
        output["global_weight_sensitivity"] = {}
        for weight in [0.0, 1.0, 4.0]:
            changed = knowledge.model_dump(mode="json")
            changed["execution_policy"]["conflict_weight"] = weight
            output["global_weight_sensitivity"][str(weight)] = signature(
                UnifiedReasoner(changed).analyze(frame, top_k=128)
            )
        if original["ranked_root_causes"]:
            candidate = original["ranked_root_causes"][0]
            used = candidate["support_obs_ids"][0]
            missing = copy.deepcopy(frame)
            target = next(o for o in missing["observations"] if o["obs_id"] == used)
            target.update(status="missing", value=None)
            output["used_observation_removed"] = used
            output["missing_result"] = signature(engine.analyze(missing, top_k=128))
            used_rule = next(
                (e for e in knowledge.effect_rules if e.from_id == candidate["candidate_id"]), None
            )
            if used_rule:
                changed = knowledge.model_dump(mode="json")
                changed["effect_rules"] = [
                    r for r in changed["effect_rules"] if r["rule_id"] != used_rule.rule_id
                ]
                output["deleted_rule"] = used_rule.rule_id
                output["deleted_rule_result"] = signature(
                    UnifiedReasoner(changed).analyze(frame, top_k=128)
                )
            output["original"] = baseline
        rows.append(output)
    summary = {
        "case_count": len(rows),
        "invariant_count": sum(r["duplicate_reorder_dataset_invariant"] for r in rows),
        "naive_duplicate_sensitive_count": sum(r["naive_source_counting_changed"] for r in rows),
        "cases": rows,
    }
    (args.output_dir / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}))
    if summary["invariant_count"] != len(rows):
        raise SystemExit("unexpected invariance failure; inspect reports")


if __name__ == "__main__":
    main()
