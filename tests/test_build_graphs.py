from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build-graphs.py"


def _load_build_graphs_module():
    spec = importlib.util.spec_from_file_location("build_graphs", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildGraphsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build_graphs = _load_build_graphs_module()

    def test_mvtec_graph_matches_kgtracevis_overlay_builder(self) -> None:
        module = self.build_graphs
        example_records = (
            module.MVTEC_KG_ROOT / "data" / "examples" / "records" / "mvtec_records.jsonl"
        )

        with tempfile.TemporaryDirectory(prefix="rootlens-build-graphs-test-") as tmp_dir:
            output_dir = Path(tmp_dir)
            mvtec_raw = module._build_mvtec_graph(
                output_dir=output_dir,
                mvtec_records_path=example_records,
            )
            normalized = module._normalize_mvtec_dataset(mvtec_raw)

            previous_cwd = os.getcwd()
            try:
                os.chdir(module.MVTEC_KG_ROOT)
                module._ensure_kgtracevis_import_context()
                from kgtracevis.kg.graph import (  # type: ignore[import-untyped]
                    DEFAULT_EDGE_PATHS,
                    DEFAULT_NODE_PATHS,
                    KnowledgeGraph,
                )
                from kgtracevis.kg_construction.case_kg_hardening import (  # type: ignore[import-untyped]
                    write_candidate_kg_artifacts,
                )

                expected_output = write_candidate_kg_artifacts(
                    output_dir=output_dir / "expected-candidate-kg",
                    mvtec_records_path=mvtec_raw["metadata"]["records_path"],
                    mvtec_adapter_table_path=mvtec_raw["metadata"]["table_path"],
                    wm811k_record_paths=mvtec_raw["metadata"]["wm811k_record_paths"],
                    overwrite=True,
                )
                expected_graph = KnowledgeGraph.from_paths(
                    [*DEFAULT_NODE_PATHS, expected_output.nodes_path],
                    [*DEFAULT_EDGE_PATHS, expected_output.edges_path],
                    skip_missing=True,
                )
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(len(normalized["nodes"]), len(expected_graph.nodes))
        self.assertEqual(len(normalized["edges"]), len(expected_graph.edges))
        self.assertEqual(
            {node["id"] for node in normalized["nodes"]},
            set(expected_graph.nodes),
        )
        self.assertEqual(
            {edge["id"] for edge in normalized["edges"]},
            {edge.edge_id for edge in expected_graph.edges},
        )
        self.assertIn(
            "candidate-nodes",
            {node["origin"]["layer"] for node in normalized["nodes"]},
        )
        self.assertIn(
            "candidate-edges",
            {edge["origin"]["layer"] for edge in normalized["edges"]},
        )
        self.assertTrue(normalized["metadata"]["overlay"]["enabled"])
        self.assertTrue(
            normalized["metadata"]["overlay"]["artifacts"]["validationPassed"]
        )


if __name__ == "__main__":
    unittest.main()
