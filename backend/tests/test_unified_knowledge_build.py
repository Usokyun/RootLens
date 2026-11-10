import json
from pathlib import Path

import pytest

from kgtracevis.adapters.unified_capabilities import visual_capabilities
from kgtracevis.schema.unified_knowledge import KnowledgePackage
from kgtracevis.source_kg_compiler.material_parser import parse_material
from kgtracevis.source_kg_compiler.unified import (
    CompiledProposal,
    compile_unified_knowledge,
    validate_proposal,
)
from kgtracevis.source_kg_compiler.unified_blueprint import KnowledgeBlueprint, lower_blueprint

DESIGN = Path(__file__).resolve().parents[2] / "src/doc/design-examples/unified-reasoning-v2"


@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / "public.txt"
    source.write_text("Public source example for compiler contract tests; no case values.")
    units = parse_material(source, source_id="public", scenario="mvtec").units
    capabilities = visual_capabilities(("metal_nut",))
    data = json.loads((DESIGN / "knowledge-package.json").read_text())
    data["example_kind"] = None
    data["feature_registry"] = [f.model_dump() for f in capabilities.features]
    data["subject_bindings"] = [
        {
            "namespace": "industrial.object",
            "external_id": "metal_nut",
            "target_id": "class:metal_nut",
        }
    ]
    data["observable_definitions"] = [
        o
        for o in data["observable_definitions"]
        if o["feature_id"] in {"geometry.eccentricity", "appearance.semantic_candidates"}
    ]
    data["observable_definitions"].append(
        {
            "predicate_id": "q:anomaly",
            "label": "Anomaly",
            "feature_id": "detection.anomaly_present",
            "op": "bool_eq",
            "operand": {"kind": "boolean", "boolean": True},
            "subject_selector": {"kind": "focus"},
            "scope_selector": {"kind": "task_scope"},
            "source_assertion_ids": [data["source_assertions"][0]["assertion_id"]],
        }
    )
    predicates = {o["predicate_id"] for o in data["observable_definitions"]}
    data["pattern_definitions"] = [
        p for p in data["pattern_definitions"] if p["pattern_id"] == "p:linear_mark"
    ]
    assert data["pattern_definitions"], "fixture pattern changed"
    data["pattern_definitions"][0]["body"] = {"all": sorted(predicates)}
    data["hypotheses"] = [
        h for h in data["hypotheses"] if h["hypothesis_id"] in {"h:contact", "h:wear"}
    ]
    data["effect_rules"] = [
        r for r in data["effect_rules"] if r["from_id"] in {"h:contact", "h:wear"}
    ]
    data["expectation_rules"] = [
        r for r in data["expectation_rules"] if r["pattern_id"] == "p:linear_mark"
    ]
    for assertion in data["source_assertions"]:
        assertion.update(
            origin="declared_demo_heuristic", source_id="public", source_unit_id=units[0].unit_id
        )
    return units, capabilities, {"knowledge": data, "unsupported_claims": []}


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def complete_json(self, *, system_prompt, user_prompt):
        assert "capabilities" in user_prompt and "Public source" in user_prompt
        self.calls += 1
        return next(self.responses)


def test_compile_repair_exports_canonical_and_capabilities(inputs, tmp_path):
    units, cap, valid = inputs
    llm = FakeLLM(['{"wrong":1}', json.dumps(valid)])
    package = compile_unified_knowledge(
        units, cap, llm_client=llm, output_dir=tmp_path / "build", title="Test", dataset="mvtec"
    )
    assert package.knowledge == KnowledgePackage.model_validate(valid["knowledge"])
    report = json.loads((tmp_path / "build/unified_build_report.json").read_text())
    assert len(report["repairs"]) == 1 and llm.calls == 2
    assert report["candidate_count"] == 2
    assert (tmp_path / "build/working-graph.v2.json").exists()
    with pytest.raises(ValueError, match="already exists"):
        compile_unified_knowledge(
            units, cap, llm_client=llm, output_dir=tmp_path / "build", title="Test", dataset="mvtec"
        )


def test_capability_unknown_feature_source_and_missing_gate_rejected(inputs):
    units, cap, valid = inputs
    proposal = CompiledProposal.model_validate(valid)
    validate_proposal(proposal, units, cap)
    proposal.knowledge.feature_registry[0].definition = "invented definition"
    with pytest.raises(ValueError, match="capability definition"):
        validate_proposal(proposal, units, cap)
    proposal = CompiledProposal.model_validate(valid)
    proposal.knowledge.pattern_definitions[0].body = {"any": ["q:anomaly", "q:elongated"]}
    with pytest.raises(ValueError, match="every proof branch"):
        validate_proposal(proposal, units, cap)
    proposal = CompiledProposal.model_validate(valid)
    proposal.knowledge.source_assertions[0].source_unit_id = "invented"
    with pytest.raises(ValueError, match="unknown or mismatched"):
        validate_proposal(proposal, units, cap)


