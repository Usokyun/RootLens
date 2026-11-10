"""Checked-in public measured JSON examples remain executable without model calls."""

import json
from pathlib import Path

import pytest

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.unified_evidence import EvidenceFrame

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "data/examples/unified"
CASES = json.loads((EXAMPLES / "manifest.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["evidence"] for c in CASES])
def test_actual_public_frames_and_seed_knowledge_reproduce_the_recorded_result(case):
    package = UnifiedWorkingGraphPackage.model_validate_json((ROOT / case["knowledge"]).read_text())
    frame = EvidenceFrame.model_validate_json((EXAMPLES / case["evidence"]).read_text())
    result = UnifiedReasoner(package.knowledge).analyze(frame, top_k=128)
    assert result["outcome"] == case["outcome"]
    assert [
        {"candidate_id": r["candidate_id"], "rank": r["rank"], "score": r["score"]}
        for r in result["ranked_root_causes"]
    ] == case["candidates"]
    assert all(r["confidence"] is None for r in result["candidate_evaluations"])
