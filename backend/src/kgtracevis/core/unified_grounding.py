"""Ground registered observations without interpreting arbitrary text/metadata."""

from __future__ import annotations

from dataclasses import dataclass, field

from kgtracevis.kg.unified_compiler import KnowledgeProgram
from kgtracevis.schema.unified_evidence import (
    CandidateSetValue,
    EvidenceFrame,
    SpatialZoneScope,
    TimeWindowScope,
)
from kgtracevis.schema.unified_knowledge import EntitySelector, ZoneScopeSelector


@dataclass
class GroundedFact:
    predicate_id: str
    subject_id: str | None
    scope_id: str | None
    dependency_group: str | None
    value: bool | None
    status: str
    measured: bool = False
    obs_ids: list[str] = field(default_factory=list)
    actual_values: list[dict] = field(default_factory=list)
    reference_id: str | None = None
    reason: str = ""
    fact_id: str = ""
    applied_value_binding_ids: list[str] = field(default_factory=list)

    def to_json(self, program: KnowledgeProgram):
        definition = program.observables[self.predicate_id]
        return {
            "fact_id": self.fact_id,
            "predicate_id": self.predicate_id,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "value": self.value,
            "status": self.status,
            "measured": self.measured,
            "dependency_group": self.dependency_group,
            "source_obs_ids": self.obs_ids,
            "actual_values": self.actual_values,
            "applied_value_binding_ids": self.applied_value_binding_ids,
            "reference_id": self.reference_id,
            "reason": self.reason,
            "predicate_check": {
                "feature_id": definition.feature_id,
                "op": definition.op,
                "operand": definition.operand.model_dump(mode="json"),
            },
        }


