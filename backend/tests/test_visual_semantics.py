"""Coordinate-grounded ROI semantics, bounded calls and honest normal/unknown outcomes."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError
from test_visual_profile_reasoning import linear_mask, pipeline

from kgtracevis.adapters.ds_mvtec_adapter import evidence_from_mvtec_record
from kgtracevis.mask.visual_regions import map_regions_to_image, regions_from_mask
from kgtracevis.producers.visual_semantics import OpenAICompatibleROISemantics
from kgtracevis.schema.visual_reasoning import VisualRegion


class VisionFixture:
    def __init__(self, prediction):
        self.prediction = prediction
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(self.prediction)),
                )
            ],
            usage=SimpleNamespace(total_tokens=80),
        )


@pytest.fixture
def image(tmp_path, monkeypatch):
    monkeypatch.setenv("KGTRACEVIS_VISION_API", "chat_completions")
    path = tmp_path / "do_not_leak_native_answer_scratch.png"
    Image.new("RGB", (400, 400), color="white").save(path)
    return path


def aligned_regions():
    return map_regions_to_image(
        regions_from_mask(linear_mask()),
        (400, 400),
        {"kind": "resize"},
    )


def test_resize_crop_inverse_is_explicit_and_geometry_validated():
    region = VisualRegion(
        region_id="roi",
        source="detector_mask",
        coordinate_space="detector_grid",
        image_shape=(100, 100),
        bbox_xyxy=(0, 0, 100, 100),
    )
    mapped = map_regions_to_image(
        [region],
        (400, 800),
        {
            "kind": "resize_center_crop",
            "resized_shape": [200, 400],
            "crop_xywh": [100, 50, 200, 100],
        },
    )[0]
    assert mapped.image_bbox_xyxy == (200, 100, 600, 300)
    assert map_regions_to_image([region], (400, 800), None)[0].image_bbox_xyxy is None
    with pytest.raises(ValueError, match="equal"):
        map_regions_to_image([region], (400, 800), {"kind": "identity"})
    assert (
        map_regions_to_image([region], (100, 100), {"kind": "identity"})[0].image_bbox_xyxy
        == region.bbox_xyxy
    )
    with pytest.raises(ValidationError, match="outside"):
        VisualRegion.model_validate(
            {
                **region.model_dump(),
                "original_image_shape": [100, 100],
                "image_bbox_xyxy": [0, 0, 101, 100],
            }
        )


def test_roi_prompt_has_neutral_crop_and_concepts_without_case_answer(image, tmp_path):
    client = VisionFixture(
        {
            "concept_ids": ["ScratchDefect"],
            "description": "A thin surface mark.",
            "observation_state": "defect",
        }
    )
    semantics = OpenAICompatibleROISemantics(client=client, model="vision-fixture")
    result = semantics.annotate(
        image,
        aligned_regions(),
        object_name="metal_nut",
        concepts=[{"concept_id": "ScratchDefect", "label": "Scratch"}],
        output_dir=tmp_path / "rois",
    )[0]
    assert result.semantic_candidates == ["ScratchDefect"]
    assert result.semantic_source == "vlm:vision-fixture"
    assert result.semantic_status == "predicted"
    assert Image.open(result.roi_path).size == (357, 117)
    assert result.roi_bbox_xyxy == (22, 132, 379, 249)
    assert semantics.calls == 1 and semantics.tokens == 80
    content = client.requests[0]["messages"][0]["content"]
    assert image.name not in content[0]["text"]
    assert "MechanicalContact" not in content[0]["text"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_optional_normal_reference_is_image_only_not_a_native_label(image, tmp_path):
    client = VisionFixture(
        {
            "concept_ids": [],
            "description": "Uncertain visual change",
            "observation_state": "uncertain",
        }
    )
    semantics = OpenAICompatibleROISemantics(client=client, model="fixture")
    semantics.annotate(
        image,
        aligned_regions(),
        object_name="bottle",
        concepts=[{"concept_id": "Broken", "label": "Broken glass"}],
        output_dir=tmp_path / "rois",
        normal_reference_path=image,
    )
    content = client.requests[0]["messages"][0]["content"]
    assert len(content) == 4
    assert "normal reference" in content[0]["text"]
    assert image.name not in content[0]["text"]


@pytest.mark.parametrize(
    "state,outcome",
    [
        ("normal", "no_match"),
        ("uncertain", "insufficient_evidence"),
    ],
)
def test_explicit_normal_and_uncertain_never_force_a_geometric_diagnosis(
    image,
    tmp_path,
    state,
    outcome,
):
    client = VisionFixture(
        {
            "concept_ids": [],
            "description": "No supported object defect.",
            "observation_state": state,
        }
    )
    regions = OpenAICompatibleROISemantics(client=client, model="vision-fixture").annotate(
        image,
        aligned_regions(),
        object_name="metal_nut",
        concepts=[{"concept_id": "ScratchDefect", "label": "Scratch"}],
        output_dir=tmp_path,
    )
    evidence = evidence_from_mvtec_record(
        {
            "object": "metal_nut",
            "visual_regions": [r.model_dump() for r in regions],
        }
    )
    result = pipeline().analyze(evidence)
    assert not result.ranked_root_causes
    assert result.reasoning_metadata["outcome"] == outcome
    assert not result.reasoning_metadata["fallback_applied"]


@pytest.mark.parametrize(
    "prediction",
    [
        {"concept_ids": ["MadeUpCause"], "description": "x", "observation_state": "defect"},
        {"concept_ids": [], "description": "x", "observation_state": "defect"},
    ],
)
def test_invalid_semantics_are_rejected_not_replaced_by_labels(image, tmp_path, prediction):
    client = VisionFixture(prediction)
    semantics = OpenAICompatibleROISemantics(client=client, model="vision-fixture")
    with pytest.raises(ValueError, match="ROI"):
        semantics.annotate(
            image,
            aligned_regions(),
            object_name="metal_nut",
            concepts=[{"concept_id": "ScratchDefect", "label": "Scratch"}],
            output_dir=tmp_path,
        )


def test_unaligned_and_budget_skipped_regions_never_trigger_extra_calls(image, tmp_path):
    regions = aligned_regions()
    regions.append(regions[0].model_copy(update={"region_id": "second", "area_ratio": 0.0001}))
    client = VisionFixture(
        {
            "concept_ids": [],
            "description": "Uncertain.",
            "observation_state": "uncertain",
        }
    )
    semantics = OpenAICompatibleROISemantics(client=client, model="vision-fixture", max_regions=1)
    result = semantics.annotate(
        image,
        regions,
        object_name="metal_nut",
        concepts=[{"concept_id": "ScratchDefect", "label": "Scratch"}],
        output_dir=tmp_path,
    )
    assert [r.semantic_status for r in result] == ["unknown", "not_evaluated_budget"]
    assert semantics.calls == 1
    unaligned = regions[0].model_copy(update={"image_bbox_xyxy": None})
    assert (
        semantics.annotate(
            image,
            [unaligned],
            object_name="metal_nut",
            concepts=[{"concept_id": "ScratchDefect", "label": "Scratch"}],
            output_dir=tmp_path,
        )[0].semantic_status
        == "unaligned"
    )
    assert semantics.calls == 1


def test_normal_detector_decision_is_distinct_from_unknown_empty_regions():
    normal = evidence_from_mvtec_record(
        {
            "object": "metal_nut",
            "visual_regions": [],
            "detector": {"raw_pred_label": False},
        }
    )
    result = pipeline().analyze(normal)
    assert result.reasoning_metadata["outcome"] == "no_match"
    assert result.reasoning_metadata["detection_status"] == "normal"
    unknown = normal.model_copy(deep=True)
    unknown.raw_evidence.extra["detector"] = None
    assert pipeline().analyze(unknown).reasoning_metadata["outcome"] == "insufficient_evidence"


def test_observed_semantic_conflict_blocks_an_otherwise_geometric_match():
    regions = aligned_regions()
    regions[0] = regions[0].model_copy(
        update={
            "semantic_candidates": ["PokeDefect"],
            "semantic_status": "predicted",
            "semantic_source": "vlm:fixture",
        }
    )
    result = pipeline().analyze(
        evidence_from_mvtec_record(
            {
                "object": "metal_nut",
                "visual_regions": [r.model_dump() for r in regions],
            }
        )
    )
    assert result.ranked_root_causes == []
    assert result.reasoning_metadata["outcome"] == "no_match"
    assert result.reasoning_metadata["trace"][0]["semantic_conflict"] is True


def test_observed_provider_transport_tag_does_not_weaken_semantic_schema(image, tmp_path):
    client = VisionFixture(
        {
            "type": "json_object",
            "concept_ids": [],
            "description": "Uncertain.",
            "observation_state": "uncertain",
        }
    )
    result = OpenAICompatibleROISemantics(client=client, model="vision-fixture").annotate(
        image,
        aligned_regions(),
        object_name="metal_nut",
        concepts=[{"concept_id": "ScratchDefect", "label": "Scratch"}],
        output_dir=tmp_path,
    )
    assert result[0].semantic_status == "unknown"
    assert (tmp_path / "roi_1.semantics.json").is_file()
