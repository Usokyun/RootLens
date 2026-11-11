"""Use the current released Evidence, with only the knowledge needed for unit contrasts."""

import copy
import json
from pathlib import Path

PUBLIC = Path(__file__).resolve().parents[1] / "data/demo/graded_rca"


def public_release(dataset):
    directory = PUBLIC / dataset
    package = json.loads((directory / "working-graph.v2.json").read_bytes())
    frames = json.loads((directory / "evidence.json").read_bytes())["frames"]
    return package, frames


def without_grades(knowledge):
    baseline = copy.deepcopy(knowledge)
    baseline.pop("graded_policy", None)
    for row in baseline["observable_definitions"]:
        row.pop("grade", None)
    return baseline


def compact_bottle(*, width_scale=1.0):
    """Isolate the published blocky-response branch and its two indistinguishable causes."""
    package, frames = public_release("mvtec")
    knowledge = package["knowledge"]
    (rule,) = [
        r
        for r in knowledge["expectation_rules"]
        if r["pattern_id"].endswith(":large_blocky_response")
    ]
    (pattern,) = [
        p for p in knowledge["pattern_definitions"] if p["pattern_id"] == rule["pattern_id"]
    ]
    gate, conditions = pattern["body"]["all"]
    ids = conditions["all"]
    pattern["body"] = {"all": [gate, *ids]}
    knowledge["pattern_definitions"] = [pattern]
    knowledge["expectation_rules"] = [rule]
    knowledge["mechanisms"] = [
        m for m in knowledge["mechanisms"] if m["mechanism_id"] == rule["from_id"]
    ]
    effects = [e for e in knowledge["effect_rules"] if e["to_id"] == rule["from_id"]]
    knowledge["effect_rules"] = effects
    knowledge["hypotheses"] = [
        h for h in knowledge["hypotheses"] if h["hypothesis_id"] in {e["from_id"] for e in effects}
    ]
    knowledge["observable_definitions"] = [
        p for p in knowledge["observable_definitions"] if p["predicate_id"] in {gate, *ids}
    ]
    policy = knowledge["graded_policy"]
    for group in policy["groups"]:
        for slot in group["slots"]:
            slot["predicate_ids"] = [p for p in slot["predicate_ids"] if p in ids]
    policy["anchor_predicate_ids"] = [
        p["predicate_id"]
        for p in knowledge["observable_definitions"]
        if p["feature_id"] == "geometry.eccentricity"
    ]
    for row in knowledge["observable_definitions"]:
        if grade := row.get("grade"):
            grade["support_width"] *= width_scale
            grade["conflict_width"] *= width_scale
    return package, frames
