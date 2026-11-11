"""Presence or subject context is a prerequisite, not evidence of a fine diagnosis."""

import copy
import json

import pytest
from graded_fixtures import public_release

from kgtracevis.adapters.unified_capabilities import (
    process_capabilities,
    spatial_capabilities,
    visual_capabilities,
)
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_compiler import KnowledgeProgram
from kgtracevis.schema.feature_catalog import authoring_feature_role
from kgtracevis.schema.unified_knowledge import FeatureDefinition
from kgtracevis.source_kg_compiler.material_parser import parse_material
from kgtracevis.source_kg_compiler.unified import (
    CompiledProposal,
    compile_unified_knowledge,
    validate_proposal,
)
from kgtracevis.source_kg_compiler.unified_blueprint import KnowledgeBlueprint, lower_blueprint


def source_blueprint(tmp_path, *, logic="any", count=None, dataset="mvtec"):
    source = tmp_path / "source.txt"
    source.write_text("Illustrative compiler-safety fixture, not an industrial factual claim.")
    units = parse_material(source, source_id="gate-test", scenario=dataset).units
    assertion = {
        "text": "Test-only stated condition",
        "origin": "declared_demo_heuristic",
        "parameter_origin": "declared_demo_heuristic",
        "source_unit_id": units[0].unit_id,
    }
    cap = {
        "mvtec": visual_capabilities,
        "tep": process_capabilities,
        "wafer": spatial_capabilities,
    }[dataset]()
    generic = {
        "label": "通用缺陷存在",
        "feature_id": "appearance.defect_present"
        if dataset == "mvtec"
        else "detection.anomaly_present",
        "op": "bool_eq",
        "operand": {"kind": "boolean", "boolean": True},
        "assertion": assertion,
    }
    specific = {
        "label": "具体诊断表现",
        "feature_id": "appearance.semantic_candidates",
        "op": "candidate_contains",
        "operand": {"kind": "category", "category": "broken_finish"},
        "assertion": assertion,
    }
    if dataset == "tep":
        specific.update(
            feature_id="statistics.mean_z",
            op="gte",
            operand={"kind": "number", "number": 2.0, "unit": "1"},
            subject_external_id="xmeas_9",
        )
    elif dataset == "wafer":
        specific.update(
            feature_id="classifier.pattern",
            op="eq",
            operand={"kind": "category", "category": "donut"},
            zone="all_valid",
        )
        generic["zone"] = "all_valid"
    blueprint = KnowledgeBlueprint.model_validate(
        {
            "title": "门控安全测试",
            "signatures": [
                {
                    "signature_key": "fine",
                    "label": "具体诊断",
                    "context_external_id": cap.context_external_ids[0],
                    "logic": logic,
                    "at_least_count": count,
                    "conditions": [generic, specific],
                    "causes": [
                        {
                            "candidate_key": "candidate",
                            "label": "测试候选",
                            "mechanism_key": "state",
                            "mechanism_label": "测试状态",
                            "assertion": assertion,
                        }
                    ],
                    "assertion": assertion,
                }
            ],
        }
    )
    return units, cap, blueprint


def test_generic_defect_true_does_not_establish_fine_finish_cue(tmp_path):
    units, cap, blueprint = source_blueprint(tmp_path)
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    validate_proposal(proposal, units, cap)
    normalization = proposal.normalizations[0].model_dump()
    assert normalization == {
        "kind": "presence_gates_lifted",
        "signature_key": "fine",
        "gate_feature_ids": ["appearance.defect_present"],
        "diagnostic_condition_count": 1,
        "authored_logic": "any",
        "semantic_change": True,
    }
    _, (frame,) = public_release("mvtec")
    # Counterexample: the detector only asserts a coarse defect. It did not observe a finish cue.
    defect = next(
        o for o in frame["observations"] if o["feature_id"] == "appearance.defect_present"
    )
    defect.update(status="observed", value={"kind": "boolean", "boolean": True}, raw_refs=["image"])
    result = UnifiedReasoner(proposal.knowledge).analyze(frame)
    assert result["outcome"] == "insufficient_evidence"
    assert result["ranked_root_causes"] == []
    assert any(
        f["value"] is True
        for f in result["grounded_facts"]
        if f["predicate_check"]["feature_id"] == "appearance.defect_present"
    )
    assert not any(r["status"] == "fully_supported" for r in result["candidate_evaluations"])


def test_semantic_tightening_is_in_report_and_progress_not_a_fake_llm_call(tmp_path):
    units, cap, blueprint = source_blueprint(tmp_path)
    events = []
    compile_unified_knowledge(
        units,
        cap,
        llm_client=None,
        stored_blueprint=blueprint,
        output_dir=tmp_path / "build",
        title="门控语义明确记录",
        dataset="mvtec",
        progress=lambda stage, label, **details: events.append((stage, label, details)),
    )
    report = json.loads((tmp_path / "build/unified_build_report.json").read_text())
    normalization = report["authoring_normalizations"][0]
    assert normalization["semantic_change"] is True
    assert any(details.get("normalization") == normalization for _, _, details in events)
    assert any("收紧" in label for _, label, _ in events)
    assert not any(stage == "llm" for stage, _, _ in events)
    assert report["generation_mode"] == "stored_blueprint"


