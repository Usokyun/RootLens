#!/usr/bin/env python3
"""RootLens Module 1: Graph Construction Pipeline.

Calls into the upstream TEP_KG and KGTraceVis projects to build their
knowledge graphs from source materials or upstream build artifacts, then
normalizes the output into RootLens' unified format.

Usage:
    python3 scripts/build-graphs.py
    python3 scripts/build-graphs.py --output-dir public/generated
    python3 scripts/build-graphs.py --skip-tep
    python3 scripts/build-graphs.py --skip-mvtec
    python3 scripts/build-graphs.py --mvtec-records path/to/mvtec_records.jsonl
    python3 scripts/build-graphs.py --mvtec-table path/to/adapter_pipeline_table.csv
"""

from __future__ import annotations

import argparse
import ast
import builtins
import csv
import json
import shutil
import sys
import tempfile
import types
import typing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── upstream project roots ──────────────────────────────────────────
TEP_KG_ROOT = Path("/Users/bytedance/my_project/TEP_KG")
MVTEC_KG_ROOT = Path("/Users/bytedance/my_project/MVTec/KGTraceVis")

_ZIP_STRICT_SENTINEL = object()


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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _display_path(path: Path, *, root: Path | None = None) -> str:
    bases = [root] if root is not None else [REPO_ROOT, MVTEC_KG_ROOT, TEP_KG_ROOT]
    for base in bases:
        if base is None:
            continue
        try:
            return str(path.relative_to(base))
        except ValueError:
            continue
    return str(path)


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


def _first_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


# =====================================================================
# KGTraceVis Python 3.9 compatibility shims
# =====================================================================

class _UnionTransformer(ast.NodeTransformer):
    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            parts = self._flatten_union(node)
            slice_node: ast.AST
            if len(parts) == 1:
                slice_node = parts[0]
            else:
                slice_node = ast.Tuple(elts=parts, ctx=ast.Load())
            return ast.copy_location(
                ast.Subscript(
                    value=ast.Attribute(
                        value=ast.Name(id="typing", ctx=ast.Load()),
                        attr="Union",
                        ctx=ast.Load(),
                    ),
                    slice=slice_node,
                    ctx=ast.Load(),
                ),
                node,
            )
        return node

    def _flatten_union(self, node: ast.AST) -> list[ast.AST]:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self._flatten_union(node.left) + self._flatten_union(node.right)
        return [node]


def _eval_type_backport_value(
    value: Any,
    globalns: dict[str, Any] | None = None,
    localns: dict[str, Any] | None = None,
    try_default: bool = True,
) -> Any:
    if isinstance(value, typing.ForwardRef):
        expression = value.__forward_arg__
    elif isinstance(value, str):
        expression = value
    else:
        expression = repr(value)

    tree = ast.parse(expression, mode="eval")
    rewritten = _UnionTransformer().visit(tree)
    ast.fix_missing_locations(rewritten)
    transformed = ast.unparse(rewritten)
    namespace = {"typing": typing, "__builtins__": __builtins__}
    if globalns:
        namespace.update(globalns)
    if localns:
        namespace.update(localns)
    try:
        return eval(transformed, namespace, namespace)
    except Exception:
        if try_default:
            return value
        raise


def _ensure_eval_type_backport() -> None:
    try:
        import eval_type_backport  # noqa: F401
        return
    except ImportError:
        pass

    module = types.ModuleType("eval_type_backport")
    module.eval_type_backport = _eval_type_backport_value
    sys.modules["eval_type_backport"] = module


def _zip_backport(
    *iterables: object,
    strict: object = _ZIP_STRICT_SENTINEL,
):
    original_zip = _zip_backport._original_zip  # type: ignore[attr-defined]
    if strict is _ZIP_STRICT_SENTINEL or strict is False:
        return original_zip(*iterables)
    if strict is not True:
        raise TypeError("strict must be a bool")

    iterators = tuple(iter(item) for item in iterables)

    def generator():
        while True:
            values: list[object] = []
            exhausted_index: int | None = None
            for index, iterator in enumerate(iterators):
                try:
                    values.append(next(iterator))
                except StopIteration:
                    exhausted_index = index
                    break
            if exhausted_index is not None:
                for later_index, iterator in enumerate(
                    iterators[exhausted_index + 1 :],
                    start=exhausted_index + 1,
                ):
                    try:
                        next(iterator)
                    except StopIteration:
                        continue
                    raise ValueError(
                        f"zip() argument {later_index + 1} is longer than "
                        f"argument {exhausted_index + 1}"
                    )
                if values:
                    raise ValueError(
                        f"zip() argument {exhausted_index + 1} is shorter than "
                        f"arguments 1-{len(iterators)}"
                    )
                return
            yield tuple(values)

    return generator()


