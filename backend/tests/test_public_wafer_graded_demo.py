"""The shipped two-grid Frame pack preserves real competing Wafer interpretations."""

import json
from pathlib import Path

import pytest

from kgtracevis.core.graded_reasoner import GradedReasoner
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.unified_evidence import EvidenceFrame

DATA = Path(__file__).resolve().parents[1] / "data/demo/graded_rca/wafer"


def test_public_graded_wafer_uses_spatial_anchors_and_retains_a_real_disagreement():
    package = UnifiedWorkingGraphPackage.model_validate_json(
        (DATA / "working-graph.v2.json").read_text()
    )
    raw = json.loads((DATA / "evidence.json").read_text())
    frames = [EvidenceFrame.model_validate(row) for row in raw["frames"]]
    assert [f.case_id for f in frames] == ["wm811k_248536/query/grid", "wm811k_31707/query/grid"]
    assert all(f.task.target_role == "pattern_family" for f in frames)
    assert all(a.uri.startswith("evidence://") for f in frames for a in f.assets)
    assert "waferMap" not in json.dumps(raw)  # the distributed Frame does not contain raw cells
    assert set(h.target_role for h in package.knowledge.hypotheses) == {"pattern_family"}
    (group,) = package.knowledge.graded_policy.groups
    assert group.group_id == "grid"
    assert {s.slot_id: s.weight for s in group.slots} == {
        "density.center": 1,
        "density.middle": 1,
        "density.edge": 1,
        "largest_component": 1,
        "edge_sector_participation": 1,
        "classifier_pattern": 0.5,
    }

    engine = GradedReasoner(package.knowledge)
    nearfull, disputed = [engine.analyze(f, top_k=8) for f in frames]
    assert nearfull["outcome"] == "supported"
    (top,) = nearfull["ranked_root_causes"]
    assert top["candidate_id"].endswith("_nearfull")
    assert top["scoring_details"] == pytest.approx(
        {"support": 0.8102889358703314, "conflict": 0, "score": 0.8102889358703314, "coverage": 1}
    )
    assert disputed["outcome"] == "insufficient_evidence" and not disputed["ranked_root_causes"]
    assert len(disputed["candidate_evaluations"]) == 4
    ring, local = disputed["graded_candidates"]
    assert ring["candidate_id"].endswith("_edge_ring") and ring["status"] == "pending"
    assert local["candidate_id"].endswith("_edge_loc") and local["status"] == "pending"
    assert ring["score"] == pytest.approx(0.1506558941526765)
    assert local["score"] == pytest.approx(-0.015396235535816816)
    sector = next(
        o for o in frames[1].observations if o.feature_id == "spatial.edge_sector_participation"
    )
    center = next(
        o
        for o in frames[1].observations
        if o.feature_id == "spatial.failure_density" and o.scope_id == "scope:center"
    )
    assert sector.scope_id == "scope:edge" and sector.dependency_group == "grid"
    assert sector.value.number == pytest.approx(0.9617714916560494)
    for obs, sign in [(sector, "support"), (center, "conflict")]:
        (path,) = [
            p
            for p in ring["explanation_paths"]
            if obs.obs_id in p["observation_ids"] and p["contribution_kind"] == sign
        ]
        assert path["path_kind"] == "graded_contribution"
        assert path["joint_proof_id"] is None and path["source_edge_views"]

    # The older engine uses the same graph and observed Frame; the difference is
    # eligibility, not a rerun of the classifier or replacement of the native label.
    boolean = UnifiedReasoner(package.knowledge).analyze(frames[1], top_k=8)
    (boolean_top,) = boolean["ranked_root_causes"]
    assert boolean_top["candidate_id"] == ring["candidate_id"]
