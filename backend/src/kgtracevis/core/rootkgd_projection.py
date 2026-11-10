"""Representation-invariant projection of logical expectations to physical channels.

Effect rules retain their explicit directed edges. Expectations describe channel
footprints, not extra propagation hops or parallel physical routes. Equivalent
logical spellings merge source witnesses rather than creating extra signal.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque

from kgtracevis.workflows.tep_root_kgd.propagation import default_relation_params

PROJECTION_VERSION = "rootkgd-host-channel.v2"


def source_path(program, edge_ids, start, end=None):
    """Expand only actual source edges; alternatives are never spliced into a main path."""
    nodes, views = [start], []
    for identity in edge_ids:
        edge = program.edges[identity]
        reverse = edge["relation"] in {"INPUT_OF", "DEFINES"}
        head, tail = (edge["tail"], edge["head"]) if reverse else (edge["head"], edge["tail"])
        if head != nodes[-1]:
            raise ValueError("RootKGD source path is not contiguous")
        nodes.append(tail)
        views.append({"edge_id": identity, "reverse": reverse})
    if end is not None and nodes[-1] != end:
        raise ValueError("RootKGD source path has the wrong endpoint")
    sources = set()
    visited = set(nodes)
    for rows in (
        program.package.effect_rules,
        program.package.expectation_rules,
        program.package.observable_definitions,
        program.package.pattern_definitions,
    ):
        for row in rows:
            identities = {
                getattr(row, name, None)
                for name in ("rule_id", "predicate_id", "pattern_id", "definition_id")
            }
            if identities & visited:
                sources.update(row.source_assertion_ids)
    return {
        "nodes": nodes,
        "source_edge_ids": list(edge_ids),
        "source_edge_views": views,
        "source_assertion_ids": sorted(sources),
    }


def effect_source_prefixes(program, source_id):
    """One actual directed effect witness per host, independent of logical patterns."""
    adjacency = defaultdict(list)
    for rule in sorted(program.package.effect_rules, key=lambda r: r.rule_id):
        adjacency[rule.from_id].append(rule)
    paths, queue = {source_id: []}, deque([source_id])
    while queue:
        host = queue.popleft()
        for rule in adjacency[host]:
            if rule.to_id not in paths:
                paths[rule.to_id] = paths[host] + [rule.rule_id + "::from", rule.rule_id + "::to"]
                queue.append(rule.to_id)
    return paths


def project_rootkgd_graph(program, hypotheses, channels):
    nodes = {n["node_id"]: {"entity_id": n["node_id"], **n} for n in program.projection["nodes"]}
    active = set().union(*(program.hypothesis_world(h.hypothesis_id)[0] for h in hypotheses))
    # Preserve every relevant explicit effect relation, not an arbitrary first
    # derivation tree selected while computing logical closure.
    effects = sorted(
        [r for r in program.package.effect_rules if r.from_id in active and r.to_id in active],
        key=lambda r: r.rule_id,
    )
    adjacency = defaultdict(set)
    for rule in effects:
        adjacency[rule.from_id].add(rule.to_id)
    reachable = {}

    def descendants(host):
        if host not in reachable:
            seen, remaining = set(), list(adjacency[host])
            while remaining:
                current = remaining.pop()
                if current not in seen:
                    seen.add(current)
                    remaining.extend(adjacency[current])
            reachable[host] = seen
        return reachable[host]

    def strictly_downstream(parent, child):
        # Cyclic physical hosts are not arbitrarily ordered or all eliminated.
        return child in descendants(parent) and parent not in descendants(child)

    channel_entities = {
        b.target_id
        for b in program.package.subject_bindings
        if b.namespace == "tep_braatz.channel" and b.external_id in channels
    }
    links = defaultdict(list)
    for rule in sorted(program.package.expectation_rules, key=lambda r: r.rule_id):
        if rule.from_id not in active:
            continue
        for predicate in sorted(program.footprint(rule.pattern_id)):
            definition = program.observables[predicate]
            entity = getattr(definition.subject_selector, "entity_id", None)
            if entity not in channel_entities:
                continue
            branch = next(b for b in program.branches(rule.pattern_id) if predicate in b.predicates)
            _, edges = program.observation_path(predicate, rule.pattern_id, branch)
            path = source_path(
                program,
                [
                    rule.rule_id + "::from",
                    rule.rule_id + "::to",
                    *reversed(edges),
                    predicate + "::binding",
                ],
                rule.from_id,
                entity,
            )
            links[(rule.from_id, entity)].append(
                {
                    "host_id": rule.from_id,
                    "expectation_rule_id": rule.rule_id,
                    "pattern_id": rule.pattern_id,
                    "predicate_ids": [predicate],
                    **path,
                }
            )
    by_channel = defaultdict(set)
    for host, channel in links:
        by_channel[channel].add(host)
    retained = {
        (host, channel)
        for host, channel in links
        if not any(strictly_downstream(host, other) for other in by_channel[channel])
    }
    edges, logical = {}, {}

    def add(identity, host, target, family, witness, alternatives=()):
        edges[identity] = {
            "edge_id": identity,
            "head_id": host,
            "tail_id": target,
            "relation_family": family,
            "edge_weight": 1.0,
        }
        logical[identity] = {
            "source_edge_ids": witness["source_edge_ids"],
            "predicate_ids": witness.get("predicate_ids", []),
            "source_path_alternatives": list(alternatives),
        }

    for rule in effects:
        add(
            "rootkgd:effect:" + rule.rule_id,
            rule.from_id,
            rule.to_id,
            "FAULT_SOURCE",
            source_path(
                program, [rule.rule_id + "::from", rule.rule_id + "::to"], rule.from_id, rule.to_id
            ),
        )
    projected_links = []
    for host, channel in sorted(retained):
        witnesses = links[(host, channel)]
        alternatives = [dict(w, kind="equivalent_host_channel_expectation") for w in witnesses[1:]]
        for parent in sorted(by_channel[channel]):
            if (parent, channel) not in retained and strictly_downstream(parent, host):
                alternatives.extend(
                    dict(w, kind="redundant_upstream_expectation") for w in links[(parent, channel)]
                )
        identity = "rootkgd:observation:" + json.dumps([host, channel], separators=(",", ":"))
        add(identity, host, channel, "OBSERVATION", witnesses[0], alternatives)
        projected_links.append(
            {
                "edge_id": identity,
                "host_id": host,
                "channel_entity_id": channel,
                "primary_source_path": witnesses[0],
                "source_path_alternatives": alternatives,
            }
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
        "projection": {
            "version": PROJECTION_VERSION,
            "effect_edge_count": len(effects),
            "host_channel_edge_count": len(projected_links),
            "redundant_upstream_link_count": len(links) - len(retained),
            "host_channel_links": projected_links,
        },
    }, logical
