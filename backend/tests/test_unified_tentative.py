"""The tentative layer must not assemble a proof that was never jointly measured."""

import copy

import pytest
from graded_fixtures import compact_bottle, public_release, without_grades

from kgtracevis.core.unified_reasoner import UnifiedReasoner

GATE = "detection.anomaly_present"
AREA = "geometry.area_ratio"
ASPECT = "geometry.aspect_ratio"
ECC = "geometry.eccentricity"


def load_demo(dataset):
    package, frames = compact_bottle() if dataset == "mvtec" else public_release(dataset)
    return without_grades(package["knowledge"]), frames[0]


def obs(frame, feature):
    return next(o for o in frame["observations"] if o["feature_id"] == feature)


def condition(knowledge, feature):
    return next(p for p in knowledge["observable_definitions"] if p["feature_id"] == feature)


def add_condition(knowledge, feature, identity, op, operand):
    row = {
        **condition(knowledge, AREA),
        "predicate_id": identity,
        "feature_id": feature,
        "op": op,
        "operand": operand,
    }
    knowledge["observable_definitions"].append(row)
    return identity


def number(value):
    return {"kind": "number", "number": value, "unit": "1"}


def partial_input():
    knowledge, frame = load_demo("mvtec")
    obs(frame, ECC)["value"]["number"] = 0.94
    return knowledge, frame


def set_missing(observation):
    observation.update(status="missing", value=None)


def assert_no_tentative(knowledge, frame):
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert not result["ranked_root_causes"]
    assert "tentative_candidates" not in result


def test_missing_is_listed_and_not_scored_as_counter_evidence():
    knowledge, frame = partial_input()
    set_missing(obs(frame, ECC))
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert result["outcome"] == "insufficient_evidence"
    assert result["tentative_diagnostic_context"]["observed_quantity_count"] == 2
    assert not result["ranked_root_causes"]
    for row in result["tentative_candidates"]:
        assert row["missing_predicate_ids"] == [condition(knowledge, ECC)["predicate_id"]]
        assert not row["counter_obs_ids"]
        checks = {c["predicate_check"]["feature_id"]: c for c in row["condition_checks"]}
        assert checks[ECC]["status"] == "unknown"
        assert checks[ECC]["unknown_obs_ids"] == [obs(frame, ECC)["obs_id"]]
        assert row["scoring_details"]["conflict_loss"] == 0
        assert row["scoring_details"]["unexplained_loss"] == 0


@pytest.mark.parametrize("gate_state", ["false", "missing", "no_gate", "one_of_two_missing"])
def test_a_branch_needs_all_its_explicit_presence_gates(gate_state):
    knowledge, frame = partial_input()
    if gate_state == "false":
        obs(frame, GATE)["value"]["boolean"] = False
    elif gate_state == "missing":
        set_missing(obs(frame, GATE))
    elif gate_state == "no_gate":
        body = knowledge["pattern_definitions"][0]["body"]["all"]
        body.remove(condition(knowledge, GATE)["predicate_id"])
    else:
        second = add_condition(
            knowledge,
            "appearance.defect_present",
            "test:second_gate",
            "bool_eq",
            {"kind": "boolean", "boolean": True},
        )
        knowledge["pattern_definitions"][0]["body"]["all"].append(second)
    assert_no_tentative(knowledge, frame)


@pytest.mark.parametrize("missing", [False, True])
def test_unestablished_necessary_rule_never_enters_tentative(missing):
    knowledge, frame = partial_input()
    knowledge["expectation_rules"][0]["mode"] = "necessary"
    if missing:
        set_missing(obs(frame, ECC))
    assert_no_tentative(knowledge, frame)


def test_repeat_measurement_cannot_add_a_vote_or_dependency_group():
    knowledge, frame = partial_input()
    repeated = copy.deepcopy(obs(frame, AREA))
    repeated.update(obs_id="test:repeat", dependency_group="test:another_group")
    frame["observations"].append(repeated)
    result = UnifiedReasoner(knowledge).analyze(frame)
    groups = result["tentative_diagnostic_context"]["groups"]
    assert len(groups) == 1
    assert set(groups[0]["dependency_group_ids"]) == {"image/roi:1", "test:another_group"}
    assert len(groups[0]["measurements"]) == 3
    for row in result["tentative_candidates"]:
        assert row["support_measurement_count"] == 2
        assert row["scoring_details"]["total_cost"] == pytest.approx(1.25)

    second_area_condition = add_condition(
        knowledge, AREA, "test:duplicate_area_predicate", "gte", number(0.15)
    )
    knowledge["pattern_definitions"][0]["body"]["all"].append(second_area_condition)
    set_missing(obs(frame, ASPECT))
    assert_no_tentative(knowledge, frame)


def test_dependency_groups_average_proportions_instead_of_pooled_votes():
    knowledge, frame = partial_input()
    obs(frame, ECC)["dependency_group"] = "test:other_group"
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert result["tentative_diagnostic_context"]["observed_quantity_count"] == 3
    for row in result["tentative_candidates"]:
        scores = row["scoring_details"]
        assert len(scores["groups"]) == 2
        assert scores["unexplained_loss"] == 0.5
        assert scores["conflict_loss"] == 0.5
        assert scores["total_cost"] == 1.75


