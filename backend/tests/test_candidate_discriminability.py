"""Authoring diagnostics use actual engine inputs, not dataset-label answers."""

import copy
import json

import pytest
from graded_fixtures import compact_bottle, public_release, without_grades

from kgtracevis.core.candidate_discriminability import analyze_candidate_discriminability
from kgtracevis.core.rootkgd_reasoner import RootKGDReasoner
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_compiler import KnowledgeProgram, SearchIncomplete, SearchLimits
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


def actual_inputs(dataset, frame_index=0):
    package, frames = public_release(dataset)
    return without_grades(package["knowledge"]), frames[frame_index]


def diagnose(knowledge, frame, reasoner_id="unified_abduction"):
    engine = UnifiedReasoner if reasoner_id == "unified_abduction" else RootKGDReasoner
    result = engine(knowledge).analyze(frame, top_k=8)
    report = analyze_candidate_discriminability(knowledge, frame, result, reasoner_id=reasoner_id)
    return result, report


@pytest.mark.parametrize(
    "dataset,frame_index,group_sizes,grounded_count",
    [
        ("mvtec", 0, [2, 2], 4),
        ("tep", 1, [2, 2], 7),
        ("wafer", 0, [], 7),
    ],
)
def test_actual_frames_reveal_same_condition_groups(
    dataset, frame_index, group_sizes, grounded_count
):
    knowledge, frame = actual_inputs(dataset, frame_index)
    result, report = diagnose(knowledge, frame)
    assert report["schema_version"] == "rootlens-candidate-discriminability.v1"
    assert report["grouping_basis"] == "reachable_expectation_conditions"
    assert report["grouping_status"] == "available"
    assert sorted(len(g["candidate_ids"]) for g in report["equivalence_groups"]) == group_sizes
    assert report["candidate_count"] == 4
    assert report["evidence_usage"]["condition_grounded_observation_count"] == grounded_count
    for group in report["equivalence_groups"]:
        assert group["evidence_distinguishes"] is False
        assert group["condition_signature"]
        assert all(cost["weighted_cost"] == 0.25 for cost in group["cost_priors"])
    for checks in report["candidate_checks"]:
        row = next(
            r
            for r in result["candidate_evaluations"]
            if r["candidate_id"] == checks["candidate_id"]
        )
        assert checks["expectation_checks"] == row["expectation_checks"]
        assert checks["condition_checks_used_for_score"] is True


def test_cost_prior_can_change_rank_without_claiming_observation_discrimination():
    package, frames = compact_bottle()
    knowledge, frame = without_grades(package["knowledge"]), frames[0]
    selected = knowledge["hypotheses"][0]
    selected["assumption_cost"] = 4.0
    result, report = diagnose(knowledge, frame)
    group = report["equivalence_groups"][0]
    assert len(group["candidate_ids"]) == 2
    assert selected["hypothesis_id"] in group["candidate_ids"]
    assert group["evidence_distinguishes"] is False
    costs = {c["candidate_id"]: c["weighted_cost"] for c in group["cost_priors"]}
    assert costs[selected["hypothesis_id"]] == 1.0
    assert set(costs.values()) == {0.25, 1.0}
    rows = {r["candidate_id"]: r for r in result["candidate_evaluations"]}
    assert rows[selected["hypothesis_id"]]["score"] == -1.0


@pytest.mark.parametrize(
    "feature,unit,op",
    [
        ("statistics.mean_z", "1", "gte"),
        ("statistics.mean_z", "1", "lte"),
        ("statistics.std_z", "1", "gte"),
        ("statistics.slope_z", "1/sample", "gte"),
    ],
)
def test_one_executable_candidate_specific_condition_splits_group(feature, unit, op):
    knowledge, frame = actual_inputs("tep", 1)
    selected = knowledge["hypotheses"][0]["hypothesis_id"]
    actual = next(
        o["value"]["number"]
        for o in frame["observations"]
        if o["subject_id"] == "variable:xmv_10" and o["feature_id"] == feature
    )
    predicate = copy.deepcopy(
        next(
            p
            for p in knowledge["observable_definitions"]
            if p["subject_selector"].get("entity_id", "").endswith(":xmv_10")
        )
    )
    # Test-only authoring change, not an assertion about industrial response.
    predicate.update(
        predicate_id="q:authoring-check",
        feature_id=feature,
        op=op,
        operand={"kind": "number", "number": actual + (0.1 if op == "lte" else -0.1), "unit": unit},
    )
    knowledge["observable_definitions"].append(predicate)
    knowledge["pattern_definitions"].append(
        {
            "definition_id": "d:authoring-check",
            "pattern_id": "p:authoring-check",
            "label": "Test-only response condition",
            "body": {"all": [predicate["predicate_id"]]},
            "scope_join": "same_event_same_window",
            "source_assertion_ids": predicate["source_assertion_ids"],
        }
    )
    knowledge["expectation_rules"].append(
        {
            "rule_id": "r:authoring-check",
            "from_id": selected,
            "pattern_id": "p:authoring-check",
            "mode": "necessary",
            "source_assertion_ids": predicate["source_assertion_ids"],
        }
    )
    result, report = diagnose(knowledge, frame)
    assert [len(g["candidate_ids"]) for g in report["equivalence_groups"]] == [2]
    assert all(selected not in g["candidate_ids"] for g in report["equivalence_groups"])
    row = next(r for r in result["candidate_evaluations"] if r["candidate_id"] == selected)
    check = next(c for c in row["expectation_checks"] if c["rule_id"] == "r:authoring-check")
    assert check["observed_value"] is True
    assert row["eligible_for_ranking"] is True
    predicate["operand"]["number"] = actual + (-0.1 if op == "lte" else 0.1)
    changed, changed_report = diagnose(knowledge, frame)
    row = next(r for r in changed["candidate_evaluations"] if r["candidate_id"] == selected)
    assert row["eligible_for_ranking"] is False
    assert row["status"] == "ruled_out"
    copied = next(c for c in changed_report["candidate_checks"] if c["candidate_id"] == selected)
    assert copied["expectation_checks"] == row["expectation_checks"]


