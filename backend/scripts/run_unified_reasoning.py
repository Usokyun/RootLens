"""Run v2 Evidence against one executable knowledge snapshot, without a database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--knowledge",
        type=Path,
        required=True,
        help="Canonical knowledge or v2 working graph package",
    )
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)
    payload = json.loads(args.knowledge.read_text(encoding="utf-8"))
    knowledge = (
        UnifiedWorkingGraphPackage.model_validate(payload).knowledge
        if payload.get("schema_version") == "rootlens-working-graph.v2"
        else KnowledgePackage.model_validate(payload)
    )
    frames = []
    for source in args.evidence:
        text = source.read_text(encoding="utf-8")
        values = (
            [json.loads(line) for line in text.splitlines() if line.strip()]
            if (source.suffix == ".jsonl")
            else json.loads(text)
        )
        values = values if isinstance(values, list) else [values]
        frames.extend(EvidenceFrame.model_validate(value) for value in values)
    engine = UnifiedReasoner(knowledge)
    # Validate all inputs before creating outputs; never overwrite a prior run.
    results = [engine.analyze(frame, top_k=args.top_k) for frame in frames]
    args.output_dir.mkdir(parents=True, exist_ok=False)

    def write(name, value):
        (args.output_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    write("knowledge-package.json", knowledge.model_dump(mode="json"))
    write("graph-view.json", engine.program.projection)
    manifest = []
    for index, (frame, result) in enumerate(zip(frames, results, strict=True)):
        prefix = f"case-{index:04d}"
        write(prefix + "-evidence.json", frame.model_dump(mode="json"))
        write(prefix + "-result.json", result)
        manifest.append(
            {
                "case_id": frame.case_id,
                "evidence": prefix + "-evidence.json",
                "result": prefix + "-result.json",
                "outcome": result["outcome"],
            }
        )
    write("manifest.json", {"scoring_method": "unified_constraint_abduction_v0", "cases": manifest})
    print(json.dumps({"output_dir": str(args.output_dir), "cases": manifest}, ensure_ascii=False))
    return 2 if any(r["outcome"] == "search_incomplete" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
