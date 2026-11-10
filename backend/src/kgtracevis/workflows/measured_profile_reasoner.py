"""Measured wafer predicates and current-graph Root-KGD propagation, with actual paths."""

from __future__ import annotations

from collections import defaultdict

from kgtracevis.core.result import RankedRootCause, RcaReasoningResult
from kgtracevis.kg.visual_profile_compiler import CAUSE_RELATIONS, edge_reference_map
from kgtracevis.schema.measured_reasoning import (
    MeasuredProfileBundle,
    ProcessMeasurements,
    WaferMeasurements,
    validate_measured_profiles,
)
from kgtracevis.workflows.tep_root_kgd.propagation import (
    default_relation_params,
    simulate_propagation,
    trace_path,
)


class MeasuredProfileReasoner:
    def __init__(self, profiles: MeasuredProfileBundle, *, graph_id=None):
        self.profiles, self.graph_id = profiles, graph_id

    def reason_root_causes(self, evidence, *, graph, linked_entities, top_k=5):
        del linked_entities
        if evidence.dataset != self.profiles.dataset:
            raise ValueError("selected working graph belongs to another dataset")
        validate_measured_profiles(self.profiles, graph)
        is_tep = evidence.dataset == "tep"
        kind = "process-measurements.v1" if is_tep else "wafer-measurements.v1"
        observations = [o for o in evidence.observations if o.value_type == kind]
        method = "process_graph_rbc" if is_tep else "wafer_spatial_profile"
        traces, candidates, links = [], {}, {}
        edge_map = edge_reference_map(graph)
        propagation = _propagation_graph(graph) if is_tep else None
        for obs in observations:
            measured = (ProcessMeasurements if is_tep else WaferMeasurements).model_validate(
                obs.value
            )
            channels = {c.channel: c for c in measured.channels} if is_tep else {}
            for profile in self.profiles.profiles:
                checks = [_check(c, measured, channels, obs.obs_id) for c in profile.conditions]
                conflicts = [_check(c, measured, channels, obs.obs_id) for c in profile.conflicts]
                required = [c for c in checks if c["required"]]
                tested = required or checks
                statuses = [c["result"] for c in tested]
                if profile.match_mode == "all":
                    status = (
                        "not_matched"
                        if "not_matched" in statuses
                        else "insufficient_evidence"
                        if "missing" in statuses
                        else "matched"
                    )
                else:
                    status = (
                        "matched"
                        if "matched" in statuses
                        else "insufficient_evidence"
                        if "missing" in statuses
                        else "not_matched"
                    )
                if any(c["result"] == "matched" for c in conflicts):
                    status = "not_matched"
                if is_tep and measured.residual_energy <= measured.normal_energy_limit:
                    status = "not_matched"
                if not is_tep and measured.failed_die_count == 0:
                    status = "not_matched"
                trace = dict(
                    profile_id=profile.profile_id,
                    obs_id=obs.obs_id,
                    anchor_id=profile.anchor_id,
                    conditions=checks,
                    conflicts=conflicts,
                    status=status,
                    reference_id=measured.reference_id if is_tep else "wm811k_012",
                    candidate_results=[],
                )
                traces.append(trace)
                if status != "matched":
                    continue
                matched = [c for c in checks if c["result"] == "matched"]
                for candidate_id in profile.candidate_ids:
                    candidate_trace = {k: v for k, v in trace.items() if k != "candidate_results"}
                    candidate_trace["candidate_id"] = candidate_id
                    paths, alignment, components = [], 0.0, {}
                    simulation = (
                        simulate_propagation(propagation, candidate_id, seed_score=1)
                        if is_tep
                        else None
                    )
                    if is_tep:
                        # Every channel participates, not just the displayed top contributors.
                        for channel in measured.channels:
                            variable = _variable_node(graph, channel.channel)
                            if variable is not None:
                                gain = float(simulation["node_scores"].get(variable, 0))
                                components[channel.channel] = channel.contribution * gain
                        alignment = sum(components.values())
                    path_checks = list(matched)
                    if is_tep:
                        already_bound = {c["concept_id"] for c in matched}
                        numeric_support = []
                        for channel in measured.channels:
                            variable = _variable_node(graph, channel.channel)
                            if (
                                not variable
                                or variable in already_bound
                                or components.get(channel.channel, 0) <= 0
                            ):
                                continue
                            parent = simulation["best_parent_edge"].get(variable)
                            if not parent:
                                continue
                            numeric_support.append(
                                dict(
                                    feature="process.contribution",
                                    channel=channel.channel,
                                    concept_id=variable,
                                    source_edge_id=propagation["edges"][parent]["origin"][
                                        "edge_id"
                                    ],
                                    actual=channel.contribution,
                                    weighted_component=components[channel.channel],
                                    result="used",
                                    required=False,
                                    obs_id=obs.obs_id,
                                    group="process_window",
                                    measurement_source=measured.reference_id,
                                    interpretation=(
                                        "RBC component used in numerical score; "
                                        "not a satisfied mean-shift predicate"
                                    ),
                                )
                            )
                        candidate_trace["numeric_support"] = numeric_support
                        path_checks.extend(numeric_support)
                    for check in path_checks:
                        concept_id = check["concept_id"]
                        if is_tep:
                            edge_ids = trace_path(
                                candidate_id,
                                concept_id,
                                simulation["best_parent_edge"],
                                propagation["edges"],
                            )
                            if not edge_ids:
                                continue
                            source_edges = [propagation["edges"][e]["origin"] for e in edge_ids]
                            nodes = [candidate_id]
                            for edge_id in edge_ids:
                                nodes.append(propagation["edges"][edge_id]["tail_id"])
                            # Diagnostic path is explicitly a reverse view of physical propagation.
                            nodes = list(reversed(nodes))
                            source_edges = [_reverse_view(e) for e in reversed(source_edges)]
                        else:
                            cause_edges = [
                                e
                                for e in graph.edges
                                if e.head == profile.anchor_id
                                and e.tail == candidate_id
                                and e.relation in CAUSE_RELATIONS
                                and e.review_status != "rejected"
                            ]
                            if not cause_edges:
                                continue
                            binding = edge_map[check["source_edge_id"]]
                            source_edges, nodes = [], [profile.anchor_id, candidate_id]
                            if concept_id != profile.anchor_id:
                                if {binding.head, binding.tail} != {profile.anchor_id, concept_id}:
                                    continue
                                source_edges.append(
                                    binding.model_dump()
                                    if binding.head == concept_id
                                    else _reverse_view(binding.model_dump())
                                )
                                nodes.insert(0, concept_id)
                            source_edges.append(cause_edges[0].model_dump())
                        links[(obs.obs_id, concept_id)] = dict(
                            link_id=f"link:{obs.obs_id}:{concept_id}",
                            obs_id=obs.obs_id,
                            field=check["feature"],
                            mention=str(check["actual"]),
                            selected_entity_id=concept_id,
                            selected_entity_name=graph.nodes[concept_id].name,
                            match_type="measured_binding",
                            score=1.0,
                            ambiguous=False,
                            candidates=[],
                        )
                        paths.append(
                            dict(
                                path_id=f"path:{evidence.case_id}:{obs.obs_id}:{profile.profile_id}:{candidate_id}:{concept_id}",
                                source_entity_id=nodes[0],
                                target_entity_id=candidate_id,
                                nodes=nodes,
                                node_names=[graph.nodes[n].name for n in nodes],
                                relations=[e["relation"] for e in source_edges],
                                length=len(source_edges),
                                score=alignment if is_tep else 1.0,
                                confidence=None,
                                source_edges=source_edges,
                                source_edge_ids=[e["edge_id"] for e in source_edges],
                                support_obs_ids=[obs.obs_id],
                                supporting_evidence=[obs.obs_id],
                                support_conditions=[check],
                                knowledge_evidence=[e["evidence"] for e in source_edges],
                            )
                        )
                    if not paths or (is_tep and alignment <= 0):
                        continue
                    groups = {c["group"] for c in matched}
                    score = alignment if is_tep else float(len(groups))
                    candidate_trace.update(
                        score=score,
                        numeric_components=components,
                        propagation_edge_flow=simulation["edge_flow"] if is_tep else {},
                    )
                    row = candidates.setdefault(
                        candidate_id, dict(score=0.0, paths={}, traces=[], obs_ids=set())
                    )
                    row["score"] = max(row["score"], score)
                    row["paths"].update({p["path_id"]: p for p in paths})
                    row["traces"].append(candidate_trace)
                    trace["candidate_results"].append(candidate_trace)
                    row["obs_ids"].add(obs.obs_id)
        ranked = []
        for index, (cid, row) in enumerate(
            sorted(candidates.items(), key=lambda item: (-item[1]["score"], item[0]))[:top_k], 1
        ):
            paths = list(row["paths"].values())
            ranked.append(
                RankedRootCause(
                    ranking_id=f"ranking:{evidence.case_id}:{cid}",
                    rank=index,
                    candidate_id=cid,
                    candidate_name=graph.nodes[cid].name,
                    candidate_label=graph.nodes[cid].label,
                    candidate_role="plausible_mechanism",
                    score=row["score"],
                    scoring_method=method,
                    support_evidence_ids=sorted(row["obs_ids"]),
                    explanation_paths=paths,
                    supporting_edges=list(
                        {e["edge_id"]: e for p in paths for e in p["source_edges"]}.values()
                    ),
                    scoring_details=dict(
                        profile_matches=row["traces"],
                        reason=(
                            "完整通道 RBC 贡献经当前图的方向、权重和衰减传播，"
                            "与多变量条件联合支持该候选。"
                            if is_tep
                            else "实际 die 空间统计与独立分类观测满足图上条件；这里只给出机制候选。"
                        ),
                        score_meaning="sum(full_channel_contribution * current_graph_propagation)"
                        if is_tep
                        else "matched independent feature groups",
                    ),
                )
            )
        outcome = (
            "matched"
            if ranked
            else "not_applicable"
            if not self.profiles.profiles
            else "insufficient_evidence"
            if not observations or any(t["status"] == "insufficient_evidence" for t in traces)
            else "no_match"
        )
        return RcaReasoningResult(
            case_id=evidence.case_id,
            ranked_root_causes=ranked,
            top_k_paths=[p for r in ranked for p in r.explanation_paths],
            scoring_method=method,
            outcome=outcome,
            linked_entities=list(links.values()),
            metadata=dict(
                reasoner=method,
                reasoner_adapter=method,
                reasoning_profile_id=f"{evidence.dataset}_measured_graph_v1",
                selection_mode="explicit",
                fallback_applied=False,
                graph_id=self.graph_id,
                trace=traces,
                outcome=outcome,
                profile_issues=self.profiles.issues,
            ),
        )


