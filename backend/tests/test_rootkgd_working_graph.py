"""RootKGD consumes current knowledge and a complete, referenced contribution vector."""

import copy
import json
from pathlib import Path

import pytest

from kgtracevis.core.rootkgd_reasoner import CHANNELS, RootKGDReasoner
from kgtracevis.kg.unified_compiler import KnowledgeProgram


@pytest.fixture
def inputs():
    package = json.loads(Path("data/kg/unified/tep-working-graph.v2.json").read_text())
    frame = json.loads(Path("data/examples/unified/tep-cooling-window.json").read_text())
    return package["knowledge"], frame


def test_current_graph_structural_score_has_full_52_channel_trace(inputs):
    knowledge, frame = inputs
    result = RootKGDReasoner(knowledge).analyze(frame)
    assert result["outcome"] == "supported"
    assert result["scoring_method"] == "tep_rootkgd_propagation_v1"
    assert result["propagation"]["fault_label_used"] is False
    assert result["propagation"]["memory_enabled"] is False
    assert len(result["propagation"]["observed_contribution_vector"]) == 52
    assert len(result["propagation"]["scoring_input_obs_ids"]) == 52
    input_ids = set(result["propagation"]["scoring_input_obs_ids"])
    assert not input_ids & {row["obs_id"] for row in result["unused_observations"]}
    assert result["propagation"]["graph_channel_coverage"]["unreached_contribution_mass"] > 0
    for row in result["ranked_root_causes"]:
        details = row["scoring_details"]
        assert details["channel_order"] == CHANNELS
        assert row["score"] == pytest.approx(
            details["cosine_similarity"] - details["coverage_penalty"] - details["entropy_penalty"]
        )
        assert len(details["propagated_channel_vector"]) == 52
        assert row["confidence"] is None


def test_rootkgd_paths_are_contiguous_actual_projection_edges(inputs):
    knowledge, frame = inputs
    result = RootKGDReasoner(knowledge).analyze(frame)
    program = KnowledgeProgram(knowledge)
    assert result["top_k_paths"]
    for path in result["top_k_paths"]:
        assert len(path["nodes"]) == len(path["source_edge_views"]) + 1
        assert path["source_assertion_ids"]
        for index, view in enumerate(path["source_edge_views"]):
            edge = program.edges[view["edge_id"]]
            endpoints = (
                [edge["tail"], edge["head"]] if view["reverse"] else [edge["head"], edge["tail"]]
            )
            assert path["nodes"][index : index + 2] == endpoints
        assert path["interpretation"] == "structural_propagation_support_not_joint_condition_proof"


def test_normal_gate_suppresses_candidates_and_missing_reference_fails(inputs):
    knowledge, frame = inputs
    normal = copy.deepcopy(frame)
    next(o for o in normal["observations"] if o["feature_id"] == "detection.anomaly_present")[
        "value"
    ]["boolean"] = False
    result = RootKGDReasoner(knowledge).analyze(normal)
    assert result["outcome"] == "no_match"
    assert not result["ranked_root_causes"]
    for observation in normal["observations"]:
        if observation["feature_id"] == "residual.contribution":
            observation["value"]["number"] = 0.0
    assert RootKGDReasoner(knowledge).analyze(normal)["outcome"] == "no_match"
    missing = copy.deepcopy(frame)
    missing["task"]["reference_id"] = None
    with pytest.raises(ValueError, match="正常参考"):
        RootKGDReasoner(knowledge).analyze(missing)


def test_rootkgd_requires_complete_not_just_top_contributions(inputs):
    knowledge, frame = inputs
    missing = copy.deepcopy(frame)
    victim = next(o for o in missing["observations"] if o["feature_id"] == "residual.contribution")
    missing["observations"].remove(victim)
    with pytest.raises(ValueError, match="52"):
        RootKGDReasoner(knowledge).analyze(missing)


def test_repeating_same_channel_predicate_does_not_multiply_propagation(inputs):
    knowledge, frame = inputs
    original = RootKGDReasoner(knowledge).analyze(frame)
    changed = copy.deepcopy(knowledge)
    predicate = next(
        o
        for o in changed["observable_definitions"]
        if o["subject_selector"]["kind"] == "bound_entity"
    )
    duplicate = copy.deepcopy(predicate)
    duplicate["predicate_id"] += ":duplicate"
    changed["observable_definitions"].append(duplicate)
    for pattern in changed["pattern_definitions"]:
        if pattern["body"].get("all") and predicate["predicate_id"] in pattern["body"]["all"]:
            pattern["body"]["all"].append(duplicate["predicate_id"])
    result = RootKGDReasoner(changed).analyze(frame)
    assert [(r["candidate_id"], r["score"]) for r in result["ranked_root_causes"]] == [
        (r["candidate_id"], r["score"]) for r in original["ranked_root_causes"]
    ]


def test_current_graph_effect_edit_changes_ranking_and_input_names_do_not(inputs):
    knowledge, frame = inputs
    original = RootKGDReasoner(knowledge).analyze(frame)
    renamed = copy.deepcopy(frame)
    renamed["source_dataset"] = "unrelated_name_not_a_fault"
    assert (
        RootKGDReasoner(knowledge).analyze(renamed)["ranked_root_causes"]
        == original["ranked_root_causes"]
    )
    changed = copy.deepcopy(knowledge)
    top = original["ranked_root_causes"][0]["candidate_id"]
    changed["effect_rules"] = [r for r in changed["effect_rules"] if r["from_id"] != top]
    result = RootKGDReasoner(changed).analyze(frame)
    assert top not in [r["candidate_id"] for r in result["ranked_root_causes"]]
