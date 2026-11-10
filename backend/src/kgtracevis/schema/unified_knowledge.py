"""Executable knowledge IR shared by every industrial observation adapter."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kgtracevis.schema.unified_evidence import (
    CategoryValue,
    FiniteNumber,
    Identifier,
    NumberValue,
    ObservationValue,
    UnifiedModel,
    indexed,
)


class Sourced(UnifiedModel):
    source_assertion_ids: list[Identifier] = Field(min_length=1)


class Entity(UnifiedModel):
    entity_id: Identifier
    label: Identifier
    kind: Identifier
    aliases: list[Identifier] = Field(default_factory=list)


class Relation(Sourced):
    relation_id: Identifier
    head: Identifier
    relation: Identifier
    tail: Identifier


class SubjectBinding(UnifiedModel):
    namespace: Identifier
    external_id: Identifier
    target_id: Identifier


class FeatureDefinition(UnifiedModel):
    feature_id: Identifier
    value_kind: Literal["number", "boolean", "category", "candidate_set", "interval", "array_ref"]
    unit: Identifier | None = None
    definition: Identifier
    requires_reference: bool = False

    @model_validator(mode="after")
    def unit_contract(self):
        if self.value_kind in {"number", "interval"} and not self.unit:
            raise ValueError("numeric feature needs an explicit unit")
        if self.value_kind not in {"number", "interval"} and self.unit is not None:
            raise ValueError("non-numeric features do not carry a numeric unit")
        return self


class FocusSelector(UnifiedModel):
    kind: Literal["focus"]


class EntitySelector(UnifiedModel):
    kind: Literal["bound_entity"]
    entity_id: Identifier


SubjectSelector = Annotated[FocusSelector | EntitySelector, Field(discriminator="kind")]


class TaskScopeSelector(UnifiedModel):
    kind: Literal["task_scope"]


class ZoneScopeSelector(UnifiedModel):
    kind: Literal["wafer_zone", "spatial_zone"]
    zone: Identifier
    parent: Literal["task_scope"] = "task_scope"


ScopeSelector = Annotated[TaskScopeSelector | ZoneScopeSelector, Field(discriminator="kind")]


class ObservableDefinition(Sourced):
    predicate_id: Identifier
    label: Identifier
    feature_id: Identifier
    op: Literal["gte", "lte", "abs_gte", "eq", "in", "intersects", "candidate_contains", "bool_eq"]
    operand: ObservationValue
    subject_selector: SubjectSelector
    scope_selector: ScopeSelector
    reference_requirement: Literal["same_as_task"] | None = None


class AllExpression(UnifiedModel):
    all: list[Expression] = Field(min_length=1)


class AnyExpression(UnifiedModel):
    any: list[Expression] = Field(min_length=1)


class AtLeastBody(UnifiedModel):
    count: Annotated[int, Field(strict=True, ge=1)]
    of: list[Expression] = Field(min_length=1)

    @model_validator(mode="after")
    def possible_count(self):
        if self.count > len(self.of):
            raise ValueError("at_least count exceeds its operands")
        return self


class AtLeastExpression(UnifiedModel):
    at_least: AtLeastBody


Expression = Identifier | AllExpression | AnyExpression | AtLeastExpression
AllExpression.model_rebuild()
AnyExpression.model_rebuild()
AtLeastBody.model_rebuild()
AtLeastExpression.model_rebuild()


def expression_refs(expr: Expression) -> set[str]:
    """Read declarative expression references without evaluating source code."""
    if isinstance(expr, str):
        return {expr}
    values = (
        expr.all
        if isinstance(expr, AllExpression)
        else (expr.any if isinstance(expr, AnyExpression) else expr.at_least.of)
    )
    return set().union(*(expression_refs(value) for value in values))


class PatternDefinition(Sourced):
    definition_id: Identifier
    pattern_id: Identifier
    label: Identifier
    semantics: Literal["iff"] = "iff"
    body: AllExpression | AnyExpression | AtLeastExpression
    scope_join: Literal[
        "same_subject_same_scope",
        "same_event_same_window",
        "same_wafer_parent_scope",
        "same_subject_parent_scope",
    ]


class Mechanism(UnifiedModel):
    mechanism_id: Identifier
    label: Identifier


class Hypothesis(UnifiedModel):
    hypothesis_id: Identifier
    label: Identifier
    target_role: Identifier
    applies_to_class_id: Identifier
    assumption_cost: Annotated[FiniteNumber, Field(ge=0)] = 1.0


class EffectRule(Sourced):
    rule_id: Identifier
    from_id: Identifier
    to_id: Identifier


class ExpectationRule(Sourced):
    rule_id: Identifier
    from_id: Identifier
    pattern_id: Identifier
    mode: Literal["possible", "expected", "necessary"]


class SourceAssertion(UnifiedModel):
    assertion_id: Identifier
    origin: Literal[
        "synthetic_design_assertion",
        "source_explicit",
        "llm_proposed",
        "normal_reference_estimate",
        "declared_demo_heuristic",
    ]
    text: Identifier
    parameter_origin: Literal[
        "source_explicit",
        "normal_reference_estimate",
        "declared_demo_heuristic",
    ] = "source_explicit"
    source_id: Identifier | None = None
    source_unit_id: Identifier | None = None
    locator: str | None = None

    @model_validator(mode="after")
    def source_identity(self):
        if self.origin == "source_explicit" and not (self.source_id and self.source_unit_id):
            raise ValueError("source-explicit assertions require actual source and unit IDs")
        return self


class ExecutionPolicy(UnifiedModel):
    conflict_weight: Annotated[FiniteNumber, Field(ge=0)] = 2.0
    assumption_weight: Annotated[FiniteNumber, Field(ge=0)] = 0.25
    score_mapping: Literal["negative_explanation_cost"] = "negative_explanation_cost"
    candidate_recall: Literal["applicable_class_and_target_role_and_observed_feature_footprint"] = (
        "applicable_class_and_target_role_and_observed_feature_footprint"
    )
    evaluation_universe: Literal["union_of_context_candidate_atomic_predicates"] = (
        "union_of_context_candidate_atomic_predicates"
    )
    positive_coverage: Literal["complete_joint_pattern_only"] = "complete_joint_pattern_only"
    group_aggregation: Literal["equal_budget_normalized_mean"] = "equal_budget_normalized_mean"
    primitive_comparison: Literal["discrete_boolean_v0"] = "discrete_boolean_v0"
    missing: Literal["unknown_not_negative"] = "unknown_not_negative"
    tie_epsilon: Annotated[FiniteNumber, Field(gt=0, le=0.001)] = 1e-9


class KnowledgePackage(UnifiedModel):
    schema_version: Literal["rootlens-knowledge-package.v2"] = "rootlens-knowledge-package.v2"
    example_kind: Literal["synthetic_design"] | None = None
    graph_id: Identifier
    semantics_version: Literal["conjunctive-explanation-v0"] = "conjunctive-explanation-v0"
    title: str = "Unified executable knowledge"
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    subject_bindings: list[SubjectBinding] = Field(default_factory=list)
    feature_registry: list[FeatureDefinition]
    observable_definitions: list[ObservableDefinition]
    pattern_definitions: list[PatternDefinition]
    mechanisms: list[Mechanism] = Field(default_factory=list)
    hypotheses: list[Hypothesis]
    effect_rules: list[EffectRule] = Field(default_factory=list)
    expectation_rules: list[ExpectationRule]
    execution_policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    source_assertions: list[SourceAssertion]

    @model_validator(mode="after")
    def executable_integrity(self):
        entities = indexed(self.entities, "entity_id")
        features = indexed(self.feature_registry, "feature_id")
        predicates = indexed(self.observable_definitions, "predicate_id")
        patterns = indexed(self.pattern_definitions, "pattern_id")
        mechanisms = indexed(self.mechanisms, "mechanism_id")
        hypotheses = indexed(self.hypotheses, "hypothesis_id")
        sources = indexed(self.source_assertions, "assertion_id")
        indexed(self.relations, "relation_id")
        all_ids = list(entities) + list(predicates) + list(patterns) + list(mechanisms)
        all_ids += list(hypotheses) + list(sources)
        all_ids += [r.definition_id for r in self.pattern_definitions]
        all_ids += [r.rule_id for r in self.effect_rules + self.expectation_rules]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("knowledge identities collide across node/rule types")
        active_ids = set(hypotheses) | set(mechanisms)
        for row in self.relations:
            if row.head not in entities or row.tail not in entities:
                raise ValueError(f"unknown structural relation endpoint: {row.relation_id}")
        for binding in self.subject_bindings:
            if binding.target_id not in entities:
                raise ValueError(f"unknown subject binding target: {binding.target_id}")
        keys = [(b.namespace, b.external_id) for b in self.subject_bindings]
        if len(keys) != len(set(keys)):
            raise ValueError("ambiguous external subject binding")
        for observable in self.observable_definitions:
            if observable.feature_id not in features:
                raise ValueError(f"unregistered feature: {observable.feature_id}")
            feature = features[observable.feature_id]
            if isinstance(observable.subject_selector, EntitySelector):
                if observable.subject_selector.entity_id not in entities:
                    raise ValueError("unknown observable subject entity")
            numeric = observable.op in {"gte", "lte", "abs_gte"}
            if numeric and (
                feature.value_kind != "number" or not isinstance(observable.operand, NumberValue)
            ):
                raise ValueError("numeric comparison requires a numeric feature and operand")
            if numeric and observable.operand.unit != feature.unit:
                raise ValueError("observable and feature units differ")
            if observable.op == "candidate_contains" and (
                feature.value_kind != "candidate_set"
                or not isinstance(observable.operand, CategoryValue)
            ):
                raise ValueError("candidate_contains requires candidate_set and category")
            if observable.op == "bool_eq" and (
                feature.value_kind != "boolean" or observable.operand.kind != "boolean"
            ):
                raise ValueError("bool_eq requires boolean feature and operand")
            if observable.op == "eq" and observable.operand.kind != feature.value_kind:
                raise ValueError("eq operand and feature types differ")
            if observable.op == "eq" and feature.value_kind not in {
                "number",
                "boolean",
                "category",
            }:
                raise ValueError("eq is a scalar comparison")
            if (
                observable.op == "eq"
                and feature.value_kind == "number"
                and observable.operand.unit != feature.unit
            ):
                raise ValueError("observable and feature units differ")
            if observable.op in {"in", "intersects"} and observable.operand.kind != "candidate_set":
                raise ValueError("set comparison requires a candidate_set operand")
            if observable.op == "in" and feature.value_kind != "category":
                raise ValueError("in requires a category feature")
            if observable.op == "intersects" and feature.value_kind != "candidate_set":
                raise ValueError("intersects requires a candidate_set feature")
        for pattern in self.pattern_definitions:
            unknown = expression_refs(pattern.body) - (set(predicates) | set(patterns))
            if unknown:
                raise ValueError(f"unknown pattern inputs: {sorted(unknown)}")
        for hypothesis in self.hypotheses:
            if hypothesis.applies_to_class_id not in entities:
                raise ValueError("unknown hypothesis applicability class")
        for rule in self.effect_rules:
            if rule.from_id not in active_ids or rule.to_id not in mechanisms:
                raise ValueError("effect rules may derive mechanism states, not new root answers")
        for rule in self.expectation_rules:
            if rule.from_id not in active_ids or rule.pattern_id not in patterns:
                raise ValueError("unknown expectation endpoint")
        for row in [
            *self.relations,
            *self.observable_definitions,
            *self.pattern_definitions,
            *self.effect_rules,
            *self.expectation_rules,
        ]:
            if not set(row.source_assertion_ids) <= sources.keys():
                raise ValueError("unknown source assertion reference")
        return self
