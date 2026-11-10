"""Common reasoning semantics, not per-dataset answer fixtures or native labels."""

import copy

import networkx as nx
import pytest
from test_unified_contracts import example

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_compiler import KnowledgeProgram, SearchLimits


@pytest.fixture
def knowledge():
    return example("knowledge-package.json")


def scores(result):
    return {r["candidate_id"]: r["score"] for r in result["candidate_evaluations"]}


def by_candidate(result, candidate_id):
    return next(r for r in result["candidate_evaluations"] if r["candidate_id"] == candidate_id)


@pytest.mark.parametrize("scene", ["mvtec", "tep", "wafer"])
def test_one_engine_reproduces_the_declared_scores_and_outcomes(knowledge, scene):
    actual = UnifiedReasoner(knowledge).analyze(example(f"{scene}-evidence.json"))
    expected = example(f"{scene}-expected-result.json")
    assert actual["outcome"] == expected["outcome"]
    assert scores(actual) == pytest.approx(scores(expected))
    assert len(actual["top_k_paths"]) == len(expected["top_k_paths"])
    assert {r["candidate_id"] for r in actual["ranked_root_causes"]} == {
        r["candidate_id"] for r in expected["ranked_root_causes"]
    }
    assert all(r["confidence"] is None for r in actual["ranked_root_causes"])


def test_graph_projection_and_explanation_views_reference_actual_edges(knowledge):
    program = KnowledgeProgram(knowledge)
    expected = example("knowledge-graph-view.json")
    assert set(program.edges) == {e["edge_id"] for e in expected["edges"]}
    result = UnifiedReasoner(knowledge).analyze(example("mvtec-evidence.json"))
    proof_ids = {n["node_id"] for n in result["proof_graph"]["nodes"]}
    for path in result["top_k_paths"]:
        assert path["joint_proof_id"] in proof_ids
        assert len(path["required_joint_fact_ids"]) == 2
        for i, view in enumerate(path["source_edge_views"]):
            edge = program.edges[view["edge_id"]]
            endpoints = (
                (edge["tail"], edge["head"]) if view["reverse"] else (edge["head"], edge["tail"])
            )
            assert endpoints == tuple(path["nodes"][i : i + 2])
    dag = nx.DiGraph()
    dag.add_nodes_from(proof_ids)
    dag.add_edges_from((e["head"], e["tail"]) for e in result["proof_graph"]["edges"])
    assert set(dag) == proof_ids
    assert nx.is_directed_acyclic_graph(dag)


def test_negative_candidate_is_recalled_but_not_put_on_the_support_ranking(knowledge):
    result = UnifiedReasoner(knowledge).analyze(example("mvtec-evidence.json"), top_k=1)
    assert "h:adhesion" in result["candidate_pool"]
    adhesion = by_candidate(result, "h:adhesion")
    assert adhesion["counter_obs_ids"] == ["o:material"]
    assert adhesion["scoring_details"]["conflict_loss"] == pytest.approx(1 / 3)
    assert adhesion["eligible_for_ranking"] is False
    assert [r["rank"] for r in result["ranked_root_causes"]] == [1, 1]


def test_order_duplicates_and_dataset_name_do_not_change_scores(knowledge):
    engine = UnifiedReasoner(knowledge)
    frame = example("mvtec-evidence.json")
    baseline = engine.analyze(frame)
    frame["source_dataset"] = "new-independent-inspection-domain"
    duplicate = copy.deepcopy(frame["observations"][1])
    duplicate["obs_id"] = "o:duplicate"
    frame["observations"].append(duplicate)
    frame["observations"].reverse()
    altered = engine.analyze(frame)
    assert scores(altered) == scores(baseline)
    assert len(altered["grounded_facts"]) == len(baseline["grounded_facts"])
    assert len(altered["top_k_paths"]) == len(baseline["top_k_paths"])


