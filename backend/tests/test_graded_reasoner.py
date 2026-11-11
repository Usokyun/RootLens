"""Compare the new method on frozen public topology and actual typed Frames."""

import copy
import json
from collections import defaultdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from kgtracevis.adapters.unified_capabilities import visual_capabilities
from kgtracevis.core.graded_reasoner import GradedReasoner
from kgtracevis.core.rootkgd_reasoner import RootKGDReasoner
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_compiler import KnowledgeProgram, SearchLimits
from kgtracevis.schema.unified_knowledge import KnowledgePackage, measurement_selector
from kgtracevis.source_kg_compiler.unified import CompiledProposal, validate_proposal

DEMO = Path(__file__).resolve().parents[1] / "data/demo/two_loop"
ECC = "geometry.eccentricity"
AREA = "geometry.area_ratio"
ASPECT = "geometry.aspect_ratio"
GATE = "detection.anomaly_present"


def frozen_public(dataset):
    directory = DEMO / dataset
    package = json.loads((directory / "working-graph.v2.json").read_bytes())
    frames = json.loads((directory / "evidence.json").read_bytes())["frames"]
    return package, frames


def graded_public(dataset, *, width_scale=1.0):
    package, frames = frozen_public(dataset)
    knowledge = package["knowledge"]
    program = KnowledgeProgram(knowledge)
    widths = {
        AREA: 0.1,
        ASPECT: 0.5,
        ECC: 0.08,
        "statistics.mean_z": 1.0,
        "spatial.failure_density": 0.08,
        "spatial.largest_component_ratio": 0.15,
    }
    groups = defaultdict(list)
    anchors = []
    for row in knowledge["observable_definitions"]:
        p, feature = row["predicate_id"], row["feature_id"]
        if feature == GATE:
            continue
        if row["op"] in {"gte", "lte"}:
            set_curve(row, widths[feature] * width_scale)
        key = measurement_selector(program.observables[p], program.features[feature])
        groups[key].append(p)
        if (
            feature == ECC
            or row["subject_selector"].get("entity_id", "").endswith(":xmv_10")
            or (
                feature == "spatial.largest_component_ratio"
                or (feature == "spatial.failure_density" and row["op"] == "lte")
            )
        ):
            anchors.append(p)
    slots = [
        {
            "slot_id": f"frozen:{i}",
            "weight": 0.25 if key[0] == "classifier.pattern" else 1.0,
            "predicate_ids": members,
        }
        for i, (key, members) in enumerate(groups.items())
    ]
    knowledge["graded_policy"] = {
        "groups": [{"group_id": "one-source-budget", "slots": slots}],
        "anchor_predicate_ids": anchors,
    }
    return package, frames


def set_curve(predicate, width):
    predicate["grade"] = {
        "direction": {"gte": "higher", "lte": "lower"}[predicate["op"]],
        "pivot": predicate["operand"]["number"],
        "unit": predicate["operand"]["unit"],
        "support_width": width,
        "conflict_width": width,
        "basis": "declared_demo_heuristic",
        "source_assertion_ids": predicate["source_assertion_ids"],
    }


def observation(frame, feature, subject=None):
    return next(
        o
        for o in frame["observations"]
        if o["feature_id"] == feature and (subject is None or o["subject_id"] == subject)
    )


def predicate(knowledge, feature):
    return next(
        p["predicate_id"] for p in knowledge["observable_definitions"] if p["feature_id"] == feature
    )


def add_component_predicate(knowledge, *, measured_target=5):
    source = next(p for p in knowledge["observable_definitions"] if p["feature_id"] == AREA)
    row = {
        **copy.deepcopy(source),
        "feature_id": "geometry.component_count",
        "predicate_id": "test:component",
        "op": "eq",
        "operand": {"kind": "number", "number": measured_target, "unit": "1"},
    }
    row.pop("grade")
    knowledge["observable_definitions"].append(row)
    return row["predicate_id"]


def add_expectation(knowledge, cue, mode):
    source = knowledge["pattern_definitions"][0]
    knowledge["pattern_definitions"].append(
        {
            **source,
            "pattern_id": "test:extra",
            "definition_id": "test:definition",
            "body": {"all": [predicate(knowledge, GATE), cue]},
        }
    )
    knowledge["expectation_rules"].append(
        {
            **knowledge["expectation_rules"][0],
            "rule_id": "test:expectation",
            "pattern_id": "test:extra",
            "mode": mode,
        }
    )