def _ensure_zip_strict_backport() -> None:
    try:
        list(zip([], [], strict=True))
        return
    except TypeError:
        pass

    if getattr(builtins.zip, "__name__", "") == "_zip_backport":
        return
    _zip_backport._original_zip = builtins.zip  # type: ignore[attr-defined]
    builtins.zip = _zip_backport


def _ensure_kgtracevis_import_context() -> None:
    source_dir = MVTEC_KG_ROOT / "src"
    source_dir_str = str(source_dir)
    if source_dir_str not in sys.path:
        sys.path.insert(0, source_dir_str)
    _ensure_eval_type_backport()
    _ensure_zip_strict_backport()

    package_name = "kgtracevis.experiments"
    if package_name not in sys.modules:
        experiments_pkg = types.ModuleType(package_name)
        experiments_pkg.__path__ = [str(source_dir / "kgtracevis" / "experiments")]
        sys.modules[package_name] = experiments_pkg


# =====================================================================
# TEP_KG  build  (calls upstream build_kg)
# =====================================================================

def _build_tep_graph() -> dict:
    """Run TEP_KG's full build_kg pipeline and return the RCA graph data."""
    sys.path.insert(0, str(TEP_KG_ROOT / "src"))
    from tep_kg.graph_build import build_kg  # type: ignore[import-untyped]

    print("[tep] running TEP_KG.build_kg() …", flush=True)
    manifest = build_kg(TEP_KG_ROOT)
    print(
        f"[tep]  done — {manifest['entities']} entities, {manifest['triples']} triples",
        flush=True,
    )

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
                    if k
                    not in (
                        "entity_id",
                        "name",
                        "entity_type",
                        "candidate_role",
                        "variable_role",
                        "aliases",
                    )
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
# MVTec / KGTraceVis build  (base KG + candidate overlay)
# =====================================================================

def _default_mvtec_records_candidates() -> list[Path]:
    return [
        MVTEC_KG_ROOT / "runs" / "mvtec_calibrated_pipeline" / "mvtec_calibrated_records.jsonl",
        MVTEC_KG_ROOT / "data" / "examples" / "records" / "mvtec_records.jsonl",
    ]


def _default_mvtec_table_candidates() -> list[Path]:
    return [
        MVTEC_KG_ROOT
        / "runs"
        / "mvtec_calibrated_pipeline"
        / "adapter_pipeline"
        / "adapter_pipeline_table.csv",
        MVTEC_KG_ROOT
        / "outputs"
        / "adapter_pipeline_v0"
        / "mvtec"
        / "adapter_pipeline_table.csv",
    ]


def _default_wm811k_record_candidates() -> list[Path]:
    return [
        MVTEC_KG_ROOT / "runs" / "wm811k_real_recognition_smoke" / "wm811k_records.jsonl",
        MVTEC_KG_ROOT / "data" / "examples" / "records" / "wm811k_records.jsonl",
    ]


def _resolve_explicit_or_default_path(
    explicit: Path | None,
    defaults: list[Path],
    *,
    label: str,
) -> Path | None:
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(f"{label} not found: {explicit}")
        return explicit
    return _first_existing_path(defaults)


def _resolve_default_paths(defaults: list[Path]) -> list[Path]:
    return [path for path in defaults if path.exists()]


def _mvtec_material_descriptor(path: Path, role: str) -> dict:
    if path.suffix == ".jsonl":
        rows = _read_jsonl(path)
        return _build_source_file_descriptor(
            _display_path(path),
            role,
            "candidate-material",
            rows,
        )
    if path.suffix == ".csv":
        rows = _read_csv_rows(path)
        return _build_source_file_descriptor(
            _display_path(path),
            role,
            "candidate-material",
            rows,
        )
    return {
        "path": _display_path(path),
        "role": role,
        "layer": "candidate-material",
        "rowCount": 0,
        "fields": [],
    }


def _mvtec_node_layer(path: Path) -> str:
    name = path.name
    if name == "nodes.csv":
        return "base-nodes"
    if name == "nodes_candidate.csv":
        return "candidate-nodes"
    if name.endswith("_nodes.csv"):
        return "scenario-nodes"
    return "node-table"


