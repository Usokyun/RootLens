"""Evidence-grounded hypothesis comparison over one common executable graph.

No dataset-specific ranking, detector confidence arithmetic, or LLM root answers
are used here. Inputs are the closed v2 contracts and registered comparisons.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product

from kgtracevis.core.unified_grounding import GroundedFact, Grounding
from kgtracevis.kg.unified_compiler import (
    KnowledgeProgram,
    ProofBranch,
    SearchIncomplete,
    SearchLimits,
)
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


@dataclass
class EvaluatedBranch:
    branch: ProofBranch
    truth: bool | None
    covered: frozenset[str]
    conflicts: frozenset[str]
    partial: frozenset[str]
    missing: frozenset[str]
    scope_valid: bool
    reason: str = ""


class UnifiedReasoner:
    def __init__(self, knowledge: KnowledgePackage | dict, *, limits: SearchLimits | None = None):
        self.program = KnowledgeProgram(knowledge, limits=limits)

    def analyze(self, evidence: EvidenceFrame | dict, *, top_k: int = 5) -> dict:
        payload = (
            evidence.model_dump(mode="json") if isinstance(evidence, EvidenceFrame) else evidence
        )
        frame = EvidenceFrame.model_validate(payload)
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if len(frame.task.focus_subject_ids) != 1:
            raise ValueError("one v2 frame is one focused query; submit one frame per ROI/object")
        try:
            return self._analyze(frame, top_k)
        except SearchIncomplete as exc:
            return self._envelope(frame, "search_incomplete", search_error=str(exc))

    def _envelope(self, frame, outcome, **fields):
        return {
            "schema_version": "rootlens-reasoning-result.v2",
            "case_id": frame.case_id,
            "graph_id": self.program.package.graph_id,
            "scoring_method": "unified_constraint_abduction_v0",
            "outcome": outcome,
            "candidate_pool": [],
            "grounded_facts": [],
            "observed_patterns": [],
            "candidate_evaluations": [],
            "unassessed_candidates": [],
            "ranked_root_causes": [],
            "top_k_paths": [],
            "proof_graph": {"nodes": [], "edges": []},
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
            return self._envelope(frame, "not_applicable", reason="no_applicable_hypothesis")
        if len(hypotheses) > program.limits.candidates:
            raise SearchIncomplete("candidate limit exceeded")
        worlds = {h.hypothesis_id: program.hypothesis_world(h.hypothesis_id) for h in hypotheses}
        pattern_ids = sorted({e.pattern_id for world in worlds.values() for e in world[3]})
        predicates = set().union(*(program.footprint(p) for p in pattern_ids))
        grounding.ground(predicates)
        facts = [f for values in grounding.facts.values() for f in values]
        known = [f for f in facts if f.value is not None]
        positive = [f for f in known if f.value is True]
        evaluated = {p: self._evaluate_pattern(p, grounding) for p in pattern_ids}
        pattern_truth = {p: self._pattern_truth(options) for p, options in evaluated.items()}
        rows, choices, unassessed = [], {}, []
        for hypothesis in hypotheses:
            world = worlds[hypothesis.hypothesis_id]
            footprint = set().union(*(program.footprint(e.pattern_id) for e in world[3]))
            if not any(f.measured for p in footprint for f in grounding.facts[p]):
                unassessed.append(
                    {
                        "candidate_id": hypothesis.hypothesis_id,
                        "reason": "no_evaluable_observation_footprint",
                        "missing_predicate_ids": sorted(footprint),
                    }
                )
                continue
            row, selected = self._compare_candidate(
                hypothesis, world, evaluated, pattern_truth, known, positive
            )
            rows.append(row)
            choices[hypothesis.hypothesis_id] = selected
        eligible = sorted(
            (r for r in rows if r["eligible_for_ranking"]),
            key=lambda r: (-r["score"], r["candidate_id"]),
        )
        ranked, paths = [], []
        last_score, rank = None, 0
        policy = program.package.execution_policy
        cutoff = eligible[min(top_k, len(eligible)) - 1]["score"] if eligible else None
        # Do not split a tie merely because top_k's boundary falls inside it.
        selected_rows = [r for r in eligible if r["score"] >= cutoff - policy.tie_epsilon]
        for row in selected_rows:
            if last_score is None or abs(last_score - row["score"]) > policy.tie_epsilon:
                rank += 1
            last_score = row["score"]
            candidate_paths = self._paths(
                frame, row, choices[row["candidate_id"]], worlds[row["candidate_id"]], grounding
            )
            paths.extend(candidate_paths)
            ranked.append(
                {
                    "candidate_id": row["candidate_id"],
                    "candidate_name": row["candidate_name"],
                    "candidate_role": row["candidate_role"],
                    "rank": rank,
                    "score": row["score"],
                    "confidence": None,
                    "support_obs_ids": row["support_obs_ids"],
                    "scoring_details": row["scoring_details"],
                    "explanation_paths": candidate_paths,
                }
            )
        if eligible:
            tied = sum(
                abs(r["score"] - eligible[0]["score"]) <= policy.tie_epsilon for r in eligible
            )
            outcome = "ambiguous" if tied > 1 else "supported"
        elif any(r["status"] == "insufficient_evidence" for r in rows) or unassessed:
            outcome = "insufficient_evidence"
        else:
            outcome = "no_match"
        bound_ids = {o for f in facts for o in f.obs_ids}
        return self._envelope(
            frame,
            outcome,
            candidate_pool=[r["candidate_id"] for r in rows],
            grounded_facts=[f.to_json(program) for f in facts],
            observed_patterns=[
                {
                    "pattern_id": p,
                    "definition_id": program.patterns[p].definition_id,
                    "value": pattern_truth[p],
                    "scope_join": program.patterns[p].scope_join,
                    "branches": [
                        {
                            "predicate_ids": sorted(b.branch.predicates),
                            "value": b.truth,
                            "scope_valid": b.scope_valid,
                            "reason": b.reason,
                        }
                        for b in evaluated[p]
                    ],
                }
                for p in pattern_ids
            ],
            candidate_evaluations=rows,
            unassessed_candidates=unassessed,
            ranked_root_causes=ranked,
            top_k_paths=paths,
            proof_graph=self._proof_graph(frame, rows, choices, worlds, grounding),
            unused_observations=[
                {
                    "obs_id": o.obs_id,
                    "reason": "unregistered_feature"
                    if o.feature_id not in program.features
                    else "not_referenced_by_applicable_knowledge",
                }
                for o in frame.observations
                if o.obs_id not in bound_ids
            ],
            execution_policy=policy.model_dump(mode="json"),
        )

    @staticmethod
    def _pattern_truth(options):
        if any(o.truth is True for o in options):
            return True
        return False if options and all(o.truth is False for o in options) else None

    def _evaluate_pattern(self, pattern_id, grounding):
        options = []
        for branch in self.program.branches(pattern_id):
            facts = [f for p in branch.predicates for f in grounding.valid(p)]
            scope_valid = grounding.joint_scope_valid(branch)
            true = frozenset(f.fact_id for f in facts if f.value is True)
            false = frozenset(f.fact_id for f in facts if f.value is False)
            missing = frozenset(p for p in branch.predicates if not grounding.valid(p))
            blocked = any(
                not any(f.value is True for f in grounding.valid(p)) and grounding.valid(p)
                for p in branch.predicates
            )
            truth = None if not scope_valid else False if blocked else None if missing else True
            options.append(
                EvaluatedBranch(
                    branch,
                    truth,
                    true if truth is True else frozenset(),
                    false if scope_valid else frozenset(),
                    true,
                    missing,
                    scope_valid,
                    "scope_join_not_satisfied"
                    if not scope_valid
                    else "missing_or_invalid_observations"
                    if missing
                    else "",
                )
            )
        if not options:
            options = [
                EvaluatedBranch(
                    ProofBranch(frozenset()),
                    None,
                    frozenset(),
                    frozenset(),
                    frozenset(),
                    frozenset(
                        p for p in self.program.footprint(pattern_id) if not grounding.valid(p)
                    ),
                    False,
                    "no_finite_definition_proof",
                )
            ]
        return options

    def _compare_candidate(self, hypothesis, world, evaluated, pattern_truth, known, positive):
        policy = self.program.package.execution_policy
        expectations = world[3]
        best = None
        selected = ()
        for iteration, options in enumerate(
            product(*(evaluated[e.pattern_id] for e in expectations))
        ):
            if iteration >= self.program.limits.combinations:
                raise SearchIncomplete("hypothesis-signature combination limit exceeded")
            covered = frozenset().union(*(o.covered for o in options))
            conflicts = frozenset().union(
                *(
                    o.conflicts
                    for e, o in zip(expectations, options, strict=True)
                    if e.mode != "possible"
                )
            )
            u, u_groups = _group_loss(positive, lambda f, used=covered: f.fact_id not in used)
            c, c_groups = _group_loss(known, lambda f, bad=conflicts: f.fact_id in bad)
            cost = (
                u
                + policy.conflict_weight * c
                + policy.assumption_weight * hypothesis.assumption_cost
            )
            if not math.isfinite(cost):
                raise ValueError("knowledge policy produces an unrepresentable explanation cost")
            if best is None or cost < best["cost"] - policy.tie_epsilon:
                best = {
                    "cost": cost,
                    "covered": covered,
                    "conflicts": conflicts,
                    "u": u,
                    "c": c,
                    "u_groups": u_groups,
                    "c_groups": c_groups,
                }
                selected = options
        assert best is not None
        necessary_violation = any(
            e.mode == "necessary" and pattern_truth[e.pattern_id] is False for e in expectations
        )
        required_missing = any(
            e.mode == "necessary" and pattern_truth[e.pattern_id] is None for e in expectations
        )
        eligible = bool(best["covered"]) and not necessary_violation and not required_missing
        pending = required_missing or any(o.truth is None for o in selected)
        status = (
            "supported"
            if eligible
            else "ruled_out"
            if necessary_violation
            else "insufficient_evidence"
            if pending
            else "no_match"
        )
        checks = [
            {
                "rule_id": e.rule_id,
                "mode": e.mode,
                "pattern_id": e.pattern_id,
                "expected_value": True,
                "observed_value": pattern_truth[e.pattern_id],
                "selected_signature_value": o.truth,
                "predicate_ids": sorted(o.branch.predicates),
                "covered_fact_ids": sorted(o.covered),
                "conflicting_fact_ids": sorted(o.conflicts) if e.mode != "possible" else [],
                "partial_matching_fact_ids": sorted(o.partial) if o.truth is not True else [],
                "missing_predicate_ids": sorted(o.missing),
                "scope_valid": o.scope_valid,
                "reason": o.reason,
            }
            for e, o in zip(expectations, selected, strict=True)
        ]
        groups = []
        for group in sorted(best["c_groups"]):
            total, count = best["c_groups"][group]
            uncovered, positive_count = best["u_groups"].get(group, (0, 0))
            groups.append(
                {
                    "group_id": group,
                    "observed_fact_count": count,
                    "positive_fact_count": positive_count,
                    "conflict_count": total,
                    "uncovered_positive_count": uncovered,
                }
            )
        return {
            "candidate_id": hypothesis.hypothesis_id,
            "candidate_name": hypothesis.label,
            "candidate_role": hypothesis.target_role,
            "status": status,
            "eligible_for_ranking": eligible,
            "score": -best["cost"],
            "confidence": None,
            "support_obs_ids": sorted(
                {o for f in positive if f.fact_id in best["covered"] for o in f.obs_ids}
            ),
            "counter_obs_ids": sorted(
                {o for f in known if f.fact_id in best["conflicts"] for o in f.obs_ids}
            ),
            "unexplained_fact_ids": sorted(
                f.fact_id for f in positive if f.fact_id not in best["covered"]
            ),
            "active_hypothesis_world_entities": sorted(world[0]),
            "activated_effect_rule_ids": [r.rule_id for r in world[2]],
            "expectation_checks": checks,
            "scoring_details": {
                "unexplained_loss": best["u"],
                "conflict_loss": best["c"],
                "assumption_cost": hypothesis.assumption_cost,
                "conflict_weight": policy.conflict_weight,
                "assumption_weight": policy.assumption_weight,
                "total_cost": best["cost"],
                "groups": groups,
                "denominator_policy": "fixed_for_all_context_candidates",
            },
        }, selected

    def _paths(self, frame, row, selected, world, grounding):
        paths = []
        for expectation, option in zip(world[3], selected, strict=True):
            if option.truth is not True:
                continue
            joint = (
                f"joint:{frame.case_id}:{row['candidate_id']}:"
                f"{expectation.pattern_id}:{expectation.rule_id}"
            )
            required = sorted(option.covered)
            for predicate in sorted(option.branch.predicates):
                for fact in grounding.valid(predicate):
                    if fact.fact_id not in option.covered:
                        continue
                    nodes, edges = self.program.observation_path(
                        predicate, expectation.pattern_id, option.branch
                    )
                    views = [{"edge_id": identity, "reverse": False} for identity in edges]
                    nodes += [expectation.rule_id, expectation.from_id]
                    views += [
                        {"edge_id": expectation.rule_id + "::to", "reverse": True},
                        {"edge_id": expectation.rule_id + "::from", "reverse": True},
                    ]
                    current = expectation.from_id
                    while current != row["candidate_id"]:
                        effect = world[1][current]
                        nodes += [effect.rule_id, effect.from_id]
                        views += [
                            {"edge_id": effect.rule_id + "::to", "reverse": True},
                            {"edge_id": effect.rule_id + "::from", "reverse": True},
                        ]
                        current = effect.from_id
                    paths.append(
                        {
                            "path_id": (
                                f"path:{frame.case_id}:{row['candidate_id']}:"
                                f"{expectation.rule_id}:{fact.fact_id}"
                            ),
                            "nodes": nodes,
                            "source_edge_views": views,
                            "support_obs_ids": fact.obs_ids,
                            "joint_proof_id": joint,
                            "required_joint_fact_ids": required,
                        }
                    )
        return paths

    def _proof_graph(self, frame, rows, choices, worlds, grounding):
        nodes, edges = {}, []

        def add(identity, kind, **attributes):
            nodes[identity] = {"node_id": identity, "kind": kind, **attributes}

        for values in grounding.facts.values():
            for fact in values:
                add(fact.fact_id, "grounded_fact", predicate_id=fact.predicate_id, value=fact.value)
                for obs_id in fact.obs_ids:
                    add(obs_id, "observation", case_id=frame.case_id)
                    edges.append({"head": obs_id, "relation": "GROUNDS", "tail": fact.fact_id})
        for row in rows:
            candidate = row["candidate_id"]
            assumed, score = "assumed:" + candidate, "score:" + candidate
            add(assumed, "hypothesis_assumption", candidate_id=candidate)
            add(score, "candidate_score", **row["scoring_details"])
            edges.append({"head": assumed, "relation": "ASSUMPTION_COST", "tail": score})
            world = worlds[candidate]
            for rule in world[2]:
                start = assumed if rule.from_id == candidate else candidate + "@" + rule.from_id
                end = candidate + "@" + rule.to_id
                add(end, "hypothesis_world_state", knowledge_entity_id=rule.to_id)
                edges.append(
                    {
                        "head": start,
                        "relation": "HYPOTHESIZED_EFFECT",
                        "tail": end,
                        "rule_id": rule.rule_id,
                        "origin_edge_ids": [rule.rule_id + "::from", rule.rule_id + "::to"],
                    }
                )
            for rule, option in zip(world[3], choices[candidate], strict=True):
                identity = f"joint:{frame.case_id}:{candidate}:{rule.pattern_id}:{rule.rule_id}"
                expected = f"expected:{candidate}:{rule.rule_id}"
                add(
                    identity,
                    "observed_joint_signature",
                    value=option.truth,
                    pattern_id=rule.pattern_id,
                    requires_all_fact_ids=sorted(option.covered),
                )
                add(expected, "expected_pattern", pattern_id=rule.pattern_id, expected_value=True)
                start = assumed if rule.from_id == candidate else candidate + "@" + rule.from_id
                edges.append(
                    {
                        "head": start,
                        "relation": "EXPECTS",
                        "tail": expected,
                        "rule_id": rule.rule_id,
                        "origin_edge_ids": [rule.rule_id + "::from", rule.rule_id + "::to"],
                    }
                )
                for predicate in sorted(option.branch.predicates):
                    for fact in grounding.facts[predicate]:
                        edges.append(
                            {
                                "head": fact.fact_id,
                                "relation": "JOINT_INPUT",
                                "tail": identity,
                                "scope_valid": option.scope_valid,
                            }
                        )
                edges.extend(
                    [
                        {"head": identity, "relation": "OBSERVED_SIDE", "tail": score},
                        {"head": expected, "relation": "EXPECTED_SIDE", "tail": score},
                    ]
                )
            for values in grounding.facts.values():
                for fact in values:
                    if fact.value is True:
                        edges.append(
                            {
                                "head": fact.fact_id,
                                "relation": "COVERAGE_TERM",
                                "tail": score,
                                "covered": fact.fact_id not in row["unexplained_fact_ids"],
                            }
                        )
        return {"nodes": list(nodes.values()), "edges": edges}


def _group_loss(facts: list[GroundedFact], loss):
    groups = {}
    for fact in facts:
        total, count = groups.get(fact.dependency_group, (0, 0))
        groups[fact.dependency_group] = (total + int(loss(fact)), count + 1)
    mean = sum(total / count for total, count in groups.values()) / len(groups) if groups else 0.0
    return mean, groups
