from dataclasses import replace

import numpy as np
import pytest

from kgtracevis.adapters.tep_adapter import evidence_from_tep_record
from kgtracevis.adapters.wm811k_adapter import evidence_from_wm811k_record
from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph
from kgtracevis.kg.working_graph_package import (
    WorkingGraphPackage,
    executable_subgraph,
    graph_package,
)
from kgtracevis.mask.wafer_map_features import measure_wafer_map
from kgtracevis.producers.tep_records import (
    TepFaultWindow,
    _record_from_window,
    compute_tep_window_contributions,
    fit_tep_fault_free_profile,
)
from kgtracevis.schema.measured_reasoning import (
    MeasuredProfileBundle,
    ProcessMeasurements,
    validate_measured_profiles,
)
from kgtracevis.workflows.measured_profile_reasoner import MeasuredProfileReasoner


def edge(h, t, dataset, **kwargs):
    return KGEdge(
        h,
        "AFFECTS_VARIABLE" if dataset == "tep" else "SUGGESTS_MECHANISM",
        t,
        dataset,
        "test notes",
        "explicit test relation",
        0.7,
        0.7,
        "auto",
        0,
        0,
        0,
        **kwargs,
    )


def test_wafer_encoding_normal_unknown_and_classifier_conflict():
    a = [[0, 1, 1, 0], [1, 2, 2, 1], [0, 1, 1, 0]]
    m = measure_wafer_map(a)
    assert m.valid_die_count == 8 and m.failed_die_count == 2
    assert m.failure_density == 0.25
    assert measure_wafer_map([[0, 1], [1, 0]]).failed_die_count == 0
    with pytest.raises(ValueError):
        measure_wafer_map([[3]])
    g = KnowledgeGraph(
        [
            KGNode("P", "nearfull", "Pattern", "wafer", ()),
            KGNode("C", "widespread failure", "Mechanism", "wafer", ()),
        ],
        [edge("P", "C", "wafer")],
    )
    b = MeasuredProfileBundle.model_validate(
        {
            "dataset": "wafer",
            "profiles": [
                {
                    "profile_id": "density",
                    "anchor_id": "P",
                    "candidate_ids": ["C"],
                    "conditions": [
                        {
                            "feature": "wafer.failure_density",
                            "op": "gte",
                            "value": 0.75,
                            "concept_id": "P",
                            "source_edge_id": g.edges[0].edge_id,
                        },
                        {
                            "feature": "wafer.classifier_pattern",
                            "op": "eq",
                            "value": "nearfull",
                            "concept_id": "P",
                            "source_edge_id": g.edges[0].edge_id,
                        },
                    ],
                }
            ],
        }
    )
    r = MeasuredProfileReasoner(b)

    def result(pattern, wafer):
        e = evidence_from_wm811k_record({"wafer_map": wafer, "predicted_pattern": pattern})
        return r.reason_root_causes(e, graph=g, linked_entities=[])

    assert result("Near-full", [[2, 2], [2, 1]]).outcome == "matched"
    assert result("Center", [[2, 2], [2, 1]]).outcome == "no_match"
    assert result("Near-full", [[1, 1], [1, 1]]).ranked_root_causes == []
    e = evidence_from_wm811k_record({"wafer_map": [[2, 2], [2, 1]], "failure_pattern": "nearfull"})
    assert r.reason_root_causes(e, graph=g, linked_entities=[]).outcome == "insufficient_evidence"


def process_case(tmp_path):
    p = tmp_path / "normal.csv"
    rng = np.random.default_rng(7)
    normal = rng.normal(size=(100, 3))
    p.write_text(
        "xmeas_1,xmeas_9,xmv_10\n" + "\n".join(",".join(str(v) for v in row) for row in normal)
    )
    reference = fit_tep_fault_free_profile(p, row_stride=1, n_components=1)
    window = TepFaultWindow(4, 1, 161, 180, rng.normal(size=(20, 3)) + [0, 5, 4])
    record = _record_from_window(
        window,
        contribution=compute_tep_window_contributions(reference, window),
        faulty_path=p,
        profile=reference,
        top_variables=1,
        fault_start_sample=161,
    )
    e = evidence_from_tep_record(record)
    measured = next(o for o in e.observations if o.value_type == "process-measurements.v1")
    assert len(measured.value["channels"]) == 3
    assert len([o for o in e.observations if o.facet == "variable"]) == 3
    return e


