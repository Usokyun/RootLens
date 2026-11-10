"""Compact authoring recommendations are not hard engine validity limits."""

import json
from pathlib import Path

import pytest

from kgtracevis.adapters.unified_capabilities import capability_manifest
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_compiler import SearchLimits
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.service.two_loop_api import BuildRequest
from kgtracevis.source_kg_compiler.material_parser import parse_material
from kgtracevis.source_kg_compiler.unified import (
    CompiledProposal,
    compile_unified_knowledge,
    validate_proposal,
)
from kgtracevis.source_kg_compiler.unified_blueprint import KnowledgeBlueprint, lower_blueprint

DESIGN = Path(__file__).resolve().parents[2] / "src/doc/design-examples/unified-reasoning-v2"


def many_candidates(tmp_path, count):
    source = tmp_path / "source.txt"
    source.write_text("Illustrative compiler budget fixture, not industrial evidence.")
    units = parse_material(source, source_id="test-budget", scenario="mvtec").units
    assertion = {
        "text": "Test-only source-bound authoring fixture",
        "origin": "declared_demo_heuristic",
        "parameter_origin": "declared_demo_heuristic",
        "source_unit_id": units[0].unit_id,
    }
    blueprint = KnowledgeBlueprint.model_validate(
        {
            "title": "完整保留候选的预算测试",
            "signatures": [
                {
                    "signature_key": "linear",
                    "label": "测试形态",
                    "context_external_id": "bottle",
                    "conditions": [
                        {
                            "label": "离心率",
                            "feature_id": "geometry.eccentricity",
                            "op": "gte",
                            "operand": {"kind": "number", "number": 0.95, "unit": "1"},
                            "assertion": assertion,
                        }
                    ],
                    "causes": [
                        {
                            "candidate_key": f"cause-{i}",
                            "label": f"测试候选{i}",
                            "mechanism_key": "shared",
                            "mechanism_label": "共享测试表现",
                            "assertion": assertion,
                        }
                        for i in range(count)
                    ],
                    "assertion": assertion,
                }
            ],
        }
    )
    return units, blueprint


@pytest.mark.parametrize("count,limit", [(17, None), (20, None), (32, None), (64, 64)])
def test_candidates_above_recommendation_compile_fully_without_truncation(tmp_path, count, limit):
    units, blueprint = many_candidates(tmp_path, count)
    capability = capability_manifest("visual-region-v2", candidate_limit=limit)
    output = tmp_path / "build"
    events = []
    package = compile_unified_knowledge(
        units,
        capability,
        llm_client=None,
        stored_blueprint=blueprint,
        output_dir=output,
        title="预算完整性",
        dataset="mvtec",
        progress=lambda stage, label, **details: events.append((stage, label)),
    )
    assert len(package.knowledge.hypotheses) == count
    assert {h.hypothesis_id for h in package.knowledge.hypotheses} == {
        f"hypothesis:bottle:cause-{i}" for i in range(count)
    }
    report = json.loads((output / "unified_build_report.json").read_text())
    assert report["candidate_count"] == count
    assert report["authoring_limits"]["recommended_max_candidates"] == 16
    assert report["authoring_limits"]["runtime_candidate_budget"] == 128
    assert report["authoring_limits"]["max_candidates"] == (limit or 32)
    assert report["authoring_warnings"] and "未截断" in report["authoring_warnings"][0]
    assert any(stage == "validation" and "完整保留" in label for stage, label in events)
    assert report["generation_mode"] == "stored_blueprint"


@pytest.mark.parametrize("count,limit", [(33, None), (65, 64)])
def test_real_authoring_hard_boundary_is_explicit(tmp_path, count, limit):
    units, blueprint = many_candidates(tmp_path, count)
    capability = capability_manifest("visual-region-v2", candidate_limit=limit)
    with pytest.raises(ValueError, match=rf"candidate_count={count} > allowed={limit or 32}"):
        lower_blueprint(blueprint, capability, units)
    assert len(blueprint.signatures[0].causes) == count  # no truncation even on failure


def test_hard_configuration_cannot_exceed_bounded_contract():
    with pytest.raises(ValueError, match="64"):
        capability_manifest("visual-region-v2", candidate_limit=65)
    with pytest.raises(ValueError, match="64"):
        BuildRequest(
            material_ids=["m"],
            dataset="mvtec",
            title="test",
            capability_id="visual-region-v2",
            candidate_limit=65,
        )
    assert (
        BuildRequest(
            material_ids=["m"],
            dataset="mvtec",
            title="test",
            capability_id="visual-region-v2",
            candidate_limit=64,
        ).candidate_limit
        == 64
    )
    with pytest.raises(ValueError, match="8个"):
        capability_manifest("spatial-grid-v2", candidate_limit=32)


def test_canonical_proposal_cannot_bypass_the_hard_candidate_limit(tmp_path):
    units, blueprint = many_candidates(tmp_path, 33)
    payload = lower_blueprint(
        blueprint, capability_manifest("visual-region-v2", candidate_limit=64), units
    )
    with pytest.raises(ValueError, match="candidate_count=33 > allowed=32"):
        validate_proposal(
            CompiledProposal.model_validate(payload), units, capability_manifest("visual-region-v2")
        )


def test_inference_search_budget_remains_separate_and_enforced(tmp_path):
    units, blueprint = many_candidates(tmp_path, 17)
    data = lower_blueprint(blueprint, capability_manifest("visual-region-v2"), units)
    frame = EvidenceFrame.model_validate_json((DESIGN / "mvtec-evidence.json").read_text())
    context = next(s for s in frame.subjects if s.subject_id == frame.task.context_subject_id)
    context.external_namespace, context.external_id = "industrial.object", "bottle"
    assert len(UnifiedReasoner(data["knowledge"]).analyze(frame)["candidate_pool"]) == 17
    limited = UnifiedReasoner(data["knowledge"], limits=SearchLimits(candidates=16)).analyze(frame)
    assert limited["outcome"] == "search_incomplete"
    assert "candidate limit" in limited["search_error"]
    assert not limited["ranked_root_causes"]
