"""Grade bound measurements and freeze the shared comparison budget."""

from __future__ import annotations

import math
from dataclasses import dataclass

from kgtracevis.core.unified_grounding import GroundedFact, Grounding
from kgtracevis.schema.unified_knowledge import NumericGrade

MeasurementKey = tuple[str, str | None, str | None, str | None]


def numeric_degrees(grade: NumericGrade, value: float) -> tuple[float, float]:
    if grade.direction == "interval":
        distance = min(value - grade.lower, grade.upper - value)
    elif grade.direction == "lower":
        distance = grade.pivot - value
    else:
        distance = (abs(value) if grade.direction == "absolute_higher" else value) - grade.pivot
    return (
        max(0.0, min(1.0, (distance - grade.neutral_support) / grade.support_width)),
        max(0.0, min(1.0, (-distance - grade.neutral_conflict) / grade.conflict_width)),
    )


def measurement_key(feature: str, fact: GroundedFact) -> MeasurementKey:
    return feature, fact.subject_id, fact.scope_id, fact.reference_id


@dataclass(frozen=True)
class ConditionReading:
    facts: tuple[GroundedFact, ...]
    valid_facts: tuple[GroundedFact, ...]
    support: float | None = None
    conflict: float | None = None
    truth: bool | None = None
    reason: str = ""

    @property
    def measured(self) -> bool:
        return self.support is not None

    @property
    def status(self) -> str:
        if not self.measured:
            return "unknown"
        if self.support:
            return "supported"
        return "conflicting" if self.conflict else "neutral"

    @property
    def observed_ids(self) -> list[str]:
        return sorted({identity for fact in self.valid_facts for identity in fact.obs_ids})


def condition_readings(grounding: Grounding) -> dict[str, ConditionReading]:
    readings = {}
    task_reference = grounding.frame.task.reference_id
    for identity, facts in grounding.facts.items():
        predicate = grounding.program.observables[identity]
        bound = tuple(facts)
        known = tuple(f for f in bound if f.measured and f.value is not None)
        eligible = tuple(
            f for f in known if task_reference is None or f.reference_id in {task_reference, None}
        )
        keys = {measurement_key(predicate.feature_id, f) for f in eligible}
        if not eligible:
            reason = (
                "incompatible_normal_reference"
                if known
                else "; ".join(sorted({f.reason for f in bound if f.reason}))
            )
            readings[identity] = ConditionReading(bound, (), reason=reason)
        elif len(keys) != 1:
            readings[identity] = ConditionReading(bound, (), reason="ambiguous_measurement_scope")
        elif any(
            f.actual_values != eligible[0].actual_values or f.value != eligible[0].value
            for f in eligible[1:]
        ):
            # Duplicate records cannot vote twice or choose whichever value better fits the rule.
            readings[identity] = ConditionReading(
                bound, (), reason="inconsistent_repeated_measurement"
            )
        else:
            selected = eligible[0]
            p, c = (
                numeric_degrees(predicate.grade, selected.actual_values[0]["number"])
                if predicate.grade is not None
                else (float(selected.value), float(not selected.value))
            )
            readings[identity] = ConditionReading(bound, eligible, p, c, selected.value)
    return readings


@dataclass(frozen=True)
class BudgetSlot:
    slot_id: str
    group_id: str
    weight: float
    predicate_ids: tuple[str, ...]

    def to_json(self):
        return {
            "slot_id": self.slot_id,
            "group_id": self.group_id,
            "weight": self.weight,
            "predicate_ids": list(self.predicate_ids),
        }


def _normalized(weights):
    largest = max(weights)
    scaled = [weight / largest for weight in weights]
    total = math.fsum(scaled)
    result = [weight / total for weight in scaled]
    if not all(result):
        raise ValueError("graded policy weights cannot be normalized without losing a slot")
    return result


def comparison_budget(policy, predicates: set[str]) -> dict[str, BudgetSlot]:
    """Applicable predicates, never observed values, determine what spends the budget."""
    groups = []
    for group in sorted(policy.groups, key=lambda g: g.group_id):
        slots = [
            (slot, tuple(sorted(predicates.intersection(slot.predicate_ids))))
            for slot in sorted(group.slots, key=lambda s: s.slot_id)
        ]
        if applicable := [(slot, ids) for slot, ids in slots if ids]:
            groups.append((group, applicable))
    if not groups:
        return {}
    budget = {}
    for (group, slots), group_weight in zip(
        groups, _normalized([group.weight for group, _ in groups]), strict=True
    ):
        for (slot, ids), weight in zip(
            slots, _normalized([slot.weight for slot, _ in slots]), strict=True
        ):
            effective = group_weight * weight
            if not effective:
                raise ValueError("graded policy weights cannot be normalized without losing a slot")
            budget[slot.slot_id] = BudgetSlot(slot.slot_id, group.group_id, effective, ids)
    return budget


def overlapping_sources(program, budget, readings, task_reference):
    """No measured quantity or producer dependency can spend two nominal budgets."""
    measured_slots: dict[MeasurementKey, set[str]] = {}
    source_groups: dict[str, set[str]] = {}
    for slot in budget.values():
        for identity in slot.predicate_ids:
            feature = program.observables[identity].feature_id
            for fact in readings[identity].facts:
                # The producer still declares the dependency for missing/invalid
                # measurements. Don't allow a split group only because one slot is missing.
                if fact.subject_id is None or (
                    task_reference is not None and fact.reference_id not in {None, task_reference}
                ):
                    continue
                key = measurement_key(feature, fact)
                measured_slots.setdefault(key, set()).add(slot.slot_id)
                if fact.dependency_group is not None:
                    source_groups.setdefault(fact.dependency_group, set()).add(slot.group_id)
    return [
        {"kind": "measurement", "measurement_key": list(key), "slot_ids": sorted(ids)}
        for key, ids in sorted(measured_slots.items(), key=lambda row: repr(row[0]))
        if len(ids) > 1
    ] + [
        {"kind": "dependency_group", "dependency_group": group, "group_ids": sorted(ids)}
        for group, ids in sorted(source_groups.items())
        if len(ids) > 1
    ]
