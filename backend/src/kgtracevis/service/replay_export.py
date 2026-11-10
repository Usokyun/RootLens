"""Export persisted analysis and its original graph as an existing RootLens session bundle."""

from __future__ import annotations

import base64
import copy
import mimetypes
from collections import Counter
from datetime import UTC, datetime

from kgtracevis.kg.working_graph_package import WorkingGraphPackage
from kgtracevis.service.runs import get_run_artifact_path, get_run_detail


def export_run_replay(run_id: str) -> dict:
    detail = get_run_detail(run_id).model_dump(mode="json")
    package_payload = (detail.get("summary") or {}).get("working_graph_snapshot")
    if not package_payload:
        raise ValueError(
            "此历史运行未保存原始工作图快照；不能用当前图冒充其推理依据。请选择新工作图运行。"
        )
    package = WorkingGraphPackage.model_validate(package_payload)
    graph = package.to_graph()
    now = datetime.now(UTC).isoformat()
    gid = package.graph_id
    origin = dict(
        projectId=gid,
        projectLabel=package.title,
        filePath="persisted-run-snapshot",
        layer="working-graph-snapshot",
        rowNumber=0,
    )
    incoming = Counter(e.tail for e in graph.edges)
    outgoing = Counter(e.head for e in graph.edges)
    dataset = dict(
        id=gid,
        label=package.title,
        description="Original graph snapshot used by this analysis run",
        graphKind="working-graph-snapshot",
        projectRoot="",
        sourceFiles=[],
        metadata={"graph_id": gid, "build_id": package.build_id, "dataset": package.dataset},
        nodes=[
            dict(
                id=n.id,
                name=n.name,
                category=n.scenario,
                kind=n.label,
                description=n.description,
                aliases=list(n.aliases),
                inDegree=incoming[n.id],
                outDegree=outgoing[n.id],
                degree=incoming[n.id] + outgoing[n.id],
                attributes={},
                origin=origin,
            )
            for n in graph.nodes.values()
        ],
        edges=[
            dict(
                id=e.edge_id,
                source=e.head,
                target=e.tail,
                relation=e.relation,
                category=e.scenario,
                label=e.relation,
                confidence=e.confidence,
                weight=e.weight,
                directed=True,
                attributes=e.model_dump(),
                origin=origin,
            )
            for e in graph.edges
        ],
    )
    # Embed generated browser previews only, using the same restricted artifact resolver as GET.
    for case in detail["cases"]:
        case["generated_evidence"]["graph_dataset_id"] = gid
        for visual in case.get("visual_evidence", []):
            if not visual.get("available"):
                continue
            url = visual.get("url") or ""
            if not url.startswith(f"/api/runs/{run_id}/artifacts/"):
                continue
            filename = url.rsplit("/", 1)[-1]
            path = get_run_artifact_path(run_id, filename)
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            visual["url"] = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode(
                "ascii"
            )
            visual["preview_path"] = visual["url"]
    detail["visual_evidence"] = [
        v for case in detail["cases"] for v in case.get("visual_evidence", [])
    ]
    cases = [_legacy_case_projection(case, gid, package.title, now) for case in detail["cases"]]
    return dict(
        schema_version="rootlens-session-export.v1",
        exported_at=now,
        sessionMeta=None,
        importSummary=None,
        analysisWorkspace=None,
        analysisFocus=None,
        graphs=dict(
            schemaVersion="rootlens-unified-graphs.v1",
            generatedAt=now,
            generator="RootLens persisted run export",
            datasets=[dataset],
        ),
        runtime=dict(
            schema_version="rootlens-runtime.v1",
            generated_at=now,
            generator="RootLens backend snapshot",
            cases=cases,
            backend_runs=[detail],
        ),
    )


def _legacy_case_projection(case, graph_id, graph_title, now):
    """Keep v1's three facets readable; the additive backend_runs field is lossless."""
    evidence = copy.deepcopy(case["generated_evidence"])
    observations = []
    for obs in evidence.get("observations", []):
        base = dict(
            obs_id=obs["obs_id"],
            confidence=obs.get("confidence") or 0.0,
            linked_entity_hints=[],
            raw_evidence_refs=[],
            attributes={"backend_observation": obs},
        )
        if obs.get("facet") == "variable":
            observations.append(
                {
                    **base,
                    "facet": "variable",
                    "variable_name": obs.get("name", ""),
                    "contribution": obs.get("value") or 0.0,
                    "direction": obs.get("direction") or "unknown",
                }
            )
        else:
            observations.append(
                {
                    **base,
                    "facet": "image_defect",
                    "object": evidence.get("object", ""),
                    "anomaly_type": obs.get("display_name") or obs.get("name", ""),
                    "location": evidence.get("location") or "",
                    "severity": evidence.get("severity") or 0.0,
                    "morphology": {},
                }
            )
    summary = case.get("label") or case.get("case_label") or case["case_id"]
    return dict(
        case_id=case["case_id"],
        case_label=case.get("case_label") or case["case_id"],
        dataset=case["dataset"],
        source=evidence.get("source", "image"),
        summary=summary,
        graph_snapshot=dict(
            dataset_id=graph_id,
            label=graph_title,
            graph_kind="working-graph-snapshot",
            description="original run graph",
        ),
        evidence=dict(
            case_id=case["case_id"],
            case_label=summary,
            dataset=case["dataset"],
            source=evidence.get("source", "image"),
            timestamp=evidence.get("timestamp") or now,
            summary=summary,
            graph_dataset_id=graph_id,
            observations=observations,
        ),
        analysis=dict(
            case_id=case["case_id"],
            timestamp=now,
            graph_dataset_id=graph_id,
            route1=None,
            route2=None,
            cross_route_signals=[],
            notes=["Complete immutable analysis is preserved in backend_runs."],
        ),
    )
