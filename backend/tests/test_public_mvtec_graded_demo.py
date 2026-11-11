"""Keep the released geometry comparison and its real controls honest."""

import copy
import json
from pathlib import Path

import pytest

from kgtracevis.core.graded_reasoner import GradedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.unified_evidence import EvidenceFrame

DEMO = Path(__file__).resolve().parents[1] / "data/demo/graded_rca/mvtec"
BLOCK = {
    "hypothesis:bottle:handling_contact_disturbance",
    "hypothesis:bottle:pre_station_surface_damage",
}
SLENDER = {
    "hypothesis:bottle:directional_surface_disturbance",
    "hypothesis:bottle:directional_imaging_contrast_change",
}


def _frame(name):
    (row,) = json.loads((DEMO / name).read_bytes())["frames"]
    return EvidenceFrame.model_validate(row)


@pytest.fixture(scope="module")
def graph():
    return UnifiedWorkingGraphPackage.model_validate_json(
        (DEMO / "working-graph.v2.json").read_bytes()
    )


def test_public_graph_keeps_physical_checks_out_of_scoring(graph):
    package = graph.knowledge
    assert {row.hypothesis_id for row in package.hypotheses} == BLOCK | SLENDER
    checks = {row.entity_id for row in package.entities if row.kind == "InspectionCheck"}
    assert checks == {"check:bottle:outline", "check:bottle:surface-optics"}
    assert {row.tail for row in package.relations if row.relation == "NEEDS_VERIFICATION"} == checks
    assert {row.feature_id for row in package.observable_definitions} == {
        "detection.anomaly_present",
        "geometry.area_ratio",
        "geometry.aspect_ratio",
        "geometry.eccentricity",
    }
    (group,) = package.graded_policy.groups
    assert len(group.slots) == 3
    assert all(len(slot.predicate_ids) == 2 and slot.weight == 1 for slot in group.slots)


def test_actual_public_frame_preserves_tie_and_eccentricity_source_path(graph):
    frame = _frame("evidence.json")
    reasoner = GradedReasoner(graph.knowledge)
    result = reasoner.analyze(frame)
    edges = {row["edge_id"]: row for row in reasoner.program.projection["edges"]}
    assert result["outcome"] == "ambiguous"
    assert {row["candidate_id"] for row in result["ranked_root_causes"]} == BLOCK
    obs = next(o for o in frame.observations if o.feature_id == "geometry.eccentricity")
    assert obs.value.number == pytest.approx(0.7969506925604166)
    assert obs.scope_id == frame.task.scope_id
    for candidate in result["graded_candidates"]:
        assert candidate["rank"] == 1
        assert candidate["scoring_details"] == {
            "support": 1.0,
            "conflict": 0.0,
            "score": 1.0,
            "coverage": 1.0,
        }
        term = next(
            c for c in candidate["graded_conditions"] if c["feature_id"] == "geometry.eccentricity"
        )
        path = next(
            p for p in candidate["explanation_paths"] if p["predicate_id"] == term["predicate_id"]
        )
        assert term["observed_obs_ids"] == path["observation_ids"] == [obs.obs_id]
        assert any(
            term["predicate_id"] in (edges[v["edge_id"]]["head"], edges[v["edge_id"]]["tail"])
            for v in path["source_edge_views"]
        )
        assert "source:mvtec-graded-human-review:shape-budget" in path["source_assertion_ids"]
        assert term["score_contribution"] == pytest.approx(1 / 3)


def test_single_value_counterfactual_reaches_slender_or_branch_without_hiding_block_support(graph):
    actual = _frame("evidence.json").model_dump(mode="json")
    changed = copy.deepcopy(actual)
    eccentricity = next(
        o for o in changed["observations"] if o["feature_id"] == "geometry.eccentricity"
    )
    eccentricity["value"]["number"] = 0.94
    result = GradedReasoner(graph.knowledge).analyze(changed)
    assert {row["candidate_id"] for row in result["ranked_root_causes"]} == SLENDER
    rows = {row["candidate_id"]: row for row in result["graded_candidates"]}
    for candidate in BLOCK:
        row = rows[candidate]
        assert row["status"] == "pending"
        assert row["scoring_details"] == pytest.approx(
            {
                "support": 2 / 3,
                "conflict": 1 / 6,
                "score": 0.5,
                "coverage": 1,
            }
        )
        assert row["counter_obs_ids"] == [eccentricity["obs_id"]]
    for candidate in SLENDER:
        row = rows[candidate]
        assert row["status"] == "supported"
        assert row["score"] == pytest.approx(0.5)
        assert {c["feature_id"] for c in row["graded_conditions"]} == {
            "detection.anomaly_present",
            "geometry.area_ratio",
            "geometry.eccentricity",
        }


def test_actual_normal_and_surface_controls_preserve_limits(graph):
    engine = GradedReasoner(graph.knowledge)
    normal = engine.analyze(_frame("contrast-a.evidence.json"))
    assert normal["outcome"] == "no_match"
    assert normal["reason"] == "anomaly_gate_is_false"
    assert not normal["graded_candidates"] and not normal["top_k_paths"]
    surface = engine.analyze(_frame("contrast-b.evidence.json"))
    assert surface["outcome"] == "ambiguous"
    assert {row["candidate_id"] for row in surface["ranked_root_causes"]} == BLOCK
    assert all(
        row["score"] == pytest.approx(0.6795247395833333) for row in surface["graded_candidates"]
    )