def test_missing_open_set_and_explicit_negative_have_different_meanings(knowledge):
    frame = example("mvtec-evidence.json")
    frame["observations"][3].update(status="missing", value=None)
    missing = UnifiedReasoner(knowledge).analyze(frame)
    assert any(x["candidate_id"] == "h:adhesion" for x in missing["unassessed_candidates"])
    assert "h:adhesion" not in scores(missing)
    frame["observations"][2]["value"]["items"] = ["crack"]
    unknown = UnifiedReasoner(knowledge).analyze(frame)
    assert unknown["outcome"] == "insufficient_evidence"
    cue = next(f for f in unknown["grounded_facts"] if f["predicate_id"] == "q:scratch_cue")
    assert cue["value"] is None and cue["measured"] is True
    frame["observations"][2]["value"]["exhaustive"] = True
    negative = UnifiedReasoner(knowledge).analyze(frame)
    cue = next(f for f in negative["grounded_facts"] if f["predicate_id"] == "q:scratch_cue")
    assert cue["value"] is False
    assert by_candidate(negative, "h:contact")["status"] == "no_match"


def test_invalid_unit_and_incompatible_scaler_cannot_turn_into_normal_values(knowledge):
    frame = example("mvtec-evidence.json")
    frame["observations"][1]["value"]["unit"] = "mm"
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert result["ranked_root_causes"] == []
    assert result["outcome"] == "insufficient_evidence"
    assert (
        next(f for f in result["grounded_facts"] if f["predicate_id"] == "q:elongated")["status"]
        == "invalid"
    )
    temporal = example("tep-evidence.json")
    temporal["references"].append({**temporal["references"][0], "reference_id": "different"})
    temporal["task"]["reference_id"] = "different"
    result = UnifiedReasoner(knowledge).analyze(temporal)
    assert result["outcome"] == "insufficient_evidence"
    assert not result["ranked_root_causes"]


def test_features_from_different_rois_are_not_joined(knowledge):
    frame = example("mvtec-evidence.json")
    frame["subjects"].append(
        {"subject_id": "roi:2", "kind": "image_region", "parent_id": "object:1"}
    )
    frame["scopes"].append({**frame["scopes"][0], "scope_id": "scope:roi2", "subject_id": "roi:2"})
    frame["observations"][1].update(subject_id="roi:2", scope_id="scope:roi2")
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert not result["ranked_root_causes"]
    assert result["outcome"] == "insufficient_evidence"


def test_changed_values_and_deleted_knowledge_change_new_reasoning(knowledge):
    frame = example("mvtec-evidence.json")
    frame["observations"][1]["value"]["number"] = 0.70
    changed = UnifiedReasoner(knowledge).analyze(frame)
    assert changed["outcome"] == "no_match"
    assert not changed["ranked_root_causes"]
    knowledge["effect_rules"] = [
        r for r in knowledge["effect_rules"] if r["rule_id"] != "r:contact_effect"
    ]
    changed = UnifiedReasoner(knowledge).analyze(example("mvtec-evidence.json"))
    assert [r["candidate_id"] for r in changed["ranked_root_causes"]] == ["h:wear"]
    assert all("r:contact_effect" not in p["nodes"] for p in changed["top_k_paths"])


def test_all_expectations_are_checked_not_only_selected_support_paths(knowledge):
    knowledge["expectation_rules"].append(
        {
            "rule_id": "r:additional_expectation",
            "from_id": "h:contact",
            "pattern_id": "p:foreign_material",
            "mode": "expected",
            "source_assertion_ids": ["s:visual-design"],
        }
    )
    result = UnifiedReasoner(knowledge).analyze(example("mvtec-evidence.json"))
    contact = by_candidate(result, "h:contact")
    assert contact["score"] == pytest.approx(-(0.25 + 2 / 3))
    assert contact["counter_obs_ids"] == ["o:material"]
    assert result["ranked_root_causes"][0]["candidate_id"] == "h:wear"


def test_or_is_a_declared_complete_alternative_not_a_conflict_on_every_branch(knowledge):
    knowledge["pattern_definitions"][0]["body"] = {"any": ["q:elongated", "q:scratch_cue"]}
    frame = example("mvtec-evidence.json")
    frame["observations"][2]["value"].update(items=["crack"], exhaustive=True)
    result = UnifiedReasoner(knowledge).analyze(frame)
    contact = by_candidate(result, "h:contact")
    assert contact["score"] == -0.25
    assert contact["scoring_details"]["conflict_loss"] == 0
    assert contact["expectation_checks"][0]["predicate_ids"] == ["q:elongated"]


