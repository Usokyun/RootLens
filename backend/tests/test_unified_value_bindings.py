import json
from pathlib import Path

import pytest

from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage

DESIGN = Path(__file__).resolve().parents[2] / "src/doc/design-examples/unified-reasoning-v2"


def test_explicit_value_alias_changes_match_and_preserves_original_value():
    knowledge = json.loads((DESIGN / "knowledge-package.json").read_text())
    frame = EvidenceFrame.model_validate_json((DESIGN / "mvtec-evidence.json").read_text())
    next(
        o for o in frame.observations if o.feature_id == "appearance.semantic_candidates"
    ).value.items = ["LegacyScratch"]
    assert not UnifiedReasoner(knowledge).analyze(frame)["ranked_root_causes"]
    knowledge["value_bindings"] = [
        dict(
            binding_id="alias:legacy-scratch",
            feature_id="appearance.semantic_candidates",
            external_value="LegacyScratch",
            canonical_value="scratch",
            source_assertion_ids=["s:visual-design"],
        )
    ]
    result = UnifiedReasoner(knowledge).analyze(frame)
    assert len(result["ranked_root_causes"]) == 2
    fact = next(f for f in result["grounded_facts"] if f["predicate_id"] == "q:scratch_cue")
    assert fact["actual_values"][0]["items"] == ["LegacyScratch"]
    assert fact["applied_value_binding_ids"] == ["alias:legacy-scratch"]
    knowledge["value_bindings"][0]["procedure_model_id"] = "another_model"
    assert not UnifiedReasoner(knowledge).analyze(frame)["ranked_root_causes"]


def test_conflicting_or_numeric_value_mappings_rejected():
    data = json.loads((DESIGN / "knowledge-package.json").read_text())
    binding = dict(
        binding_id="alias:one",
        feature_id="appearance.semantic_candidates",
        external_value="old",
        canonical_value="scratch",
        source_assertion_ids=["s:visual-design"],
    )
    data["value_bindings"] = [
        binding,
        {
            **binding,
            "binding_id": "alias:two",
            "procedure_model_id": "a_model",
            "canonical_value": "crack",
        },
    ]
    with pytest.raises(ValueError, match="overlapping"):
        KnowledgePackage.model_validate(data)
    data["value_bindings"] = [{**binding, "feature_id": "geometry.eccentricity"}]
    with pytest.raises(ValueError, match="categorical"):
        KnowledgePackage.model_validate(data)
