"""Same-input reference calculations for the unified diagnosis prototype.

The flat reference independently evaluates fully expanded candidate signatures.
It deliberately shares primitive grounding/scope contracts, not the reasoner's
candidate evaluation, ranking or cost implementation. Equivalence is expected:
hierarchical storage alone is not an accuracy contribution.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import product

from kgtracevis.core.unified_grounding import Grounding
from kgtracevis.kg.unified_compiler import KnowledgeProgram, SearchIncomplete
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.schema.unified_knowledge import KnowledgePackage


def flat_reference(
    knowledge: KnowledgePackage | dict, frame: EvidenceFrame, *, count_source_rows: bool = False
):
    program = KnowledgeProgram(knowledge)
    ground = Grounding(frame, program)
    hypotheses = [
        h
        for h in program.hypotheses.values()
        if h.target_role == frame.task.target_role
        and program.is_a(
            ground.resolved_subjects[frame.task.context_subject_id], h.applies_to_class_id
        )
    ]
    # Independently materialize a flat profile for every assumed root.
    profiles = {}
    for hypothesis in hypotheses:
        active = {hypothesis.hypothesis_id}
        while True:
            expanded = active | {
                r.to_id for r in program.package.effect_rules if r.from_id in active
            }
            if expanded == active:
                break
            active = expanded
        profiles[hypothesis.hypothesis_id] = sorted(
            (r for r in program.package.expectation_rules if r.from_id in active),
            key=lambda r: r.rule_id,
        )
    predicate_ids = set()
    for rules in profiles.values():
        for rule in rules:
            predicate_ids |= program.footprint(rule.pattern_id)
    ground.ground(predicate_ids)
    known = [f for rows in ground.facts.values() for f in rows if f.value is not None]
    positive = [f for f in known if f.value is True]

    def loss(facts, loss_ids):
        groups = defaultdict(list)
        for fact in facts:
            # Deliberately naive ablation: repeated source rows become extra votes.
            repeats = len(fact.obs_ids) if count_source_rows else 1
            groups[fact.dependency_group].extend([fact.fact_id in loss_ids] * repeats)
        return sum(sum(v) / len(v) for v in groups.values()) / len(groups) if groups else 0.0

    options = {}
    for rule in [r for rules in profiles.values() for r in rules]:
        if rule.pattern_id in options:
            continue
        rows = []
        for branch in program.branches(rule.pattern_id):
            facts = [f for p in branch.predicates for f in ground.valid(p)]
            joined = ground.joint_scope_valid(branch)
            missing = any(not ground.valid(p) for p in branch.predicates)
            blocked = any(
                ground.valid(p) and not any(f.value is True for f in ground.valid(p))
                for p in branch.predicates
            )
            truth = None if not joined else False if blocked else None if missing else True
            rows.append(
                (
                    truth,
                    {f.fact_id for f in facts if f.value is True} if truth is True else set(),
                    {f.fact_id for f in facts if f.value is False} if joined else set(),
                )
            )
        options[rule.pattern_id] = rows or [(None, set(), set())]
    result = []
    for hypothesis in hypotheses:
        rules = profiles[hypothesis.hypothesis_id]
        footprint = set().union(*(program.footprint(r.pattern_id) for r in rules))
        if not any(f.measured for p in footprint for f in ground.facts[p]):
            continue
        best = None
        all_positive = {f.fact_id for f in positive}
        for index, choice in enumerate(product(*(options[r.pattern_id] for r in rules))):
            if index >= program.limits.combinations:
                raise SearchIncomplete("flat reference combination limit exceeded")
            covered = set().union(*(row[1] for row in choice))
            conflicts = set().union(
                *(
                    row[2]
                    for rule, row in zip(rules, choice, strict=True)
                    if rule.mode != "possible"
                )
            )
            cost = loss(
                positive, all_positive - covered
            ) + program.package.execution_policy.conflict_weight * loss(known, conflicts)
            cost += program.package.execution_policy.assumption_weight * hypothesis.assumption_cost
            if best is None or cost < best[0]:
                best = cost, bool(covered)
        necessary_ok = True
        for rule in rules:
            if rule.mode == "necessary" and not any(
                row[0] is True for row in options[rule.pattern_id]
            ):
                necessary_ok = False
        result.append(
            {
                "candidate_id": hypothesis.hypothesis_id,
                "cost": best[0],
                "eligible": best[1] and necessary_ok,
            }
        )
    return sorted(result, key=lambda r: r["candidate_id"])


def atom_path_reference(knowledge, frame):
    """An explicit single-positive-atom baseline, dropping conjunction/conflict.

    Uses the same reachable signature footprint (including diagnostic reverse
    views); unlike an unadapted legacy ranker, every bound observation is retained.
    """
    program = KnowledgeProgram(knowledge)
    ground = Grounding(frame, program)
    rows = []
    for hypothesis in program.hypotheses.values():
        if hypothesis.target_role != frame.task.target_role or not program.is_a(
            ground.resolved_subjects[frame.task.context_subject_id], hypothesis.applies_to_class_id
        ):
            continue
        footprint = set().union(
            *(
                program.footprint(r.pattern_id)
                for r in program.hypothesis_world(hypothesis.hypothesis_id)[3]
            )
        )
        ground.ground(footprint)
        true = {f.fact_id for p in footprint for f in ground.facts[p] if f.value is True}
        if true:
            rows.append(
                {"candidate_id": hypothesis.hypothesis_id, "positive_atom_count": len(true)}
            )
    return sorted(rows, key=lambda r: (-r["positive_atom_count"], r["candidate_id"]))


def flattened_knowledge(knowledge):
    """Remove intermediate states without removing their logical consequences."""
    program = KnowledgeProgram(knowledge)
    data = program.package.model_dump(mode="json")
    expectations = []
    for hypothesis in program.package.hypotheses:
        for i, rule in enumerate(program.hypothesis_world(hypothesis.hypothesis_id)[3]):
            expectations.append(
                {
                    **rule.model_dump(mode="json"),
                    "rule_id": f"flat:{hypothesis.hypothesis_id}:{i}",
                    "from_id": hypothesis.hypothesis_id,
                }
            )
    data.update(effect_rules=[], mechanisms=[], expectation_rules=expectations)
    return KnowledgePackage.model_validate(data)


def freeze_runs(run_paths, output_dir):
    """Freeze actual persisted inputs and their original knowledge, not current seeds."""
    import json
    from pathlib import Path

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for run_index, path in enumerate(run_paths):
        run = json.loads(Path(path).read_text())
        knowledge = KnowledgePackage.model_validate(
            run["summary"]["working_graph_snapshot"]["knowledge"]
        )
        knowledge_path = output / f"run-{run_index:02d}-knowledge.json"
        knowledge_path.write_text(knowledge.model_dump_json(indent=2))
        for case in run["cases"]:
            for query_index, payload in enumerate(case["reasoning_metadata"]["evidence_frames"]):
                frame = EvidenceFrame.model_validate(payload)
                frame_path = output / f"{len(cases):03d}-evidence.json"
                frame_path.write_text(frame.model_dump_json(indent=2))
                cases.append(
                    {
                        "run_id": run["run"]["run_id"],
                        "case_id": case["case_id"],
                        "query_index": query_index,
                        "dataset": case["dataset"],
                        "knowledge": str(knowledge_path.resolve()),
                        "evidence": str(frame_path.resolve()),
                        "source_run": str(Path(path).resolve()),
                    }
                )
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2))
    return manifest