def test_failure_is_bounded_and_retains_raw_proposals(inputs, tmp_path):
    units, cap, _ = inputs
    llm = FakeLLM(["{}", "{}"])
    with pytest.raises(ValueError, match="bounded repair"):
        compile_unified_knowledge(
            units,
            cap,
            llm_client=llm,
            output_dir=tmp_path / "failed",
            title="Test",
            dataset="mvtec",
        )
    assert llm.calls == 2
    assert (
        json.loads((tmp_path / "failed/unified_build_report.json").read_text())["status"]
        == "failed"
    )


def test_blueprint_deterministic_shared_mechanism_and_atomic_dedup(inputs, tmp_path):
    units, cap, _ = inputs
    assertion = dict(
        text="Illustrative source-bound condition",
        origin="declared_demo_heuristic",
        parameter_origin="declared_demo_heuristic",
        source_unit_id=units[0].unit_id,
    )
    condition = dict(
        label="Elongated",
        feature_id="geometry.eccentricity",
        op="gte",
        operand={"kind": "number", "number": 0.95, "unit": "1"},
        assertion=assertion,
    )
    causes = [
        dict(
            candidate_key=name,
            label=name,
            mechanism_key="shared",
            mechanism_label="Shared state",
            assertion=assertion,
        )
        for name in ("contact", "thermal")
    ]
    signature = dict(
        signature_key="mark",
        label="Mark",
        context_external_id="metal_nut",
        conditions=[condition],
        causes=causes,
        assertion=assertion,
    )
    repeated = {
        **signature,
        "signature_key": "alternative-description",
        "causes": [{**cause, "label": cause["label"] + " paraphrased"} for cause in causes],
    }
    blueprint = KnowledgeBlueprint.model_validate(
        {"title": "Test", "signatures": [signature, repeated]}
    )
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    validate_proposal(proposal, units, cap)
    assert len(proposal.knowledge.hypotheses) == 2
    assert len(proposal.knowledge.mechanisms) == 1
    assert len(proposal.knowledge.observable_definitions) == 2  # one gate, one real atom
    assert len(proposal.knowledge.expectation_rules) == 2
    package = compile_unified_knowledge(
        units,
        cap,
        llm_client=None,
        output_dir=tmp_path / "stored",
        title="Stored",
        dataset="mvtec",
        stored_blueprint=blueprint,
    )
    assert package.knowledge == proposal.knowledge
    assert (
        json.loads((tmp_path / "stored/unified_build_report.json").read_text())["generation_mode"]
        == "stored_blueprint"
    )


def test_authoring_scalar_membership_is_typed_lowering_not_an_ir_fallback(inputs):
    units, cap, _ = inputs
    assertion = dict(
        text="Declared morphological test",
        origin="declared_demo_heuristic",
        parameter_origin="declared_demo_heuristic",
        source_unit_id=units[0].unit_id,
    )
    blueprint = KnowledgeBlueprint.model_validate(
        dict(
            title="Test",
            signatures=[
                dict(
                    signature_key="linear",
                    label="Linear",
                    context_external_id="metal_nut",
                    conditions=[
                        dict(
                            label="Linear shape",
                            feature_id="geometry.morphology",
                            op="candidate_contains",
                            operand=dict(kind="category", category="linear"),
                            assertion=assertion,
                        )
                    ],
                    causes=[
                        dict(
                            candidate_key="contact",
                            label="Contact",
                            mechanism_key="mark",
                            mechanism_label="Mark",
                            assertion=assertion,
                        )
                    ],
                    assertion=assertion,
                )
            ],
        )
    )
    proposal = lower_blueprint(blueprint, cap, units)
    condition = proposal["knowledge"]["observable_definitions"][1]
    assert condition["op"] == "eq"
    assert proposal["normalizations"][0]["kind"] == "scalar_membership_to_equality"
    condition["op"] = "candidate_contains"
    with pytest.raises(ValueError, match="candidate_set"):
        KnowledgePackage.model_validate(proposal["knowledge"])


def test_progress_exposes_first_validation_error_and_unique_repair(inputs, tmp_path):
    units, cap, valid = inputs
    llm, events = FakeLLM(["{}", json.dumps(valid)]), []
    compile_unified_knowledge(
        units,
        cap,
        llm_client=llm,
        output_dir=tmp_path / "visible-repair",
        title="中文知识",
        dataset="mvtec",
        max_repairs=1,
        progress=lambda stage, label, **details: events.append((stage, label, details)),
    )
    calls = [e for e in events if e[0] == "llm"]
    assert len(calls) == 2 and llm.calls == 2
    assert calls[0][2]["max_calls"] == 2
    assert calls[1][2]["attempt"] == 2
    assert "唯一一次" in calls[1][1]
    failures = [e for e in events if "validation_error" in e[2]]
    assert len(failures) == 1
    assert failures[0][0] == "validation"
    assert events[-1][0] == "compilation"