def test_current_graph_direction_weight_profiles_and_full_vector_change_tep(tmp_path):
    e = process_case(tmp_path)
    g = KnowledgeGraph(
        [
            KGNode("F", "Cooling disturbance", "Fault", "tep", ()),
            KGNode("V", "Reactor temperature", "Variable", "tep", ("xmeas_9",)),
            KGNode("W", "Cooling valve", "Variable", "tep", ("xmv_10",)),
        ],
        [
            edge("F", "V", "tep", propagation_enabled=True, relation_family="FAULT_SOURCE"),
            edge("F", "W", "tep", propagation_enabled=True, relation_family="CONTROL"),
        ],
    )
    b = MeasuredProfileBundle.model_validate(
        {
            "dataset": "tep",
            "profiles": [
                {
                    "profile_id": "cooling",
                    "anchor_id": "F",
                    "candidate_ids": ["F"],
                    "conditions": [
                        {
                            "feature": "process.mean_z",
                            "channel": "xmeas_9",
                            "op": "abs_gte",
                            "value": 2.0,
                            "concept_id": "V",
                            "source_edge_id": g.edges[0].edge_id,
                        },
                        {
                            "feature": "process.mean_z",
                            "channel": "xmv_10",
                            "op": "abs_gte",
                            "value": 2.0,
                            "concept_id": "W",
                            "source_edge_id": g.edges[1].edge_id,
                        },
                    ],
                }
            ],
        }
    )

    def run(graph=g, bundle=b):
        return MeasuredProfileReasoner(bundle).reason_root_causes(
            e, graph=graph, linked_entities=[]
        )

    before = run()
    assert before.outcome == "matched" and len(before.top_k_paths) == 2
    assert set(before.metadata["trace"][0]["candidate_results"][0]["numeric_components"]) == {
        "xmeas_9",
        "xmv_10",
    }
    weakened = KnowledgeGraph(g.nodes.values(), [replace(x, edge_weight=0.1) for x in g.edges])
    assert run(weakened).ranked_root_causes[0].score < before.ranked_root_causes[0].score
    backwards = KnowledgeGraph(
        g.nodes.values(), [replace(x, propagation_direction="reverse") for x in g.edges]
    )
    assert run(backwards).ranked_root_causes == []
    stricter = b.model_copy(deep=True)
    stricter.profiles[0].conditions[0].value = 100.0
    assert run(bundle=stricter).outcome == "no_match"
    package = graph_package(
        g, graph_id="tep-test", title="TEP", build_id="test", dataset="tep", profiles=b
    )
    assert WorkingGraphPackage.model_validate_json(package.model_dump_json()) == package
    noisy = KnowledgeGraph(
        [*g.nodes.values(), KGNode("FileName", "File name", "Other", "tep", ())], g.edges
    )
    projected = executable_subgraph(noisy, b)
    assert set(projected.nodes) == set(g.nodes)
    assert (
        MeasuredProfileReasoner(b)
        .reason_root_causes(e, graph=projected, linked_entities=[])
        .ranked_root_causes
        == before.ranked_root_causes
    )
    bad = b.model_copy(deep=True)
    bad.profiles[0].conditions[0].concept_id = "F"
    with pytest.raises(ValueError, match="Variable"):
        validate_measured_profiles(bad, g)


def test_window_schema_rejects_channel_and_sample_mismatch(tmp_path):
    e = process_case(tmp_path)
    payload = next(o for o in e.observations if o.value_type == "process-measurements.v1").value
    payload["sample_end"] += 1
    with pytest.raises(ValueError, match="contiguous"):
        ProcessMeasurements.model_validate(payload)
