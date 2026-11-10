"""Compile executable knowledge into indices, finite proofs and a graph projection."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

from kgtracevis.schema.unified_knowledge import (
    AllExpression,
    AnyExpression,
    AtLeastExpression,
    KnowledgePackage,
    expression_refs,
)


class SearchIncomplete(RuntimeError):
    """A declared search budget was exhausted, rather than an empty diagnosis."""


@dataclass(frozen=True)
class SearchLimits:
    candidates: int = 128
    branches: int = 256
    combinations: int = 2048
    active_states: int = 1024

    def __post_init__(self):
        if min(self.candidates, self.branches, self.combinations, self.active_states) < 1:
            raise ValueError("search limits must be positive")


@dataclass(frozen=True)
class ProofBranch:
    predicates: frozenset[str]
    # Each definition retains its own join even after nested expressions expand.
    joins: tuple[tuple[str, frozenset[str]], ...] = ()


class KnowledgeProgram:
    """One immutable-at-use compiled snapshot; dataset names are not dispatch keys."""

    def __init__(self, package: KnowledgePackage | dict, *, limits: SearchLimits | None = None):
        payload = (
            package.model_dump(mode="json") if isinstance(package, KnowledgePackage) else package
        )
        self.package = KnowledgePackage.model_validate(payload)
        self.limits = limits or SearchLimits()
        self.entities = {x.entity_id: x for x in self.package.entities}
        self.features = {x.feature_id: x for x in self.package.feature_registry}
        self.observables = {x.predicate_id: x for x in self.package.observable_definitions}
        self.patterns = {x.pattern_id: x for x in self.package.pattern_definitions}
        self.hypotheses = {x.hypothesis_id: x for x in self.package.hypotheses}
        self.bindings = {
            (x.namespace, x.external_id): x.target_id for x in self.package.subject_bindings
        }
        self.value_bindings = {}
        for binding in self.package.value_bindings:
            self.value_bindings.setdefault((binding.feature_id, binding.procedure_model_id), {})[
                binding.external_value
            ] = binding
        self._branches: dict[str, tuple[ProofBranch, ...]] = {}
        self.projection = project_knowledge(self.package)
        self.edges = {x["edge_id"]: x for x in self.projection["edges"]}

    def is_a(self, actual: str | None, expected: str) -> bool:
        remaining, seen = [actual], set()
        while remaining:
            current = remaining.pop()
            if current == expected:
                return True
            if current in seen:
                continue
            seen.add(current)
            remaining.extend(
                r.tail
                for r in self.package.relations
                if r.head == current and r.relation == "SUBCLASS_OF"
            )
        return False

    def hypothesis_world(self, hypothesis_id: str):
        active, parents, rules = {hypothesis_id}, {}, []
        changed = True
        while changed:
            changed = False
            for rule in sorted(self.package.effect_rules, key=lambda r: r.rule_id):
                if rule.from_id in active and rule.to_id not in active:
                    if len(active) >= self.limits.active_states:
                        raise SearchIncomplete("active-state limit exceeded")
                    active.add(rule.to_id)
                    parents[rule.to_id] = rule
                    rules.append(rule)
                    changed = True
        expectations = sorted(
            (r for r in self.package.expectation_rules if r.from_id in active),
            key=lambda r: r.rule_id,
        )
        return active, parents, rules, expectations

    def footprint(self, pattern_id: str, seen: frozenset[str] = frozenset()) -> set[str]:
        if pattern_id in seen:
            return set()
        refs = expression_refs(self.patterns[pattern_id].body)
        result = refs & self.observables.keys()
        for reference in refs & self.patterns.keys():
            result |= self.footprint(reference, seen | {pattern_id})
        return result

    def branches(self, pattern_id: str) -> tuple[ProofBranch, ...]:
        if pattern_id not in self._branches:
            self._branches[pattern_id] = tuple(self._pattern_branches(pattern_id, frozenset()))
        return self._branches[pattern_id]

    def _pattern_branches(self, pattern_id, seen):
        if pattern_id in seen:
            # A circular definition supplies no finite proof of its own truth.
            return []
        definition = self.patterns[pattern_id]
        return [
            ProofBranch(b.predicates, b.joins + ((definition.definition_id, b.predicates),))
            for b in self._expression_branches(definition.body, seen | {pattern_id})
        ]

    def _expression_branches(self, expression, seen):
        if isinstance(expression, str):
            if expression in self.observables:
                return [ProofBranch(frozenset({expression}))]
            return self._pattern_branches(expression, seen)
        if isinstance(expression, AllExpression):
            groups = [expression.all]
        elif isinstance(expression, AnyExpression):
            groups = [[x] for x in expression.any]
        elif isinstance(expression, AtLeastExpression):
            groups = combinations(expression.at_least.of, expression.at_least.count)
        else:
            raise TypeError("unknown expression")
        result = {}
        expanded = 0
        for group in groups:
            options = [self._expression_branches(x, seen) for x in group]
            for parts in product(*options):
                expanded += 1
                if expanded > self.limits.combinations:
                    raise SearchIncomplete("expression-combination limit exceeded")
                predicates = frozenset().union(*(p.predicates for p in parts))
                joins = tuple(dict.fromkeys(j for p in parts for j in p.joins))
                branch = ProofBranch(predicates, joins)
                result[(predicates, joins)] = branch
                if len(result) > self.limits.branches:
                    raise SearchIncomplete("proof-branch limit exceeded")
        return sorted(result.values(), key=lambda b: (sorted(b.predicates), repr(b.joins)))

    def observation_path(self, predicate_id: str, pattern_id: str, branch: ProofBranch):
        """Use only actual input/definition edges of the selected proof."""
        allowed = {d for d, _ in branch.joins}
        queue = [(predicate_id, [predicate_id], [])]
        seen = set()
        while queue:
            current, nodes, edges = queue.pop(0)
            if current == pattern_id:
                return nodes, edges
            if current in seen:
                continue
            seen.add(current)
            for edge in sorted(self.edges.values(), key=lambda e: e["edge_id"]):
                if edge["head"] != current or edge["relation"] not in {"INPUT_OF", "DEFINES"}:
                    continue
                target = edge["tail"]
                if edge["relation"] == "INPUT_OF" and not any(
                    target == d or target.startswith(d + "::gate::") for d in allowed
                ):
                    continue
                queue.append((target, nodes + [target], edges + [edge["edge_id"]]))
        raise ValueError("selected proof has no actual graph path")


def project_knowledge(package: KnowledgePackage) -> dict:
    """Rule nodes and their provenance are a projection of the canonical package."""
    nodes, edges = {}, {}

    def node(identity, kind, **properties):
        if identity in nodes:
            raise ValueError(f"generated graph identity collides: {identity}")
        nodes[identity] = {"node_id": identity, "kind": kind, **properties}

    def edge(identity, head, relation, tail):
        edges[identity] = {"edge_id": identity, "head": head, "relation": relation, "tail": tail}

    for entity in package.entities:
        node(entity.entity_id, entity.kind, label=entity.label, aliases=entity.aliases)
    for hypothesis in package.hypotheses:
        node(
            hypothesis.hypothesis_id,
            "Hypothesis",
            label=hypothesis.label,
            target_role=hypothesis.target_role,
        )
        edge(
            hypothesis.hypothesis_id + "::applies",
            hypothesis.hypothesis_id,
            "APPLIES_TO",
            hypothesis.applies_to_class_id,
        )
    for mechanism in package.mechanisms:
        node(mechanism.mechanism_id, "Mechanism", label=mechanism.label)
    for observable in package.observable_definitions:
        node(
            observable.predicate_id,
            "ObservablePredicate",
            **observable.model_dump(mode="json", exclude={"predicate_id", "source_assertion_ids"}),
        )
        subject = getattr(observable.subject_selector, "entity_id", None)
        if subject:
            edge(
                observable.predicate_id + "::binding", observable.predicate_id, "OBSERVES", subject
            )
    for binding in package.value_bindings:
        node(
            binding.binding_id,
            "ValueBinding",
            **binding.model_dump(mode="json", exclude={"binding_id", "source_assertion_ids"}),
        )
        for observable in package.observable_definitions:
            if observable.feature_id == binding.feature_id:
                edge(
                    binding.binding_id + "::normalizes::" + observable.predicate_id,
                    binding.binding_id,
                    "NORMALIZES_VALUE_FOR",
                    observable.predicate_id,
                )

    def expression(expr, target, definition_id, location=""):
        if isinstance(expr, str):
            edge(target + "::input::" + expr, expr, "INPUT_OF", target)
            return
        values = (
            expr.all
            if isinstance(expr, AllExpression)
            else (expr.any if isinstance(expr, AnyExpression) else expr.at_least.of)
        )
        for index, child in enumerate(values):
            if isinstance(child, str):
                expression(child, target, definition_id, location)
            else:
                identity = f"{definition_id}::gate::{location}{index}"
                kind = (
                    "ALL"
                    if isinstance(child, AllExpression)
                    else ("ANY" if isinstance(child, AnyExpression) else "AT_LEAST")
                )
                props = {"logic": kind}
                if isinstance(child, AtLeastExpression):
                    props["count"] = child.at_least.count
                node(identity, "LogicGate", **props)
                edge(identity + "::parent", identity, "INPUT_OF", target)
                expression(child, identity, definition_id, f"{location}{index}.")

    for pattern in package.pattern_definitions:
        node(pattern.pattern_id, "Phenomenon", label=pattern.label)
        logic = (
            "ALL"
            if isinstance(pattern.body, AllExpression)
            else ("ANY" if isinstance(pattern.body, AnyExpression) else "AT_LEAST")
        )
        props = {"logic": logic, "semantics": pattern.semantics, "scope_join": pattern.scope_join}
        if isinstance(pattern.body, AtLeastExpression):
            props["count"] = pattern.body.at_least.count
        node(pattern.definition_id, "DefinitionRule", **props)
        expression(pattern.body, pattern.definition_id, pattern.definition_id)
        edge(pattern.definition_id + "::head", pattern.definition_id, "DEFINES", pattern.pattern_id)
    for rule in package.effect_rules:
        node(rule.rule_id, "EffectRule")
        edge(rule.rule_id + "::from", rule.from_id, "ACTIVATES_RULE", rule.rule_id)
        edge(rule.rule_id + "::to", rule.rule_id, "DERIVES_STATE", rule.to_id)
    for rule in package.expectation_rules:
        node(rule.rule_id, "ExpectationRule", mode=rule.mode)
        edge(rule.rule_id + "::from", rule.from_id, "HAS_EXPECTATION", rule.rule_id)
        edge(rule.rule_id + "::to", rule.rule_id, "EXPECTS", rule.pattern_id)
    for relation in package.relations:
        edge(relation.relation_id, relation.head, relation.relation, relation.tail)
    for source in package.source_assertions:
        node(
            source.assertion_id,
            "SourceAssertion",
            **source.model_dump(exclude={"assertion_id"}, mode="json"),
        )
    for row in [
        *package.relations,
        *package.observable_definitions,
        *package.pattern_definitions,
        *package.effect_rules,
        *package.expectation_rules,
        *package.value_bindings,
    ]:
        identity = getattr(row, "predicate_id", None) or getattr(row, "definition_id", None)
        identity = identity or getattr(row, "rule_id", None)
        identity = identity or getattr(row, "binding_id", None)
        # Structural relation provenance is carried by its edge, not a dangling node.
        if identity is not None:
            for source in row.source_assertion_ids:
                edge(f"{source}::supports::{identity}", source, "SUPPORTS", identity)
    return {
        "schema_version": "rootlens-knowledge-graph-view.v2",
        "graph_id": package.graph_id,
        "editable": False,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