def test_new_authoring_budgets_cover_source_families_without_silent_truncation():
    from kgtracevis.adapters.unified_capabilities import process_capabilities

    for capability in (visual_capabilities(), process_capabilities()):
        assert capability.recommended_max_candidates == 16
        assert capability.max_candidates == 32
        assert capability.max_hypotheses_per_signature == 32
        assert capability.max_signatures >= 8


@pytest.mark.parametrize("op", ["eq", "in"])
def test_finite_category_unknown_operand_rejected_with_feature_and_values(inputs, op):
    _, _, valid = inputs
    data = valid["knowledge"]
    data["observable_definitions"][0].update(
        feature_id="geometry.morphology",
        op=op,
        operand={"kind": "category", "category": "irregular"}
        if op == "eq"
        else {"kind": "candidate_set", "items": ["linear", "compact"]},
    )
    with pytest.raises(ValueError, match=r"geometry.morphology.*unknown category.*allowed_values"):
        KnowledgePackage.model_validate(data)


def test_finite_category_error_is_visible_and_uses_existing_single_repair(inputs, tmp_path):
    units, cap, valid = inputs
    bad = json.loads(json.dumps(valid))
    bad["knowledge"]["observable_definitions"][0].update(
        feature_id="geometry.location", op="eq", operand={"kind": "category", "category": "upper"}
    )
    events, llm = [], FakeLLM([json.dumps(bad), json.dumps(valid)])
    compile_unified_knowledge(
        units,
        cap,
        llm_client=llm,
        output_dir=tmp_path / "finite-repair",
        title="有限词汇校验",
        dataset="mvtec",
        max_repairs=1,
        progress=lambda stage, label, **details: events.append((stage, label, details)),
    )
    failures = [
        details["validation_error"] for _, _, details in events if "validation_error" in details
    ]
    assert len(failures) == 1
    assert all(term in failures[0] for term in ("geometry.location", "upper", "edge", "surface"))
    assert llm.calls == 2


def test_binding_external_term_is_open_but_finite_canonical_target_is_checked(inputs):
    _, _, valid = inputs
    data = valid["knowledge"]
    data["value_bindings"] = [
        {
            "binding_id": "binding:external-line",
            "feature_id": "geometry.morphology",
            "external_value": "LegacyLine",
            "canonical_value": "linear",
            "source_assertion_ids": [data["source_assertions"][0]["assertion_id"]],
        }
    ]
    assert KnowledgePackage.model_validate(data).value_bindings[0].external_value == "LegacyLine"
    data["value_bindings"][0]["canonical_value"] = "irregular"
    with pytest.raises(ValueError, match=r"value binding.*unknown category"):
        KnowledgePackage.model_validate(data)


def test_blueprint_explicit_equivalence_lowers_with_actual_source_locator(tmp_path):
    source = tmp_path / "glossary.txt"
    source.write_text(
        "LegacyScratch and scratch are equivalent names for the same appearance. "
        "Surface contact can leave a scratch mark."
    )
    units = parse_material(source, source_id="glossary", scenario="mvtec").units
    assertion = dict(
        text=source.read_text(), origin="source_explicit", source_unit_id=units[0].unit_id
    )
    blueprint = KnowledgeBlueprint.model_validate(
        {
            "title": "显式术语等价",
            "signatures": [
                {
                    "signature_key": "mark",
                    "label": "划痕",
                    "context_external_id": "metal_nut",
                    "conditions": [
                        {
                            "label": "外观",
                            "feature_id": "appearance.semantic_candidates",
                            "op": "candidate_contains",
                            "operand": {"kind": "category", "category": "scratch"},
                            "assertion": assertion,
                        }
                    ],
                    "causes": [
                        {
                            "candidate_key": "contact",
                            "label": "接触",
                            "mechanism_key": "mark",
                            "mechanism_label": "表面痕迹",
                            "assertion": assertion,
                        }
                    ],
                    "assertion": assertion,
                }
            ],
            "value_bindings": [
                {
                    "binding_key": "legacy-scratch",
                    "relation": "equivalent",
                    "feature_id": "appearance.semantic_candidates",
                    "external_value": "LegacyScratch",
                    "canonical_value": "scratch",
                    "assertion": assertion,
                }
            ],
        }
    )
    cap = visual_capabilities(("metal_nut",))
    proposal = CompiledProposal.model_validate(lower_blueprint(blueprint, cap, units))
    validate_proposal(proposal, units, cap)
    binding = proposal.knowledge.value_bindings[0]
    assert binding.binding_id == "binding:legacy-scratch"
    evidence = next(
        s
        for s in proposal.knowledge.source_assertions
        if s.assertion_id in binding.source_assertion_ids
    )
    assert (evidence.source_id, evidence.source_unit_id) == ("glossary", units[0].unit_id)
    assert json.loads(evidence.locator) == units[0].source_span
    assert binding.external_value == "LegacyScratch" and binding.canonical_value == "scratch"
    data = blueprint.model_dump(mode="json")
    data["value_bindings"][0]["assertion"]["origin"] = "llm_proposed"
    with pytest.raises(ValueError, match="source_explicit"):
        KnowledgeBlueprint.model_validate(data)