def _mvtec_edge_layer(path: Path) -> str:
    name = path.name
    if name == "edges.csv":
        return "base-edges"
    if name == "mvtec_rca_reference.csv":
        return "reference-edges"
    if name == "edges_candidate.csv":
        return "candidate-edges"
    if name.endswith("_edges.csv"):
        return "scenario-edges"
    return "edge-table"


def _load_mvtec_merged_rows(node_paths: list[Path], edge_paths: list[Path]) -> dict:
    from kgtracevis.kg.graph import KGEdge, KGNode, split_aliases  # type: ignore[import-untyped]

    merged_nodes: dict[str, dict[str, object]] = {}
    merged_edges: dict[str, dict[str, object]] = {}
    source_files: list[dict] = []

    for path in node_paths:
        if not path.exists():
            continue
        rows = _read_csv_rows(path)
        source_files.append(
            _build_source_file_descriptor(
                _display_path(path),
                "node-table",
                _mvtec_node_layer(path),
                rows,
            )
        )
        for row_number, row in enumerate(rows, start=1):
            node = KGNode(
                id=row["id"].strip(),
                name=row["name"].strip(),
                label=row["label"].strip(),
                scenario=row["scenario"].strip(),
                aliases=tuple(split_aliases(row.get("aliases"))),
                description=row.get("description", "").strip(),
            )
            existing = merged_nodes.get(node.id)
            if existing is not None and existing["node"] != node:
                raise ValueError(f"conflicting node definition for {node.id}")
            merged_nodes[node.id] = {
                "node": node,
                "path": path,
                "rowNumber": row_number,
                "layer": _mvtec_node_layer(path),
            }

    for path in edge_paths:
        if not path.exists():
            continue
        rows = _read_csv_rows(path)
        source_files.append(
            _build_source_file_descriptor(
                _display_path(path),
                "edge-table",
                _mvtec_edge_layer(path),
                rows,
            )
        )
        for row_number, row in enumerate(rows, start=1):
            edge = KGEdge(
                head=row["head"].strip(),
                relation=row["relation"].strip(),
                tail=row["tail"].strip(),
                scenario=row["scenario"].strip(),
                source=row["source"].strip(),
                evidence=row["evidence"].strip(),
                confidence=float(row["confidence"]),
                weight=float(row["weight"]),
                review_status=row["review_status"].strip(),
                feedback_count=int(row["feedback_count"]),
                accepted_count=int(row["accepted_count"]),
                rejected_count=int(row["rejected_count"]),
            )
            existing = merged_edges.get(edge.edge_id)
            if existing is None:
                merged_edges[edge.edge_id] = {
                    "edge": edge,
                    "path": path,
                    "rowNumber": row_number,
                    "layer": _mvtec_edge_layer(path),
                }
                continue
            existing_edge = existing["edge"]
            if existing_edge == edge:
                continue
            if existing_edge.review_status == "reviewed":
                raise ValueError(f"refusing to overwrite reviewed edge {edge.edge_id}")
            if edge.review_status == "reviewed" or existing_edge.review_status != "reviewed":
                merged_edges[edge.edge_id] = {
                    "edge": edge,
                    "path": path,
                    "rowNumber": row_number,
                    "layer": _mvtec_edge_layer(path),
                }

    return {
        "nodes": merged_nodes,
        "edges": merged_edges,
        "sourceFiles": source_files,
    }


