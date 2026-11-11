"""FastAPI entry point for KGTraceVis API clients."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from neo4j.exceptions import DriverError, Neo4jError
from pydantic import BaseModel, ConfigDict

from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.kg.working_graph_repository import WorkingGraphRepository
from kgtracevis.service.kg_materials import (
    KGMaterialRegisterRequest,
    MaterialConflictError,
    MaterialNotFoundError,
    MaterialType,
    get_kg_material,
    list_kg_material_chunks,
    list_kg_material_extraction_artifacts,
    list_kg_material_extraction_runs,
    list_kg_materials,
    register_kg_material,
    save_kg_material_upload,
    set_kg_material_archived,
)
from kgtracevis.service.kg_studio import KGStudioRuntimeError, kg_studio_payload
from kgtracevis.service.two_loop_store import TwoLoopStorageError
from kgtracevis.service.working_graph_editor import (
    export_v2_working_graph,
    import_working_graph,
    save_working_graph,
)
from kgtracevis.service.working_graphs import (
    WorkingGraphStorageError,
    working_graph_store,
)


class KGMaterialRegisterUrlRequest(BaseModel):
    """Frontend-friendly request to register one remote source material URL."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str | None = None
    scenario: str = "shared"
    source_type: str = "webpage"
    notes: str | None = None
    metadata: dict[str, Any] | None = None
    material_id: str | None = None


