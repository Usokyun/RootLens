#!/usr/bin/env python3
"""RootLens Module 1: Graph Construction Pipeline.

Calls into the upstream TEP_KG and KGTraceVis projects to build their
knowledge graphs from raw materials, then normalizes the output into
RootLens' unified format.

Usage:
    python3 scripts/build-graphs.py
    python3 scripts/build-graphs.py --output-dir public/generated
    python3 scripts/build-graphs.py --skip-tep
    python3 scripts/build-graphs.py --skip-mvtec
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── upstream project roots ──────────────────────────────────────────
TEP_KG_ROOT = Path("/Users/bytedance/my_project/TEP_KG")
MVTEC_KG_ROOT = Path("/Users/bytedance/my_project/MVTec/KGTraceVis")


# =====================================================================
# helpers
# =====================================================================

def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _parse_number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_aliases(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    parts: list[str] = []
    for part in str(value).split("|"):
        for sub in part.split(";"):
            stripped = sub.strip()
            if stripped:
                parts.append(stripped)
    return parts


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            records.append(json.loads(stripped))
    return records


def _build_source_file_descriptor(
    pathname: str, role: str, layer: str, rows: list[dict]
) -> dict:
    return {
        "path": pathname,
        "role": role,
        "layer": layer,
        "rowCount": len(rows),
        "fields": list(rows[0].keys()) if rows else [],
    }


def _enrich_nodes_with_degree(
    nodes: list[dict], edges: list[dict]
) -> list[dict]:
    degree: dict[str, dict[str, int]] = {
        n["id"]: {"inDegree": 0, "outDegree": 0} for n in nodes
    }
    for e in edges:
        src = degree.get(e["source"])
        if src is not None:
            src["outDegree"] += 1
        tgt = degree.get(e["target"])
        if tgt is not None:
            tgt["inDegree"] += 1
    for n in nodes:
        d = degree.get(n["id"], {"inDegree": 0, "outDegree": 0})
        n["degree"] = d["inDegree"] + d["outDegree"]
        n["inDegree"] = d["inDegree"]
        n["outDegree"] = d["outDegree"]
        attrs = dict(n.get("attributes", {}))
        attrs["degree"] = n["degree"]
        attrs["inDegree"] = n["inDegree"]
        attrs["outDegree"] = n["outDegree"]
        n["attributes"] = attrs
    return nodes


# =====================================================================
# TEP_KG  build  (calls upstream build_kg)
# =====================================================================

def _build_tep_graph() -> dict:
    """Run TEP_KG's full build_kg pipeline and return the RCA graph data."""
    sys.path.insert(0, str(TEP_KG_ROOT / "src"))
    from tep_kg.graph_build import build_kg  # type: ignore[import-untyped]

    print("[tep] running TEP_KG.build_kg() …", flush=True)
    manifest = build_kg(TEP_KG_ROOT)
    print(f"[tep]  done — {manifest['entities']} entities, {manifest['triples']} triples",
          flush=True)

    nodes_path = TEP_KG_ROOT / "data" / "processed" / "rca" / "nodes.jsonl"
    edges_path = TEP_KG_ROOT / "data" / "processed" / "rca" / "edges.jsonl"
    report_path = TEP_KG_ROOT / "outputs" / "rca" / "graph_report.json"

    if not nodes_path.exists() or not edges_path.exists():
        raise FileNotFoundError(
            "TEP_KG build_kg completed but RCA nodes/edges were not written. "
            f"Expected: {nodes_path}, {edges_path}"
        )

    return {
        "nodes": _read_jsonl(nodes_path),
        "edges": _read_jsonl(edges_path),
        "report": json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.exists()
        else {},
        "manifest": manifest,
    }


