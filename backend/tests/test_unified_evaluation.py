"""Independent flat calculation and deliberately weaker same-input references."""

import copy
import json
from pathlib import Path

import pytest
from test_unified_contracts import example

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.experiments.unified_diagnosis import (
    atom_path_reference,
    flat_reference,
    flattened_knowledge,
    freeze_runs,
)
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


@pytest.mark.parametrize("scene", ["mvtec", "tep", "wafer"])
@pytest.mark.parametrize("missing", [False, True])
def test_flat_reference_checks_every_candidate_and_cost(scene, missing):
    knowledge = example("knowledge-package.json")
    payload = example(f"{scene}-evidence.json")
    if missing:
        payload["observations"][1].update(status="missing", value=None)
    frame = EvidenceFrame.model_validate(payload)
    actual = UnifiedReasoner(knowledge).analyze(frame)
    expected = flat_reference(knowledge, frame)
    assert len(expected) == len(actual["candidate_evaluations"])
    for row in expected:
        candidate = next(
            r for r in actual["candidate_evaluations"] if r["candidate_id"] == row["candidate_id"]
        )
        assert candidate["scoring_details"]["total_cost"] == pytest.approx(row["cost"])
        assert candidate["eligible_for_ranking"] == row["eligible"]
    lifted = UnifiedReasoner(flattened_knowledge(knowledge)).analyze(frame)
    assert [(r["candidate_id"], r["score"]) for r in lifted["candidate_evaluations"]] == [
        (r["candidate_id"], r["score"]) for r in actual["candidate_evaluations"]
    ]


def test_single_atom_reference_does_not_check_the_other_required_condition():
    knowledge = example("knowledge-package.json")
    frame = example("mvtec-evidence.json")
    frame["observations"][1]["value"]["number"] = 0.70
    typed = EvidenceFrame.model_validate(frame)
    assert not UnifiedReasoner(knowledge).analyze(typed)["ranked_root_causes"]
    assert atom_path_reference(knowledge, typed)


def test_duplicate_sensitive_reference_is_explicitly_an_ablation():
    knowledge = example("knowledge-package.json")
    frame = example("mvtec-evidence.json")
    baseline = flat_reference(knowledge, EvidenceFrame.model_validate(frame))
    duplicate = copy.deepcopy(frame["observations"][3])
    duplicate["obs_id"] = "o:copied-negative"
    frame["observations"].append(duplicate)
    typed = EvidenceFrame.model_validate(frame)
    assert baseline == flat_reference(knowledge, typed)
    assert baseline != flat_reference(knowledge, typed, count_source_rows=True)


def test_freezer_uses_original_snapshot_and_refuses_to_overwrite(tmp_path):
    payload = {
        "run": {"run_id": "actual-run"},
        "summary": {"working_graph_snapshot": {"knowledge": example("knowledge-package.json")}},
        "cases": [
            {
                "case_id": "actual-case",
                "dataset": "mvtec",
                "reasoning_metadata": {"evidence_frames": [example("mvtec-evidence.json")]},
            }
        ],
    }
    path = tmp_path / "run.json"
    path.write_text(json.dumps(payload))
    manifest = freeze_runs([path], tmp_path / "frozen")
    case = json.loads(manifest.read_text())["cases"][0]
    assert case["run_id"] == "actual-run"
    assert KnowledgePackage.model_validate_json(Path(case["knowledge"]).read_text()) == (
        KnowledgePackage.model_validate(payload["summary"]["working_graph_snapshot"]["knowledge"])
    )
    with pytest.raises(FileExistsError):
        freeze_runs([path], tmp_path / "frozen")
