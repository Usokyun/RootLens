"""A controlled angular contrast independent of the classifier and radial density."""

import numpy as np
import pytest

from kgtracevis.adapters.unified import evidence_frames
from kgtracevis.adapters.wm811k_adapter import evidence_from_wm811k_record
from kgtracevis.mask.wafer_map_features import measure_edge_sectors, measure_wafer_map


def density_matched_maps():
    y, x = np.indices((81, 81)) - 40
    distance_squared = x * x + y * y
    disk = (distance_squared <= 40**2).astype(int)
    edge = (disk == 1) & (distance_squared >= 32**2)
    angle = np.mod(np.degrees(np.arctan2(y, x)), 360)
    broad, localized = disk.copy(), disk.copy()
    for i in range(12):
        rows, cols = np.where(edge & (angle >= 30 * i) & (angle < 30 * (i + 1)))
        assert len(rows) >= 80
        broad[rows[:20], cols[:20]] = 2
        if i in {2, 3, 4}:
            localized[rows[:80], cols[:80]] = 2
    return broad, localized


def test_equal_density_ring_and_local_failures_have_different_angular_participation():
    broad, localized = density_matched_maps()
    a, b = measure_edge_sectors(broad), measure_edge_sectors(localized)
    assert sum(a.failed) == sum(b.failed) == 240
    assert a.valid == b.valid and all(a.eligible) and all(b.eligible)
    assert measure_wafer_map(broad).edge_density == measure_wafer_map(localized).edge_density
    assert a.participation > 0.95 and b.participation < 0.27
    # Cardinal rotation and transposition may move individual boundary dice; not the conclusion.
    assert measure_edge_sectors(np.rot90(broad)).participation > 0.90
    assert measure_edge_sectors(np.rot90(localized)).participation < 0.32


def test_angular_measurement_is_missing_without_usable_denominators_or_failures():
    assert measure_edge_sectors([[0, 0], [0, 0]]).participation is None
    assert measure_edge_sectors([[2, 2], [2, 2]]).participation is None
    assert measure_edge_sectors(np.ones((81, 81), dtype=int)).participation is None
    with pytest.raises(ValueError, match="0/1/2 grid"):
        measure_edge_sectors([[1, 0], [2, 3]])


def test_frame_binds_angular_measurement_to_exact_edge_scope_and_source_grid():
    broad, _ = density_matched_maps()
    e = evidence_from_wm811k_record(
        {
            "case_id": "test-wafer-sector",
            "wafer_map": broad.tolist(),
            "predicted_pattern": "donut",
            "native_failure_pattern": "unrelated tag",
        }
    )
    (frame,) = evidence_frames(e)
    angular = next(
        o for o in frame.observations if o.feature_id == "spatial.edge_sector_participation"
    )
    assert angular.scope_id == "scope:edge" and angular.dependency_group == "grid"
    assert angular.status == "observed" and angular.value.unit == "1"
    assert angular.value.number == measure_edge_sectors(broad).participation
    assert angular.raw_refs == ["grid"]
    assert next(p for p in frame.procedures if p.procedure_id == angular.procedure_id).version == (
        "wafer-edge-sector-participation.v1"
    )
    assert "unrelated tag" not in frame.model_dump_json()

    # Existing imported measured records can contain only a path. An arbitrary URI must not be read.
    e.raw_evidence.extra["wm811k"].pop("wafer_map")
    e.raw_evidence.extra["wafer_map_path"] = "untrusted/missing-grid.json"
    (no_grid,) = evidence_frames(e)
    angular = next(o for o in no_grid.observations if o.feature_id == angular.feature_id)
    assert angular.status == "missing" and angular.value is None