class Grounding:
    def __init__(self, frame: EvidenceFrame, program: KnowledgeProgram):
        self.frame, self.program = frame, program
        self.subjects = {s.subject_id: s for s in frame.subjects}
        self.scopes = {s.scope_id: s for s in frame.scopes}
        self.procedures = {p.procedure_id: p for p in frame.procedures}
        self.resolved_subjects = {
            identity: self.resolve_subject(identity) for identity in self.subjects
        }
        self.facts: dict[str, list[GroundedFact]] = {}

    def resolve_subject(self, identity: str) -> str | None:
        subject = self.subjects[identity]
        explicit = self.program.bindings.get((subject.external_namespace, subject.external_id))
        if explicit:
            return explicit
        if not subject.external_id:
            return None
        # Only declared aliases, never fuzzy matching or a guessed channel meaning.
        aliases = [
            e.entity_id
            for e in self.program.entities.values()
            if subject.external_id.casefold() in {a.casefold() for a in e.aliases}
        ]
        return aliases[0] if len(aliases) == 1 else None

    def ground(self, predicate_ids: set[str], *, individual_observations=False):
        for predicate in sorted(predicate_ids):
            definition = self.program.observables[predicate]
            rows = {}
            for observation in self.frame.observations:
                if observation.feature_id != definition.feature_id:
                    continue
                if not self._subject_matches(definition, observation.subject_id):
                    continue
                if not self._scope_matches(definition, observation.scope_id):
                    continue
                comparison_value, bindings = self._comparison_value(observation)
                value, status, measured, reason = self._compare(
                    definition, observation, comparison_value
                )
                key = (
                    observation.subject_id,
                    observation.scope_id,
                    observation.dependency_group,
                    value,
                    status,
                )
                if individual_observations:
                    key += (observation.obs_id,)
                if key not in rows:
                    rows[key] = GroundedFact(
                        predicate,
                        observation.subject_id,
                        observation.scope_id,
                        observation.dependency_group,
                        value,
                        status,
                        measured,
                        reference_id=observation.reference_id,
                        reason=reason,
                    )
                fact = rows[key]
                fact.applied_value_binding_ids = sorted(
                    set(fact.applied_value_binding_ids) | set(bindings)
                )
                fact.obs_ids.append(observation.obs_id)
                if observation.value is not None:
                    encoded = observation.value.model_dump(mode="json")
                    if encoded not in fact.actual_values:
                        fact.actual_values.append(encoded)
            values = sorted(
                rows.values(),
                key=lambda f: (
                    f.subject_id or "",
                    f.scope_id or "",
                    f.dependency_group or "",
                    f.status,
                    f.obs_ids[0] if individual_observations else "",
                ),
            )
            if not values:
                values = [
                    GroundedFact(
                        predicate,
                        None,
                        None,
                        None,
                        None,
                        "unobserved",
                        reason="no_bound_observation",
                    )
                ]
            for fact in values:
                fact.obs_ids.sort()
                # Canonical sorting keeps trace IDs and values stable under input reorder.
                fact.actual_values.sort(key=repr)
                fact.fact_id = "fact:" + predicate
                if individual_observations and fact.obs_ids:
                    fact.fact_id += "@" + fact.obs_ids[0]
                elif len(values) > 1:
                    fact.fact_id += (
                        f"@{fact.subject_id}@{fact.scope_id}@{fact.dependency_group}@{fact.status}"
                    )
            self.facts[predicate] = values
        return self.facts

    def _subject_matches(self, definition, subject_id):
        selector = definition.subject_selector
        if isinstance(selector, EntitySelector):
            return self.resolved_subjects[subject_id] == selector.entity_id
        return subject_id in self.frame.task.focus_subject_ids

    def _scope_matches(self, definition, scope_id):
        selector = definition.scope_selector
        if isinstance(selector, ZoneScopeSelector):
            scope = self.scopes[scope_id]
            return (
                isinstance(scope, SpatialZoneScope)
                and scope.parent_scope_id == self.frame.task.scope_id
                and scope.zone == selector.zone
            )
        return scope_id == self.frame.task.scope_id

    def _comparison_value(self, observation):
        value = observation.value
        if value is None or value.kind not in {"category", "candidate_set"}:
            return value, []
        procedure = self.procedures[observation.procedure_id]
        mappings = dict(self.program.value_bindings.get((observation.feature_id, None), {}))
        if procedure.model_id is not None:
            mappings.update(
                self.program.value_bindings.get((observation.feature_id, procedure.model_id), {})
            )
        values = [value.category] if value.kind == "category" else value.items
        applied = [mappings[v].binding_id for v in values if v in mappings]
        mapped = [mappings[v].canonical_value if v in mappings else v for v in values]
        return value.model_copy(
            update={"category": mapped[0]}
            if value.kind == "category"
            else {"items": list(dict.fromkeys(mapped))}
        ), applied

    def _compare(self, definition, observation, value):
        if observation.status != "observed":
            return None, observation.status, False, "observation_not_available"
        feature = self.program.features[definition.feature_id]
        if value.kind != feature.value_kind or getattr(value, "unit", None) != feature.unit:
            return None, "invalid", False, "feature_type_or_unit_mismatch"
        requires_reference = (
            feature.requires_reference or definition.reference_requirement is not None
        )
        if requires_reference and (
            not self.frame.task.reference_id
            or observation.reference_id != self.frame.task.reference_id
        ):
            return None, "invalid", False, "incompatible_normal_reference"
        operand, op = definition.operand, definition.op
        if op == "gte":
            result = value.number >= operand.number
        elif op == "lte":
            result = value.number <= operand.number
        elif op == "abs_gte":
            result = abs(value.number) >= operand.number
        elif op == "between":
            result = operand.lower <= value.number <= operand.upper
        elif op in {"eq", "bool_eq"}:
            attribute = {"number": "number", "boolean": "boolean", "category": "category"}[
                value.kind
            ]
            result = getattr(value, attribute) == getattr(operand, attribute)
        elif op == "in":
            result = value.category in operand.items
        elif op == "intersects":
            result = bool(set(value.items) & set(operand.items))
            if not result and not value.exhaustive:
                return None, "unobserved", True, "open_candidate_set_does_not_refute"
        elif op == "candidate_contains":
            assert isinstance(value, CandidateSetValue)
            result = operand.category in value.items
            if not result and not value.exhaustive:
                return None, "unobserved", True, "open_candidate_set_does_not_refute"
        else:
            raise ValueError(f"unregistered comparison: {op}")
        return bool(result), "matched" if result else "violated", True, ""

    def valid(self, predicate_id: str) -> list[GroundedFact]:
        return [f for f in self.facts[predicate_id] if f.value is not None]

    def joint_scope_valid(self, branch, *, selected=None) -> bool:
        definitions = {p.definition_id: p for p in self.program.patterns.values()}
        for definition_id, predicates in branch.joins:
            definition = definitions[definition_id]
            facts = [
                f for p in predicates for f in (self.valid(p) if selected is None else selected[p])
            ]
            if not facts:
                continue
            if definition.scope_join == "same_subject_same_scope":
                if len({(f.subject_id, f.scope_id) for f in facts}) != 1:
                    return False
            elif definition.scope_join == "same_event_same_window":
                scopes = [self.scopes[f.scope_id] for f in facts]
                if not all(isinstance(s, TimeWindowScope) for s in scopes):
                    return False
                if len({f.scope_id for f in facts}) != 1:
                    return False
                if scopes[0].context_subject_id != self.frame.task.context_subject_id:
                    return False
            else:
                scopes = [self.scopes[f.scope_id] for f in facts]
                if not all(isinstance(s, SpatialZoneScope) for s in scopes):
                    return False
                if (
                    len({(f.subject_id, self.scopes[f.scope_id].parent_scope_id) for f in facts})
                    != 1
                ):
                    return False
        return True