def create_app() -> FastAPI:
    """Create the FastAPI application used by dashboard/API clients."""
    app = FastAPI(
        title="KGTraceVis Web API",
        version="0.1.0",
        description=("API for evidence inspection and candidate/plausible KG explanation paths."),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from kgtracevis.service.two_loop_api import router as two_loop_router

    app.include_router(two_loop_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/kg/studio")
    def kg_studio(graph_id: str) -> dict[str, object]:
        try:
            record = working_graph_store().get(graph_id)
            if record.status != "ready" or record.knowledge is None:
                raise ValueError("仅可查看已就绪的 v2 工作图。")
            try:
                repository = WorkingGraphRepository.connect(graph_id)
            except (DriverError, Neo4jError, OSError, ValueError) as exc:
                raise KGStudioRuntimeError("无法连接工作图 Neo4j 存储。") from exc
            try:
                payload = kg_studio_payload(repository=repository).model_dump(mode="json")
                payload["graph_id"] = graph_id
                return payload
            finally:
                repository.close()
        except KGStudioRuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except WorkingGraphStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (DriverError, Neo4jError) as exc:
            raise HTTPException(status_code=503, detail="工作图 Neo4j 存储不可用。") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/kg/working-graphs")
    def working_graphs() -> dict[str, object]:
        try:
            return {
                "graphs": [
                    record.model_dump(mode="json")
                    for record in working_graph_store().list_ready()
                    if record.knowledge is not None
                ]
            }
        except WorkingGraphStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def graph_action(action):
        try:
            return action().model_dump(mode="json")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (WorkingGraphStorageError, DriverError, Neo4jError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/kg/working-graphs/{graph_id}/package")
    def export_graph_package(graph_id: str):
        return graph_action(lambda: export_v2_working_graph(graph_id))

    @app.post("/api/kg/working-graphs/import")
    def import_graph_package(package: UnifiedWorkingGraphPackage):
        return graph_action(lambda: import_working_graph(package))

    @app.put("/api/kg/working-graphs/{graph_id}/package")
    def save_graph_package(graph_id: str, package: UnifiedWorkingGraphPackage):
        return graph_action(lambda: save_working_graph(graph_id, package))

    @app.get("/api/kg/materials")
    def kg_materials(archived: bool = False) -> dict[str, object]:
        try:
            response = list_kg_materials(archived=archived)
            materials = [_material_api_record(material) for material in response.materials]
            return {
                "status": "ok",
                "material_dir": response.material_root,
                "material_root": response.material_root,
                "count": len(materials),
                "materials": materials,
                "note": "registered source materials for source-grounded KG construction",
            }
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/kg/materials/{material_id}")
    def kg_material_detail(material_id: str) -> dict[str, object]:
        try:
            material = get_kg_material(material_id).material
            return {"status": "ok", "material": _material_api_record(material)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/kg/materials/{material_id}/chunks")
    def kg_material_chunks(material_id: str) -> dict[str, object]:
        try:
            response = list_kg_material_chunks(material_id)
            payload = response.model_dump(mode="json")
            payload["material"] = _material_api_record(response.material)
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/kg/materials/{material_id}/extractions")
    def kg_material_extractions(material_id: str) -> dict[str, object]:
        try:
            response = list_kg_material_extraction_runs(material_id)
            payload = response.model_dump(mode="json")
            payload["material"] = _material_api_record(response.material)
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/kg/materials/{material_id}/artifacts")
    def kg_material_artifacts(material_id: str) -> dict[str, object]:
        try:
            response = list_kg_material_extraction_artifacts(material_id)
            payload = response.model_dump(mode="json")
            payload["material"] = _material_api_record(response.material)
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def update_material_archive(material_id: str, *, archived: bool) -> dict[str, object]:
        try:
            material = set_kg_material_archived(material_id, archived=archived)
        except MaterialNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MaterialConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except TwoLoopStorageError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "archived" if archived else "restored",
            "material": _material_api_record(material),
            "note": (
                "已移出素材库，原文件、提取结果和历史来源保留。" if archived else "已恢复到素材库。"
            ),
        }

    @app.post("/api/kg/materials/{material_id}/archive")
    def kg_material_archive(material_id: str) -> dict[str, object]:
        return update_material_archive(material_id, archived=True)

    @app.post("/api/kg/materials/{material_id}/restore")
    def kg_material_restore(material_id: str) -> dict[str, object]:
        return update_material_archive(material_id, archived=False)

    @app.post("/api/kg/materials/upload")
    def kg_material_upload(
        file: Annotated[UploadFile, File()],
        title: Annotated[str | None, Form()] = None,
        scenario: Annotated[str, Form()] = "shared",
        source_type: Annotated[str, Form()] = "other",
        notes: Annotated[str | None, Form()] = None,
        metadata: Annotated[str | None, Form()] = None,
        material_id: Annotated[str | None, Form()] = None,
        overwrite: Annotated[bool, Form()] = False,
    ) -> dict[str, object]:
        try:
            content = file.file.read()
            parsed_metadata = _metadata_from_form(metadata)
            if notes:
                parsed_metadata["notes"] = notes
            record = save_kg_material_upload(
                material_id=material_id
                or _generated_material_id(title or file.filename or "material"),
                title=title or Path(file.filename or "material").stem,
                filename=file.filename or "material.txt",
                content=content,
                scenario=scenario,
                material_type=cast(
                    MaterialType,
                    _material_type_from_source_type(
                        source_type,
                        filename=file.filename or "",
                        content_type=file.content_type,
                    ),
                ),
                content_type=file.content_type,
                metadata=parsed_metadata,
                overwrite=overwrite,
            )
            return {
                "status": "uploaded",
                "material": _material_api_record(record),
                "note": record.claim_boundary,
            }
        except MaterialConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/kg/materials/register-url")
    def kg_material_register_url(request: KGMaterialRegisterUrlRequest) -> dict[str, object]:
        try:
            metadata = dict(request.metadata or {})
            if request.notes:
                metadata["notes"] = request.notes
            record = register_kg_material(
                KGMaterialRegisterRequest(
                    material_id=request.material_id
                    or _generated_material_id(request.title or request.url),
                    title=request.title or request.url,
                    source_uri=request.url,
                    source_kind="url",
                    scenario=request.scenario,
                    material_type=cast(
                        MaterialType,
                        _material_type_from_source_type(request.source_type),
                    ),
                    metadata=metadata,
                )
            )
            return {
                "status": "registered",
                "material": _material_api_record(record),
                "note": record.claim_boundary,
            }
        except MaterialConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()


def _metadata_from_form(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("metadata must be a JSON object")
    return payload


def _generated_material_id(seed: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", seed.strip()).strip("._").lower()
    slug = slug[:40].strip("._") or "material"
    return f"{slug}_{uuid.uuid4().hex[:8]}"


def _material_type_from_source_type(
    source_type: str,
    *,
    filename: str = "",
    content_type: str | None = None,
) -> str:
    lowered = " ".join([source_type, filename, content_type or ""]).lower()
    if "pdf" in lowered:
        return "pdf"
    if "web" in lowered or lowered.startswith("url"):
        return "webpage"
    if "jsonl" in lowered:
        return "jsonl"
    if "json" in lowered:
        return "json"
    if "csv" in lowered:
        return "csv"
    if "markdown" in lowered or filename.lower().endswith(".md"):
        return "markdown"
    if "text" in lowered or filename.lower().endswith(".txt"):
        return "text"
    return "other"


def _material_api_record(material: Any) -> dict[str, object]:
    payload = material.model_dump(mode="json")
    extraction = payload.get("extraction") if isinstance(payload.get("extraction"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        **payload,
        "source_type": payload.get("material_type"),
        "source_format": extraction.get("source_format"),
        "path": payload.get("source_uri") if payload.get("source_kind") != "url" else None,
        "url": payload.get("source_uri") if payload.get("source_kind") == "url" else None,
        "uri": payload.get("source_uri"),
        "filename": payload.get("original_filename"),
        "processing_status": payload.get("status"),
        "extraction_status": extraction.get("status"),
        "chunk_count": (
            extraction["chunk_count"]
            if extraction.get("chunk_count") is not None
            else metadata.get("chunk_count")
        ),
        "page_count": metadata.get("page_count"),
        "source_id": extraction.get("source_id"),
        "notes": metadata.get("notes"),
        "created_at": payload.get("registered_at"),
    }