def _build_mvtec_graph(
    *,
    output_dir: Path | None = None,
    mvtec_records_path: Path | None = None,
    mvtec_table_path: Path | None = None,
) -> dict:
    """Build KGTraceVis base KG plus candidate overlay when records are available."""
    import os as _os

    resolved_output_dir = output_dir.resolve() if output_dir is not None else None
    resolved_mvtec_records_path = (
        mvtec_records_path.resolve() if mvtec_records_path is not None else None
    )
    resolved_mvtec_table_path = (
        mvtec_table_path.resolve() if mvtec_table_path is not None else None
    )

    _prev_cwd = _os.getcwd()
    try:
        _os.chdir(str(MVTEC_KG_ROOT))
        _ensure_kgtracevis_import_context()

        from kgtracevis.experiments.adapter_pipeline import run_adapter_pipeline  # type: ignore[import-untyped]
        from kgtracevis.kg.graph import (  # type: ignore[import-untyped]
            DEFAULT_EDGE_PATHS,
            DEFAULT_NODE_PATHS,
            KnowledgeGraph,
        )
        from kgtracevis.kg_construction.case_kg_hardening import (  # type: ignore[import-untyped]
            write_candidate_kg_artifacts,
        )

        base_node_paths = [
            path if path.is_absolute() else (MVTEC_KG_ROOT / path).resolve()
            for path in (Path(value) for value in DEFAULT_NODE_PATHS)
        ]
        base_edge_paths = [
            path if path.is_absolute() else (MVTEC_KG_ROOT / path).resolve()
            for path in (Path(value) for value in DEFAULT_EDGE_PATHS)
        ]
        records_path = _resolve_explicit_or_default_path(
            resolved_mvtec_records_path,
            _default_mvtec_records_candidates(),
            label="MVTec records",
        )
        table_path = _resolve_explicit_or_default_path(
            resolved_mvtec_table_path,
            _default_mvtec_table_candidates(),
            label="MVTec adapter table",
        )
        wm811k_record_paths = _resolve_default_paths(_default_wm811k_record_candidates())

        temp_dir_handle: tempfile.TemporaryDirectory[str] | None = None
        if resolved_output_dir is not None:
            build_root = resolved_output_dir
        else:
            temp_dir_handle = tempfile.TemporaryDirectory(prefix="rootlens-mvtec-build-")
            build_root = Path(temp_dir_handle.name)

        adapter_generated = False
        adapter_output_dir = build_root / "mvtec-adapter-pipeline"
        candidate_output_dir = build_root / "mvtec-candidate-kg"
        candidate_output: Any | None = None

        if records_path is not None and table_path is None:
            print(
                f"[mvtec] generating adapter pipeline table from {records_path} …",
                flush=True,
            )
            shutil.rmtree(adapter_output_dir, ignore_errors=True)
            adapter_output = run_adapter_pipeline(
                records_path,
                adapter_output_dir,
                dataset="mvtec",
                overwrite=True,
            )
            table_path = Path(adapter_output.table_path)
            adapter_generated = True

        node_paths = list(base_node_paths)
        edge_paths = list(base_edge_paths)
        if records_path is not None:
            print("[mvtec] building candidate KG overlay …", flush=True)
            shutil.rmtree(candidate_output_dir, ignore_errors=True)
            candidate_output = write_candidate_kg_artifacts(
                output_dir=candidate_output_dir,
                mvtec_records_path=records_path,
                mvtec_adapter_table_path=table_path,
                wm811k_record_paths=wm811k_record_paths,
                overwrite=True,
            )
            node_paths.append(Path(candidate_output.nodes_path).resolve())
            edge_paths.append(Path(candidate_output.edges_path).resolve())

        print("[mvtec] loading KG from CSV …", flush=True)
        kg = KnowledgeGraph.from_paths(node_paths, edge_paths, skip_missing=True)
        print(
            f"[mvtec]  done — {len(kg.nodes)} nodes, {len(kg.edges)} edges",
            flush=True,
        )

        metadata = {
            "records_path": records_path,
            "table_path": table_path,
            "wm811k_record_paths": wm811k_record_paths,
            "adapter_generated": adapter_generated,
            "candidate_output": candidate_output,
            "temp_dir_handle": temp_dir_handle,
        }
        return {
            "kg": kg,
            "node_paths": node_paths,
            "edge_paths": edge_paths,
            "metadata": metadata,
        }
    finally:
        _os.chdir(_prev_cwd)