def test_expectation_mode_and_repeated_or_witnesses_are_not_merged():
    knowledge, frame = actual_inputs("mvtec")
    candidate = knowledge["hypotheses"][0]["hypothesis_id"]
    pattern = knowledge["expectation_rules"][0]["pattern_id"]
    for mode in ("expected", "necessary", "possible"):
        altered = copy.deepcopy(knowledge)
        altered["expectation_rules"].append(
            {
                "rule_id": "r:additional",
                "from_id": candidate,
                "pattern_id": pattern,
                "mode": mode,
                "source_assertion_ids": [knowledge["source_assertions"][0]["assertion_id"]],
            }
        )
        _, report = diagnose(altered, frame)
        assert [len(g["candidate_ids"]) for g in report["equivalence_groups"]] == [2]
        assert candidate not in report["equivalence_groups"][0]["candidate_ids"]


def test_rootkgd_groups_actual_structural_vectors_not_logical_conditions():
    knowledge, frame = actual_inputs("tep", 1)
    result, report = diagnose(knowledge, frame, "tep_rootkgd")
    assert report["grouping_basis"] == "actual_structural_projection"
    assert report["grouping_status"] == "available"
    assert sorted(len(g["candidate_ids"]) for g in report["equivalence_groups"]) == [2, 2]
    assert all(
        g["condition_signature"] == [] and g["cost_priors"] == []
        for g in report["equivalence_groups"]
    )
    usage = report["evidence_usage"]
    assert usage["condition_grounded_observation_count"] == 7
    assert usage["score_input_observation_count"] == 52
    assert usage["score_input_feature_ids"] == ["residual.contribution"]
    assert "statistics.mean_z" in {f["feature_id"] for f in usage["not_scored_features"]}
    for checks in report["candidate_checks"]:
        assert checks["condition_checks_used_for_score"] is False
        assert checks["expectation_checks"] == []
        assert checks["predicate_checks"]
    for predicate in knowledge["observable_definitions"]:
        if predicate["feature_id"] == "statistics.mean_z":
            predicate["operand"]["number"] = 1e6
    changed, report2 = diagnose(knowledge, frame, "tep_rootkgd")
    assert report2["equivalence_groups"] == report["equivalence_groups"]
    assert [r["score"] for r in changed["candidate_evaluations"]] == [
        r["score"] for r in result["candidate_evaluations"]
    ]
    assert report2["candidate_checks"] != report["candidate_checks"]


@pytest.mark.parametrize("partial", [False, True])
def test_missing_structural_vectors_are_explicit_and_never_use_logical_groups(partial):
    knowledge, frame = actual_inputs("tep", 1)
    result = RootKGDReasoner(knowledge).analyze(frame, top_k=8)
    rows = result["candidate_evaluations"][:1] if partial else result["candidate_evaluations"]
    for row in rows:
        row["scoring_details"].pop("propagated_channel_vector")
    report = analyze_candidate_discriminability(knowledge, frame, result, reasoner_id="tep_rootkgd")
    assert report["grouping_status"] == ("incomplete" if partial else "unavailable")
    assert report["grouping_basis"] == (
        "actual_structural_projection" if partial else "structural_inputs_unavailable"
    )
    assert report["issues"]
    if not partial:
        assert report["equivalence_groups"] == []