def test_unseeded_recursive_definition_is_not_its_own_evidence(knowledge):
    knowledge["pattern_definitions"][0]["body"] = {"all": ["p:linear_mark", "q:elongated"]}
    result = UnifiedReasoner(knowledge).analyze(example("mvtec-evidence.json"))
    assert not result["ranked_root_causes"]
    assert (
        by_candidate(result, "h:contact")["expectation_checks"][0]["reason"]
        == "no_finite_definition_proof"
    )


def test_empty_evidence_and_budget_exhaustion_never_fall_back_to_generic_paths(knowledge):
    frame = example("mvtec-evidence.json")
    frame["observations"] = []
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert result["outcome"] == "insufficient_evidence"
    assert not result["ranked_root_causes"]
    limited = UnifiedReasoner(knowledge, limits=SearchLimits(candidates=1))
    result = limited.analyze(example("mvtec-evidence.json"))
    assert result["outcome"] == "search_incomplete"
    assert not result["ranked_root_causes"]


def test_consistent_knowledge_identity_renaming_preserves_the_method(knowledge):
    ids = {node["node_id"] for node in KnowledgeProgram(knowledge).projection["nodes"]}
    renamed = {identity: "renamed:" + identity for identity in ids}

    def rewrite(value):
        if isinstance(value, str):
            return renamed.get(value, value)
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        return value

    frame = example("tep-evidence.json")
    original = UnifiedReasoner(knowledge).analyze(frame)
    changed = UnifiedReasoner(rewrite(knowledge)).analyze(frame)
    assert scores(changed) == {renamed[key]: value for key, value in scores(original).items()}


def test_compiled_snapshot_does_not_change_when_callers_mutate_their_working_copy(knowledge):
    frozen = UnifiedReasoner(knowledge)
    knowledge["observable_definitions"][0]["operand"]["number"] = 0.999
    frame = example("mvtec-evidence.json")
    assert frozen.analyze(frame)["outcome"] == "ambiguous"
    assert UnifiedReasoner(knowledge).analyze(frame)["outcome"] == "no_match"


def test_new_alias_changes_binding_without_a_new_dataset_reasoner(knowledge):
    frame = example("mvtec-evidence.json")
    frame["subjects"][0]["external_id"] = "new-nut-alias"
    assert UnifiedReasoner(knowledge).analyze(frame)["outcome"] == "not_applicable"
    knowledge["entities"][1]["aliases"] = ["new-nut-alias"]
    assert UnifiedReasoner(knowledge).analyze(frame)["outcome"] == "ambiguous"


def test_unregistered_features_are_saved_as_unused_not_self_interpreted(knowledge):
    frame = example("mvtec-evidence.json")
    bogus = copy.deepcopy(frame["observations"][1])
    bogus.update(obs_id="invented", feature_id="mystery.root_cause_strength")
    frame["observations"].append(bogus)
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert scores(result)["h:contact"] == -0.25
    assert {"obs_id": "invented", "reason": "unregistered_feature"} in result["unused_observations"]


def test_at_least_and_branch_budgets_are_explicit(knowledge):
    knowledge["pattern_definitions"][0]["body"] = {
        "at_least": {"count": 2, "of": ["q:elongated", "q:scratch_cue", "q:foreign_material"]}
    }
    frame = example("mvtec-evidence.json")
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert scores(result)["h:contact"] == -0.25
    limited = UnifiedReasoner(knowledge, limits=SearchLimits(branches=1)).analyze(frame)
    assert limited["outcome"] == "search_incomplete"
    assert not limited["ranked_root_causes"]


def test_cli_exports_actual_inputs_graph_and_results_without_overwriting(tmp_path):
    import json

    from test_unified_contracts import EXAMPLES

    from scripts.run_unified_reasoning import main

    target = tmp_path / "run"
    args = [
        "--knowledge",
        str(EXAMPLES / "knowledge-package.json"),
        "--evidence",
        str(EXAMPLES / "mvtec-evidence.json"),
        "--output-dir",
        str(target),
    ]
    assert main(args) == 0
    assert json.loads((target / "case-0000-result.json").read_text())["outcome"] == "ambiguous"
    assert json.loads((target / "graph-view.json").read_text())["nodes"]
    with pytest.raises(FileExistsError):
        main(args)