@pytest.mark.parametrize(
    "number,expected,state,coverage",
    [
        (0.7969506925604166, 1.0, "supported", 1),
        (0.899, 0.6708333333333333, "supported", 1),
        (0.900, 2 / 3, "pending", 1),
        (0.901, 0.6625, "pending", 1),
        (0.94, 0.5, "pending", 1),
        (0.98, 1 / 3, "pending", 1),
        (None, 2 / 3, "pending", 2 / 3),
    ],
)
def test_frozen_006_continuous_sweep_preserves_indistinguishable_candidates(
    number, expected, state, coverage
):
    pkg, frames = graded_public("mvtec")
    frame = frames[0]
    ecc = observation(frame, ECC)
    if number is None:
        ecc.update(value=None, status="missing")
    else:
        ecc["value"]["number"] = number
    result = GradedReasoner(pkg["knowledge"]).analyze(frame, top_k=1)
    assert result["scoring_method"] == "graded_joint_abduction_v1"
    rows = result["graded_candidates"]
    assert [(r["status"], r["rank"]) for r in rows] == [(state, 1), (state, 1)]
    assert len(result["ranked_root_causes"]) == (2 if state == "supported" else 0)
    assert not result["proof_graph"]["nodes"]
    for row in rows:
        scores = row["scoring_details"]
        assert scores["score"] == pytest.approx(expected)
        assert scores["coverage"] == pytest.approx(coverage)
        assert sum(c["score_contribution"] for c in row["graded_conditions"]) == pytest.approx(
            expected
        )
        cue = next(c for c in row["graded_conditions"] if c["feature_id"] == ECC)
        assert cue["weight"] == pytest.approx(1 / 3)
        if number is None:
            assert cue["status"] == "unknown" and cue["support"] is cue["conflict"] is None
        elif number > 0.9:
            (trace,) = [
                t for t in row["explanation_paths"] if t["predicate_id"] == cue["predicate_id"]
            ]
            assert trace["counter_obs_ids"] == trace["observation_ids"] == [ecc["obs_id"]]
            assert trace["support_obs_ids"] == [] and trace["joint_proof_id"] is None
            assert trace["path_kind"] == "graded_contribution"


@pytest.mark.parametrize("dataset", ["mvtec", "tep", "wafer"])
def test_three_public_topologies_same_old_results_and_bounded_new_method(dataset):
    previous, frames = frozen_public(dataset)
    new, _ = graded_public(dataset)
    strict_old, strict_new = (
        UnifiedReasoner(previous["knowledge"]),
        UnifiedReasoner(new["knowledge"]),
    )
    assert strict_old.program.edges == strict_new.program.edges
    reasoner = GradedReasoner(new["knowledge"])
    results = []
    for frame in frames:
        assert strict_old.analyze(frame) == strict_new.analyze(frame)
        if dataset == "tep":
            assert RootKGDReasoner(previous["knowledge"]).analyze(frame) == RootKGDReasoner(
                new["knowledge"]
            ).analyze(frame)
        result = reasoner.analyze(frame)
        results.append(result)
        for row in result["graded_candidates"]:
            assert -1.0 <= row["score"] <= 1.0
            for trace in row["explanation_paths"]:
                assert trace["joint_proof_id"] is None
                for i, edge_view in enumerate(trace["source_edge_views"]):
                    edge = reasoner.program.edges[edge_view["edge_id"]]
                    pair = (edge["head"], edge["tail"])
                    assert tuple(trace["nodes"][i : i + 2]) == (
                        pair[::-1] if edge_view["reverse"] else pair
                    )
    if dataset == "tep":
        assert results[0]["reason"] == "anomaly_gate_is_false"
        assert results[0]["graded_candidates"] == []
        assert [r["outcome"] for r in results] == ["no_match", "ambiguous", "ambiguous"]
    if dataset == "wafer":
        assert results[0]["outcome"] == "supported"
        assert results[0]["ranked_root_causes"][0]["candidate_id"].endswith(
            ":pattern_family_nearfull"
        )


