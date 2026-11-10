"""Executable v2 contracts; design fixtures are independent of runtime model assets."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage

EXAMPLES = Path(__file__).resolve().parents[2] / "src/doc/design-examples/unified-reasoning-v2"


def example(name):
    return json.loads((EXAMPLES / name).read_text())


@pytest.mark.parametrize("scene", ["mvtec", "tep", "wafer"])
def test_design_frames_roundtrip_through_closed_contract(scene):
    frame = EvidenceFrame.model_validate(example(f"{scene}-evidence.json"))
    assert EvidenceFrame.model_validate_json(frame.model_dump_json()) == frame
    assert frame.source_dataset == scene


def test_knowledge_roundtrip_and_machine_readable_schemas():
    knowledge = KnowledgePackage.model_validate(example("knowledge-package.json"))
    assert KnowledgePackage.model_validate_json(knowledge.model_dump_json()) == knowledge
    assert len(knowledge.hypotheses) == 7
    schema = EvidenceFrame.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["NumberValue"]["additionalProperties"] is False
    assert "number" in schema["$defs"]["NumberValue"]["required"]
    assert KnowledgePackage.model_json_schema()["additionalProperties"] is False


@pytest.mark.parametrize("value", [True, "0.97", float("nan"), float("inf")])
def test_numeric_measurements_refuse_coercion_or_nonfinite(value):
    frame = example("mvtec-evidence.json")
    frame["observations"][1]["value"]["number"] = value
    with pytest.raises(ValidationError):
        EvidenceFrame.model_validate(frame)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda e: e["observations"][1].update(subject_id="missing"),
        lambda e: e["observations"][1].update(scope_id="missing"),
        lambda e: e["observations"][1].update(procedure_id="missing"),
        lambda e: e["observations"][1].update(raw_refs=["missing"]),
        lambda e: e["observations"][1].update(status="missing"),
        lambda e: e["observations"][1].update(description="interpret arbitrary text"),
        lambda e: e["scopes"][0].update(bbox_xyxy=[0, 0, 901, 900]),
        lambda e: e["subjects"][1].update(parent_id="roi:1"),
        lambda e: e["observations"].append(dict(e["observations"][1])),
    ],
)
def test_invalid_or_ambiguous_evidence_is_rejected(mutation):
    frame = example("mvtec-evidence.json")
    mutation(frame)
    with pytest.raises(ValidationError):
        EvidenceFrame.model_validate(frame)


def test_missing_is_explicit_and_not_a_zero_or_false_default():
    frame = example("mvtec-evidence.json")
    frame["observations"][3].update(status="missing", value=None)
    parsed = EvidenceFrame.model_validate(frame)
    assert parsed.observations[3].value is None
    assert parsed.observations[2].value.exhaustive is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda e: e["observations"][0].update(reference_id="another-scaler"),
        lambda e: e["scopes"][0].update(sample_start=260, sample_end=161),
        lambda e: e["assets"][0].update(columns=["same"] * 52),
        lambda e: e["references"][0].update(scaler_asset_id=None),
        lambda e: e["references"][0].update(normal_asset_id="scaler:1"),
        lambda e: e["subjects"][1].update(context_subject_id=None),
    ],
)
def test_temporal_identity_and_normal_reference_are_not_optional_metadata(mutation):
    frame = example("tep-evidence.json")
    mutation(frame)
    with pytest.raises(ValidationError):
        EvidenceFrame.model_validate(frame)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda k: k["observable_definitions"][0].update(feature_id="any.undefined"),
        lambda k: k["observable_definitions"][0]["operand"].update(unit="mm"),
        lambda k: k["observable_definitions"][0].update(op="eval_python"),
        lambda k: k["observable_definitions"][0].update(source_assertion_ids=["missing"]),
        lambda k: k["subject_bindings"].append(dict(k["subject_bindings"][0])),
        lambda k: k["pattern_definitions"][0].update(body={"all": ["missing"]}),
        lambda k: k["effect_rules"][0].update(to_id="h:wear"),
        lambda k: k["expectation_rules"][0].update(pattern_id="missing"),
        lambda k: k["entities"][0].update(entity_id="q:elongated"),
        lambda k: k["hypotheses"][0].update(assumption_cost=-1),
        lambda k: k["execution_policy"].update(conflict_weight=True),
    ],
)
def test_executable_knowledge_checks_bindings_types_and_source_references(mutation):
    payload = example("knowledge-package.json")
    mutation(payload)
    with pytest.raises(ValidationError):
        KnowledgePackage.model_validate(payload)


def test_new_dataset_name_does_not_require_a_schema_or_scoring_branch():
    frame = example("mvtec-evidence.json")
    frame["source_dataset"] = "new-inspection-domain"
    assert EvidenceFrame.model_validate(frame).source_dataset == "new-inspection-domain"


def test_declared_boolean_expressions_remain_data_not_executable_code():
    knowledge = example("knowledge-package.json")
    knowledge["pattern_definitions"][0]["body"] = {
        "all": ["q:elongated", {"any": ["q:scratch_cue", "q:foreign_material"]}]
    }
    parsed = KnowledgePackage.model_validate(knowledge)
    assert parsed.pattern_definitions[0].body.all[1].any == ["q:scratch_cue", "q:foreign_material"]
