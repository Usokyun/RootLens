"""Executable knowledge IR shared by every industrial observation adapter."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kgtracevis.schema.unified_evidence import (
    CategoryValue,
    FiniteNumber,
    Identifier,
    IntervalValue,
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


class ValueBinding(Sourced):
    binding_id: Identifier
    feature_id: Identifier
    external_value: Identifier
    canonical_value: Identifier
    procedure_model_id: Identifier | None = None


class FeatureDefinition(UnifiedModel):
    feature_id: Identifier
    value_kind: Literal["number", "boolean", "category", "candidate_set", "interval", "array_ref"]
    unit: Identifier | None = None
    definition: Identifier
    requires_reference: bool = False
    allowed_values: list[Identifier] | None = None
    semantic_role: Literal["diagnostic", "presence_gate", "context"] | None = None

    @model_validator(mode="after")
    def unit_contract(self):
        if self.value_kind in {"number", "interval"} and not self.unit:
            raise ValueError("numeric feature needs an explicit unit")
        if self.value_kind not in {"number", "interval"} and self.unit is not None:
            raise ValueError("non-numeric features do not carry a numeric unit")
        if self.allowed_values is not None:
            if self.value_kind not in {"category", "candidate_set"}:
                raise ValueError("allowed_values requires a categorical feature")
            if not self.allowed_values or len(set(self.allowed_values)) != len(self.allowed_values):
                raise ValueError("allowed_values must be a nonempty unique finite vocabulary")
        return self

    def validate_category_values(self, values: list[str], *, subject: str):
        if self.allowed_values is not None:
            unknown = sorted(set(values) - set(self.allowed_values))
            if unknown:
                raise ValueError(
                    f"{subject}: feature={self.feature_id}, unknown category values={unknown}; "
                    f"allowed_values={self.allowed_values}"
                )


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


ParameterOrigin = Literal["source_explicit", "normal_reference_estimate", "declared_demo_heuristic"]
PositiveWidth = Annotated[FiniteNumber, Field(gt=0)]
NonnegativeWidth = Annotated[FiniteNumber, Field(ge=0)]


class NumericGrade(Sourced):
    direction: Literal["lower", "higher", "interval", "absolute_higher"]
    pivot: FiniteNumber | None = Field(default=None, exclude_if=lambda value: value is None)
    lower: FiniteNumber | None = Field(default=None, exclude_if=lambda value: value is None)
    upper: FiniteNumber | None = Field(default=None, exclude_if=lambda value: value is None)
    support_width: PositiveWidth
    conflict_width: PositiveWidth
    neutral_support: NonnegativeWidth = 0.0
    neutral_conflict: NonnegativeWidth = 0.0
    unit: Identifier
    basis: ParameterOrigin

    @model_validator(mode="after")
    def ordered_parameters(self):
        if self.direction == "interval":
            if (
                self.pivot is not None
                or self.lower is None
                or self.upper is None
                or self.lower >= self.upper
            ):
                raise ValueError("interval grade needs lower < upper and no pivot")
        elif self.pivot is None or self.lower is not None or self.upper is not None:
            raise ValueError("directional grade needs one pivot and no interval bounds")
        elif self.direction == "absolute_higher" and self.pivot < 0:
            raise ValueError("absolute grade needs a nonnegative pivot")
        if len(set(self.source_assertion_ids)) != len(self.source_assertion_ids):
            raise ValueError("grade source assertions must be unique")
        return self

    def validate_projection(self, observable):
        op = {"lower": "lte", "higher": "gte", "interval": "between", "absolute_higher": "abs_gte"}
        operand = observable.operand
        if (
            observable.op != op[self.direction]
            or getattr(operand, "unit", None) != self.unit
            or (
                (getattr(operand, "lower", None), getattr(operand, "upper", None))
                != (self.lower, self.upper)
                if self.direction == "interval"
                else getattr(operand, "number", None) != self.pivot
            )
        ):
            raise ValueError(
                f"grade must project to the same typed comparison: {observable.predicate_id}"
            )


class ObservableDefinition(Sourced):
    predicate_id: Identifier
    label: Identifier
    feature_id: Identifier
    op: Literal[
        "gte",
        "lte",
        "abs_gte",
        "between",
        "eq",
        "in",
        "intersects",
        "candidate_contains",
        "bool_eq",
    ]
    operand: ObservationValue
    subject_selector: SubjectSelector
    scope_selector: ScopeSelector
    reference_requirement: Literal["same_as_task"] | None = None
    grade: NumericGrade | None = Field(default=None, exclude_if=lambda value: value is None)


class GradedSlot(UnifiedModel):
    slot_id: Identifier
    weight: PositiveWidth = 1.0
    predicate_ids: list[Identifier] = Field(min_length=1)


class GradedGroup(UnifiedModel):
    group_id: Identifier
    weight: PositiveWidth = 1.0
    slots: list[GradedSlot] = Field(min_length=1)


class GradedPolicy(UnifiedModel):
    groups: list[GradedGroup] = Field(min_length=1)
    anchor_predicate_ids: list[Identifier] = Field(min_length=1)


def measurement_selector(observable: ObservableDefinition, feature: FeatureDefinition) -> tuple:
    """Same declaration even when the historical and current zone type names differ."""
    subject, scope = observable.subject_selector, observable.scope_selector
    return (
        feature.feature_id,
        subject.kind,
        getattr(subject, "entity_id", None),
        getattr(scope, "zone", None),
        feature.requires_reference or observable.reference_requirement is not None,
    )


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
        identities = [x if isinstance(x, str) else x.model_dump_json() for x in self.of]
        if len(identities) != len(set(identities)):
            raise ValueError("at_least cannot count duplicate operands as separate conditions")
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
    parameter_origin: ParameterOrigin = "source_explicit"
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
    value_bindings: list[ValueBinding] = Field(default_factory=list)
    feature_registry: list[FeatureDefinition]
    observable_definitions: list[ObservableDefinition]
    pattern_definitions: list[PatternDefinition]
    mechanisms: list[Mechanism] = Field(default_factory=list)
    hypotheses: list[Hypothesis]
    effect_rules: list[EffectRule] = Field(default_factory=list)
    expectation_rules: list[ExpectationRule]
    execution_policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    graded_policy: GradedPolicy | None = Field(default=None, exclude_if=lambda value: value is None)
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
        all_ids += [r.binding_id for r in self.value_bindings]
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
        value_keys = [
            (b.feature_id, b.procedure_model_id, b.external_value) for b in self.value_bindings
        ]
        if len(value_keys) != len(set(value_keys)):
            raise ValueError("ambiguous external feature-value binding")
        for binding in self.value_bindings:
            if binding.feature_id not in features or features[
                binding.feature_id
            ].value_kind not in {"category", "candidate_set"}:
                raise ValueError("value bindings require a registered categorical feature")
            features[binding.feature_id].validate_category_values(
                [binding.canonical_value], subject=f"value binding {binding.binding_id}"
            )
            for other in self.value_bindings:
                if (
                    binding.feature_id == other.feature_id
                    and binding.external_value == other.external_value
                    and None in {binding.procedure_model_id, other.procedure_model_id}
                    and binding.canonical_value != other.canonical_value
                ):
                    raise ValueError("overlapping global and model value bindings disagree")
        for observable in self.observable_definitions:
            if observable.feature_id not in features:
                raise ValueError(f"unregistered feature: {observable.feature_id}")
            feature = features[observable.feature_id]
            category_values = (
                [observable.operand.category]
                if observable.operand.kind == "category"
                else observable.operand.items
                if observable.operand.kind == "candidate_set"
                else []
            )
            feature.validate_category_values(
                category_values, subject=f"observable {observable.predicate_id}"
            )
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
            if observable.op == "between" and (
                feature.value_kind != "number"
                or not isinstance(observable.operand, IntervalValue)
                or observable.operand.unit != feature.unit
            ):
                raise ValueError("between requires a numeric feature and interval in its unit")
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
            if observable.grade is not None:
                grade = observable.grade
                grade.validate_projection(observable)
                if not set(grade.source_assertion_ids) <= sources.keys():
                    raise ValueError(f"unknown grade source assertion: {observable.predicate_id}")
                if not any(
                    sources[i].parameter_origin == grade.basis for i in grade.source_assertion_ids
                ):
                    raise ValueError(
                        f"grade basis needs a matching source: {observable.predicate_id}"
                    )
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
            *self.value_bindings,
        ]:
            if not set(row.source_assertion_ids) <= sources.keys():
                raise ValueError("unknown source assertion reference")
        if self.graded_policy is not None:
            self._validate_graded_policy(features, predicates)
        return self

    def _validate_graded_policy(self, features, predicates):
        from kgtracevis.schema.feature_catalog import authoring_feature_role

        policy = self.graded_policy
        indexed(policy.groups, "group_id")
        indexed([slot for group in policy.groups for slot in group.slots], "slot_id")
        slots, seen = {}, set()
        for group in policy.groups:
            for slot in group.slots:
                keys = set()
                for identity in slot.predicate_ids:
                    predicate = predicates.get(identity)
                    if predicate is None:
                        raise ValueError(f"unknown graded predicate: {identity}")
                    feature = features[predicate.feature_id]
                    if authoring_feature_role(feature) != "diagnostic":
                        raise ValueError(
                            f"presence and context cannot spend a graded slot: {identity}"
                        )
                    if identity in seen:
                        raise ValueError(f"graded predicate listed more than once: {identity}")
                    seen.add(identity)
                    keys.add(measurement_selector(predicate, feature))
                if len(keys) != 1:
                    raise ValueError(f"graded slot must describe one measurement: {slot.slot_id}")
                key = keys.pop()
                if key in slots:
                    raise ValueError(
                        f"same measurement cannot spend two slots: {slots[key]}, {slot.slot_id}"
                    )
                slots[key] = slot.slot_id
        anchors = policy.anchor_predicate_ids
        if len(set(anchors)) != len(anchors) or not set(anchors) <= seen:
            raise ValueError("graded anchors must be unique predicates in the scored slots")
