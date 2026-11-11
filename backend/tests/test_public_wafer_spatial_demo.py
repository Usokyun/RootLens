"""The published real Wafer observations exercise the authored spatial conditions."""

import copy
import json
from pathlib import Path

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.unified_evidence import EvidenceFrame

DATA = Path(__file__).resolve().parents[1] / "data/demo/two_loop/wafer"


def test_public_wafer_nearfull_requires_spatial_support_beyond_classifier():
    package = UnifiedWorkingGraphPackage.model_validate_json(
        (DATA / "working-graph.v2.json").read_text()
    )
    (payload,) = json.loads((DATA / "evidence.json").read_text())["frames"]
    engine = UnifiedReasoner(package.knowledge)
    result = engine.analyze(EvidenceFrame.model_validate(payload), top_k=8)
    assert result["outcome"] == "supported"
    (ranked,) = result["ranked_root_causes"]
    assert ranked["candidate_id"].endswith(":pattern_family_nearfull")
    assert len(result["top_k_paths"]) == 6
    assert any(
        f["scope_id"] == "scope:center"
        and f["predicate_id"].startswith("signature:pattern_edge_ring:")
        and f["value"] is False
        for f in result["grounded_facts"]
    )

    # Controlled single-observation test, not another raw grid measurement.
    variant = copy.deepcopy(payload)
    largest = next(
        o for o in variant["observations"] if o["feature_id"] == "spatial.largest_component_ratio"
    )
    largest["value"]["number"] = 0.50
    changed = engine.analyze(EvidenceFrame.model_validate(variant), top_k=8)
    assert changed["outcome"] == "insufficient_evidence"
    assert changed["ranked_root_causes"] == [] and changed["top_k_paths"] == []
    (tentative,) = changed["tentative_candidates"]
    assert tentative["candidate_id"] == ranked["candidate_id"]