@pytest.mark.parametrize("scale", [0.75, 1.25])
def test_predeclared_curve_width_perturbation_does_not_break_geometry_tie(scale):
    pkg, frames = graded_public("mvtec", width_scale=scale)
    rows = GradedReasoner(pkg["knowledge"]).analyze(frames[0])["graded_candidates"]
    assert len(rows) == 2
    assert rows[0]["score"] == rows[1]["score"] > 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("support_width", 0),
        ("conflict_width", -1),
        ("pivot", 0.89),
        ("unit", "mm"),
        ("basis", "source_explicit"),
        ("source_assertion_ids", ["unknown"]),
    ],
)
def test_grade_rejects_inconsistent_units_direction_or_provenance(field, value):
    pkg, _ = graded_public("mvtec")
    pkg["knowledge"]["observable_definitions"][-1]["grade"][field] = value
    with pytest.raises(ValidationError):
        KnowledgePackage.model_validate(pkg["knowledge"])


def test_one_measurement_and_one_actual_dependency_group_have_one_budget():
    pkg, frames = graded_public("mvtec")
    knowledge = pkg["knowledge"]
    groups = knowledge["graded_policy"]["groups"]
    slots = groups[0]["slots"]
    duplicate = copy.deepcopy(knowledge["observable_definitions"][1])
    duplicate["predicate_id"] = "test:repeat"
    knowledge["observable_definitions"].append(duplicate)
    groups.append(
        {
            "group_id": "misleading-name",
            "slots": [{"slot_id": "duplicate", "predicate_ids": ["test:repeat"]}],
        }
    )
    with pytest.raises(ValidationError, match="same measurement cannot spend two slots"):
        GradedReasoner(knowledge)
    groups.pop()
    groups.append({"group_id": "same-source-different-name", "slots": [slots.pop()]})
    rejected = GradedReasoner(knowledge).analyze(frames[0])
    assert rejected["reason"] == "graded_budget_source_overlap"
    assert rejected["graded_candidates"] == []
    assert rejected["graded_comparison"]["source_overlaps"][0]["dependency_group"] == "image/roi:1"
    observation(frames[0], ECC).update(status="missing", value=None)
    assert GradedReasoner(knowledge).analyze(frames[0])["reason"] == "graded_budget_source_overlap"


def test_repeated_values_and_conditions_do_not_add_score_or_support_slots():
    pkg, frames = graded_public("mvtec")
    knowledge, frame = pkg["knowledge"], frames[0]
    baseline = GradedReasoner(knowledge).analyze(frame)
    dup_pred = copy.deepcopy(knowledge["observable_definitions"][1])
    dup_pred["predicate_id"] = "test:duplicate-condition"
    knowledge["observable_definitions"].append(dup_pred)
    knowledge["pattern_definitions"][0]["body"]["all"].append(dup_pred["predicate_id"])
    knowledge["graded_policy"]["groups"][0]["slots"][0]["predicate_ids"].append(
        dup_pred["predicate_id"]
    )
    dup_obs = copy.deepcopy(observation(frame, AREA))
    dup_obs.update(obs_id="test:duplicate-observation", dependency_group="test:fake-new-source")
    frame["observations"].append(dup_obs)
    repeated = GradedReasoner(knowledge).analyze(frame)
    for new, old in zip(repeated["graded_candidates"], baseline["graded_candidates"], strict=True):
        assert new["score"] == old["score"]
        assert new["support_measurement_count"] == old["support_measurement_count"] == 3
        assert (
            len(
                [
                    c
                    for c in new["graded_conditions"]
                    if c["feature_id"] == AREA and c["score_contribution"]
                ]
            )
            == 1
        )
    dup_obs["value"]["number"] = 0.26
    conflicting = GradedReasoner(knowledge).analyze(frame)["graded_candidates"][0]
    assert conflicting["scoring_details"]["conflict"] == 0
    assert conflicting["scoring_details"]["coverage"] == pytest.approx(2 / 3)
    assert {c["reason"] for c in conflicting["graded_conditions"] if c["feature_id"] == AREA} == {
        "inconsistent_repeated_measurement"
    }


@pytest.mark.parametrize(
    "state", ["gate_false", "gate_unknown", "required_false", "required_unknown"]
)
def test_hard_refutation_excludes_and_unknown_never_becomes_supported(state):
    pkg, frames = graded_public("mvtec")
    knowledge, frame = pkg["knowledge"], frames[0]
    if state.startswith("required"):
        add_expectation(knowledge, add_component_predicate(knowledge), "necessary")
        cue = observation(frame, "geometry.component_count")
    else:
        cue = observation(frame, GATE)
    if state.endswith("unknown"):
        cue.update(value=None, status="missing")
    elif state == "gate_false":
        cue["value"]["boolean"] = False
    result = GradedReasoner(knowledge).analyze(frame)
    assert not result["ranked_root_causes"]
    if state.endswith("false"):
        assert not result["graded_candidates"]
        assert all(r["status"] == "ruled_out" for r in result["candidate_evaluations"])
    else:
        assert {r["status"] for r in result["graded_candidates"]} == {"pending"}
        assert all(
            "hard_constraint_unverified" in r["reasons"] for r in result["graded_candidates"]
        )