def _normalize_mvtec_dataset(mvtec_graph: dict) -> dict:
    """Convert KGTraceVis base KG + candidate overlay into RootLens format."""
    kg = mvtec_graph["kg"]
    node_paths = [Path(path) for path in mvtec_graph.get("node_paths", [])]
    edge_paths = [Path(path) for path in mvtec_graph.get("edge_paths", [])]
    merged = _load_mvtec_merged_rows(node_paths, edge_paths)
    merged_nodes = merged["nodes"]
    merged_edges = merged["edges"]

    if len(merged_nodes) != len(kg.nodes):
        raise RuntimeError(
            "Normalized MVTec node count diverged from KGTraceVis merge result: "
            f"{len(merged_nodes)} != {len(kg.nodes)}"
        )
    if len(merged_edges) != len(kg.edges):
        raise RuntimeError(
            "Normalized MVTec edge count diverged from KGTraceVis merge result: "
            f"{len(merged_edges)} != {len(kg.edges)}"
        )

    kg_node_ids = set(kg.nodes)
    merged_node_ids = set(merged_nodes)
    if kg_node_ids != merged_node_ids:
        raise RuntimeError("Normalized MVTec node IDs diverged from KGTraceVis merge result")
    kg_edge_ids = {edge.edge_id for edge in kg.edges}
    merged_edge_ids = set(merged_edges)
    if kg_edge_ids != merged_edge_ids:
        raise RuntimeError("Normalized MVTec edge IDs diverged from KGTraceVis merge result")

    node_rows: list[dict] = []
    for node_id in sorted(merged_nodes):
        record = merged_nodes[node_id]
        node = record["node"]
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
                "filePath": _display_path(record["path"]),
                "layer": record["layer"],
                "rowNumber": record["rowNumber"],
            },
        })

    edge_rows: list[dict] = []
    for edge_id in sorted(merged_edges):
        record = merged_edges[edge_id]
        edge = record["edge"]
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
                "filePath": _display_path(record["path"]),
                "layer": record["layer"],
                "rowNumber": record["rowNumber"],
            },
        })

    nodes = _enrich_nodes_with_degree(node_rows, edge_rows)
    metadata = mvtec_graph.get("metadata", {})
    candidate_output = metadata.get("candidate_output")
    records_path = metadata.get("records_path")
    table_path = metadata.get("table_path")
    wm811k_record_paths = metadata.get("wm811k_record_paths", [])
    source_files = list(merged["sourceFiles"])
    if records_path is not None:
        source_files.append(_mvtec_material_descriptor(records_path, "mvtec-records"))
    if table_path is not None:
        source_files.append(_mvtec_material_descriptor(table_path, "adapter-pipeline-table"))
    for path in wm811k_record_paths:
        source_files.append(_mvtec_material_descriptor(path, "wm811k-records"))

    overlay_metadata = {
        "enabled": candidate_output is not None,
        "recordsPath": _display_path(records_path) if records_path is not None else None,
        "adapterTablePath": _display_path(table_path) if table_path is not None else None,
        "wm811kRecordPaths": [_display_path(path) for path in wm811k_record_paths],
        "adapterTableGenerated": bool(metadata.get("adapter_generated")),
    }
    if candidate_output is not None:
        overlay_metadata["artifacts"] = {
            "nodesPath": _display_path(Path(candidate_output.nodes_path)),
            "edgesPath": _display_path(Path(candidate_output.edges_path)),
            "summaryPath": _display_path(Path(candidate_output.summary_path)),
            "validationPath": _display_path(Path(candidate_output.validation_path)),
            "reviewQueuePath": _display_path(Path(candidate_output.review_queue_path)),
            "coverageReportPath": _display_path(Path(candidate_output.coverage_report_path)),
            "beforeAfterPath": _display_path(Path(candidate_output.before_after_path)),
            "explanationsPath": _display_path(Path(candidate_output.explanations_path)),
            "nodeCount": candidate_output.node_count,
            "edgeCount": candidate_output.edge_count,
            "validationPassed": candidate_output.validation_passed,
        }

    return {
        "id": "mvtec-project",
        "label": "MVTec Runtime KG",
        "description": (
            "KGTraceVis runtime knowledge graph plus coverage-first candidate "
            "overlay generated from MVTec/WM811K evidence records when available."
        ),
        "graphKind": "runtime-kg",
        "projectRoot": str(MVTEC_KG_ROOT),
        "sourceFiles": source_files,
        "nodes": nodes,
        "edges": edge_rows,
        "metadata": {
            "builtBy": "KGTraceVis default KG + write_candidate_kg_artifacts",
            "nodeCount": len(nodes),
            "edgeCount": len(edge_rows),
            "baseNodeFileCount": len(
                [path for path in node_paths if path.name != "nodes_candidate.csv"]
            ),
            "baseEdgeFileCount": len(
                [path for path in edge_paths if path.name != "edges_candidate.csv"]
            ),
            "overlay": overlay_metadata,
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
    mvtec_records_path: Path | None = None,
    mvtec_table_path: Path | None = None,
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
            mvtec_raw = _build_mvtec_graph(
                output_dir=output_dir,
                mvtec_records_path=mvtec_records_path,
                mvtec_table_path=mvtec_table_path,
            )
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
        "--mvtec-records",
        type=Path,
        help=(
            "Optional MVTec records JSONL for KGTraceVis candidate overlay. "
            "Defaults to KGTraceVis runs path, then example records."
        ),
    )
    parser.add_argument(
        "--mvtec-table",
        type=Path,
        help=(
            "Optional KGTraceVis adapter_pipeline_table.csv. If omitted and records "
            "are available, RootLens will generate a table with run_adapter_pipeline."
        ),
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
        mvtec_records_path=args.mvtec_records,
        mvtec_table_path=args.mvtec_table,
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
            print(
                f"  {ds_id}: {count} nodes, {summary['edgeCounts'][ds_id]} edges",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
