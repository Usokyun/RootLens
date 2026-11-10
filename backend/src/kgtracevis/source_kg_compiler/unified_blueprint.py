"""Small LLM authoring language lowered deterministically into the common IR.

Names and domain assertions come from the LLM; feature definitions, IDs, source
locators, rule direction and prerequisite wiring come from the compiler.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from kgtracevis.schema.unified_evidence import Identifier, ObservationValue, UnifiedModel
from kgtracevis.schema.unified_knowledge import KnowledgePackage


class AssertionDraft(UnifiedModel):
    text: Identifier
    origin: Literal["source_explicit", "llm_proposed", "declared_demo_heuristic"]
    source_unit_id: Identifier
    parameter_origin: Literal[
        "source_explicit", "normal_reference_estimate", "declared_demo_heuristic"
    ] = "source_explicit"


class ConditionDraft(UnifiedModel):
    label: Identifier
    feature_id: Identifier
    op: Literal["gte", "lte", "abs_gte", "eq", "in", "intersects", "candidate_contains", "bool_eq"]
    operand: ObservationValue
    subject_external_id: Identifier = "$focus"
    zone: Identifier | None = None
    assertion: AssertionDraft


class CauseDraft(UnifiedModel):
    candidate_key: Identifier
    label: Identifier
    mechanism_key: Identifier
    mechanism_label: Identifier
    mode: Literal["possible", "expected", "necessary"] = "expected"
    assertion: AssertionDraft


class SignatureDraft(UnifiedModel):
    signature_key: Identifier
    label: Identifier
    context_external_id: Identifier
    logic: Literal["all", "any", "at_least"] = "all"
    at_least_count: int | None = Field(default=None, ge=1)
    conditions: list[ConditionDraft] = Field(min_length=1)
    causes: list[CauseDraft] = Field(min_length=1)
    assertion: AssertionDraft


class UnsupportedDraft(UnifiedModel):
    claim: str
    source_unit_ids: list[str] = Field(min_length=1)
    missing_features: list[str] = Field(min_length=1)


class EquivalenceAssertionDraft(AssertionDraft):
    """Vocabulary equivalence must be stated in the source, not hypothesized."""

    origin: Literal["source_explicit"] = "source_explicit"
    parameter_origin: Literal["source_explicit"] = "source_explicit"


class ValueBindingDraft(UnifiedModel):
    binding_key: Identifier
    relation: Literal["equivalent"] = "equivalent"
    feature_id: Identifier
    external_value: Identifier
    canonical_value: Identifier
    procedure_model_id: Identifier | None = None
    assertion: EquivalenceAssertionDraft


class KnowledgeBlueprint(UnifiedModel):
    title: Identifier
    signatures: list[SignatureDraft] = Field(min_length=1, max_length=16)
    unsupported_claims: list[UnsupportedDraft] = Field(default_factory=list)
    value_bindings: list[ValueBindingDraft] = Field(default_factory=list)


def lower_blueprint(blueprint: KnowledgeBlueprint, capabilities, units):
    unit_map = {unit.unit_id: unit for unit in units}
    entities, bindings, sources, predicates, patterns, hypotheses, mechanisms = (
        [],
        [],
        [],
        [],
        [],
        {},
        {},
    )
    effects, expectations = {}, {}
    normalizations = []
    identity_map = {}
    candidate_keys = {
        (s.context_external_id, c.candidate_key) for s in blueprint.signatures for c in s.causes
    }
    budget_errors = []
    if len(candidate_keys) > capabilities.max_candidates:
        budget_errors.append(
            f"candidate_count={len(candidate_keys)} > allowed={capabilities.max_candidates}; "
            f"candidate_keys={sorted(candidate_keys)}"
        )
    if len(blueprint.signatures) > capabilities.max_signatures:
        budget_errors.append(
            f"signature_count={len(blueprint.signatures)} > allowed={capabilities.max_signatures}"
        )
    if budget_errors:
        raise ValueError(
            "exceeds capability authoring limits: "
            + "; ".join(budget_errors)
            + "; group source-indistinguishable detailed candidates; never drop source facts"
        )
    conflicts = []
    for signature in blueprint.signatures:
        if len(signature.causes) > capabilities.max_hypotheses_per_signature:
            raise ValueError(
                f"signature={signature.signature_key}: hypotheses={len(signature.causes)} "
                f"> allowed={capabilities.max_hypotheses_per_signature}; "
                "group indistinguishable hypotheses, or compare classes via separate signatures"
            )
        modes = {}
        for cause in signature.causes:
            modes.setdefault(cause.mechanism_key, set()).add(cause.mode)
        for key, values in modes.items():
            if len(values) > 1:
                conflicts.append(
                    f"signature={signature.signature_key}, mechanism={key}, modes={sorted(values)}"
                )
    if conflicts:
        raise ValueError(
            "One shared mechanism/signature has ONE expectation mode; harmonize all groups: "
            + "; ".join(conflicts)
        )
    for namespace, identifiers, kind in (
        (capabilities.context_namespace, capabilities.context_external_ids, "Object"),
        (capabilities.variable_namespace, capabilities.variable_external_ids, "Variable"),
    ):
        for external in identifiers:
            identity = f"entity:{namespace}:{external}"
            identity_map[(namespace, external)] = identity
            entities.append({"entity_id": identity, "label": external, "kind": kind})
            bindings.append(
                {"namespace": namespace, "external_id": external, "target_id": identity}
            )

    def assertion(draft, identity):
        if draft.source_unit_id not in unit_map:
            raise ValueError(f"unknown source unit: {draft.source_unit_id}")
        unit = unit_map[draft.source_unit_id]
        sources.append(
            {
                "assertion_id": identity,
                "origin": draft.origin,
                "text": draft.text,
                "parameter_origin": draft.parameter_origin,
                "source_id": unit.source_id,
                "source_unit_id": unit.unit_id,
                "locator": json.dumps(unit.source_span, sort_keys=True),
            }
        )
        return [identity]

    def predicate(row):
        # Identical conditions reused across signatures are one atom, not new
        # votes merely because the model wrote them twice.
        fields = (
            "feature_id",
            "op",
            "operand",
            "subject_selector",
            "scope_selector",
            "reference_requirement",
        )
        for previous in predicates:
            if all(previous.get(key) == row.get(key) for key in fields):
                previous["source_assertion_ids"] += row["source_assertion_ids"]
                return previous["predicate_id"]
        predicates.append(row)
        return row["predicate_id"]

    value_bindings = [
        {
            "binding_id": "binding:" + binding.binding_key,
            "feature_id": binding.feature_id,
            "external_value": binding.external_value,
            "canonical_value": binding.canonical_value,
            "procedure_model_id": binding.procedure_model_id,
            "source_assertion_ids": assertion(binding.assertion, f"source:value-binding:{i}"),
        }
        for i, binding in enumerate(blueprint.value_bindings)
    ]

    seen = set()
    for si, signature in enumerate(blueprint.signatures):
        if signature.signature_key in seen:
            raise ValueError("duplicate signature_key")
        seen.add(signature.signature_key)
        context = identity_map.get((capabilities.context_namespace, signature.context_external_id))
        if not context:
            raise ValueError("signature context is not an adapter subject")
        stem = "signature:" + signature.signature_key
        signature_sources = assertion(signature.assertion, f"source:signature:{si}")
        gate = stem + ":anomaly"
        gate = predicate(
            {
                "predicate_id": gate,
                "label": "Explicit anomaly prerequisite",
                "feature_id": "detection.anomaly_present",
                "op": "bool_eq",
                "operand": {"kind": "boolean", "boolean": True},
                "subject_selector": {"kind": "focus"},
                "scope_selector": {"kind": "spatial_zone", "zone": "all_valid"}
                if capabilities.zones
                else {"kind": "task_scope"},
                "source_assertion_ids": signature_sources,
            }
        )
        refs = []
        for ci, condition in enumerate(signature.conditions):
            identity = stem + f":condition:{ci}"
            selector = {"kind": "focus"}
            if condition.subject_external_id != "$focus":
                bound = identity_map.get(
                    (capabilities.variable_namespace, condition.subject_external_id)
                )
                if not bound:
                    raise ValueError("condition variable is not an adapter subject")
                selector = {"kind": "bound_entity", "entity_id": bound}
            feature = next(
                (f for f in capabilities.features if f.feature_id == condition.feature_id), None
            )
            if not feature:
                raise ValueError(f"unsupported feature: {condition.feature_id}")
            op = condition.op
            # Authoring shorthand: membership of a single categorical model
            # output is equality, not membership of an open candidate set.
            # The canonical IR remains strictly typed and records the lowering.
            if (
                feature.value_kind == "category"
                and op == "candidate_contains"
                and condition.operand.kind == "category"
            ):
                op = "eq"
                normalizations.append(
                    {
                        "kind": "scalar_membership_to_equality",
                        "signature_key": signature.signature_key,
                        "condition_index": ci,
                        "feature_id": condition.feature_id,
                    }
                )
            identity = predicate(
                {
                    "predicate_id": identity,
                    "label": condition.label,
                    "feature_id": condition.feature_id,
                    "op": op,
                    "operand": condition.operand.model_dump(),
                    "subject_selector": selector,
                    "scope_selector": {
                        "kind": "spatial_zone",
                        "zone": condition.zone or "all_valid",
                    }
                    if capabilities.zones
                    else {"kind": "task_scope"},
                    "reference_requirement": "same_as_task" if feature.requires_reference else None,
                    "source_assertion_ids": assertion(
                        condition.assertion, f"source:condition:{si}:{ci}"
                    ),
                }
            )
            if identity not in refs:
                refs.append(identity)
        if signature.logic == "at_least":
            body = {"at_least": {"count": signature.at_least_count, "of": refs}}
        else:
            body = {signature.logic: refs}
        patterns.append(
            {
                "definition_id": stem + ":definition",
                "pattern_id": stem,
                "label": signature.label,
                "semantics": "iff",
                "body": {"all": [gate, body]},
                "scope_join": "same_subject_parent_scope"
                if capabilities.zones
                else "same_event_same_window"
                if capabilities.variable_namespace
                else "same_subject_same_scope",
                "source_assertion_ids": signature_sources,
            }
        )
        for hi, cause in enumerate(signature.causes):
            hypothesis_id = f"hypothesis:{signature.context_external_id}:{cause.candidate_key}"
            mechanism_id = f"mechanism:{signature.context_external_id}:{cause.mechanism_key}"
            hypothesis = {
                "hypothesis_id": hypothesis_id,
                "label": cause.label,
                "target_role": capabilities.target_role,
                "applies_to_class_id": context,
                "assumption_cost": 1.0,
            }
            mechanism = {"mechanism_id": mechanism_id, "label": cause.mechanism_label}
            # Identity is the declared key and context. Display paraphrases are
            # not new candidates; all source-specific wording remains sourced.
            hypotheses.setdefault(hypothesis_id, hypothesis)
            mechanisms.setdefault(mechanism_id, mechanism)
            source_ids = assertion(cause.assertion, f"source:cause:{si}:{hi}")
            effect_id = "effect:" + hypothesis_id + ":" + mechanism_id
            # Repeated shared rules retain every actual source assertion.
            if effect_id in effects:
                effects[effect_id]["source_assertion_ids"] += source_ids
            else:
                effects[effect_id] = {
                    "rule_id": effect_id,
                    "from_id": hypothesis_id,
                    "to_id": mechanism_id,
                    "source_assertion_ids": list(source_ids),
                }
            expect_id = "expectation:" + mechanism_id + ":" + stem
            row = {
                "rule_id": expect_id,
                "from_id": mechanism_id,
                "pattern_id": stem,
                "mode": cause.mode,
                "source_assertion_ids": list(source_ids),
            }
            if expect_id in expectations:
                if expectations[expect_id]["mode"] != cause.mode:
                    raise ValueError("shared mechanism has conflicting expectation modes")
                expectations[expect_id]["source_assertion_ids"] += source_ids
            else:
                expectations[expect_id] = row
    return {
        "knowledge": KnowledgePackage.model_validate(
            {
                "graph_id": "source-compiled",
                "title": blueprint.title,
                "entities": entities,
                "subject_bindings": bindings,
                "value_bindings": value_bindings,
                "feature_registry": [f.model_dump() for f in capabilities.features],
                "observable_definitions": predicates,
                "pattern_definitions": patterns,
                "hypotheses": list(hypotheses.values()),
                "mechanisms": list(mechanisms.values()),
                "effect_rules": list(effects.values()),
                "expectation_rules": list(expectations.values()),
                "source_assertions": sources,
            }
        ).model_dump(mode="json"),
        "unsupported_claims": [c.model_dump() for c in blueprint.unsupported_claims],
        "normalizations": normalizations,
    }
