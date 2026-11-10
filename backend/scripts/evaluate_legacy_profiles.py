"""Run existing generic/scenario reasoners on frozen legacy observations.

These are system references with DIFFERENT knowledge and target vocabularies,
not a controlled same-knowledge accuracy comparison against the v2 method.
"""

import argparse
import json
from pathlib import Path

from kgtracevis.core.rca import GenericGraphPathReasoner
from kgtracevis.kg.entity_linker import link_evidence_entities
from kgtracevis.kg.working_graph_package import WorkingGraphPackage
from kgtracevis.schema.evidence_schema import Evidence
from kgtracevis.workflows.measured_profile_reasoner import MeasuredProfileReasoner
from kgtracevis.workflows.profile_match_reasoner import VisualProfileReasoner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--package", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    packages = [WorkingGraphPackage.model_validate_json(p.read_text()) for p in args.package]
    by_dataset = {p.dataset: p for p in packages}
    if len(by_dataset) != len(packages):
        raise ValueError("supply one legacy knowledge package per dataset")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for item in json.loads(args.manifest.read_text())["cases"]:
        run = json.loads(Path(item["source_run"]).read_text())
        case = next(c for c in run["cases"] if c["case_id"] == item["case_id"])
        evidence = Evidence.model_validate(case["generated_evidence"])
        package = by_dataset[item["dataset"]]
        graph = package.to_graph()
        reasoner = (
            VisualProfileReasoner(package.profiles)
            if package.dataset == "mvtec"
            else MeasuredProfileReasoner(package.profiles)
        )
        links = link_evidence_entities(evidence, graph)
        results = {}
        for name, method in [("scenario", reasoner), ("generic", GenericGraphPathReasoner())]:
            result = method.reason_root_causes(
                evidence, graph=graph, linked_entities=links, top_k=128
            )
            results[name] = {
                "outcome": result.outcome,
                "method": result.scoring_method,
                "path_count": len(result.top_k_paths),
                "candidates": [r.model_dump() for r in result.ranked_root_causes],
            }
        rows.append({**item, "legacy_graph_id": package.graph_id, **results})
    summary = {
        "case_count": len(rows),
        "knowledge_condition": "different_legacy_packages",
        "cases": rows,
    }
    (args.output_dir / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        json.dumps({"case_count": len(rows), "knowledge_condition": summary["knowledge_condition"]})
    )


if __name__ == "__main__":
    main()