def _normalize_tep_dataset(tep_graph: dict) -> dict:
    """Convert TEP_KG RCA graph nodes/edges into RootLens unified format."""
    node_rows = tep_graph["nodes"]
    edge_rows = tep_graph["edges"]

    edges: list[dict] = []
    for i, row in enumerate(edge_rows):
        edges.append({
            "id": str(row.get("edge_id", f"tep-edge-{i + 1}")),
            "source": str(row["head_id"]),
            "target": str(row["tail_id"]),
            "relation": str(row.get("relation", "")),
            "category": str(row.get("relation_family", row.get("edge_origin", ""))),
            "label": str(row.get("relation", "")),
            "confidence": _parse_number(row.get("confidence")),
            "weight": _parse_number(row.get("support_count", row.get("confidence"))),
            "directed": True,
            "attributes": {k: v for k, v in row.items() if k != "edge_id"},
            "origin": {
                "projectId": "tep-kg",
                "projectLabel": "TEP_KG",
                "filePath": "data/processed/rca/edges.jsonl",
                "layer": str(row.get("edge_origin", "rca-graph")),
                "rowNumber": i + 1,
            },
        })

    nodes = _enrich_nodes_with_degree(
        [
            {
                "id": str(row["entity_id"]),
                "name": str(row.get("name", row["entity_id"])),
                "category": str(row.get("entity_type", "")),
                "kind": str(row.get("candidate_role", row.get("entity_type", ""))),
                "description": str(row.get("variable_role", "")),
                "aliases": _split_aliases(row.get("aliases")),
                "attributes": {
                    k: v
                    for k, v in row.items()
                    if k not in ("entity_id", "name", "entity_type", "candidate_role",
                                  "variable_role", "aliases")
                },
                "origin": {
                    "projectId": "tep-kg",
                    "projectLabel": "TEP_KG",
                    "filePath": "data/processed/rca/nodes.jsonl",
                    "layer": "rca-graph",
                    "rowNumber": i + 1,
                },
            }
            for i, row in enumerate(node_rows)
        ],
        edges,
    )

    return {
        "id": "tep-kg",
        "label": "TEP RCA Graph",
        "description": (
            "TEP_KG RCA graph built from materials (Simulink, MATLAB, C, "
            "prior graph, ontology). Includes FaultAnchor and SemanticConcept nodes."
        ),
        "graphKind": "rca-graph",
        "projectRoot": str(TEP_KG_ROOT),
        "sourceFiles": [
            _build_source_file_descriptor(
                "data/processed/rca/nodes.jsonl", "rca-node-table",
                "rca-graph", node_rows,
            ),
            _build_source_file_descriptor(
                "data/processed/rca/edges.jsonl", "rca-edge-table",
                "rca-graph", edge_rows,
            ),
        ],
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "builtBy": "tep_kg.graph_build.build_kg",
            "entityCount": len(node_rows),
            "tripleCount": len(edge_rows),
            "report": tep_graph.get("report", {}),
        },
    }


# =====================================================================
# MVTec / KGTraceVis  build  (reads & validates existing CSV KG)
# =====================================================================

def _build_mvtec_graph() -> dict:
    """Load, validate, and return the KGTraceVis task-oriented KG."""
    import os as _os
    _prev_cwd = _os.getcwd()
    try:
        _os.chdir(str(MVTEC_KG_ROOT))
        sys.path.insert(0, str(MVTEC_KG_ROOT / "src"))
        from kgtracevis.kg.graph import (  # type: ignore[import-untyped]
            DEFAULT_EDGE_PATHS,
            DEFAULT_NODE_PATHS,
            KnowledgeGraph,
        )

        node_paths = [Path(p) for p in DEFAULT_NODE_PATHS]
        edge_paths = [Path(p) for p in DEFAULT_EDGE_PATHS]

        print("[mvtec] loading KG from CSV …", flush=True)
        kg = KnowledgeGraph.from_paths(node_paths, edge_paths, skip_missing=True)
        print(f"[mvtec]  done — {len(kg.nodes)} nodes, {len(kg.edges)} edges", flush=True)

        return {"kg": kg, "node_paths": node_paths, "edge_paths": edge_paths}
    finally:
        _os.chdir(_prev_cwd)