def test_all_is_only_algebraically_regrouped(tmp_path):
    units, cap, blueprint = source_blueprint(tmp_path, logic="all")
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    assert proposal.normalizations[0].semantic_change is False
    new = KnowledgeProgram(proposal.knowledge)
    original = proposal.knowledge.model_dump(mode="json")
    p = original["pattern_definitions"][0]
    refs = sorted(new.footprint(p["pattern_id"]))
    p["body"] = {"all": [refs[0], {"all": refs[1:]}]}
    old = KnowledgeProgram(original)
    assert [b.predicates for b in old.branches(p["pattern_id"])] == [
        b.predicates for b in new.branches(p["pattern_id"])
    ]


def test_at_least_keeps_explicit_diagnostic_count_and_reports_tightening(tmp_path):
    units, cap, blueprint = source_blueprint(tmp_path, logic="at_least", count=1)
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    validate_proposal(proposal, units, cap)
    pattern = proposal.knowledge.pattern_definitions[0]
    assert pattern.body.all[-1].at_least.count == 1
    assert len(pattern.body.all[-1].at_least.of) == 1
    assert proposal.normalizations[0].authored_logic == "at_least"
    assert proposal.normalizations[0].semantic_change is True
    blueprint.signatures[0].at_least_count = 2
    with pytest.raises(ValueError, match="will not guess"):
        lower_blueprint(blueprint, cap, units)


def test_pure_presence_signature_is_a_specific_validation_error(tmp_path):
    units, cap, blueprint = source_blueprint(tmp_path)
    blueprint.signatures[0].conditions = blueprint.signatures[0].conditions[:1]
    with pytest.raises(ValueError, match="gates alone"):
        lower_blueprint(blueprint, cap, units)


def test_canonical_proposal_cannot_bypass_branch_safety(tmp_path):
    units, cap, blueprint = source_blueprint(tmp_path)
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    definitions = {p.feature_id: p.predicate_id for p in proposal.knowledge.observable_definitions}
    data = proposal.model_dump(mode="json")
    data["knowledge"]["pattern_definitions"][0]["body"] = {
        "all": [
            definitions["detection.anomaly_present"],
            {
                "any": [
                    definitions["appearance.defect_present"],
                    definitions["appearance.semantic_candidates"],
                ]
            },
        ]
    }
    unsafe = CompiledProposal.model_validate(data)
    with pytest.raises(ValueError, match="specific diagnostic observation"):
        validate_proposal(unsafe, units, cap)
    # Even an older/forged captured capability cannot relabel a known generic
    # producer field as specific diagnosis and bypass the authoritative catalog.
    cap = cap.model_copy(deep=True)
    for feature in [*cap.features, *unsafe.knowledge.feature_registry]:
        if feature.feature_id == "appearance.defect_present":
            feature.semantic_role = "diagnostic"
    with pytest.raises(ValueError, match="specific diagnostic observation"):
        validate_proposal(unsafe, units, cap)


@pytest.mark.parametrize("dataset", ["tep", "wafer"])
def test_presence_lifting_is_shared_across_process_and_spatial_contracts(tmp_path, dataset):
    units, cap, blueprint = source_blueprint(tmp_path, dataset=dataset)
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    program = validate_proposal(proposal, units, cap)
    pattern = proposal.knowledge.pattern_definitions[0]
    assert len(program.branches(pattern.pattern_id)) == 1
    assert any(
        program.observables[p].feature_id != "detection.anomaly_present"
        for p in program.branches(pattern.pattern_id)[0].predicates
    )
    assert proposal.normalizations[0].semantic_change is True


def test_role_semantics_are_not_a_blanket_boolean_rule_or_a_metadata_bypass(tmp_path):
    specific = FeatureDefinition(
        feature_id="test.specific_response",
        value_kind="boolean",
        definition="Test-only modeled response",
        semantic_role="diagnostic",
    )
    assert authoring_feature_role(specific) == "diagnostic"
    forged = specific.model_copy(update={"feature_id": "appearance.defect_present"})
    assert authoring_feature_role(forged) == "presence_gate"
    units, cap, blueprint = source_blueprint(tmp_path)
    cap = cap.model_copy(update={"features": [*cap.features, specific]})
    blueprint.signatures[0].conditions[1].feature_id = "test.specific_response"
    blueprint.signatures[0].conditions[1].op = "bool_eq"
    from kgtracevis.schema.unified_evidence import BooleanValue

    blueprint.signatures[0].conditions[1].operand = BooleanValue(kind="boolean", boolean=True)
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    validate_proposal(proposal, units, cap)
    assert proposal.normalizations[0].diagnostic_condition_count == 1


def test_reference_background_alone_is_not_a_specific_diagnostic_cue(tmp_path):
    units, cap, blueprint = source_blueprint(tmp_path, dataset="tep")
    condition = copy.deepcopy(blueprint.signatures[0].conditions[1])
    condition.feature_id, condition.subject_external_id = "residual.normal_limit", "$focus"
    blueprint.signatures[0].conditions = [condition]
    with pytest.raises(ValueError, match="context gates alone"):
        lower_blueprint(blueprint, cap, units)
