"""Narrow, reversible candidate-local condition authoring on the existing typed KG.

Each operation owns a predicate, anomaly-gated pattern, direct hypothesis
expectation and explicit authoring assertion. The existing gate is borrowed,
never duplicated or removed. No shared mechanism or observation is changed.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import Field

from kgtracevis.adapters.unified_capabilities import (
    process_capabilities,
    spatial_capabilities,
    visual_capabilities,
)
from kgtracevis.schema.unified_evidence import Identifier, ObservationValue, UnifiedModel
from kgtracevis.schema.unified_knowledge import (
    AllExpression,
    KnowledgePackage,
    expression_refs,
)
from kgtracevis.service import working_graph_editor as editor
from kgtracevis.service.working_graphs import working_graph_store

PREFIX = "candidate-condition:"
OPERATORS = {
    "number": ["gte", "lte", "abs_gte", "eq"],
    "boolean": ["bool_eq", "eq"],
    "category": ["eq", "in"],
    "candidate_set": ["candidate_contains", "intersects"],
}
VARIABLE_FEATURES = {
    "statistics.mean_z",
    "statistics.std_z",
    "statistics.slope_z",
    "residual.contribution",
}


class CandidateConditionRequest(UnifiedModel):
    candidate_id: Identifier
    label: Identifier
    feature_id: Identifier
    op: Literal["gte", "lte", "abs_gte", "eq", "in", "intersects", "candidate_contains", "bool_eq"]
    operand: ObservationValue
    subject_entity_id: Identifier | None = None
    zone: Identifier | None = None
    mode: Literal["necessary", "expected", "possible"] = "necessary"
    description: str = Field(default="", max_length=10000)
    source_assertion_ids: list[Identifier] = Field(default_factory=list)


def _capability(dataset):
    factories = {
        "mvtec": visual_capabilities,
        "tep": process_capabilities,
        "wafer": spatial_capabilities,
    }
    if dataset not in factories:
        raise ValueError("当前场景没有可用的候选条件制作目录。")
    return factories[dataset]()


def _subjects(knowledge, capability):
    entities = {e.entity_id: e for e in knowledge.entities}
    return [
        {
            "entity_id": b.target_id,
            "label": entities[b.target_id].label,
            "external_id": b.external_id,
        }
        for b in knowledge.subject_bindings
        if b.namespace == capability.variable_namespace
        and b.external_id in capability.variable_external_ids
    ]


def condition_options(graph_id):
    record = working_graph_store().get(graph_id)
    if record.status != "ready" or record.knowledge is None:
        raise ValueError("候选级条件仅支持已就绪的v2工作图。")
    capability = _capability(record.dataset)
    return {
        "conditions": list_conditions(record.knowledge),
        "features": [
            {
                **feature.model_dump(mode="json"),
                "allowed_operators": OPERATORS[feature.value_kind],
                "subject_kind": "variable" if feature.feature_id in VARIABLE_FEATURES else "focus",
            }
            for feature in capability.features
            if feature.value_kind in OPERATORS
        ],
        "subjects": _subjects(record.knowledge, capability),
        "zones": capability.zones,
    }


def create_condition(graph_id, request: CandidateConditionRequest):
    identity = PREFIX + uuid.uuid4().hex
    record = editor.update_working_knowledge(
        graph_id, lambda knowledge, dataset: add_condition(knowledge, dataset, request, identity)
    )
    return {
        "graph": record.model_dump(mode="json"),
        "conditions": list_conditions(record.knowledge),
    }


def delete_condition(graph_id, condition_id):
    record = editor.update_working_knowledge(
        graph_id, lambda knowledge, _: remove_condition(knowledge, condition_id)
    )
    return {
        "graph": record.model_dump(mode="json"),
        "conditions": list_conditions(record.knowledge),
    }


def add_condition(knowledge, dataset, request, identity):
    capability = _capability(dataset)
    hypotheses = {h.hypothesis_id for h in knowledge.hypotheses}
    if request.candidate_id not in hypotheses:
        raise ValueError("目标候选不属于当前图；不会自动创建候选。")
    feature = next((f for f in capability.features if f.feature_id == request.feature_id), None)
    if feature is None or request.op not in OPERATORS.get(feature.value_kind, []):
        raise ValueError("该特征／算子不在当前可产出的诊断条件目录中。")
    categorical = (
        [request.operand.category]
        if request.operand.kind == "category"
        else request.operand.items
        if request.operand.kind == "candidate_set"
        else []
    )
    feature.validate_category_values(categorical, subject="候选级诊断条件")
    existing = next(
        (f for f in knowledge.feature_registry if f.feature_id == feature.feature_id), None
    )
    if existing and (
        existing.value_kind != feature.value_kind
        or existing.unit != feature.unit
        or existing.requires_reference != feature.requires_reference
    ):
        raise ValueError("此图的同ID特征类型／单位／参考要求与当前目录不同，请先检查定义。")
    if feature.feature_id in VARIABLE_FEATURES:
        valid_subjects = {row["entity_id"] for row in _subjects(knowledge, capability)}
        if request.subject_entity_id not in valid_subjects:
            raise ValueError("请选择此图已绑定的过程通道；未知变量不会自动创建。")
        subject = {"kind": "bound_entity", "entity_id": request.subject_entity_id}
    else:
        if request.subject_entity_id is not None:
            raise ValueError("该特征使用当前对象／ROI范围，不接受过程通道。")
        subject = {"kind": "focus"}
    if capability.zones:
        if request.zone not in capability.zones:
            raise ValueError("请选择目录内的现有晶圆区域。")
        scope = {"kind": "spatial_zone", "zone": request.zone}
    else:
        if request.zone is not None:
            raise ValueError("此场景只支持当前对象／时间窗口范围，不支持额外空间区域。")
        scope = {"kind": "task_scope"}
    if set(request.source_assertion_ids) - {s.assertion_id for s in knowledge.source_assertions}:
        raise ValueError("来源断言不属于当前图；不会制造来源或定位。")
    gate = _anomaly_gate(knowledge, bool(capability.zones))
    data = knowledge.model_dump(mode="json")
    marker = identity + ":source"
    sources = list(dict.fromkeys([marker, *request.source_assertion_ids]))
    data["source_assertions"].append(
        {
            "assertion_id": marker,
            "origin": "declared_demo_heuristic",
            "parameter_origin": "declared_demo_heuristic",
            "text": request.description
            or f"人工候选级诊断条件：{request.label}。参数为作者声明，不是观测事实。",
        }
    )
    if existing is None:
        data["feature_registry"].append(feature.model_dump(mode="json"))
    data["observable_definitions"].append(
        {
            "predicate_id": identity + ":predicate",
            "label": request.label,
            "feature_id": request.feature_id,
            "op": request.op,
            "operand": request.operand.model_dump(mode="json"),
            "subject_selector": subject,
            "scope_selector": scope,
            "reference_requirement": "same_as_task" if feature.requires_reference else None,
            "source_assertion_ids": sources,
        }
    )
    data["pattern_definitions"].append(
        {
            "definition_id": identity + ":definition",
            "pattern_id": identity + ":pattern",
            "label": request.label,
            "body": {"all": [gate.predicate_id, identity + ":predicate"]},
            "scope_join": "same_subject_parent_scope"
            if capability.zones
            else "same_event_same_window"
            if capability.variable_namespace
            else "same_subject_same_scope",
            "source_assertion_ids": sources,
        }
    )
    data["expectation_rules"].append(
        {
            "rule_id": identity + ":expectation",
            "from_id": request.candidate_id,
            "pattern_id": identity + ":pattern",
            "mode": request.mode,
            "source_assertion_ids": sources,
        }
    )
    return KnowledgePackage.model_validate(data)


def _is_gate(predicate, spatial):
    return (
        predicate.feature_id == "detection.anomaly_present"
        and predicate.op in {"bool_eq", "eq"}
        and predicate.operand.kind == "boolean"
        and predicate.operand.boolean is True
        and predicate.subject_selector.kind == "focus"
        and (
            predicate.scope_selector.kind == "spatial_zone"
            and predicate.scope_selector.zone == "all_valid"
            if spatial
            else predicate.scope_selector.kind == "task_scope"
        )
    )


def _anomaly_gate(knowledge, spatial):
    gates = [p for p in knowledge.observable_definitions if _is_gate(p, spatial)]
    if not gates:
        raise ValueError("此图缺少当前范围的显式异常前置条件，请先检查图谱；不会生成观测。")
    return min(gates, key=lambda p: p.predicate_id)


def _bundle(knowledge, identity):
    if not re.fullmatch(PREFIX + r"[0-9a-f]{32}", identity):
        raise ValueError("只能撤销由候选条件向导创建的独立条件。")
    predicates = [
        p for p in knowledge.observable_definitions if p.predicate_id == identity + ":predicate"
    ]
    patterns = [p for p in knowledge.pattern_definitions if p.pattern_id == identity + ":pattern"]
    rules = [r for r in knowledge.expectation_rules if r.rule_id == identity + ":expectation"]
    markers = [s for s in knowledge.source_assertions if s.assertion_id == identity + ":source"]
    if not all(len(rows) == 1 for rows in (predicates, patterns, rules, markers)):
        raise ValueError("该独立条件已不存在或被完整图编辑改写，请检查图包。")
    predicate, pattern, rule, marker = predicates[0], patterns[0], rules[0], markers[0]
    refs = pattern.body.all if isinstance(pattern.body, AllExpression) else []
    gates = [
        p
        for p in knowledge.observable_definitions
        if p.predicate_id in refs and p.predicate_id != predicate.predicate_id
    ]
    if (
        pattern.definition_id != identity + ":definition"
        or len(refs) != 2
        or predicate.predicate_id not in refs
        or len(gates) != 1
        or not _is_gate(gates[0], predicate.scope_selector.kind == "spatial_zone")
        or rule.pattern_id != pattern.pattern_id
        or rule.from_id not in {h.hypothesis_id for h in knowledge.hypotheses}
        or marker.origin != "declared_demo_heuristic"
        or any(
            marker.assertion_id not in row.source_assertion_ids
            for row in (predicate, pattern, rule)
        )
    ):
        raise ValueError("条件结构已被改写，不能作为独立小束撤销。")
    return predicate, pattern, rule, marker


def _delete_blocker(knowledge, bundle):
    predicate, pattern, rule, marker = bundle
    if any(
        p.pattern_id != pattern.pattern_id
        and expression_refs(p.body) & {predicate.predicate_id, pattern.pattern_id}
        for p in knowledge.pattern_definitions
    ) or any(
        r.rule_id != rule.rule_id and r.pattern_id == pattern.pattern_id
        for r in knowledge.expectation_rules
    ):
        return "条件已被其他模式或候选引用，不能独立撤销；请先处理共享依赖。"
    for row in [
        *knowledge.relations,
        *knowledge.observable_definitions,
        *knowledge.pattern_definitions,
        *knowledge.effect_rules,
        *knowledge.expectation_rules,
        *knowledge.value_bindings,
    ]:
        if row not in bundle[:3] and marker.assertion_id in row.source_assertion_ids:
            return "此条件的作者来源已被其他知识引用，不能一并撤销。"
    return None


def list_conditions(knowledge):
    conditions = []
    for rule in knowledge.expectation_rules:
        if rule.rule_id.startswith(PREFIX) and rule.rule_id.endswith(":expectation"):
            identity = rule.rule_id.removesuffix(":expectation")
            bundle = _bundle(knowledge, identity)
            predicate, pattern, _, marker = bundle
            blocker = _delete_blocker(knowledge, bundle)
            conditions.append(
                {
                    "condition_id": identity,
                    "candidate_id": rule.from_id,
                    "label": predicate.label,
                    "feature_id": predicate.feature_id,
                    "op": predicate.op,
                    "operand": predicate.operand.model_dump(mode="json"),
                    "subject_entity_id": getattr(predicate.subject_selector, "entity_id", None),
                    "zone": getattr(predicate.scope_selector, "zone", None),
                    "mode": rule.mode,
                    "description": marker.text,
                    "source_assertion_ids": [
                        s for s in predicate.source_assertion_ids if s != marker.assertion_id
                    ],
                    "predicate_id": predicate.predicate_id,
                    "pattern_id": pattern.pattern_id,
                    "anomaly_gate_id": next(
                        ref for ref in pattern.body.all if ref != predicate.predicate_id
                    ),
                    "expectation_rule_id": rule.rule_id,
                    "can_delete": blocker is None,
                    "delete_blocker": blocker,
                }
            )
    return conditions


def remove_condition(knowledge, identity):
    bundle = _bundle(knowledge, identity)
    if blocker := _delete_blocker(knowledge, bundle):
        raise ValueError(blocker)
    predicate, pattern, rule, marker = bundle
    data = knowledge.model_dump(mode="json")
    for field, key, value in (
        ("observable_definitions", "predicate_id", predicate.predicate_id),
        ("pattern_definitions", "pattern_id", pattern.pattern_id),
        ("expectation_rules", "rule_id", rule.rule_id),
        ("source_assertions", "assertion_id", marker.assertion_id),
    ):
        data[field] = [row for row in data[field] if row[key] != value]
    return KnowledgePackage.model_validate(data)
