"""The shipped native Bottle Frame tests geometry, not the model or a defect label."""

import copy
import json
from pathlib import Path

import pytest

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage

PACK = Path(__file__).resolve().parents[1] / "data/demo/two_loop/mvtec"


def test_eccentricity_is_required_even_with_a_near_square_bounding_box():
    graph = UnifiedWorkingGraphPackage.model_validate_json(
        (PACK / "working-graph.v2.json").read_bytes()
    )
    original = json.loads((PACK / "evidence.json").read_bytes())["frames"][0]
    alternative = copy.deepcopy(original)
    (eccentricity,) = (
        observation
        for observation in alternative["observations"]
        if observation["feature_id"] == "geometry.eccentricity"
    )
    assert eccentricity["status"] == "observed"
    assert eccentricity["value"]["unit"] == "1"
    assert eccentricity["value"]["number"] < 0.90
    eccentricity["value"]["number"] = 0.94

    reasoner = UnifiedReasoner(graph.knowledge)
    baseline = reasoner.analyze(original, top_k=8)
    counterfactual = reasoner.analyze(alternative, top_k=8)
    assert baseline["outcome"] == "ambiguous"
    assert "tentative_candidates" not in baseline
    assert [row["rank"] for row in baseline["ranked_root_causes"]] == [1, 1]
    assert all(
        eccentricity["obs_id"] in row["support_obs_ids"] for row in baseline["ranked_root_causes"]
    )
    assert any(
        eccentricity["obs_id"] in path["support_obs_ids"] for path in baseline["top_k_paths"]
    )

    assert {
        fact["predicate_check"]["feature_id"]: fact["value"]
        for fact in counterfactual["grounded_facts"]
    } == {
        "detection.anomaly_present": True,
        "geometry.area_ratio": True,
        "geometry.aspect_ratio": True,
        "geometry.eccentricity": False,
    }
    assert [pattern["value"] for pattern in counterfactual["observed_patterns"]] == [False]
    assert counterfactual["outcome"] == "insufficient_evidence"
    assert not counterfactual["ranked_root_causes"]
    assert not counterfactual["top_k_paths"]
    assert len(counterfactual["candidate_evaluations"]) == 2
    for row in counterfactual["candidate_evaluations"]:
        assert row["status"] == "no_match"  # Strict comparison is unchanged.
        assert not row["eligible_for_ranking"]
        assert row["counter_obs_ids"] == [eccentricity["obs_id"]]
    assert counterfactual["tentative_diagnostic_context"]["observed_quantity_count"] == 3
    tentative = counterfactual["tentative_candidates"]
    assert len(tentative) == 2
    for row in tentative:
        assert row["counter_obs_ids"] == [eccentricity["obs_id"]]
        assert row["support_measurement_count"] == 2
        assert not row["missing_predicate_ids"]
        assert {c["predicate_check"]["feature_id"] for c in row["condition_checks"]} == {
            "detection.anomaly_present",
            "geometry.area_ratio",
            "geometry.aspect_ratio",
            "geometry.eccentricity",
        }
        scores = row["scoring_details"]
        assert scores["unexplained_loss"] == pytest.approx(1 / 3)
        assert scores["conflict_loss"] == pytest.approx(1 / 3)
        assert scores["assumption_cost"] == 1
        assert scores["total_cost"] == pytest.approx(1.25)
