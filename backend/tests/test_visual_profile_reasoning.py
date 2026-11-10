"""MVTec region → executable graph conditions → candidate/path behavior."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from kgtracevis.adapters.ds_mvtec_adapter import evidence_from_mvtec_record
from kgtracevis.core.pipeline import KGTracePipeline
from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph
from kgtracevis.kg.visual_profile_compiler import compile_visual_profiles
from kgtracevis.mask.visual_regions import regions_from_mask
from kgtracevis.schema.visual_reasoning import VisualCondition, VisualProfileBundle
from kgtracevis.service.run_enrichment import dashboard_fields_from_analysis
from kgtracevis.source_kg_compiler import SourceKGCompilerConfig, run_source_kg_compiler_workflow
from kgtracevis.workflows.profile_match_reasoner import VisualProfileReasoner
from kgtracevis.workflows.root_cause_provider_selection import build_pipeline


def visual_graph() -> KnowledgeGraph:
    nodes = [
        KGNode("MetalNutObject", "Metal nut", "Object", "mvtec", ("metal_nut",)),
        KGNode("ScratchDefect", "Scratch", "Defect", "mvtec", ("scratch",)),
        KGNode("LinearMorphology", "Linear morphology", "Morphology", "mvtec", ("linear",)),
        KGNode("MechanicalContact", "Mechanical contact", "CandidateCause", "mvtec", ()),
        KGNode("SurfaceWear", "Surface wear", "CandidateCause", "mvtec", ()),
    ]

    def edge(head: str, relation: str, tail: str) -> KGEdge:
        return KGEdge(
            head,
            relation,
            tail,
            "mvtec",
            "test-source",
            "source excerpt",
            0.7,
            0.7,
            "auto",
            0,
            0,
            0,
            external_edge_id=f"compiler:{head}:{tail}",
        )

    return KnowledgeGraph(
        nodes,
        [
            edge("MetalNutObject", "HAS_ANOMALY", "ScratchDefect"),
            edge("ScratchDefect", "HAS_MORPHOLOGY", "LinearMorphology"),
            edge("ScratchDefect", "HAS_PLAUSIBLE_CAUSE", "MechanicalContact"),
            edge("ScratchDefect", "HAS_PLAUSIBLE_CAUSE", "SurfaceWear"),
        ],
    )


def evidence_for(mask: np.ndarray, **overrides):
    return evidence_from_mvtec_record(
        {
            "case_id": "obs_case",
            "object": "metal_nut",
            "predicted_mask": mask.tolist(),
            **overrides,
        }
    )


def pipeline(graph=None, profiles=None):
    return KGTracePipeline(
        graph=graph or visual_graph(), root_cause_reasoner=VisualProfileReasoner(profiles)
    )


def linear_mask():
    mask = np.zeros((40, 40))
    mask[18:20, 7:33] = 1
    return mask


def test_regions_measure_separate_components_and_zero_centroid():
    mask = np.zeros((10, 10))
    mask[0, 0] = 1
    mask[5:7, 2:9] = 1
    regions = regions_from_mask(mask)
    assert len(regions) == 2
    assert regions[0].bbox_xyxy == (0, 0, 1, 1)
    assert regions[0].location == "edge"
    assert regions[1].area_ratio == 0.14
    assert sum(r.area_ratio for r in regions) == pytest.approx(0.15)
    assert regions_from_mask(np.zeros((4, 4))) == []


@pytest.mark.parametrize("mask", [[], [[float("nan")]], [1, 2]])
def test_invalid_mask_is_rejected(mask):
    with pytest.raises(ValueError):
        regions_from_mask(mask)


@pytest.mark.parametrize(
    "condition",
    [
        {"feature": "region.area_ratio", "op": "in", "value": ["large"]},
        {"feature": "region.semantic_candidates", "op": "gte", "value": 1},
        {"feature": "region.morphology", "op": "eq", "value": ["linear"]},
        {"feature": "arbitrary.code", "op": "eq", "value": "anything"},
    ],
)
def test_incompatible_feature_operators_are_rejected(condition):
    with pytest.raises(ValidationError):
        VisualCondition.model_validate(condition)


def test_unknown_semantics_still_use_geometry_and_do_not_invent_a_label():
    evidence = evidence_for(linear_mask())
    assert evidence.anomaly_type == "unknown"
    result = pipeline().analyze(evidence)
    assert {c.candidate_id for c in result.ranked_root_causes} == {
        "MechanicalContact",
        "SurfaceWear",
    }
    assert len({c.score for c in result.ranked_root_causes}) == 1
    assert all(
        o.value["semantic_candidates"] == []
        for o in evidence.observations
        if o.value_type == "visual_region.v1"
    )
    assert result.consistency_score is None
    assert result.reasoning_metadata["outcome"] == "matched"
    assert result.reasoning_metadata["fallback_applied"] is False
    obs_ids = {o.obs_id for o in evidence.observations}
    for path in result.top_k_paths:
        assert path["source_entity_id"] != "MetalNutObject"
        assert path["supporting_evidence"] == path["support_obs_ids"]
        assert set(path["support_obs_ids"]) <= obs_ids
        assert len(path["nodes"]) == len(path["source_edges"]) + 1
        for head, edge, tail in zip(
            path["nodes"], path["source_edges"], path["nodes"][1:], strict=False
        ):
            assert (edge["head"], edge["tail"]) == (head, tail)
    fields = dashboard_fields_from_analysis(evidence, result)
    assert fields["path_graph"]["paths"][0]["nodes"]


def test_numeric_condition_really_changes_candidate_eligibility():
    graph = visual_graph()
    bundle = compile_visual_profiles(graph)
    bundle.profiles[0].conditions.append(
        VisualCondition(
            feature="region.area_ratio",
            op="gte",
            value=0.05,
        )
    )
    result = pipeline(graph, bundle).analyze(evidence_for(linear_mask()))
    assert not result.ranked_root_causes
    assert result.reasoning_metadata["outcome"] == "no_match"
    bundle.profiles[0].conditions[-1].value = 0.01
    assert pipeline(graph, bundle).analyze(evidence_for(linear_mask())).ranked_root_causes


def test_spot_and_missing_geometry_do_not_fallback_to_label_path():
    spot = np.zeros((40, 40))
    spot[16:23, 16:23] = 1
    result = pipeline().analyze(evidence_for(spot, defect_type="scratch"))
    assert result.ranked_root_causes == []
    assert result.reasoning_metadata["outcome"] == "no_match"
    missing = evidence_from_mvtec_record({"object": "metal_nut", "defect_type": "scratch"})
    assert pipeline().analyze(missing).reasoning_metadata["outcome"] == "insufficient_evidence"


def test_multiple_regions_remain_distinct_and_observation_order_does_not_select_answer():
    mask = linear_mask()
    mask[2:6, 2:6] = 1
    evidence = evidence_for(mask)
    first = pipeline().analyze(evidence)
    reverse = pipeline().analyze(
        evidence.model_copy(
            update={
                "observations": list(reversed(evidence.observations)),
            }
        )
    )
    assert [c.candidate_id for c in first.ranked_root_causes] == [
        c.candidate_id for c in reverse.ranked_root_causes
    ]
    assert first.reasoning_metadata["region_count"] == 2
    assert all(
        c.support_evidence_ids == ["obs:obs_case:region_2"] for c in first.ranked_root_causes
    )


def test_removing_or_rejecting_graph_edge_changes_actual_candidates():
    graph = visual_graph()
    removed = KnowledgeGraph(
        graph.nodes.values(), [e for e in graph.edges if e.tail != "MechanicalContact"]
    )
    assert [
        c.candidate_id
        for c in pipeline(removed).analyze(evidence_for(linear_mask())).ranked_root_causes
    ] == ["SurfaceWear"]
    rejected = KnowledgeGraph(
        graph.nodes.values(),
        [
            replace(e, review_status="rejected") if e.tail == "MechanicalContact" else e
            for e in graph.edges
        ],
    )
    assert [
        c.candidate_id
        for c in pipeline(rejected).analyze(evidence_for(linear_mask())).ranked_root_causes
    ] == ["SurfaceWear"]


def test_new_registry_option_uses_actual_graph_and_keeps_legacy_default():
    new = build_pipeline(graph=visual_graph(), reasoning_profile_id="mvtec_feature_graph_v1")
    assert (
        new.analyze(evidence_for(linear_mask())).reasoning_metadata["reasoning_profile_id"]
        == "mvtec_feature_graph_v1"
    )
    legacy = build_pipeline(graph=visual_graph()).analyze(
        evidence_for(linear_mask(), defect_type="scratch")
    )
    assert legacy.reasoning_metadata["reasoner_adapter"] == "generic_graph_path"


def test_out_of_scope_object_reports_not_applicable_without_fallback():
    result = pipeline().analyze(evidence_for(linear_mask(), object="capsule"))
    assert result.ranked_root_causes == []
    assert result.reasoning_metadata["outcome"] == "not_applicable"
    assert "capsule" in result.reasoning_metadata["reason"]
    assert result.reasoning_metadata["fallback_applied"] is False


def test_duplicate_region_identity_is_rejected_instead_of_overwriting_links():
    region = regions_from_mask(linear_mask())[0].model_dump()
    with pytest.raises(ValueError, match="unique"):
        evidence_from_mvtec_record({"object": "metal_nut", "visual_regions": [region, region]})


class CompilerLLMFixture:
    """A local response fixture, not a provider/model accuracy test."""

    def complete_json(self, *, system_prompt, **_kwargs):
        if "canonical entities" in system_prompt:
            return json.dumps(
                {
                    "entities": [
                        {
                            "entity_id": n.id,
                            "canonical_name": n.name,
                            "entity_type": n.label,
                            "aliases": list(n.aliases),
                            "scenario": "mvtec",
                        }
                        for n in visual_graph().nodes.values()
                    ]
                }
            )
        return "{}"

    def repair_json(self, text, _error):
        return text


def test_source_compiler_emits_consumable_profiles_and_keeps_compiler_edge_identity(tmp_path: Path):
    source = tmp_path / "knowledge.md"
    source.write_text(
        "MetalNutObject HAS_ANOMALY ScratchDefect\n"
        "ScratchDefect HAS_MORPHOLOGY LinearMorphology\n"
        "ScratchDefect HAS_PLAUSIBLE_CAUSE MechanicalContact\n",
        encoding="utf-8",
    )
    output = run_source_kg_compiler_workflow(
        SourceKGCompilerConfig(
            source_paths=(source,),
            output_dir=tmp_path / "build",
            default_scenario="mvtec",
            llm_client=CompilerLLMFixture(),
        )
    )
    graph = KnowledgeGraph.from_csv(
        output.artifact_paths.nodes_csv, output.artifact_paths.edges_csv
    )
    payload = json.loads(output.artifact_paths.domain_profiles.read_text())
    bundle = VisualProfileBundle.model_validate(payload["visual_runtime"])
    assert bundle.profiles
    assert all(e.external_edge_id for e in graph.edges)
    result = pipeline(graph, bundle).analyze(evidence_for(linear_mask()))
    assert result.ranked_root_causes
    assert any(e.get("origin_edge_id") for p in result.top_k_paths for e in p["source_edges"])


@pytest.mark.parametrize("repair_succeeds", [True, False])
def test_condition_repair_is_bounded_and_preserves_unusable_results(tmp_path, repair_succeeds):
    class RepairFixture(CompilerLLMFixture):
        profile_calls = 0

        def complete_json(self, *, system_prompt, **kwargs):
            if "reusable reasoning profiles" not in system_prompt:
                return super().complete_json(system_prompt=system_prompt, **kwargs)
            self.profile_calls += 1
            conditions = (
                []
                if self.profile_calls > 1 and repair_succeeds
                else [
                    {
                        "feature": "arbitrary.code",
                        "op": "eq",
                        "value": "not executable",
                    }
                ]
            )
            return json.dumps(
                {
                    "profiles": {
                        "mvtec": {
                            "object_defect_profiles": [
                                {
                                    "object_id": "MetalNutObject",
                                    "defect_id": "ScratchDefect",
                                    "evidence_conditions": conditions,
                                }
                            ]
                        }
                    }
                }
            )

    client = RepairFixture()
    source = tmp_path / "knowledge.md"
    source.write_text(
        "MetalNutObject HAS_ANOMALY ScratchDefect\n"
        "ScratchDefect HAS_MORPHOLOGY LinearMorphology\n"
        "ScratchDefect HAS_PLAUSIBLE_CAUSE MechanicalContact\n",
    )
    output = run_source_kg_compiler_workflow(
        SourceKGCompilerConfig(
            source_paths=(source,),
            output_dir=tmp_path / "build",
            default_scenario="mvtec",
            llm_client=client,
        )
    )
    payload = json.loads(output.artifact_paths.domain_profiles.read_text())
    assert client.profile_calls == 2
    assert payload["metadata"]["runtime_profile_repair_attempts"] == 1
    assert bool(payload["visual_runtime"]["profiles"]) == repair_succeeds
    assert bool(payload["visual_runtime"]["issues"]) != repair_succeeds
