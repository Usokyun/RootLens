"""Actual public TEP Frames exercise the authored signed, same-window rule."""

import json
from pathlib import Path

import pytest

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.unified_evidence import EvidenceFrame

DEMO = Path("data/demo/two_loop/tep")
WARM = "signature:reactor_cooling_load_shift:condition:1"
RESPONSE = "signature:reactor_alternative_responses"


@pytest.fixture(scope="module")
def public_demo():
    graph = UnifiedWorkingGraphPackage.model_validate_json(
        (DEMO / "working-graph.v2.json").read_text()
    )
    frames = [
        EvidenceFrame.model_validate(item)
        for item in json.loads((DEMO / "evidence.json").read_text())["frames"]
    ]
    return graph, frames


def test_three_real_windows_keep_warm_outlet_distinct_from_cascade_compensation(public_demo):
    graph, frames = public_demo
    assert len(frames) == 3
    assert len({frame.task.reference_id for frame in frames}) == 1
    reasoner = UnifiedReasoner(graph.knowledge)
    results = [reasoner.analyze(frame, top_k=8) for frame in frames]
    assert [result["outcome"] for result in results] == ["no_match", "ambiguous", "ambiguous"]
    assert not results[0]["ranked_root_causes"]
    assert not results[0]["top_k_paths"]
    for frame, result in zip(frames[1:], results[1:], strict=True):
        assert len([o for o in frame.observations if o.feature_id == "residual.contribution"]) == 52
        facts = {fact["predicate_id"]: fact for fact in result["grounded_facts"]}
        assert facts[WARM]["value"] is False
        patterns = {row["pattern_id"]: row["value"] for row in result["observed_patterns"]}
        assert patterns[RESPONSE] is True
        ranks = result["ranked_root_causes"]
        assert [(rank["rank"], rank["score"]) for rank in ranks] == [(1, -0.25), (1, -0.25)]
        assert all(rank["scoring_details"]["conflict_loss"] == 0 for rank in ranks)
        supporting_channels = {
            obs.subject_id
            for obs in frame.observations
            if obs.obs_id in ranks[0]["support_obs_ids"] and obs.feature_id == "statistics.mean_z"
        }
        assert supporting_channels == {"variable:xmv_10", "variable:xmeas_9"}
        assert len(result["top_k_paths"]) == 8


@pytest.mark.parametrize("channel,value", [("xmv_10", None), ("xmeas_9", 2.5)])
def test_cascade_requires_both_measured_channels_and_keeps_signed_direction(
    public_demo, channel, value
):
    graph, frames = public_demo
    raw = frames[1]
    counterfactual = raw.model_dump(mode="json")
    measurement = next(
        item
        for item in counterfactual["observations"]
        if item["feature_id"] == "statistics.mean_z" and item["subject_id"] == f"variable:{channel}"
    )
    prior = measurement["value"]["number"]
    # Change one typed value in memory, not the stored Frame or the original series.
    measurement["value"]["number"] = -prior if value is None else value
    changed = EvidenceFrame.model_validate(counterfactual)
    result = UnifiedReasoner(graph.knowledge).analyze(changed, top_k=8)
    assert result["outcome"] == "no_match"
    assert result["ranked_root_causes"] == []
    assert result["top_k_paths"] == []
    assert any(
        row["pattern_id"] == RESPONSE and row["value"] is False
        for row in result["observed_patterns"]
    )
