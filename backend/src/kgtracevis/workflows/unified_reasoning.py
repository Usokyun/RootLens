"""Compatibility client: typed facts and common core, existing result/UI envelope."""

from __future__ import annotations

from kgtracevis.adapters.unified import evidence_frames
from kgtracevis.core.result import RankedRootCause, RcaReasoningResult
from kgtracevis.core.unified_reasoner import UnifiedReasoner


class UnifiedWorkingGraphReasoner:
    def __init__(self, knowledge):
        self.reasoner = UnifiedReasoner(knowledge)

    def reason_root_causes(self, evidence, *, graph, linked_entities, top_k=5):
        del linked_entities
        frames = evidence_frames(evidence)
        results = [self.reasoner.analyze(frame, top_k=top_k) for frame in frames]
        edge_map = {edge.external_edge_id: edge for edge in graph.edges}
        legacy_ids = sorted((o.obs_id for o in evidence.observations), key=len, reverse=True)

        def legacy_obs(identity):
            return next((o for o in legacy_ids if identity.startswith(o + ":")), identity)

        paths, rankings, links = [], [], []
        for frame, result in zip(frames, results, strict=True):
            query_paths = {}
            for row in result["ranked_root_causes"]:
                candidate_paths = []
                for path in row["explanation_paths"]:
                    views = path["source_edge_views"]
                    source_edges = [edge_map[view["edge_id"]].model_dump() for view in views]
                    projected = {
                        **path,
                        "source_entity_id": path["nodes"][0],
                        "target_entity_id": row["candidate_id"],
                        "score": row["score"],
                        "confidence": None,
                        "evidence_match": None,
                        "node_names": [graph.nodes[n].name for n in path["nodes"]],
                        "relations": [view["relation"] for view in source_edges],
                        "edge_ids": [view["edge_id"] for view in source_edges],
                        "source_edges": source_edges,
                        "edge_views": [
                            {"edge_id": edge["edge_id"], "reversed": view["reverse"]}
                            for edge, view in zip(source_edges, views, strict=True)
                        ],
                        "query_id": frame.case_id,
                        "typed_support_obs_ids": path["support_obs_ids"],
                        "support_obs_ids": list(
                            dict.fromkeys(legacy_obs(o) for o in path["support_obs_ids"])
                        ),
                    }
                    candidate_paths.append(projected)
                    paths.append(projected)
                query_paths[row["candidate_id"]] = candidate_paths
                rankings.append(
                    RankedRootCause(
                        ranking_id=f"rca:{frame.case_id}:{row['candidate_id']}",
                        rank=row["rank"],
                        candidate_id=row["candidate_id"],
                        candidate_name=row["candidate_name"],
                        candidate_label="Hypothesis",
                        candidate_role=row["candidate_role"],
                        score=row["score"],
                        confidence=None,
                        explanation_paths=candidate_paths,
                        supporting_edges=[
                            edge for path in candidate_paths for edge in path["source_edges"]
                        ],
                        support_evidence_ids=row["support_obs_ids"],
                        scoring_method=result["scoring_method"],
                        scoring_details={**row["scoring_details"], "query_id": frame.case_id},
                        source="unified_knowledge",
                    )
                )
            for fact in result["grounded_facts"]:
                if fact["value"] is True:
                    for obs_id in fact["source_obs_ids"]:
                        links.append(
                            {
                                "obs_id": legacy_obs(obs_id),
                                "entity_id": fact["predicate_id"],
                                "entity_name": graph.nodes[fact["predicate_id"]].name,
                                "field": "observation",
                                "method": "typed_grounding",
                                "score": 1.0,
                            }
                        )
        outcomes = {result["outcome"] for result in results}
        outcome = (
            "matched"
            if rankings
            else "insufficient_evidence"
            if outcomes & {"insufficient_evidence", "search_incomplete"}
            else "not_applicable"
            if outcomes == {"not_applicable"}
            else "no_match"
        )
        return RcaReasoningResult(
            case_id=evidence.case_id,
            top_k_paths=paths,
            ranked_root_causes=rankings,
            scoring_method="unified_constraint_abduction_v0",
            outcome=outcome,
            linked_entities=links,
            metadata={
                "reasoner": "unified_constraint_abduction_v0",
                "reasoner_adapter": "unified_working_graph",
                "selection_mode": "explicit",
                "reasoning_profile_id": f"working:{self.reasoner.program.package.graph_id}",
                "graph_id": self.reasoner.program.package.graph_id,
                "outcome": outcome,
                "fallback_applied": False,
                "query_results": results,
                "evidence_frames": [frame.model_dump(mode="json") for frame in frames],
                "aggregation": "independent_queries_no_cross_roi_score_comparison",
            },
        )
