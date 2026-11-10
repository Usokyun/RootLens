import numpy as np
import pytest
from fastapi.testclient import TestClient

from kgtracevis.adapters.unified_capabilities import (
    process_capabilities,
    spatial_capabilities,
    visual_capabilities,
)
from kgtracevis.mask.mask_feature_extractor import derive_mask_location, derive_mask_morphology
from kgtracevis.mask.visual_regions import regions_from_mask
from kgtracevis.schema.feature_catalog import (
    MASK_LOCATIONS,
    MASK_MORPHOLOGIES,
    WAFER_PATTERNS,
)
from kgtracevis.schema.unified_knowledge import FeatureDefinition
from kgtracevis.service.api import create_app


def test_public_catalog_is_the_compiler_contract_with_open_appearance():
    response = TestClient(create_app()).get("/api/authoring/capabilities")
    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    for dataset, manifest in (
        ("mvtec", visual_capabilities()),
        ("tep", process_capabilities()),
        ("wafer", spatial_capabilities()),
    ):
        assert capabilities[dataset] == manifest.model_dump(mode="json")
    features = {f["feature_id"]: f for f in capabilities["mvtec"]["features"]}
    assert features["geometry.morphology"]["allowed_values"] == list(MASK_MORPHOLOGIES)
    assert features["geometry.location"]["allowed_values"] == list(MASK_LOCATIONS)
    assert features["appearance.semantic_candidates"]["allowed_values"] is None
    assert next(
        f for f in capabilities["wafer"]["features"] if f["feature_id"] == "classifier.pattern"
    )["allowed_values"] == list(WAFER_PATTERNS)
    features["geometry.location"]["allowed_values"].append("not-a-producer-value")
    assert next(
        f for f in visual_capabilities().features if f.feature_id == "geometry.location"
    ).allowed_values == list(MASK_LOCATIONS)


def test_deterministic_producer_values_are_in_the_shared_finite_vocabulary():
    thin = np.zeros((20, 20))
    thin[2:3, 2:18] = 1
    square = np.zeros((20, 20))
    square[5:10, 5:10] = 1
    measured = [*regions_from_mask(thin), *regions_from_mask(square)]
    assert {r.morphology for r in measured} == {"linear", "spot"}
    assert all(r.morphology in MASK_MORPHOLOGIES for r in measured)
    assert all(r.location in MASK_LOCATIONS for r in measured)
    assert derive_mask_morphology({"component_count": 4}) == "scattered"
    assert derive_mask_morphology({"area_ratio": 0.5}) == "dense"
    assert derive_mask_location({"centroid_norm": [0.1, 0.5]}) == "edge"
    assert derive_mask_location({"centroid_norm": [0.5, 0.5]}) == "surface"


@pytest.mark.parametrize("values", [[], ["spot", "spot"]])
def test_finite_vocabulary_must_be_nonempty_unique(values):
    with pytest.raises(ValueError, match="nonempty unique"):
        FeatureDefinition(
            feature_id="geometry.morphology",
            value_kind="category",
            definition="Controlled morphology",
            allowed_values=values,
        )


def test_numeric_feature_cannot_claim_categorical_values():
    with pytest.raises(ValueError, match="categorical feature"):
        FeatureDefinition(
            feature_id="geometry.area_ratio",
            value_kind="number",
            unit="1",
            definition="Pixel proportion",
            allowed_values=["spot"],
        )
