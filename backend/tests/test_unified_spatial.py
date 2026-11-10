import json

import numpy as np
import pytest

from kgtracevis.adapters.unified import evidence_frames
from kgtracevis.adapters.unified_capabilities import spatial_capabilities
from kgtracevis.adapters.wm811k_adapter import evidence_from_wm811k_record
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.schema.unified_evidence import DieEncoding
from kgtracevis.source_kg_compiler.material_parser import parse_material
from kgtracevis.source_kg_compiler.unified_blueprint import KnowledgeBlueprint, lower_blueprint


@pytest.fixture
def knowledge(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Illustrative spatial constraints for tests, not validated process causes.")
    units = parse_material(source, source_id="test", scenario="wafer").units
    assertion = dict(
        text="Declared test pattern condition",
        origin="declared_demo_heuristic",
        parameter_origin="declared_demo_heuristic",
        source_unit_id=units[0].unit_id,
    )
    signatures = []
    for key, conditions in [
        ("edge_ring", [("edge", "gte", 0.5), ("center", "lte", 0.1)]),
        ("nearfull", [("all_valid", "gte", 0.8), ("center", "gte", 0.8)]),
    ]:
        signatures.append(
            dict(
                signature_key=key,
                label=key,
                context_external_id="wafer",
                conditions=[
                    dict(
                        label=f"{zone} density",
                        feature_id="spatial.failure_density",
                        op=op,
                        operand=dict(kind="number", number=value, unit="1"),
                        zone=zone,
                        assertion=assertion,
                    )
                    for zone, op, value in conditions
                ],
                causes=[
                    dict(
                        candidate_key=key,
                        label=key,
                        mechanism_key=key,
                        mechanism_label=key,
                        assertion=assertion,
                    )
                ],
                assertion=assertion,
            )
        )
    return lower_blueprint(
        KnowledgeBlueprint.model_validate(dict(title="Test", signatures=signatures)),
        spatial_capabilities(),
        units,
    )["knowledge"]


def evidence(grid, prediction="edge_ring", **extra):
    return evidence_from_wm811k_record(
        dict(case_id="wafer-test", wafer_map=grid, predicted_pattern=prediction, **extra)
    )


def test_spatial_zones_frozen_core_and_classifier_independence(knowledge):
    grid = np.ones((21, 21), dtype=int)
    y, x = np.indices(grid.shape)
    radius = np.sqrt(((x - 10) / 10) ** 2 + ((y - 10) / 10) ** 2)
    grid[radius >= 0.8] = 2
    frame = evidence_frames(evidence(grid.tolist(), prediction="nearfull"))[0]
    assert len(frame.scopes) == 5 and frame.task.target_role == "pattern_family"
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert [r["candidate_name"] for r in result["ranked_root_causes"]] == ["edge_ring"]
    assert result["unused_observations"]  # classifier isn't silently used by numeric-only knowledge
    assert all(
        f["scope_id"] in {"scope:all_valid", "scope:edge", "scope:center"}
        for f in result["grounded_facts"]
    )
    frame.source_dataset = "new-spatial-backbone"
    assert (
        UnifiedReasoner(knowledge).analyze(frame)["ranked_root_causes"]
        == result["ranked_root_causes"]
    )


def test_normal_empty_encoding_and_native_labels(knowledge):
    for grid in [[[0, 1], [1, 0]], [[0, 0], [0, 0]]]:
        frame = evidence_frames(
            evidence(grid, prediction="nearfull", native_failure_pattern="Near-full")
        )[0]
        assert not UnifiedReasoner(knowledge).analyze(frame)["ranked_root_causes"]
        assert "native_failure_pattern" not in frame.model_dump_json()
    empty = evidence_frames(evidence([[0, 0], [0, 0]]))[0]
    density = next(
        o
        for o in empty.observations
        if o.feature_id == "spatial.failure_density" and o.scope_id == "scope:all_valid"
    )
    assert density.status == "missing" and density.value is None
    for bad in [dict(background=False), dict(normal=1.0)]:
        with pytest.raises(ValueError, match="literal integers"):
            DieEncoding.model_validate(bad)
    with pytest.raises(ValueError, match="boolean"):
        evidence_frames(evidence([[True, False], [True, False]]))


def test_grid_measurements_verified_and_path_assets_supported(tmp_path):
    e = evidence([[1, 2], [1, 1]])
    observation = next(o for o in e.observations if o.value_type == "wafer-measurements.v1")
    observation.value["failed_die_count"] = 2
    with pytest.raises(ValueError, match="disagrees"):
        evidence_frames(e)
    e = evidence([[1, 2], [1, 1]])
    path = tmp_path / "grid.json"
    path.write_text(json.dumps([[1, 2], [1, 1]]))
    e.raw_evidence.extra["wm811k"].pop("wafer_map")
    e.raw_evidence.extra["wafer_map_path"] = str(path)
    frame = evidence_frames(e)[0]
    assert frame.assets[0].uri == str(path) and frame.assets[0].shape == [2, 2]
