"""Compile public/source material with a registered adapter capability manifest."""

import argparse
import json
from pathlib import Path

from kgtracevis.adapters.unified_capabilities import capability_manifest
from kgtracevis.source_kg_compiler.llm import OpenAICompatibleSourceKGLLM
from kgtracevis.source_kg_compiler.material_parser import parse_material, read_parsed_bundle
from kgtracevis.source_kg_compiler.unified import compile_unified_knowledge
from kgtracevis.source_kg_compiler.unified_blueprint import KnowledgeBlueprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--scenario", choices=["mvtec", "tep", "wafer"], required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--blueprint", type=Path, help="Recompile a saved LLM blueprint without a model call"
    )
    args = parser.parse_args()
    capabilities = capability_manifest(args.capability)
    units = []
    for index, path in enumerate(args.source):
        bundle = read_parsed_bundle(path) or parse_material(
            path,
            source_id=f"source:{index + 1}:{path.stem}",
            scenario=args.scenario,
        )
        units.extend(bundle.units)
    package = compile_unified_knowledge(
        units,
        capabilities,
        llm_client=None if args.blueprint else OpenAICompatibleSourceKGLLM(),
        output_dir=args.output_dir,
        title=args.title,
        dataset=args.scenario,
        stored_blueprint=KnowledgeBlueprint.model_validate_json(args.blueprint.read_text())
        if args.blueprint
        else None,
    )
    print(
        json.dumps(
            {
                "package": str(args.output_dir / "working-graph.v2.json"),
                "nodes": len(package.nodes),
                "edges": len(package.edges),
            }
        )
    )


if __name__ == "__main__":
    main()