@pytest.mark.parametrize("mode,conflict", [("expected", 0.25), ("possible", 0.0)])
def test_simultaneous_expected_cannot_drop_refutation_but_possible_never_penalizes(mode, conflict):
    pkg, frames = graded_public("mvtec")
    knowledge = pkg["knowledge"]
    extra = add_component_predicate(knowledge)
    knowledge["graded_policy"]["groups"][0]["slots"].append(
        {"slot_id": "extra", "predicate_ids": [extra]}
    )
    add_expectation(knowledge, extra, mode)
    row = GradedReasoner(knowledge).analyze(frames[0])["graded_candidates"][0]
    assert row["scoring_details"]["support"] == 0.75
    assert row["scoring_details"]["conflict"] == conflict
    assert row["score"] == 0.75 - conflict
    optional = next(
        c
        for c in row["expectation_checks"]
        if c["mode"] == mode and c["rule_id"] == "test:expectation"
    )
    if mode == "possible":
        assert optional["reason"] == "optional_not_selected"
    else:
        assert extra in optional["predicate_ids"]


def test_or_cannot_join_two_half_branches_and_paths_follow_the_actual_selected_arm():
    pkg, frames = graded_public("mvtec")
    knowledge, frame = pkg["knowledge"], frames[0]
    a, c, d, gate = [predicate(knowledge, feature) for feature in (AREA, ASPECT, ECC, GATE)]
    b = add_component_predicate(knowledge)
    pattern = knowledge["pattern_definitions"][0]
    pattern["body"] = {"all": [gate, {"any": [{"all": [a, b]}, {"all": [c, d]}]}]}
    knowledge["graded_policy"]["groups"][0]["slots"].append({"slot_id": "b", "predicate_ids": [b]})
    observation(frame, ECC)["value"]["number"] = 0.98
    insufficient = GradedReasoner(knowledge).analyze(frame)
    assert not insufficient["graded_candidates"]
    assert not insufficient["top_k_paths"]
    observation(frame, ECC)["value"]["number"] = 0.8
    pattern["body"]["all"][1]["any"][1]["all"].append(a)
    supported = GradedReasoner(knowledge).analyze(frame)
    for path in supported["top_k_paths"]:
        if path["predicate_id"] == a:
            assert (
                path["source_edge_views"][0]["edge_id"]
                == f"{pattern['definition_id']}::gate::1.1::input::{a}"
            )


def test_never_combine_a_different_roi_or_normal_reference():
    pkg, frames = graded_public("mvtec")
    frame = frames[0]
    roi = next(s for s in frame["subjects"] if s["subject_id"] == "roi:1")
    frame["subjects"].append({**roi, "subject_id": "roi:2"})
    frame["scopes"].append({**frame["scopes"][0], "scope_id": "scope:2", "subject_id": "roi:2"})
    for feature in (ASPECT, ECC):
        observation(frame, feature).update(subject_id="roi:2", scope_id="scope:2")
    assert not GradedReasoner(pkg["knowledge"]).analyze(frame)["graded_candidates"]
    pkg, frames = graded_public("tep")
    frame = frames[1]
    altered = observation(frame, "statistics.mean_z", "variable:xmeas_9")
    frame["references"].append({**frame["references"][0], "reference_id": "other"})
    procedure = next(p for p in frame["procedures"] if p["procedure_id"] == altered["procedure_id"])
    frame["procedures"].append({**procedure, "procedure_id": "other", "reference_id": "other"})
    altered.update(reference_id="other", procedure_id="other")
    result = GradedReasoner(pkg["knowledge"]).analyze(frame)
    assert not result["graded_candidates"]
    assert any(f["reason"] == "incompatible_normal_reference" for f in result["grounded_facts"])


def test_time_window_is_not_a_bucket_for_other_windows():
    package, frames = graded_public("tep")
    frame = frames[1]
    window = next(s for s in frame["scopes"] if s["scope_id"] == frame["task"]["scope_id"])
    frame["scopes"].append(
        {
            **window,
            "scope_id": "other-window",
            "sample_start": 261,
            "sample_end": 360,
        }
    )
    temperature = observation(frame, "statistics.mean_z", "variable:xmeas_9")
    temperature["scope_id"] = "other-window"
    result = GradedReasoner(package["knowledge"]).analyze(frame)
    assert not result["graded_candidates"]
    assert temperature["obs_id"] in {o["obs_id"] for o in result["unused_observations"]}


