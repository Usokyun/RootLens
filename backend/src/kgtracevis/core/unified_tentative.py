"""Explain a single partly matched branch without changing the strict proof."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from kgtracevis.core.unified_grounding import GroundedFact, Grounding
from kgtracevis.schema.feature_catalog import authoring_feature_role

MeasurementKey = tuple[str, str, str]


@dataclass
class MeasuredQuantity:
    groups: set[str] = field(default_factory=set)
    obs_ids: set[str] = field(default_factory=set)


def _quantity(fact: GroundedFact, grounding: Grounding) -> MeasurementKey:
    assert fact.subject_id is not None and fact.scope_id is not None
    return (
        grounding.program.observables[fact.predicate_id].feature_id,
        fact.subject_id,
        fact.scope_id,
    )


def _usable(fact: GroundedFact) -> bool:
    return fact.measured and fact.value is not None


def _observed_diagnostics(grounding: Grounding, roles: dict[str, str]):
    """One denominator for all candidates; a repeated quantity cannot create a new vote."""
    quantities: dict[MeasurementKey, MeasuredQuantity] = {}
    parents: dict[str, str] = {}
    for predicate, facts in grounding.facts.items():
        if roles[predicate] != "diagnostic":
            continue
        for fact in facts:
            if not _usable(fact):
                continue
            assert fact.dependency_group is not None
            group = fact.dependency_group
            quantity = quantities.setdefault(_quantity(fact, grounding), MeasuredQuantity())
            quantity.groups.add(group)
            quantity.obs_ids.update(fact.obs_ids)
            parents[group] = group

    def representative(group: str) -> str:
        while group != parents[group]:
            group = parents[group]
        return group

    # If the same measurement is attributed to several groups, those groups are
    # not independent for this calculation. Merge instead of choosing one label.
    for quantity in quantities.values():
        roots = sorted({representative(g) for g in quantity.groups})
        for group in roots[1:]:
            parents[group] = roots[0]
    groups = defaultdict(list)
    for key, quantity in sorted(quantities.items()):
        groups[representative(min(quantity.groups))].append(key)
    return quantities, dict(sorted(groups.items()))


def _ids(facts, *, value):
    return sorted({obs_id for fact in facts if fact.value is value for obs_id in fact.obs_ids})


def _partial_branch(grounding, roles, expected, option, candidate, groups, group_names, references):
    # The strict evaluator already checks nested joins, including Wafer zones
    # sharing a parent grid. Never take a union of alternative proof branches.
    if not option.scope_valid or option.truth is True or not option.branch.predicates:
        return None
    by_predicate = {p: grounding.facts[p] for p in sorted(option.branch.predicates)}
    gates = [p for p in by_predicate if roles[p] == "presence_gate"]
    if not gates:
        return None
    if any({f.value for f in by_predicate[p] if _usable(f)} != {True} for p in gates):
        return None

    ref_ids = {
        references[obs_id]
        for facts in by_predicate.values()
        for fact in facts
        if _usable(fact)
        for obs_id in fact.obs_ids
        if references[obs_id] is not None
    }
    task_ref = grounding.frame.task.reference_id
    if len(ref_ids) > 1 or (task_ref is not None and ref_ids - {task_ref}):
        return None

    support, counter = defaultdict(set), defaultdict(set)
    for predicate, facts in by_predicate.items():
        if roles[predicate] != "diagnostic":
            continue
        for fact in facts:
            if _usable(fact):
                bucket = support if fact.value is True else counter
                bucket[_quantity(fact, grounding)].update(fact.obs_ids)
    supported = support.keys() - counter.keys()
    if len(supported) < 2:
        return None

    program = grounding.program
    policy = program.package.execution_policy
    pattern = program.patterns[expected.pattern_id]
    checks = []
    for predicate, facts in by_predicate.items():
        true, false, unknown = (_ids(facts, value=value) for value in (True, False, None))
        condition = program.observables[predicate]
        checks.append(
            {
                "predicate_id": predicate,
                "predicate_check": {
                    "feature_id": condition.feature_id,
                    "op": condition.op,
                    "operand": condition.operand.model_dump(mode="json"),
                },
                "label": condition.label,
                "role": roles[predicate],
                "status": "conflicting"
                if true and false
                else "refuted"
                if false
                else "supported"
                if true
                else "unknown",
                "fact_ids": sorted(f.fact_id for f in facts),
                "support_obs_ids": true,
                "counter_obs_ids": false,
                "unknown_obs_ids": unknown,
                "unknown_reasons": sorted(
                    {f.reason for f in facts if f.value is None and f.reason}
                ),
                "counts_toward_support": roles[predicate] == "diagnostic"
                and any(
                    f.value is True and _usable(f) and _quantity(f, grounding) in supported
                    for f in facts
                ),
                "source_assertion_ids": condition.source_assertion_ids,
            }
        )

    group_scores = []
    for group, keys in groups.items():
        found = len(supported.intersection(keys))
        group_scores.append(
            {
                "group_id": group,
                "dependency_group_ids": group_names[group],
                "observed_quantity_count": len(keys),
                "supported_quantity_count": found,
                "uncovered_quantity_count": len(keys) - found,
                "conflicting_quantity_count": len(counter.keys() & set(keys)),
            }
        )
    u = sum(g["uncovered_quantity_count"] / g["observed_quantity_count"] for g in group_scores)
    c = sum(g["conflicting_quantity_count"] / g["observed_quantity_count"] for g in group_scores)
    u, c = u / len(group_scores), c / len(group_scores)
    a = candidate.assumption_cost
    return {
        "candidate_id": candidate.hypothesis_id,
        "candidate_name": candidate.label,
        "candidate_role": candidate.target_role,
        "rule_id": expected.rule_id,
        "rule_mode": expected.mode,
        "pattern_id": pattern.pattern_id,
        "pattern_label": pattern.label,
        "definition_id": pattern.definition_id,
        "scope_join": pattern.scope_join,
        "branch_predicate_ids": list(by_predicate),
        "condition_checks": checks,
        "support_obs_ids": sorted({obs for key in supported for obs in support[key]}),
        "counter_obs_ids": sorted({obs for ids in counter.values() for obs in ids}),
        "missing_predicate_ids": [
            row["predicate_id"] for row in checks if row["status"] == "unknown"
        ],
        "support_measurement_count": len(supported),
        "scoring_details": {
            "denominator_policy": "shared_observed_diagnostics_v1",
            "unexplained_loss": u,
            "conflict_loss": c,
            "assumption_cost": a,
            "conflict_weight": policy.conflict_weight,
            "assumption_weight": policy.assumption_weight,
            "total_cost": u + policy.conflict_weight * c + policy.assumption_weight * a,
            "groups": group_scores,
        },
    }


def tentative_evidence(grounding, rows, worlds, evaluated, pattern_truth):
    pending = [
        row
        for row in rows
        if not row["eligible_for_ranking"]
        and all(
            rule.mode != "necessary" or pattern_truth[rule.pattern_id] is True
            for rule in worlds[row["candidate_id"]][3]
        )
    ]
    if not pending:
        return {}
    program = grounding.program
    roles = {
        predicate: authoring_feature_role(
            program.features[program.observables[predicate].feature_id]
        )
        for predicate in grounding.facts
    }
    quantities, groups = _observed_diagnostics(grounding, roles)
    if len(quantities) < 2:
        return {}
    group_names = {
        g: sorted({name for key in keys for name in quantities[key].groups})
        for g, keys in groups.items()
    }
    references = {obs.obs_id: obs.reference_id for obs in grounding.frame.observations}
    candidates = []
    for row in pending:
        candidate_id = row["candidate_id"]
        candidate = program.hypotheses[candidate_id]
        choices = (
            _partial_branch(
                grounding, roles, rule, option, candidate, groups, group_names, references
            )
            for rule in worlds[candidate_id][3]
            for option in evaluated[rule.pattern_id]
        )
        best = min(
            (choice for choice in choices if choice is not None),
            key=lambda choice: (
                choice["scoring_details"]["total_cost"],
                -choice["support_measurement_count"],
                len(choice["missing_predicate_ids"]),
                choice["rule_id"],
                choice["branch_predicate_ids"],
            ),
            default=None,
        )
        if best is not None:
            candidates.append(best)
    if not candidates:
        return {}
    candidates.sort(key=lambda row: (row["scoring_details"]["total_cost"], row["candidate_id"]))
    return {
        "tentative_candidates": candidates,
        "tentative_diagnostic_context": {
            "observed_quantity_count": len(quantities),
            "groups": [
                {
                    "group_id": group,
                    "dependency_group_ids": group_names[group],
                    "measurements": [
                        {
                            "feature_id": feature,
                            "subject_id": subject,
                            "scope_id": scope,
                            "obs_ids": sorted(quantities[feature, subject, scope].obs_ids),
                        }
                        for feature, subject, scope in keys
                    ],
                }
                for group, keys in groups.items()
            ],
        },
    }
