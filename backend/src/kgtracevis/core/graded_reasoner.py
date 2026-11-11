"""Compare legal joint branches with one fixed, evidence-independent budget."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from itertools import product

from kgtracevis.core.graded_evidence import (
    BudgetSlot,
    ConditionReading,
    comparison_budget,
    condition_readings,
    overlapping_sources,
)
from kgtracevis.core.unified_grounding import Grounding
from kgtracevis.kg.unified_compiler import (
    KnowledgeProgram,
    ProofBranch,
    SearchIncomplete,
    SearchLimits,
)
from kgtracevis.schema.feature_catalog import authoring_feature_role
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import ExpectationRule, KnowledgePackage

GRADED_METHOD = "graded_joint_abduction_v1"


@dataclass(frozen=True)
class Term:
    predicate_id: str
    reading: ConditionReading
    role: str
    expectation: ExpectationRule
    branch: ProofBranch
    slot: BudgetSlot | None
    anomaly_prerequisite: bool

    @property
    def hard(self):
        return self.role != "diagnostic" or self.expectation.mode == "necessary"

    @property
    def possible(self):
        return self.expectation.mode == "possible"


@dataclass(frozen=True)
class Option:
    branch: ProofBranch
    terms: tuple[Term, ...]
    scope_valid: bool

    @property
    def hard_refuted(self):
        return any(t.hard and t.reading.truth is False for t in self.terms)


@dataclass
class Joint:
    options: tuple[Option | None, ...]
    terms: tuple[Term, ...]
    status: str
    reasons: list[str]
    p: float
    c: float
    v: float
    support_count: int
    slots: list[dict]
    credit: dict[int, tuple[float, float]]

    @property
    def score(self):
        return self.p - self.c


class GradedReasoner:
    def __init__(self, knowledge: KnowledgePackage | dict, *, limits: SearchLimits | None = None):
        self.program = KnowledgeProgram(knowledge, limits=limits)
        if self.program.package.graded_policy is None:
            raise ValueError("分级解释溯因需要工作图声明 graded_policy 比较预算和判别锚点。")

    def analyze(self, evidence: EvidenceFrame | dict, *, top_k: int = 5) -> dict:
        payload = (
            evidence.model_dump(mode="json") if isinstance(evidence, EvidenceFrame) else evidence
        )
        frame = EvidenceFrame.model_validate(payload)
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if len(frame.task.focus_subject_ids) != 1:
            raise ValueError("one v2 frame is one focused query; submit one frame per ROI/object")
        try:
            return self._analyze(frame, top_k)
        except SearchIncomplete as exc:
            return self._result(frame, "search_incomplete", search_error=str(exc))

    def _result(self, frame, outcome, **fields):
        return {
            "schema_version": "rootlens-reasoning-result.v2",
            "case_id": frame.case_id,
            "graph_id": self.program.package.graph_id,
            "scoring_method": GRADED_METHOD,
            "outcome": outcome,
            "candidate_pool": [],
            "grounded_facts": [],
            "observed_patterns": [],
            "candidate_evaluations": [],
            "unassessed_candidates": [],
            "ranked_root_causes": [],
            "top_k_paths": [],
            "proof_graph": {"nodes": [], "edges": []},
            "graded_candidates": [],
            "graded_comparison": _comparison({}),
            **fields,
        }

    def _analyze(self, frame, top_k):
        program = self.program
        grounding = Grounding(frame, program)
        actual_class = grounding.resolved_subjects[frame.task.context_subject_id]
        hypotheses = sorted(
            (
                h
                for h in program.hypotheses.values()
                if h.target_role == frame.task.target_role
                and program.is_a(actual_class, h.applies_to_class_id)
            ),
            key=lambda h: h.hypothesis_id,
        )
        if not hypotheses:
            return self._result(frame, "not_applicable", reason="no_applicable_hypothesis")
        if len(hypotheses) > program.limits.candidates:
            raise SearchIncomplete("candidate limit exceeded")
        worlds = {h.hypothesis_id: program.hypothesis_world(h.hypothesis_id) for h in hypotheses}
        rules = {r.rule_id: r for world in worlds.values() for r in world[3]}
        pattern_ids = sorted({r.pattern_id for r in rules.values()})
        predicates = set().union(*(program.footprint(p) for p in pattern_ids))
        policy = program.package.graded_policy
        budget = comparison_budget(policy, predicates)
        if not budget:
            return self._result(frame, "not_applicable", reason="no_applicable_graded_slots")
        grounding.ground(predicates, individual_observations=True)
        readings = condition_readings(grounding)
        facts = [f for rows in grounding.facts.values() for f in rows]
        comparison = _comparison(budget)
        common = {
            "candidate_pool": [h.hypothesis_id for h in hypotheses],
            "grounded_facts": [f.to_json(program) for f in facts],
            "graded_comparison": comparison,
        }
        overlap = overlapping_sources(program, budget, readings, frame.task.reference_id)
        if overlap:
            comparison["source_overlaps"] = overlap
            return self._result(
                frame, "not_applicable", reason="graded_budget_source_overlap", **common
            )

        slots = {p: slot for slot in budget.values() for p in slot.predicate_ids}
        roles = {
            p: authoring_feature_role(program.features[program.observables[p].feature_id])
            for p in predicates
        }
        branches = {p: program.branches(p) for p in pattern_ids}
        scoped_facts = {p: r.valid_facts for p, r in readings.items()}
        scope_valid = {
            branch: grounding.joint_scope_valid(branch, selected=scoped_facts)
            for alternatives in branches.values()
            for branch in alternatives
        }
        options = {
            r.rule_id: tuple(
                Option(
                    branch,
                    tuple(
                        self._term(p, readings, roles, r, branch, slots)
                        for p in sorted(branch.predicates)
                    ),
                    scope_valid[branch],
                )
                for branch in branches[r.pattern_id]
            )
            for r in rules.values()
        }
        normal = _closed_anomaly_gate(program, readings)
        rows, selected = [], {}
        anchors = set(policy.anchor_predicate_ids)
        for h in hypotheses:
            world = worlds[h.hypothesis_id]
            row, joint = self._evaluate_candidate(h, world[3], options, anchors)
            rows.append(row)
            if joint is not None and joint.status in {"supported", "pending"} and not normal:
                selected[h.hypothesis_id] = joint

        supported = [
            r for r in rows if r["candidate_id"] in selected and r["status"] == "supported"
        ]
        pending = [r for r in rows if r["candidate_id"] in selected and r["status"] == "pending"]
        epsilon = program.package.execution_policy.tie_epsilon
        ranked, paths = [], []
        for group in (supported, pending):
            for rank, row in _ranks(group, top_k, epsilon):
                cid = row["candidate_id"]
                traces = self._paths(frame, cid, selected[cid], worlds[cid][1])
                paths.extend(traces)
                ranked.append({**row, "rank": rank, "explanation_paths": traces})
        comparison.update(
            supported_count=len(supported),
            pending_count=len(pending),
            scoring_input_obs_ids=sorted(
                {
                    obs
                    for r in rows
                    for term in r.get("graded_conditions", [])
                    if term["slot_id"] and term["support"] is not None
                    for obs in term["observed_obs_ids"]
                }
            )
            if not normal
            else [],
        )
        if normal:
            outcome, reason = "no_match", "anomaly_gate_is_false"
        elif supported:
            best = max(row["score"] for row in supported)
            outcome = (
                "ambiguous"
                if sum(abs(r["score"] - best) <= epsilon for r in supported) > 1
                else "supported"
            )
            reason = None
        elif pending or any(r["status"] == "insufficient_evidence" for r in rows):
            outcome, reason = "insufficient_evidence", None
        else:
            outcome, reason = "no_match", None
        used = {identity for f in facts for identity in f.obs_ids}
        return self._result(
            frame,
            outcome,
            **({"reason": reason} if reason else {}),
            **common,
            candidate_evaluations=rows,
            graded_candidates=ranked,
            ranked_root_causes=[r for r in ranked if r["status"] == "supported"],
            top_k_paths=paths,
            observed_patterns=[
                {
                    "pattern_id": p,
                    "definition_id": program.patterns[p].definition_id,
                    "value": None,
                    "scope_join": program.patterns[p].scope_join,
                    "branches": [
                        {
                            "predicate_ids": sorted(b.predicates),
                            "value": None,
                            "scope_valid": scope_valid[b],
                        }
                        for b in branches[p]
                    ],
                }
                for p in pattern_ids
            ],
            unused_observations=[
                {"obs_id": o.obs_id, "reason": "not_referenced_by_applicable_knowledge"}
                for o in frame.observations
                if o.obs_id not in used
            ],
        )

    def _term(self, identity, readings, roles, rule, branch, slots):
        predicate = self.program.observables[identity]
        anomaly = (
            predicate.feature_id == "detection.anomaly_present"
            and getattr(predicate.operand, "boolean", False) is True
        )
        return Term(
            identity,
            readings[identity],
            roles[identity],
            rule,
            branch,
            slots.get(identity),
            anomaly,
        )

    def _evaluate_candidate(self, hypothesis, expectations, options, anchors):
        choices = []
        refutations = {}
        for rule in expectations:
            scoped = [o for o in options[rule.rule_id] if o.scope_valid]
            viable = [o for o in scoped if not o.hard_refuted]
            if rule.mode == "possible":
                # An optional branch with an unknown prerequisite supplies no usable cue.
                choices.append(
                    [
                        None,
                        *(
                            o
                            for o in viable
                            if all(not t.hard or t.reading.truth is True for t in o.terms)
                        ),
                    ]
                )
            else:
                if not viable and scoped:
                    for option in scoped:
                        for term in option.terms:
                            if term.hard and term.reading.truth is False:
                                refutations[rule.rule_id, term.predicate_id] = {
                                    "rule_id": rule.rule_id,
                                    "pattern_id": rule.pattern_id,
                                    "predicate_id": term.predicate_id,
                                    "obs_ids": term.reading.observed_ids,
                                    "fact_ids": [f.fact_id for f in term.reading.valid_facts],
                                }
                choices.append(viable)
        best = None
        best_key = None
        for iteration, parts in enumerate(product(*choices)):
            if iteration >= self.program.limits.combinations:
                raise SearchIncomplete("graded joint-branch combination limit exceeded")
            joint = _evaluate_joint(parts, anchors)
            if joint is None:
                continue
            key = (
                {"supported": 2, "pending": 1, "insufficient_evidence": 0}[joint.status],
                joint.score,
                joint.v,
                joint.support_count,
            )
            if best_key is None or key > best_key:
                best, best_key = joint, key
        row = {
            "candidate_id": hypothesis.hypothesis_id,
            "candidate_name": hypothesis.label,
            "candidate_role": hypothesis.target_role,
        }
        if best is None:
            row.update(
                status="ruled_out" if refutations else "insufficient_evidence",
                eligible_for_ranking=False,
                score=None,
                reasons=["hard_constraint_refuted" if refutations else "no_legal_joint_scope"],
                hard_refutations=list(refutations.values()),
            )
        else:
            row.update(self._describe_joint(best, expectations))
        return row, best

    def _describe_joint(self, joint, expectations):
        conditions = []
        for index, term in enumerate(joint.terms):
            predicate = self.program.observables[term.predicate_id]
            reading = term.reading
            positive, negative = joint.credit.get(index, (0.0, 0.0))
            sources = set(predicate.source_assertion_ids)
            if predicate.grade:
                sources.update(predicate.grade.source_assertion_ids)
            values = {repr(value): value for fact in reading.facts for value in fact.actual_values}
            conditions.append(
                {
                    "predicate_id": term.predicate_id,
                    "rule_id": term.expectation.rule_id,
                    "pattern_id": term.expectation.pattern_id,
                    "mode": term.expectation.mode,
                    "label": predicate.label,
                    "role": term.role,
                    "feature_id": predicate.feature_id,
                    "op": predicate.op,
                    "operand": predicate.operand.model_dump(mode="json"),
                    "grade": predicate.grade.model_dump(mode="json") if predicate.grade else None,
                    "source_assertion_ids": sorted(sources),
                    "status": reading.status,
                    "reason": reading.reason,
                    "hard_constraint": term.hard,
                    "hard_constraint_satisfied": reading.truth if term.hard else None,
                    "obs_ids": sorted({obs for fact in reading.facts for obs in fact.obs_ids}),
                    "observed_obs_ids": reading.observed_ids,
                    "fact_ids": sorted(fact.fact_id for fact in reading.facts),
                    "actual_values": [values[key] for key in sorted(values)],
                    "support": reading.support,
                    "conflict": reading.conflict,
                    "slot_id": term.slot.slot_id if term.slot else None,
                    "weight": term.slot.weight if term.slot else 0.0,
                    "support_credit": positive,
                    "conflict_credit": negative,
                    "score_contribution": positive - negative,
                }
            )
        checks = []
        for rule, option in zip(expectations, joint.options, strict=True):
            checks.append(
                {
                    "rule_id": rule.rule_id,
                    "mode": rule.mode,
                    "pattern_id": rule.pattern_id,
                    "predicate_ids": sorted(option.branch.predicates) if option else [],
                    "branch_edge_ids": sorted(option.branch.edge_ids) if option else [],
                    "scope_valid": option.scope_valid if option else None,
                    "reason": "" if option else "optional_not_selected",
                    "evaluation_kind": "graded_branch",
                    "selected_signature_value": None,
                }
            )
        return {
            "status": joint.status,
            "reasons": joint.reasons,
            "eligible_for_ranking": joint.status == "supported",
            "score": joint.score,
            "confidence": None,
            "support_measurement_count": joint.support_count,
            "support_obs_ids": sorted(
                {obs for c in conditions if c["support_credit"] for obs in c["observed_obs_ids"]}
            ),
            "counter_obs_ids": sorted(
                {obs for c in conditions if c["conflict_credit"] for obs in c["observed_obs_ids"]}
            ),
            "expectation_checks": checks,
            "graded_conditions": conditions,
            "graded_slots": joint.slots,
            "scoring_details": {
                "support": joint.p,
                "conflict": joint.c,
                "score": joint.score,
                "coverage": joint.v,
            },
        }

    def _paths(self, frame, candidate, joint, parents):
        paths = []
        for index, term in enumerate(joint.terms):
            positive, negative = joint.credit.get(index, (0.0, 0.0))
            if not (positive or negative or (term.hard and term.reading.truth is True)):
                continue
            nodes, views = self.program.diagnostic_path(
                term.predicate_id, term.expectation, term.branch, candidate, parents, exact=True
            )
            obs_ids = term.reading.observed_ids
            predicate = self.program.observables[term.predicate_id]
            paths.append(
                {
                    "path_id": (
                        f"path:graded:{frame.case_id}:{candidate}:"
                        f"{term.expectation.rule_id}:{term.predicate_id}"
                    ),
                    "path_kind": "graded_contribution",
                    "contribution_kind": "support"
                    if positive
                    else "conflict"
                    if negative
                    else "prerequisite",
                    "candidate_id": candidate,
                    "predicate_id": term.predicate_id,
                    "rule_id": term.expectation.rule_id,
                    "nodes": nodes,
                    "source_edge_views": views,
                    "observation_ids": obs_ids,
                    "support_obs_ids": obs_ids if positive else [],
                    "counter_obs_ids": obs_ids if negative else [],
                    "joint_proof_id": None,
                    "required_joint_fact_ids": [],
                    "score_contribution": positive - negative,
                    "source_assertion_ids": predicate.grade.source_assertion_ids[:]
                    if predicate.grade
                    else [],
                }
            )
        return paths


def _closed_anomaly_gate(program, readings):
    readings = [
        r.truth
        for p, r in readings.items()
        if program.observables[p].feature_id == "detection.anomaly_present"
        and getattr(program.observables[p].operand, "boolean", False) is True
    ]
    return bool(readings) and all(truth is False for truth in readings)


def _evaluate_joint(options, anchors):
    terms = tuple(term for o in options if o for term in o.terms)
    references = {
        f.reference_id for t in terms for f in t.reading.valid_facts if f.reference_id is not None
    }
    if len(references) > 1:
        return None
    by_slot = defaultdict(list)
    for index, term in enumerate(terms):
        if term.slot:
            by_slot[term.slot.slot_id].append((index, term))
    slots, credit = [], {}
    for slot_id, selected in sorted(by_slot.items()):
        slot = selected[0][1].slot
        mandatory = [(i, t) for i, t in selected if not t.possible]
        if mandatory:
            # Two bounds, repeated predicates, and simultaneous expected rules spend a slot once.
            support_term = min(mandatory, key=lambda row: (row[1].reading.support or 0.0, row[0]))
            conflict_term = max(
                mandatory, key=lambda row: (row[1].reading.conflict or 0.0, -row[0])
            )
        else:
            alternatives = defaultdict(list)
            for index, term in selected:
                alternatives[term.expectation.rule_id].append((index, term))
            support_term = max(
                (
                    min(terms, key=lambda row: (row[1].reading.support or 0.0, row[0]))
                    for terms in alternatives.values()
                ),
                key=lambda row: (row[1].reading.support or 0.0, -row[0]),
            )
            conflict_term = None  # Possible effects never contribute negative evidence.
        p = support_term[1].reading.support or 0.0
        c = (conflict_term[1].reading.conflict or 0.0) if conflict_term else 0.0
        if p:
            credit[support_term[0]] = (slot.weight * p, 0.0)
        if c:
            credit[conflict_term[0]] = (
                credit.get(conflict_term[0], (0.0, 0.0))[0],
                slot.weight * c,
            )
        slots.append(
            {
                "slot_id": slot_id,
                "group_id": slot.group_id,
                "weight": slot.weight,
                "predicate_ids": sorted({t.predicate_id for _, t in selected}),
                "verified": all(t.reading.measured for _, t in (mandatory or selected)),
                "support": p,
                "conflict": c,
                "score_contribution": slot.weight * (p - c),
            }
        )
    p, c = (math.fsum(row[key] * row["weight"] for row in slots) for key in ("support", "conflict"))
    weight = math.fsum(row["weight"] for row in slots)
    v = math.fsum(row["weight"] for row in slots if row["verified"]) / weight if weight else 0.0
    count = sum(row["support"] > row["conflict"] for row in slots)
    anchor_terms = [t for t in terms if t.predicate_id in anchors]
    positive_slots = {row["slot_id"] for row in slots if row["support"] > row["conflict"]}
    gates = [t for t in terms if t.anomaly_prerequisite]
    reasons = []
    if count < 2:
        reasons.append("fewer_than_two_supported_measurements")
    if not gates:
        reasons.append("no_declared_anomaly_prerequisite")
    if any(t.hard and t.reading.truth is not True for t in terms):
        reasons.append("hard_constraint_unverified")
    if not anchor_terms or any(
        t.slot.slot_id not in positive_slots
        or (t.reading.support or 0.0) <= (t.reading.conflict or 0.0)
        for t in anchor_terms
    ):
        reasons.append("anchor_without_measured_net_support")
    if p <= c:
        reasons.append("nonpositive_branch_score")
    status = (
        "insufficient_evidence" if count < 2 or not gates else "pending" if reasons else "supported"
    )
    return Joint(options, terms, status, reasons, p, c, v, count, slots, credit)


def _comparison(budget):
    return {
        "budget_policy": "fixed_shared_measurement_slots_v1",
        "formula": "S = P - C; P = sum(w * p); C = sum(w * c)",
        "slots": [slot.to_json() for slot in budget.values()],
        "minimum_supported_measurements": 2,
        "supported_count": 0,
        "pending_count": 0,
        "scoring_input_obs_ids": [],
    }


def _ranks(group, top_k, epsilon):
    rows = sorted(group, key=lambda row: (-row["score"], row["candidate_id"]))
    if not rows:
        return
    cutoff = rows[min(top_k, len(rows)) - 1]["score"]
    previous, rank = None, 0
    for row in rows:
        if row["score"] < cutoff - epsilon:
            break
        if previous is None or abs(row["score"] - previous) > epsilon:
            previous, rank = row["score"], rank + 1
        yield rank, row