def _check(condition, measured, channels, obs_id):
    if condition.channel:
        channel = channels.get(condition.channel)
        actual = getattr(channel, condition.feature.split(".")[1], None)
    else:
        actual = getattr(measured, condition.feature.split(".")[1], None)
    if actual is None:
        result = "missing"
    else:
        v = condition.value
        match = (
            actual >= v
            if condition.op == "gte"
            else actual <= v
            if condition.op == "lte"
            else abs(actual) >= v
            if condition.op == "abs_gte"
            else actual in v
            if condition.op == "in"
            else actual == v
        )
        result = "matched" if match else "not_matched"
    return {
        **condition.model_dump(mode="json"),
        "actual": actual,
        "result": result,
        "obs_id": obs_id,
        "group": "process_window"
        if condition.channel
        else "classifier"
        if condition.feature == "wafer.classifier_pattern"
        else "spatial",
        "measurement_source": measured.reference_id if condition.channel else "wm811k_map_012",
    }


def _variable_node(graph, channel):
    normalized = channel.lower().replace("_", "")
    return next(
        (
            node.id
            for node in graph.nodes.values()
            if node.label.lower() == "variable"
            and any(t.lower().replace("_", "") == normalized for t in node.searchable_terms)
        ),
        None,
    )


def _propagation_graph(graph):
    outgoing, edges = defaultdict(list), {}
    for edge in graph.edges:
        if not edge.propagation_enabled or edge.review_status == "rejected":
            continue
        family = edge.relation_family or "OBSERVATION"
        if family not in default_relation_params():
            raise ValueError(f"unregistered propagation family: {family}")
        if edge.propagation_direction not in {"forward", "reverse", "both"}:
            raise ValueError("invalid propagation direction")
        origin = edge.model_dump()
        for reverse in (
            [False, True]
            if edge.propagation_direction == "both"
            else [edge.propagation_direction == "reverse"]
        ):
            h, t = (edge.tail, edge.head) if reverse else (edge.head, edge.tail)
            eid = ("reverse:" if reverse else "") + edge.edge_id
            row = dict(
                edge_id=eid,
                head_id=h,
                tail_id=t,
                relation_family=family,
                edge_weight=max(
                    0.0, min(1.0, edge.edge_weight if edge.edge_weight is not None else edge.weight)
                )
                * edge.attenuation,
                origin=_reverse_view(origin) if reverse else origin,
            )
            outgoing[h].append(row)
            edges[eid] = row
    return dict(
        nodes=graph.nodes,
        edges=edges,
        outgoing=dict(outgoing),
        relation_params=default_relation_params(),
    )


def _reverse_view(edge):
    return {
        **edge,
        "head": edge["tail"],
        "tail": edge["head"],
        "relation": "DIAGNOSTIC_SUPPORT",
        "edge_id": "view:" + edge["edge_id"],
        "origin_edge_id": edge["edge_id"],
        "origin_edge": edge,
        "interpretation": "diagnostic reverse view of current knowledge; not physical causation",
    }