def test_same_quantity_true_and_false_counts_only_as_counter_evidence():
    knowledge, frame = load_demo("mvtec")
    contradiction = add_condition(knowledge, AREA, "test:area_counter", "lte", number(0.1))
    knowledge["pattern_definitions"][0]["body"]["all"].append(contradiction)
    result = UnifiedReasoner(knowledge).analyze(frame)
    for row in result["tentative_candidates"]:
        assert row["support_measurement_count"] == 2
        assert row["counter_obs_ids"] == [obs(frame, AREA)["obs_id"]]
        assert obs(frame, AREA)["obs_id"] not in row["support_obs_ids"]
        assert row["scoring_details"]["groups"][0]["conflicting_quantity_count"] == 1


def test_alternative_branches_cannot_pool_two_single_measurement_supports():
    knowledge, frame = load_demo("mvtec")
    obs(frame, ASPECT)["value"]["number"] = 3.0
    unknown = add_condition(
        knowledge, "geometry.component_count", "test:missing", "eq", number(1.0)
    )
    set_missing(obs(frame, "geometry.component_count"))
    gate, area, aspect, ecc = (
        condition(knowledge, feature)["predicate_id"] for feature in [GATE, AREA, ASPECT, ECC]
    )
    knowledge["pattern_definitions"][0]["body"] = {
        "all": [gate, {"any": [{"all": [area, aspect]}, {"all": [ecc, unknown]}]}]
    }
    assert_no_tentative(knowledge, frame)


def test_selects_one_best_valid_branch_and_retains_its_actual_ids():
    knowledge, frame = partial_input()
    unknown = add_condition(
        knowledge, "geometry.component_count", "test:missing", "eq", number(1.0)
    )
    set_missing(obs(frame, "geometry.component_count"))
    gate, area, aspect, ecc = (
        condition(knowledge, feature)["predicate_id"] for feature in [GATE, AREA, ASPECT, ECC]
    )
    knowledge["pattern_definitions"][0]["body"] = {
        "all": [gate, area, aspect, {"any": [ecc, unknown]}]
    }
    result = UnifiedReasoner(knowledge).analyze(frame)
    for row in result["tentative_candidates"]:
        assert row["branch_predicate_ids"] == sorted([gate, area, aspect, unknown])
        assert not row["counter_obs_ids"]
        assert row["missing_predicate_ids"] == [unknown]
        assert row["scoring_details"]["unexplained_loss"] == pytest.approx(1 / 3)


def test_cannot_borrow_measurements_from_another_roi():
    knowledge, frame = partial_input()
    frame["subjects"].append({**frame["subjects"][-1], "subject_id": "roi:other"})
    frame["scopes"].append(
        {**frame["scopes"][0], "scope_id": "scope:other", "subject_id": "roi:other"}
    )
    obs(frame, ASPECT).update(subject_id="roi:other", scope_id="scope:other")
    assert_no_tentative(knowledge, frame)


def test_cannot_join_observations_from_two_references():
    knowledge, frame = partial_input()
    frame["references"] = [
        {"reference_id": identity, "kind": "normal_image", "normal_asset_id": "image"}
        for identity in ("reference:a", "reference:b")
    ]
    obs(frame, AREA)["reference_id"] = "reference:a"
    obs(frame, ASPECT)["reference_id"] = "reference:b"
    assert_no_tentative(knowledge, frame)


def test_real_wafer_one_value_counterexample_uses_only_same_parent_grid():
    knowledge, frame = load_demo("wafer")
    # Isolate the strict research proof: require the classifier together with all
    # spatial conditions here. The public graded graph treats it as optional advice.
    (rule,) = [
        r for r in knowledge["expectation_rules"] if r["pattern_id"] == "signature:pattern_nearfull"
    ]
    pattern, classifier = [
        p
        for p in knowledge["pattern_definitions"]
        if p["pattern_id"] in {rule["pattern_id"], rule["pattern_id"] + ":classifier-advice"}
    ]
    pattern["body"]["all"].extend(classifier["body"]["all"])
    knowledge["expectation_rules"] = [rule]
    knowledge["effect_rules"] = [
        r for r in knowledge["effect_rules"] if r["to_id"] == rule["from_id"]
    ]
    knowledge["hypotheses"] = [
        h
        for h in knowledge["hypotheses"]
        if h["hypothesis_id"].endswith(":pattern_family_nearfull")
    ]
    component = obs(frame, "spatial.largest_component_ratio")
    component["value"]["number"] = 0.50
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert not result["ranked_root_causes"]
    assert not result["top_k_paths"]
    assert result["outcome"] == "insufficient_evidence"
    (row,) = result["tentative_candidates"]
    assert row["candidate_role"] == "pattern_family"
    assert row["scope_join"] == "same_subject_parent_scope"
    assert row["support_measurement_count"] == 4
    assert row["counter_obs_ids"] == [component["obs_id"]]
    assert row["scoring_details"]["total_cost"] == pytest.approx(0.85)

    # Three zones have different scopes; only the explicit common-parent join is legal.
    for pattern in knowledge["pattern_definitions"]:
        pattern["scope_join"] = "same_subject_same_scope"
    assert_no_tentative(knowledge, frame)
