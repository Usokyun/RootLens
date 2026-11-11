"""Explain what the selected knowledge can distinguish, without changing inference.

This pure authoring report consumes the *same* knowledge snapshot, Frame and
completed result. It never reruns grounding, a model, or an inference engine.
Logical expectation groups and RootKGD's actual structural projection groups
are deliberately different contracts. Neither grouping declares a true cause.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from copy import deepcopy
from typing import Literal, TypedDict

from kgtracevis.kg.unified_compiler import KnowledgeProgram, SearchIncomplete
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


class ConditionExpectation(TypedDict):
    pattern_id: str
    mode: str


class CostPrior(TypedDict):
    candidate_id: str
    assumption_cost: float
    assumption_weight: float
    weighted_cost: float
    applied_to_score: bool


class EquivalenceGroup(TypedDict):
    group_id: str
    candidate_ids: list[str]
    candidate_names: list[str]
    condition_signature: list[ConditionExpectation]
    cost_priors: list[CostPrior]
    evidence_distinguishes: Literal[False]


class FeatureObservationCount(TypedDict):
    feature_id: str
    observation_count: int
    observed_count: int


class EvidenceUsage(TypedDict):
    total_observation_count: int
    observed_observation_count: int
    condition_reference_status: Literal["available", "incomplete"]
    condition_grounded_observation_count: int
    score_input_status: Literal["available", "not_ranked", "unavailable"]
    score_input_observation_count: int
    condition_feature_ids: list[str]
    score_input_feature_ids: list[str]
    unreferenced_features: list[FeatureObservationCount]
    not_scored_features: list[FeatureObservationCount]


class CandidateChecks(TypedDict):
    candidate_id: str
    assessment_status: str
    eligible_for_ranking: bool | None
    condition_checks_used_for_score: bool
    expectation_checks: list[dict]
    predicate_checks: list[dict]


class DiscriminabilityReport(TypedDict):
    schema_version: Literal["rootlens-candidate-discriminability.v1"]
    reasoner_id: str
    grouping_basis: str
    grouping_status: Literal["available", "unavailable", "incomplete"]
    grouping_note: str
    issues: list[str]
    candidate_count: int
    equivalence_groups: list[EquivalenceGroup]
    evidence_usage: EvidenceUsage
    candidate_checks: list[CandidateChecks]


def analyze_candidate_discriminability(
    knowledge: KnowledgePackage | dict,
    frame: EvidenceFrame | dict,
    result: dict,
    *,
    reasoner_id: str,
) -> DiscriminabilityReport:
    """Return JSON-compatible authoring diagnostics for an existing inference.

    Unified groups have the same reachable (pattern, expectation mode) multiset,
    regardless of assumption costs. Multiplicity is retained: two expectations
    may select different witnesses of an OR pattern in the existing engine.
    RootKGD groups require identical actual full-channel vectors and score terms;
    absent structural inputs never fall back to logical groups. Existing checks
    are copied, not reinterpreted; a search budget failure remains explicit.
    """
    if reasoner_id not in {"unified_abduction", "graded_abduction", "tep_rootkgd"}:
        raise ValueError(f"unsupported diagnostic reasoner: {reasoner_id}")
    program = KnowledgeProgram(knowledge)
    evidence = EvidenceFrame.model_validate(
        frame.model_dump(mode="json") if isinstance(frame, EvidenceFrame) else frame
    )
    if result.get("graph_id") != program.package.graph_id:
        raise ValueError("diagnostics require the inference's knowledge snapshot")
    if result.get("case_id") != evidence.case_id:
        raise ValueError("diagnostics require the inference's EvidenceFrame")

    graded = reasoner_id == "graded_abduction"
    unified = reasoner_id != "tep_rootkgd"
    rows = {r["candidate_id"]: r for r in result.get("candidate_evaluations", [])}
    unassessed = {r["candidate_id"]: r for r in result.get("unassessed_candidates", [])}
    identities = sorted(set(result.get("candidate_pool", [])) | rows.keys() | unassessed.keys())
    # Candidates come from the inference result, not all hypotheses in the graph.
    if any(identity not in program.hypotheses for identity in identities):
        raise ValueError("inference candidates are not in its knowledge snapshot")
    issues = []
    incomplete = result.get("outcome") == "search_incomplete"
    if incomplete:
        issues.append(result.get("search_error", "inference search did not complete"))
    signatures, footprints = {}, {}
    for identity in identities:
        try:
            expectations = program.hypothesis_world(identity)[3]
            signatures[identity] = tuple(sorted((r.pattern_id, r.mode) for r in expectations))
            footprints[identity] = set().union(
                *(program.footprint(r.pattern_id) for r in expectations)
            )
        except SearchIncomplete as exc:
            incomplete = True
            issues.append(f"{identity}: {exc}")

    groups = defaultdict(list)
    if unified:
        for identity, signature in signatures.items():
            groups[signature].append(identity)
        basis = "reachable_expectation_conditions"
        status = "incomplete" if incomplete else "available"
        note = "同组候选拥有相同的可达条件与期待模式，当前知识不能用观测区分它们。" + (
            "分级相容分不使用假设先验，组内候选共享已声明的曲线和测量预算。"
            if graded
            else "必要、预期、可能及 OR 分支沿用本次推理；假设成本只是成本先验。"
        )
    else:
        unavailable = []
        for identity in identities:
            key = _structural_key(rows.get(identity), result)
            if key is None:
                unavailable.append(identity)
            else:
                groups[key].append(identity)
        basis = "actual_structural_projection" if groups else "structural_inputs_unavailable"
        status = (
            "incomplete"
            if incomplete or (groups and unavailable)
            else ("available" if groups else "unavailable")
        )
        if unavailable:
            issues.append("未生成完整结构评分输入的候选：" + "、".join(unavailable))
        note = (
            "仅按本次实际全通道传播向量、观测贡献与评分项分组；条件检查只供知识作者核对，"
            "不参与 RootKGD 结构评分。未生成结构输入时不使用逻辑签名替代。"
        )

    equivalent = []
    for members in sorted(sorted(v) for v in groups.values() if len(v) > 1):
        equivalent.append(
            EquivalenceGroup(
                group_id=f"diagnostic-group:{reasoner_id}:{len(equivalent) + 1}",
                candidate_ids=members,
                candidate_names=[program.hypotheses[i].label for i in members],
                condition_signature=[
                    ConditionExpectation(pattern_id=pattern, mode=mode)
                    for pattern, mode in signatures[members[0]]
                ]
                if unified
                else [],
                cost_priors=[_cost_prior(program, i) for i in members]
                if unified and not graded
                else [],
                evidence_distinguishes=False,
            )
        )

    facts = result.get("grounded_facts", [])
    candidate_checks = []
    for identity in identities:
        row = rows.get(identity, {})
        candidate_checks.append(
            CandidateChecks(
                candidate_id=identity,
                assessment_status=row.get(
                    "status", unassessed.get(identity, {}).get("reason", "not_evaluated")
                ),
                eligible_for_ranking=row.get("eligible_for_ranking"),
                condition_checks_used_for_score=unified,
                expectation_checks=deepcopy(row.get("expectation_checks", [])) if unified else [],
                predicate_checks=deepcopy(
                    [
                        fact
                        for fact in facts
                        if fact["predicate_id"] in footprints.get(identity, set())
                    ]
                ),
            )
        )
    predicates = set().union(*footprints.values())
    referenced_features = {program.observables[p].feature_id for p in predicates}
    usage = _evidence_usage(evidence, result, referenced_features, incomplete, unified, graded)
    return DiscriminabilityReport(
        schema_version="rootlens-candidate-discriminability.v1",
        reasoner_id=reasoner_id,
        grouping_basis=basis,
        grouping_status=status,
        grouping_note=note,
        issues=issues,
        candidate_count=len(identities),
        equivalence_groups=equivalent,
        evidence_usage=usage,
        candidate_checks=candidate_checks,
    )


def _cost_prior(program, identity):
    cost = program.hypotheses[identity].assumption_cost
    weight = program.package.execution_policy.assumption_weight
    return CostPrior(
        candidate_id=identity,
        assumption_cost=cost,
        assumption_weight=weight,
        weighted_cost=cost * weight,
        applied_to_score=True,
    )


def _structural_key(row, result):
    if row is None:
        return None
    details = row.get("scoring_details", {})
    order = details.get("channel_order", [])
    propagated = details.get("propagated_channel_vector", [])
    observed = details.get("observed_channel_vector", [])
    propagation = result.get("propagation", {})
    if not all(isinstance(values, list) for values in (order, propagated, observed)):
        return None
    terms = [
        details.get(k)
        for k in (
            "cosine_similarity",
            "covered_contribution_mass",
            "propagation_entropy",
            "structural_score",
        )
    ]
    if (
        len(order) != 52
        or len(set(order)) != 52
        or len(propagated) != 52
        or len(observed) != 52
        or order != propagation.get("channel_order")
        or observed != propagation.get("observed_contribution_vector")
        or any(
            type(n) not in (int, float) or not math.isfinite(n)
            for n in [*propagated, *observed, *terms]
        )
    ):
        return None
    return tuple(order), tuple(propagated), tuple(observed), tuple(terms)


def _feature_counts(observations):
    total = Counter(o.feature_id for o in observations)
    observed = Counter(o.feature_id for o in observations if o.status == "observed")
    return [
        FeatureObservationCount(
            feature_id=feature, observation_count=count, observed_count=observed[feature]
        )
        for feature, count in sorted(total.items())
    ]


def _evidence_usage(frame, result, referenced_features, incomplete, unified, graded):
    observations = {o.obs_id: o for o in frame.observations}
    facts = result.get("grounded_facts", [])
    grounded = {
        obs for fact in facts for obs in fact.get("source_obs_ids", [])
    } & observations.keys()
    if result.get("outcome") == "search_incomplete":
        score_status, scoring = "unavailable", set()
    elif not result.get("candidate_evaluations"):
        score_status, scoring = "not_ranked", set()
    elif graded:
        inputs = result.get("graded_comparison", {}).get("scoring_input_obs_ids")
        score_status = "available" if inputs else "not_ranked"
        scoring = set(inputs or []) & observations.keys()
    elif unified:
        score_status = "available"
        scoring = {
            obs
            for fact in facts
            if fact.get("value") is not None
            for obs in fact.get("source_obs_ids", [])
        } & observations.keys()
    else:
        inputs = result.get("propagation", {}).get("scoring_input_obs_ids")
        score_status = "available" if inputs is not None else "unavailable"
        scoring = set(inputs or []) & observations.keys()
    return EvidenceUsage(
        total_observation_count=len(observations),
        observed_observation_count=sum(o.status == "observed" for o in observations.values()),
        condition_reference_status="incomplete" if incomplete else "available",
        condition_grounded_observation_count=len(grounded),
        score_input_status=score_status,
        score_input_observation_count=len(scoring),
        condition_feature_ids=sorted(referenced_features),
        score_input_feature_ids=sorted({observations[i].feature_id for i in scoring}),
        unreferenced_features=[]
        if incomplete
        else _feature_counts(
            [o for o in observations.values() if o.feature_id not in referenced_features]
        ),
        not_scored_features=[]
        if score_status == "unavailable"
        else _feature_counts([o for o in observations.values() if o.obs_id not in scoring]),
    )