def _normalize_mvtec_dataset(mvtec_graph: dict) -> dict:
    """Convert KGTraceVis KnowledgeGraph into RootLens unified format."""
    kg = mvtec_graph["kg"]
    node_rows: list[dict] = []
    for node in kg.nodes.values():
        node_rows.append({
            "id": node.id,
            "name": node.name,
            "category": node.label,
            "kind": node.label,
            "description": node.description or "",
            "aliases": list(node.aliases),
            "attributes": {
                "scenario": node.scenario,
                "label": node.label,
                "aliases_list": list(node.aliases),
            },
            "origin": {
                "projectId": "mvtec-project",
                "projectLabel": "MVTec / KGTraceVis",
                "filePath": "data/kg/nodes.csv",
                "layer": "nodes",
                "rowNumber": 0,
            },
        })

    edge_rows: list[dict] = []
    for i, edge in enumerate(kg.edges):
        edge_rows.append({
            "id": edge.edge_id,
            "source": edge.head,
            "target": edge.tail,
            "relation": edge.relation,
            "category": edge.scenario,
            "label": edge.relation,
            "confidence": edge.confidence,
            "weight": edge.weight,
            "directed": True,
            "attributes": {
                "scenario": edge.scenario,
                "source": edge.source,
                "evidence": edge.evidence,
                "review_status": edge.review_status,
                "feedback_count": edge.feedback_count,
                "accepted_count": edge.accepted_count,
                "rejected_count": edge.rejected_count,
            },
            "origin": {
                "projectId": "mvtec-project",
                "projectLabel": "MVTec / KGTraceVis",
                "filePath": "data/kg/edges.csv",
                "layer": "base-edges",
                "rowNumber": i + 1,
            },
        })

    nodes = _enrich_nodes_with_degree(node_rows, edge_rows)

    source_files: list[dict] = []
    for path in mvtec_graph.get("node_paths", []):
        source_files.append(
            _build_source_file_descriptor(
                str(path), "node-table", "nodes", []
            )
        )
    for path in mvtec_graph.get("edge_paths", []):
        source_files.append(
            _build_source_file_descriptor(
                str(path), "edge-table", "base-edges", []
            )
        )

    return {
        "id": "mvtec-project",
        "label": "MVTec Runtime KG",
        "description": (
            "KGTraceVis task-oriented knowledge graph covering MVTec product "
            "defects, TEP timeseries, and Wafer fab-log scenarios. "
            "Source-constrained with confidence assignments and review status."
        ),
        "graphKind": "runtime-kg",
        "projectRoot": str(MVTEC_KG_ROOT),
        "sourceFiles": source_files,
        "nodes": nodes,
        "edges": edge_rows,
        "metadata": {
            "builtBy": "kgtracevis.kg.graph.KnowledgeGraph.from_paths",
            "nodeCount": len(nodes),
            "edgeCount": len(edge_rows),
        },
    }


# =====================================================================
# orchestrator
# =====================================================================

def build_all(
    *,
    output_dir: Path | None = None,
    skip_tep: bool = False,
    skip_mvtec: bool = False,
) -> dict:
    """Run all graph construction and write unified-graphs.json."""
    started_at = _now_iso()
    datasets: list[dict] = []
    errors: list[str] = []

    # ── TEP ──────────────────────────────────────────────────────
    if not skip_tep:
        try:
            tep_raw = _build_tep_graph()
            datasets.append(_normalize_tep_dataset(tep_raw))
        except Exception as exc:
            errors.append(f"TEP build failed: {exc}")

    # ── MVTec ────────────────────────────────────────────────────
    if not skip_mvtec:
        try:
            mvtec_raw = _build_mvtec_graph()
            datasets.append(_normalize_mvtec_dataset(mvtec_raw))
        except Exception as exc:
            errors.append(f"MVTec build failed: {exc}")

    if not datasets:
        raise RuntimeError(
            "No graph datasets were built. Errors:\n" + "\n".join(errors)
        )

    unified: dict = {
        "schemaVersion": "graph.v1",
        "generatedAt": _now_iso(),
        "generator": "scripts/build-graphs.py",
        "datasets": datasets,
    }

    if output_dir is not None:
        out_path = output_dir / "unified-graphs.json"
        _write_json(out_path, unified)
        print(f"[done] wrote {out_path}  ({len(datasets)} dataset(s))", flush=True)

    return {
        "ok": len(errors) == 0,
        "generatedAt": unified["generatedAt"],
        "startedAt": started_at,
        "datasets": [d["id"] for d in datasets],
        "nodeCounts": {d["id"]: len(d["nodes"]) for d in datasets},
        "edgeCounts": {d["id"]: len(d["edges"]) for d in datasets},
        "errors": errors,
    }


# =====================================================================
# CLI
# =====================================================================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RootLens Module 1 — Graph Construction Pipeline"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "public" / "generated",
        help="Output directory for unified-graphs.json",
    )
    parser.add_argument(
        "--skip-tep",
        action="store_true",
        help="Skip TEP_KG graph build",
    )
    parser.add_argument(
        "--skip-mvtec",
        action="store_true",
        help="Skip MVTec/KGTraceVis graph build",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final summary as JSON to stdout",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = build_all(
        output_dir=args.output_dir,
        skip_tep=args.skip_tep,
        skip_mvtec=args.skip_mvtec,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    elif not summary["ok"]:
        print("[FAIL] graph construction completed with errors:", file=sys.stderr)
        for err in summary["errors"]:
            print(f"  - {err}", file=sys.stderr)
        return 1
    else:
        print("[OK] graph construction complete", flush=True)
        for ds_id, count in summary["nodeCounts"].items():
            print(f"  {ds_id}: {count} nodes, {summary['edgeCounts'][ds_id]} edges",
                  flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