@pytest.mark.parametrize("reasoner_id", ["unified_abduction", "tep_rootkgd"])
def test_normal_gate_keeps_original_outcome_and_reports_no_structural_ranking(reasoner_id):
    knowledge, frame = actual_inputs("tep")
    result, report = diagnose(knowledge, frame, reasoner_id)
    assert result["outcome"] == "no_match"
    assert not result["ranked_root_causes"]
    if reasoner_id == "tep_rootkgd":
        assert report["grouping_status"] == "unavailable"
        assert report["equivalence_groups"] == []
        assert report["evidence_usage"]["score_input_status"] == "not_ranked"
        assert report["evidence_usage"]["score_input_observation_count"] == 0


def test_insufficient_observations_preserve_missing_checks():
    knowledge, frame = actual_inputs("tep", 1)
    frame["observations"] = []
    result, report = diagnose(knowledge, frame)
    assert result["outcome"] == "insufficient_evidence"
    assert report["candidate_count"] == 4
    assert report["evidence_usage"]["observed_observation_count"] == 0
    assert report["evidence_usage"]["condition_grounded_observation_count"] == 0
    assert all(
        c["assessment_status"] == "no_evaluable_observation_footprint"
        for c in report["candidate_checks"]
    )
    assert all(
        f["value"] is None for c in report["candidate_checks"] for f in c["predicate_checks"]
    )


def test_search_incomplete_never_becomes_no_knowledge_or_full_coverage():
    knowledge, frame = actual_inputs("tep", 1)
    result = UnifiedReasoner(knowledge, limits=SearchLimits(candidates=1)).analyze(frame)
    report = analyze_candidate_discriminability(
        knowledge, frame, result, reasoner_id="unified_abduction"
    )
    assert report["grouping_status"] == "incomplete"
    assert report["issues"] == [result["search_error"]]
    assert report["equivalence_groups"] == []
    assert report["evidence_usage"]["condition_reference_status"] == "incomplete"
    assert report["evidence_usage"]["score_input_status"] == "unavailable"
    assert report["evidence_usage"]["unreferenced_features"] == []


def test_diagnostic_expansion_budget_does_not_fail_completed_inference(monkeypatch):
    knowledge, frame = actual_inputs("tep", 1)
    result = UnifiedReasoner(knowledge).analyze(frame)

    def exhausted(self, identity):
        raise SearchIncomplete("authoring expansion budget exhausted")

    monkeypatch.setattr(KnowledgeProgram, "hypothesis_world", exhausted)
    report = analyze_candidate_discriminability(
        knowledge, frame, result, reasoner_id="unified_abduction"
    )
    assert report["grouping_status"] == "incomplete"
    assert len(report["issues"]) == 4
    assert result["outcome"] == "ambiguous"
    assert report["evidence_usage"]["unreferenced_features"] == []


@pytest.mark.parametrize("field", ["graph_id", "case_id"])
def test_diagnostics_require_same_inference_snapshot(field):
    knowledge, frame = actual_inputs("mvtec")
    result = UnifiedReasoner(knowledge).analyze(frame)
    result[field] = "different"
    with pytest.raises(ValueError, match="knowledge snapshot|EvidenceFrame"):
        analyze_candidate_discriminability(
            knowledge, frame, result, reasoner_id="unified_abduction"
        )


def test_report_is_detached_json_and_accepts_typed_inputs():
    knowledge, frame = actual_inputs("tep", 1)
    result = UnifiedReasoner(knowledge).analyze(frame)
    original = copy.deepcopy((knowledge, frame, result))
    report = analyze_candidate_discriminability(
        KnowledgePackage.model_validate(knowledge),
        EvidenceFrame.model_validate(frame),
        result,
        reasoner_id="unified_abduction",
    )
    assert json.loads(json.dumps(report, allow_nan=False)) == report
    assert (knowledge, frame, result) == original
    report["candidate_checks"][0]["predicate_checks"][0]["actual_values"].append({"changed": True})
    assert (knowledge, frame, result) == original
    usage = report["evidence_usage"]
    assert usage["total_observation_count"] == 263
    assert usage["score_input_observation_count"] == 7
    assert {f["feature_id"] for f in usage["unreferenced_features"]} == {
        "residual.contribution",
        "residual.energy",
        "residual.normal_limit",
        "series.raw_values",
        "statistics.slope_z",
    }


def test_unrelated_task_has_no_applicable_candidate_groups():
    knowledge, frame = actual_inputs("tep", 1)
    frame["task"]["target_role"] = "unrelated-role"
    result, report = diagnose(knowledge, frame)
    assert result["outcome"] == "not_applicable"
    assert report["candidate_count"] == 0
    assert report["equivalence_groups"] == []


def test_unregistered_reasoner_is_not_given_an_invented_basis():
    knowledge, frame = actual_inputs("tep", 1)
    with pytest.raises(ValueError, match="unsupported diagnostic reasoner"):
        analyze_candidate_discriminability(knowledge, frame, {}, reasoner_id="unknown")