@pytest.mark.parametrize("temperature", [0.0, 2.5, -2.5])
def test_interval_and_two_numeric_bounds_spend_one_identical_measurement_slot(temperature):
    package, frames = graded_public("tep")
    frame = frames[1]
    observation(frame, "statistics.mean_z", "variable:xmeas_9")["value"]["number"] = temperature
    knowledge = package["knowledge"]
    dual = GradedReasoner(knowledge).analyze(frame)
    lower, upper = [
        p for p in knowledge["observable_definitions"] if ":temperature_" in p["predicate_id"]
    ]
    lo, hi = lower["predicate_id"], upper["predicate_id"]
    lower["op"] = "between"
    lower["operand"] = {"kind": "interval", "lower": -2, "upper": 2, "unit": "1"}
    grade = lower["grade"]
    grade.pop("pivot")
    grade.update(direction="interval", lower=-2, upper=2)
    for group in knowledge["graded_policy"]["groups"]:
        for slot in group["slots"]:
            if hi in slot["predicate_ids"]:
                slot["predicate_ids"].remove(hi)

    def remove_upper(body):
        for children in body.values():
            if hi in children:
                children.remove(hi)
            for child in children:
                if isinstance(child, dict):
                    remove_upper(child)

    for definition in knowledge["pattern_definitions"]:
        remove_upper(definition["body"])
    knowledge["observable_definitions"].remove(upper)
    single = GradedReasoner(knowledge).analyze(frame)
    assert single["outcome"] == dual["outcome"]

    def reactor_details(result):
        return [
            r["scoring_details"]
            for r in result["candidate_evaluations"]
            if "reactor" in r["candidate_id"]
        ]

    assert reactor_details(single) == reactor_details(dual)
    fact = next(f for f in single["grounded_facts"] if f["predicate_id"] == lo)
    assert fact["value"] == (-2 <= temperature <= 2)


def test_canonical_source_proposals_cannot_inject_a_grade_or_budget():
    package, _ = graded_public("mvtec")
    knowledge = package["knowledge"]
    for config in (knowledge, {**knowledge, "graded_policy": None}):
        proposal = CompiledProposal(knowledge=KnowledgePackage.model_validate(config))
        with pytest.raises(
            ValueError, match="source builds cannot assign graded curves or budgets"
        ):
            validate_proposal(proposal, [], visual_capabilities())


def test_open_appearance_and_wrong_units_are_unknown_not_conflict():
    pkg, frames = graded_public("mvtec")
    knowledge, frame = pkg["knowledge"], frames[0]
    source = next(p for p in knowledge["observable_definitions"] if p["feature_id"] == AREA)
    semantic = copy.deepcopy(source)
    semantic.pop("grade")
    semantic.update(
        predicate_id="test:open",
        feature_id="appearance.semantic_candidates",
        op="candidate_contains",
        operand={"kind": "category", "category": "structural_cue"},
    )
    knowledge["observable_definitions"].append(semantic)
    knowledge["pattern_definitions"][0]["body"]["all"].append("test:open")
    knowledge["graded_policy"]["groups"][0]["slots"].append(
        {"slot_id": "semantic", "predicate_ids": ["test:open"]}
    )
    observed = observation(frame, "appearance.semantic_candidates")
    observed.update(
        status="observed",
        raw_refs=frame["observations"][0]["raw_refs"],
        value={"kind": "candidate_set", "items": ["other"], "exhaustive": False},
    )
    observation(frame, ECC)["value"]["unit"] = "mm"
    row = GradedReasoner(knowledge).analyze(frame)["graded_candidates"][0]
    assert row["scoring_details"]["conflict"] == 0
    assert row["scoring_details"]["coverage"] == 0.5
    assert {c["reason"] for c in row["graded_conditions"] if c["status"] == "unknown"} == {
        "open_candidate_set_does_not_refute",
        "feature_type_or_unit_mismatch",
    }


def test_search_budget_exhaustion_remains_explicit():
    pkg, frames = graded_public("mvtec")
    result = GradedReasoner(pkg["knowledge"], limits=SearchLimits(candidates=1)).analyze(frames[0])
    assert result["outcome"] == "search_incomplete" and not result["graded_candidates"]
