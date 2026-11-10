"""RootKGD structural propagation on the selected canonical working knowledge.

Reuses the original propagation and structural ranking functions, not its old
fixed graph, fault-anchor memories or fault-family tie-break rules. Conditions
are grounded for inspection; propagation compares the complete 52-channel PCA
residual vector to the graph's expected affected-channel vector.
"""

from __future__ import annotations

import math
from collections import defaultdict

from kgtracevis.core.unified_grounding import Grounding
from kgtracevis.kg.unified_compiler import KnowledgeProgram
from kgtracevis.schema.unified_evidence import EvidenceFrame
from kgtracevis.workflows.tep_root_kgd.propagation import (
    default_relation_params,
    simulate_propagation,
    trace_path,
)
from kgtracevis.workflows.tep_root_kgd.rca_signal_utils import dense_cosine_similarity
from kgtracevis.workflows.tep_root_kgd.root_kgd import _pattern_entropy, ranking_score

CHANNELS = [f"xmeas_{i}" for i in range(1, 42)] + [f"xmv_{i}" for i in range(1, 12)]


class RootKGDReasoner:
    def __init__(self, knowledge):
        self.program = KnowledgeProgram(knowledge)

    def analyze(self, evidence, *, top_k=5):
        frame = EvidenceFrame.model_validate(
            evidence.model_dump(mode="json") if isinstance(evidence, EvidenceFrame) else evidence
        )
        if top_k < 1 or isinstance(top_k, bool):
            raise ValueError("top_k must be a positive integer")
        if frame.task.target_role != "mechanism":
            raise ValueError("RootKGD 图传播仅支持 TEP 过程机制诊断。")
        grounding = Grounding(frame, self.program)
        vector, observed = self._contributions(frame)
        context = grounding.resolved_subjects[frame.task.context_subject_id]
        hypotheses = [
            h
            for h in self.program.hypotheses.values()
            if h.target_role == "mechanism" and self.program.is_a(context, h.applies_to_class_id)
        ]
        graph, logical_paths = self._propagation_graph(hypotheses)
        grounding.ground(set(self.program.observables))
        facts = [f.to_json(self.program) for rows in grounding.facts.values() for f in rows]
        result = {
            "schema_version": "rootlens-reasoning-result.v2",
            "case_id": frame.case_id,
            "graph_id": self.program.package.graph_id,
            "scoring_method": "tep_rootkgd_propagation_v1",
            "outcome": "no_match",
            "candidate_pool": [h.hypothesis_id for h in hypotheses],
            "grounded_facts": facts,
            "observed_patterns": [],
            "candidate_evaluations": [],
            "unassessed_candidates": [],
            "ranked_root_causes": [],
            "top_k_paths": [],
            "proof_graph": {"nodes": [], "edges": []},
            "unused_observations": [],
            "propagation": {
                "channel_order": CHANNELS,
                "observed_contribution_vector": vector,
                "reused_functions": [
                    "simulate_propagation",
                    "trace_path",
                    "dense_cosine_similarity",
                    "_pattern_entropy",
                    "ranking_score",
                ],
                "max_hops": 12,
                "seed_score": 0.35,
                "condition_semantics": "conditions_grounded_for_trace; structural_vector_ranking",
                "memory_enabled": False,
                "fault_label_used": False,
                "scoring_input_obs_ids": sorted(observed.values()),
            },
        }
        anomaly = [
            o
            for o in frame.observations
            if o.feature_id == "detection.anomaly_present"
            and o.subject_id == frame.task.context_subject_id
            and o.scope_id == frame.task.scope_id
            and o.status == "observed"
            and o.value is not None
            and o.value.kind == "boolean"
        ]
        if len(anomaly) != 1:
            result.update(outcome="insufficient_evidence", reason="missing_unambiguous_normal_gate")
            return result
        if not anomaly[0].value.boolean:
            result.update(outcome="no_match", reason="normal_reference_gate_is_false")
            return result
        if not hypotheses:
            result.update(outcome="not_applicable", reason="no_applicable_process_hypotheses")
            return result
        channel_nodes = {
            b.external_id: b.target_id
            for b in self.program.package.subject_bindings
            if b.namespace == "tep_braatz.channel" and b.external_id in CHANNELS
        }
        if len(set(channel_nodes.values())) != len(channel_nodes):
            raise ValueError("RootKGD requires one stable entity per TEP channel")
        rows = []
        for hypothesis in sorted(hypotheses, key=lambda h: h.hypothesis_id):
            simulation = simulate_propagation(
                graph, hypothesis.hypothesis_id, seed_score=0.35, max_hops=12
            )
            propagated = [
                simulation["node_scores"].get(channel_nodes.get(c), 0.0) for c in CHANNELS
            ]
            if not any(propagated):
                result["unassessed_candidates"].append(
                    {
                        "candidate_id": hypothesis.hypothesis_id,
                        "reason": "no_path_to_bound_channels",
                    }
                )
                continue
            cosine = dense_cosine_similarity(propagated, vector)
            active, entropy = _pattern_entropy(dict(zip(CHANNELS, propagated, strict=True)))
            threshold = max(propagated) * 0.10
            covered = sum(v for v, s in zip(vector, propagated, strict=True) if s >= threshold)
            score = ranking_score(
                root_score=cosine,
                covered_contribution_mass=covered,
                pattern_entropy=entropy,
                candidate_type="Hypothesis",
                candidate_role="mechanism",
            )
            details = {
                "cosine_similarity": cosine,
                "covered_contribution_mass": covered,
                "uncovered_contribution_mass": max(0.0, 1.0 - covered),
                "propagation_entropy": entropy,
                "active_channel_count": active,
                "coverage_penalty": 0.12 * covered,
                "entropy_penalty": 0.03 * entropy,
                "structural_score": score,
                "memory_bonus": 0.0,
                "fault_family_adjustment": 0.0,
                "propagated_channel_vector": propagated,
                "observed_channel_vector": vector,
                "channel_order": CHANNELS,
                "formula": "cosine - 0.12 * covered_mass - 0.03 * entropy",
            }
            paths = self._paths(
                frame,
                hypothesis,
                graph,
                simulation,
                logical_paths,
                channel_nodes,
                observed,
                vector,
                propagated,
            )
            rows.append(
                {
                    "candidate_id": hypothesis.hypothesis_id,
                    "candidate_name": hypothesis.label,
                    "candidate_role": "mechanism",
                    "score": score,
                    "confidence": None,
                    "status": "structural_match",
                    "eligible_for_ranking": covered > 0 and cosine > 0,
                    "support_obs_ids": sorted({o for p in paths for o in p["support_obs_ids"]}),
                    "scoring_details": details,
                    "explanation_paths": paths,
                }
            )
        rows.sort(key=lambda r: (-r["score"], r["candidate_id"]))
        eligible = [r for r in rows if r["eligible_for_ranking"]]
        selected = eligible[:top_k]
        if selected:
            cutoff = selected[-1]["score"]
            selected = [r for r in eligible if r["score"] >= cutoff - 1e-9]
        rank, previous = 0, None
        for row in selected:
            if previous is None or abs(row["score"] - previous) > 1e-9:
                rank += 1
            previous = row["score"]
            row["rank"] = rank
        result["candidate_evaluations"] = rows
        result["ranked_root_causes"] = selected
        result["top_k_paths"] = [p for r in selected for p in r["explanation_paths"]]
        # Every contribution participates in the 52-D cosine norm, including
        # channels with zero predicted signal. Displaying eight paths must not
        # mislabel the remaining measured contributions as unused.
        used = set(observed.values())
        result["unused_observations"] = [
            {"obs_id": o.obs_id, "reason": "not_a_propagation_contribution_input"}
            for o in frame.observations
            if o.obs_id not in used and o != anomaly[0]
        ]
        if selected:
            result["outcome"] = (
                "ambiguous" if len(selected) > 1 and selected[1]["rank"] == 1 else "supported"
            )
        result["propagation"]["graph_channel_coverage"] = {
            "bound_channels": sorted(channel_nodes),
            "unbound_channels": [c for c in CHANNELS if c not in channel_nodes],
            "unbound_contribution_mass": sum(
                vector[i] for i, c in enumerate(CHANNELS) if c not in channel_nodes
            ),
            "unreached_channels": [
                c
                for i, c in enumerate(CHANNELS)
                if not any(
                    row["scoring_details"]["propagated_channel_vector"][i] > 0 for row in rows
                )
            ],
            "unreached_contribution_mass": sum(
                vector[i]
                for i in range(52)
                if not any(
                    row["scoring_details"]["propagated_channel_vector"][i] > 0 for row in rows
                )
            ),
        }
        result["proof_graph"] = self._proof_graph(result["top_k_paths"])
        return result

    def _contributions(self, frame):
        if frame.task.reference_id is None or not any(
            r.reference_id == frame.task.reference_id and r.kind == "normal_standardization"
            for r in frame.references
        ):
            raise ValueError("RootKGD 需要完整正常参考与标准化来源，不能使用无参考贡献。")
        subjects = {s.subject_id: s for s in frame.subjects}
        values, observed = {}, {}
        for o in frame.observations:
            if o.feature_id != "residual.contribution" or o.scope_id != frame.task.scope_id:
                continue
            subject = subjects[o.subject_id]
            channel = subject.external_id
            if subject.external_namespace != "tep_braatz.channel" or channel not in CHANNELS:
                continue
            if (
                o.status != "observed"
                or o.value is None
                or o.value.kind != "number"
                or o.value.unit != "1"
                or o.reference_id != frame.task.reference_id
            ):
                raise ValueError(f"invalid referenced contribution: {channel}")
            if channel in values:
                raise ValueError(f"duplicate contribution channel: {channel}")
            if not 0 <= o.value.number <= 1:
                raise ValueError(f"contribution outside [0,1]: {channel}")
            values[channel], observed[channel] = o.value.number, o.obs_id
        if set(values) != set(CHANNELS):
            raise ValueError("RootKGD 需要全部 52 个 TEP 通道的贡献向量。")
        total = sum(values.values())
        normal_gate = any(
            o.feature_id == "detection.anomaly_present"
            and o.subject_id == frame.task.context_subject_id
            and o.scope_id == frame.task.scope_id
            and o.status == "observed"
            and o.value is not None
            and o.value.kind == "boolean"
            and not o.value.boolean
            for o in frame.observations
        )
        if total == 0 and normal_gate:
            return [0.0] * 52, observed
        if total <= 0 or not math.isclose(total, 1.0, abs_tol=1e-5):
            raise ValueError("RootKGD contributions must be normalized to unit mass")
        return [values[c] for c in CHANNELS], observed

    def _propagation_graph(self, hypotheses):
        """Collapse logical rule plumbing, preserving exact source projection edge paths.

        Each pattern has one edge per stable channel. Multiple mean/std/slope atoms
        on that channel are retained as trace alternatives, never added as signals.
        """
        nodes = {
            n["node_id"]: {"entity_id": n["node_id"], **n} for n in self.program.projection["nodes"]
        }
        edges, logical = {}, {}
        channel_entities = {
            b.target_id
            for b in self.program.package.subject_bindings
            if b.namespace == "tep_braatz.channel" and b.external_id in CHANNELS
        }

        def add(identity, head, tail, family, source_edges, predicates=()):
            edges[identity] = {
                "edge_id": identity,
                "head_id": head,
                "tail_id": tail,
                "relation_family": family,
                "edge_weight": 1.0,
            }
            logical[identity] = {"source_edge_ids": source_edges, "predicate_ids": list(predicates)}

        active_effects, active_expectations = set(), set()
        for h in hypotheses:
            world = self.program.hypothesis_world(h.hypothesis_id)
            # The world's rule lists are canonical and source-bound.
            for e in world[2]:
                active_effects.add(e.rule_id)
            for e in world[3]:
                active_expectations.add(e.rule_id)
        for rule in self.program.package.effect_rules:
            if rule.rule_id in active_effects:
                add(
                    rule.rule_id,
                    rule.from_id,
                    rule.to_id,
                    "FAULT_SOURCE",
                    [rule.rule_id + "::from", rule.rule_id + "::to"],
                )
        patterns = set()
        for rule in self.program.package.expectation_rules:
            if rule.rule_id in active_expectations:
                add(
                    rule.rule_id,
                    rule.from_id,
                    rule.pattern_id,
                    "OBSERVATION",
                    [rule.rule_id + "::from", rule.rule_id + "::to"],
                )
                patterns.add(rule.pattern_id)
        for pattern_id in sorted(patterns):
            by_channel = defaultdict(list)
            for predicate in sorted(self.program.footprint(pattern_id)):
                definition = self.program.observables[predicate]
                subject = getattr(definition.subject_selector, "entity_id", None)
                if subject in channel_entities:
                    by_channel[subject].append(predicate)
            for subject, predicates in sorted(by_channel.items()):
                predicate = predicates[0]
                branch = next(
                    b for b in self.program.branches(pattern_id) if predicate in b.predicates
                )
                _, source_edges = self.program.observation_path(predicate, pattern_id, branch)
                add(
                    pattern_id + "::channel::" + subject,
                    pattern_id,
                    subject,
                    "OBSERVATION",
                    list(reversed(source_edges)) + [predicate + "::binding"],
                    predicates,
                )
        outgoing, incoming = defaultdict(list), defaultdict(list)
        for edge in edges.values():
            outgoing[edge["head_id"]].append(edge)
            incoming[edge["tail_id"]].append(edge)
        return {
            "nodes": nodes,
            "edges": edges,
            "outgoing": outgoing,
            "incoming": incoming,
            "relation_params": default_relation_params(),
        }, logical

    def _paths(
        self,
        frame,
        hypothesis,
        graph,
        simulation,
        logical,
        channel_nodes,
        observed,
        vector,
        propagated,
    ):
        paths = []
        for index in sorted(range(52), key=lambda i: (-vector[i] * propagated[i], CHANNELS[i])):
            channel = CHANNELS[index]
            target = channel_nodes.get(channel)
            if target is None or vector[index] <= 0 or propagated[index] <= 0:
                continue
            reduced = trace_path(
                hypothesis.hypothesis_id,
                target,
                simulation["best_parent_edge"],
                graph["edges"],
                max_depth=12,
            )
            if not reduced:
                continue
            views, source_ids, predicates = [], [], []
            for identity in reduced:
                step = logical[identity]
                predicates.extend(step["predicate_ids"])
                for edge_id in step["source_edge_ids"]:
                    edge = self.program.edges[edge_id]
                    reverse = edge["relation"] in {"INPUT_OF", "DEFINES"}
                    views.append({"edge_id": edge_id, "reverse": reverse})
                    source_ids.append(edge_id)
            reduced_nodes = [hypothesis.hypothesis_id]
            for edge_id in reduced:
                node_id = graph["edges"][edge_id]["tail_id"]
                reduced_nodes.append(node_id)
            full_nodes = [hypothesis.hypothesis_id]
            for view in views:
                edge = self.program.edges[view["edge_id"]]
                head, tail = (
                    (edge["tail"], edge["head"])
                    if view["reverse"]
                    else (edge["head"], edge["tail"])
                )
                if head != full_nodes[-1]:
                    raise ValueError("RootKGD source path is not contiguous")
                full_nodes.append(tail)
            names = [graph["nodes"][n].get("label", n) for n in full_nodes]
            assertion_ids = set()
            for rows in (
                self.program.package.effect_rules,
                self.program.package.expectation_rules,
                self.program.package.observable_definitions,
                self.program.package.pattern_definitions,
            ):
                for row in rows:
                    identity = getattr(row, "rule_id", None) or getattr(row, "predicate_id", None)
                    identity = identity or getattr(row, "pattern_id", None)
                    if identity in reduced or identity in predicates or identity in reduced_nodes:
                        assertion_ids.update(row.source_assertion_ids)
            paths.append(
                {
                    "path_id": f"rootkgd:{frame.case_id}:{hypothesis.hypothesis_id}:{channel}",
                    "nodes": full_nodes,
                    "node_names": names,
                    "source_edge_ids": source_ids,
                    "source_edge_views": views,
                    "source_edges": [self.program.edges[i] for i in source_ids],
                    "source_assertion_ids": sorted(assertion_ids),
                    "support_obs_ids": [observed[channel]],
                    "required_joint_fact_ids": [],
                    "channel": channel,
                    "predicate_ids": sorted(set(predicates)),
                    "propagated_signal": propagated[index],
                    "observed_contribution": vector[index],
                    "scope_id": frame.task.scope_id,
                    "reason": (
                        "候选沿当前知识关系传播至此通道；传播向量与全通道残差贡献进行结构比较。"
                    ),
                    "interpretation": "structural_propagation_support_not_joint_condition_proof",
                }
            )
            if len(paths) >= 8:
                break
        return paths

    @staticmethod
    def _proof_graph(paths):
        nodes, edges = {}, {}
        for path in paths:
            for identity, name in zip(path["nodes"], path["node_names"], strict=True):
                nodes[identity] = {"node_id": identity, "label": name}
            for source in path["source_edges"]:
                edges[source["edge_id"]] = source
        return {"nodes": list(nodes.values()), "edges": list(edges.values())}
