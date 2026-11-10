import json

import numpy as np
import pytest

from kgtracevis.adapters.tep_adapter import evidence_from_tep_record
from kgtracevis.adapters.unified import evidence_frames
from kgtracevis.adapters.unified_capabilities import process_capabilities
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.producers.tep_records import build_tep_dat_records
from kgtracevis.source_kg_compiler.material_parser import parse_material
from kgtracevis.source_kg_compiler.unified_blueprint import KnowledgeBlueprint, lower_blueprint


@pytest.fixture
def data(tmp_path):
    rng = np.random.default_rng(71)
    normal, sequence = rng.normal(size=(80, 52)), rng.normal(size=(40, 52))
    sequence[20:, 50] += 6  # xmv_10
    sequence[20:, 20] += 4  # xmeas_21
    np.savetxt(tmp_path / "normal.dat", normal)
    np.savetxt(tmp_path / "sequence.dat", sequence)
    records = build_tep_dat_records(
        tmp_path / "normal.dat",
        tmp_path / "sequence.dat",
        output_dir=tmp_path / "output",
        windows=[(1, 20), (21, 40)],
        n_components=3,
    )
    source = tmp_path / "source.txt"
    source.write_text("Illustrative control families for unit tests, not industrial facts.")
    units = parse_material(source, source_id="unit-test", scenario="tep").units
    assertion = dict(
        text="Declared test relation/parameter",
        origin="declared_demo_heuristic",
        source_unit_id=units[0].unit_id,
        parameter_origin="declared_demo_heuristic",
    )
    signatures = []
    for label, channels in [("cooling", ["xmv_10", "xmeas_21"]), ("feed", ["xmeas_1", "xmv_1"])]:
        signatures.append(
            dict(
                signature_key=label,
                label=label,
                context_external_id="Tennessee Eastman Process",
                conditions=[
                    dict(
                        label=channel,
                        feature_id="statistics.mean_z",
                        op="abs_gte",
                        operand=dict(kind="number", number=2.0, unit="1"),
                        subject_external_id=channel,
                        assertion=assertion,
                    )
                    for channel in channels
                ],
                causes=[
                    dict(
                        candidate_key=label,
                        label=label,
                        mechanism_key=label,
                        mechanism_label=label,
                        assertion=assertion,
                    )
                ],
                assertion=assertion,
            )
        )
    knowledge = lower_blueprint(
        KnowledgeBlueprint.model_validate(dict(title="Test", signatures=signatures)),
        process_capabilities(),
        units,
    )["knowledge"]
    return records, sequence, knowledge


def test_full_window_features_reference_and_same_core(data):
    records, sequence, knowledge = data
    frames = [evidence_frames(evidence_from_tep_record(record))[0] for record in records]
    frame = frames[1]
    assert len(frame.subjects) == 53 and len(frame.observations) == 263
    assert frame.scopes[0].sample_start == 21 and frame.scopes[0].end_inclusive
    assert (
        frame.references[0].reference_id
        == records[1]["extra"]["process_measurements"]["reference_id"]
    )
    window = np.load(records[1]["extra"]["window_array_path"], allow_pickle=False)
    np.testing.assert_allclose(window, sequence[20:40])
    fit = json.loads(open(records[1]["extra"]["normal_reference_assets"]["scaler_uri"]).read())
    standardized = (sequence[20:40, 50] - fit["mean"][50]) / fit["scale"][50]
    slope = next(
        o
        for o in frame.observations
        if o.subject_id == "variable:xmv_10" and o.feature_id == "statistics.slope_z"
    )
    assert slope.value.number == pytest.approx(np.polyfit(np.arange(20), standardized, 1)[0])
    results = [UnifiedReasoner(knowledge).analyze(f) for f in frames]
    assert not results[0]["ranked_root_causes"]
    assert [r["candidate_name"] for r in results[1]["ranked_root_causes"]] == ["cooling"]
    assert len(results[1]["ranked_root_causes"][0]["support_obs_ids"]) == 3


def test_reference_missing_mismatch_and_top_channel_order_do_not_fake_values(data):
    records, _, knowledge = data
    record = records[1]
    before = UnifiedReasoner(knowledge).analyze(
        evidence_frames(evidence_from_tep_record(record))[0]
    )
    record["variables"] = ["xmeas_1"]
    record["variable_contributions"] = {"xmeas_1": 1.0}
    after = UnifiedReasoner(knowledge).analyze(evidence_frames(evidence_from_tep_record(record))[0])
    assert before == after  # only complete measured channels drive v2
    ref = record["extra"].pop("normal_reference_assets")
    frame = evidence_frames(evidence_from_tep_record(record))[0]
    assert not frame.references and frame.task.reference_id is None
    assert not UnifiedReasoner(knowledge).analyze(frame)["ranked_root_causes"]
    record["extra"]["normal_reference_assets"] = {**ref, "reference_id": "another-fit"}
    with pytest.raises(ValueError, match="identity or channel order"):
        evidence_frames(evidence_from_tep_record(record))
