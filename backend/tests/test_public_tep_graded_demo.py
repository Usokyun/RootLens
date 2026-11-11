"""The two released TEP series share a graph, not a diagnosis or reference instance."""

import copy
import json
from pathlib import Path

import pytest
from test_graded_reasoner import observation

from kgtracevis.core.graded_reasoner import GradedReasoner
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage

PUBLIC = Path(__file__).resolve().parents[1] / "data/demo/graded_rca/tep"


@pytest.fixture(scope="module")
def release():
    graph = UnifiedWorkingGraphPackage.model_validate_json(
        (PUBLIC / "working-graph.v2.json").read_bytes()
    )
    d04 = json.loads((PUBLIC / "evidence.json").read_bytes())["frames"]
    (d05,) = json.loads((PUBLIC / "evidence-d05.json").read_bytes())["frames"]
    return GradedReasoner(graph.knowledge), d04, d05


def test_the_actual_windows_distinguish_cooling_response_families_not_their_causes(release):
    engine, d04, d05 = release
    before, reactor, later = [engine.analyze(frame, top_k=8) for frame in d04]
    condenser = engine.analyze(d05, top_k=8)
    assert before["reason"] == "anomaly_gate_is_false" and not before["graded_candidates"]
    assert len({f["task"]["reference_id"] for f in d04}) == 1
    assert d05["task"]["reference_id"] != d04[0]["task"]["reference_id"]
    assert [r["outcome"] for r in (reactor, later, condenser)] == ["ambiguous"] * 3
    for r in (reactor, later):
        rows = r["graded_candidates"]
        assert (
            len(rows) == 2
            and [(row["status"], row["rank"]) for row in rows] == [("supported", 1)] * 2
        )
        assert [row["score"] for row in rows] == pytest.approx([1 / 3] * 2)
        assert all("reactor" in row["candidate_id"] for row in rows)
        assert all(
            {slot["slot_id"] for slot in row["graded_slots"]} == {"xmv_10.mean_z", "xmeas_9.mean_z"}
            for row in rows
        )
    cold = condenser["graded_candidates"]
    assert len(cold) == 2 and all("condenser" in row["candidate_id"] for row in cold)
    assert [row["score"] for row in cold] == pytest.approx([0.41194009156189165] * 2)
    assert all(row["support_measurement_count"] == 3 for row in cold)
    assert len(condenser["top_k_paths"]) == 8
    for trace in condenser["top_k_paths"]:
        assert trace["joint_proof_id"] is None
        assert all(v["edge_id"] in engine.program.edges for v in trace["source_edge_views"])
    off = next(
        row for row in condenser["candidate_evaluations"] if "reactor" in row["candidate_id"]
    )
    assert off["status"] == "insufficient_evidence" and off["support_measurement_count"] == 1
    negative = next(c for c in off["graded_conditions"] if c["slot_id"] == "xmv_10.mean_z")
    assert negative["score_contribution"] == pytest.approx(-0.009534978476341313)
    assert not any(p["candidate_id"] == off["candidate_id"] for p in condenser["top_k_paths"])


def test_same_actual_d05_frame_separates_new_knowledge_from_scoring_formula(release):
    engine, _, d05 = release
    # Control: hold the engine/curves fixed but remove the new condenser/separator
    # expectation. This is a topology ablation, not a reconstruction of a prior run.
    without_cold_branch = engine.program.package.model_dump(mode="json")
    without_cold_branch["expectation_rules"] = [
        row for row in without_cold_branch["expectation_rules"] if "condenser" not in row["from_id"]
    ]
    old_strict = UnifiedReasoner(without_cold_branch).analyze(d05)
    old_graded = GradedReasoner(without_cold_branch).analyze(d05)
    assert old_strict["outcome"] == "insufficient_evidence"
    assert not old_strict["ranked_root_causes"]
    assert not old_graded["graded_candidates"]
    new_strict = UnifiedReasoner(engine.program.package).analyze(d05)
    new_graded = engine.analyze(d05)
    assert new_strict["outcome"] == new_graded["outcome"] == "ambiguous"
    assert {r["candidate_id"] for r in new_strict["ranked_root_causes"]} == {
        r["candidate_id"] for r in new_graded["ranked_root_causes"]
    }


@pytest.mark.parametrize("value,coverage", [(1.0, 1.0), (None, 2 / 3)])
def test_separator_temperature_is_a_decisive_slot_not_an_ignored_column(release, value, coverage):
    engine, _, d05 = release
    contrast = copy.deepcopy(d05)
    cue = observation(contrast, "statistics.std_z", "variable:xmeas_11")
    if value is None:
        cue.update(status="missing", value=None)
    else:
        cue["value"]["number"] = value
    result = engine.analyze(contrast)
    assert not result["ranked_root_causes"]
    rows = result["graded_candidates"]
    assert [(row["status"], row["rank"]) for row in rows] == [("pending", 1)] * 2
    for row in rows:
        assert row["scoring_details"]["coverage"] == pytest.approx(coverage)
        assert row["scoring_details"]["conflict"] == 0
        assert row["score"] == pytest.approx(0.41194009156189165 - 1 / 6)
