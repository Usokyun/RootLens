"""Appearance vocabulary for the ROI model, excluding causal hypotheses."""

from __future__ import annotations


def visual_semantic_concepts(knowledge: dict) -> list[dict[str, str]]:
    assertions = {row["assertion_id"]: row for row in knowledge["source_assertions"]}
    vocabulary = {}
    for row in knowledge["observable_definitions"]:
        if row["feature_id"] != "appearance.semantic_candidates":
            continue
        if row["op"] == "candidate_contains":
            labels = [row["operand"]["category"]]
        elif row["op"] == "intersects":
            labels = row["operand"]["items"]
        else:
            continue
        description = "; ".join(assertions[s]["text"] for s in row["source_assertion_ids"])
        for label in labels:
            vocabulary.setdefault(
                label, {"concept_id": label, "label": row["label"], "description": description}
            )
    return [vocabulary[label] for label in sorted(vocabulary)]
