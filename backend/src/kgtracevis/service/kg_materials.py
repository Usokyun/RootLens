"""Source material library management for the current KG compiler."""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.request
import uuid
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kgtracevis.service.kg_construction import (
    ConstructionSourceFormat,
    KGConstructionBuildRequest,
    KGConstructionSourceInput,
)

DEFAULT_SOURCE_KG_MATERIAL_DIR = Path("runs/source_kg_materials")
DEFAULT_MATERIAL_POSTGRES_CONFIG_PATH = Path("configs/database.yaml")
MAX_MATERIAL_UPLOAD_BYTES = 20_000_000
REMOTE_MATERIAL_FETCH_TIMEOUT_SECONDS = 10
REMOTE_MATERIAL_FETCH_CHUNK_BYTES = 8 * 1024

MaterialSourceKind = Literal["uploaded_file", "url", "local_path", "citation"]
MaterialType = Literal[
    "pdf",
    "webpage",
    "text",
    "markdown",
    "csv",
    "json",
    "jsonl",
    "other",
]
MaterialStatus = Literal["registered", "uploaded", "extracted", "failed"]
ExtractionStatus = Literal["not_started", "extracted", "failed"]


class MaterialConflictError(ValueError):
    """The material's current lifecycle state does not allow this operation."""


class MaterialNotFoundError(ValueError):
    """The material identity does not exist."""


def material_busy_error(material_id: str) -> MaterialConflictError:
    return MaterialConflictError(f"素材正在被处理，任务结束后可移出：{material_id}")


class KGMaterialExtractionState(BaseModel):
    """Lightweight source-readiness metadata for one material."""

    model_config = ConfigDict(extra="forbid")

    status: ExtractionStatus = "not_started"
    structured_records_path: str | None = None
    source_format: ConstructionSourceFormat = "text"
    source_id: str | None = None
    extractor_name: str | None = None
    extractor_version: str | None = None
    prompt_version: str | None = None
    document_understanding_mode: str = "compiler_source"
    extracted_at: str | None = None
    record_count: int | None = Field(default=None, ge=0)
    chunk_count: int | None = Field(default=None, ge=0)
    error_count: int | None = Field(default=None, ge=0)
    extraction_manifest_path: str | None = None
    chunk_results_path: str | None = None
    document_understanding_map_path: str | None = None
    chunk_prompt_context_path: str | None = None
    hypothesis_mode: str = "none"
    hypothesis_provider: str = "none"
    hypothesis_influence: str = "review_only"
    hypothesis_brainstorming_manifest_path: str | None = None
    brainstorm_hypotheses_path: str | None = None
    brainstorm_review_items_path: str | None = None
    brainstorm_evidence_tasks_path: str | None = None
    brainstorm_profile_gaps_path: str | None = None
    alignment_suggestions_path: str | None = None
    semantic_layer_suggestions_path: str | None = None
    profile_gap_suggestions_path: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_extraction_shape(self) -> KGMaterialExtractionState:
        """Keep readiness metadata explicit."""
        if self.status == "extracted" and not self.structured_records_path:
            raise ValueError("extraction.status=extracted requires structured_records_path")
        if self.status != "failed" and self.error_message:
            raise ValueError("error_message is only valid when extraction.status=failed")
        return self


class KGMaterialUploadRequest(BaseModel):
    """Metadata for an uploaded material file."""

    model_config = ConfigDict(extra="forbid")

    material_id: str
    title: str
    scenario: str = "shared"
    material_type: MaterialType = "other"
    filename: str
    content_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_upload_shape(self) -> KGMaterialUploadRequest:
        """Validate upload metadata."""
        self.material_id = _safe_path_component(self.material_id, field_name="material_id")
        _safe_upload_filename(self.filename)
        _require_non_empty(self.title, field_name="title")
        _require_non_empty(self.scenario, field_name="scenario")
        return self


class KGMaterialRegisterRequest(BaseModel):
    """Request to register a URL, local path, citation, or compiler-ready source."""

    model_config = ConfigDict(extra="forbid")

    material_id: str
    title: str
    source_uri: str
    source_kind: MaterialSourceKind = "url"
    scenario: str = "shared"
    material_type: MaterialType = "other"
    metadata: dict[str, Any] = Field(default_factory=dict)
    extraction: KGMaterialExtractionState = Field(default_factory=KGMaterialExtractionState)

    @model_validator(mode="after")
    def validate_register_shape(self) -> KGMaterialRegisterRequest:
        """Reject ambiguous source references."""
        self.material_id = _safe_path_component(self.material_id, field_name="material_id")
        _require_non_empty(self.title, field_name="title")
        _require_non_empty(self.scenario, field_name="scenario")
        _require_non_empty(self.source_uri, field_name="source_uri")
        is_url = _looks_like_url(self.source_uri)
        if self.source_kind == "url" and not is_url:
            raise ValueError(
                "source_kind=url requires source_uri to start with http:// or https://"
            )
        if self.source_kind != "url" and is_url:
            raise ValueError("remote URLs must use source_kind=url")
        return self


class KGMaterialRecord(BaseModel):
    """Persisted material-library record."""

    model_config = ConfigDict(extra="forbid")

    status: MaterialStatus
    material_id: str
    title: str
    scenario: str
    material_type: MaterialType
    source_kind: MaterialSourceKind
    source_uri: str
    metadata_path: str
    registered_at: str
    updated_at: str
    archived_at: str | None = None
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extraction: KGMaterialExtractionState = Field(default_factory=KGMaterialExtractionState)
    claim_boundary: str = (
        "source materials are provenance inputs for source KG compiler builds; "
        "registration or upload does not verify industrial facts"
    )

    @property
    def is_build_ready(self) -> bool:
        """Return whether this material can be fed to the source KG compiler."""
        needs_parse = self.source_kind == "url" or self.material_type in {"pdf", "webpage"}
        return (
            self.archived_at is None
            and (not needs_parse or self.extraction.status == "extracted")
            and self.extraction.status != "failed"
            and bool(_compiler_source_path(self, must_exist=False))
        )


class KGMaterialListResponse(BaseModel):
    """List response for stored material-library records."""

    model_config = ConfigDict(extra="forbid")

    material_root: str
    materials: list[KGMaterialRecord]


class KGMaterialDetailResponse(BaseModel):
    """Detail response for one material-library record."""

    model_config = ConfigDict(extra="forbid")

    material: KGMaterialRecord


class KGMaterialSelectedBuildRequest(BaseModel):
    """Request to convert selected materials into compiler source inputs."""

    model_config = ConfigDict(extra="forbid")

    material_ids: list[str]
    output_name: str = "material_library"
    overwrite: bool = False
    run_id: str | None = None
    profile_path: str | None = None
    source_type: Literal["structured_records", "manual_table", "document"] = "document"
    target_contract: Literal["legacy", "unified-v2"] = "legacy"
    capability_id: str | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> KGMaterialSelectedBuildRequest:
        """Require a concrete, unambiguous material selection."""
        if not self.material_ids:
            raise ValueError("material_ids must contain at least one material_id")
        normalized = [
            _safe_path_component(material_id, field_name="material_id")
            for material_id in self.material_ids
        ]
        duplicates = sorted(
            {material_id for material_id in normalized if normalized.count(material_id) > 1}
        )
        if duplicates:
            raise ValueError(f"material_ids contains duplicates: {', '.join(duplicates)}")
        self.material_ids = normalized
        return self


class KGMaterialBuildSourcesResponse(BaseModel):
    """Compiler source inputs derived from selected materials."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"] = "ready"
    material_root: str
    request: KGMaterialSelectedBuildRequest
    materials: list[KGMaterialRecord]
    sources: list[KGConstructionSourceInput]
    construction_request: KGConstructionBuildRequest
    claim_boundary: str = (
        "material-derived source inputs feed the current source KG compiler; "
        "they do not use the removed legacy construction pipeline"
    )


class KGMaterialExtractionRunRequest(BaseModel):
    """Parse material content into located chunks consumed directly by the compiler."""

    model_config = ConfigDict(extra="forbid")

    overwrite: bool = False
    provider: Literal["none"] = "none"
    chunk_size: int = Field(default=8000, ge=64)
    chunk_overlap: int = Field(default=800, ge=0)

    @model_validator(mode="after")
    def validate_chunks(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class KGMaterialExtractionRunResponse(BaseModel):
    """Response for a compiler-readiness extraction step."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["extracted"] = "extracted"
    material: KGMaterialRecord
    structured_records_path: str
    record_count: int
    extraction_manifest_path: str
    chunk_results_path: str | None = None
    document_ie_raw_responses_path: str | None = None
    document_ie_payload_repairs_path: str | None = None
    document_understanding_map_path: str | None = None
    chunk_prompt_context_path: str | None = None
    hypothesis_brainstorming_manifest_path: str | None = None
    brainstorm_hypotheses_path: str | None = None
    brainstorm_review_items_path: str | None = None
    chunk_count: int
    error_count: int
    provider: str = "none"
    extractor_name: str = "source_kg_compiler.material_source.v1"
    extractor_version: str = "v1"
    prompt_version: str = "none"
    claim_boundary: str = (
        "the material is compiler-ready source text; no legacy DraftKG extraction ran"
    )


class KGMaterialChunkRecord(BaseModel):
    """One parsed source chunk for review and extraction traceability."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    material_id: str
    chunk_index: int
    source_locator: str | None = None
    text_content: str
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class KGMaterialChunkListResponse(BaseModel):
    """Read-side response for one material's parsed chunks."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    material: KGMaterialRecord
    count: int
    chunks: list[KGMaterialChunkRecord] = Field(default_factory=list)
    claim_boundary: str = (
        "source chunks are parsed provenance context for candidate extraction; "
        "they are not verified industrial facts"
    )


class KGMaterialExtractionRunRecord(BaseModel):
    """One persisted extraction execution record."""

    model_config = ConfigDict(extra="forbid")

    extraction_run_id: str
    material_id: str
    status: str
    provider: str | None = None
    source_format: str | None = None
    structured_records_path: str | None = None
    source_id: str | None = None
    extractor_name: str | None = None
    extractor_version: str | None = None
    record_count: int | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    recorded_at: str | None = None
    extraction: KGMaterialExtractionState | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)


class KGMaterialExtractionRunListResponse(BaseModel):
    """Read-side response for one material's extraction runs."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    material: KGMaterialRecord
    count: int
    runs: list[KGMaterialExtractionRunRecord] = Field(default_factory=list)
    claim_boundary: str = (
        "extraction runs describe candidate-generation provenance and runtime state; "
        "they do not verify industrial facts or publish KG rows"
    )


class KGMaterialExtractionArtifactRecord(BaseModel):
    """One persisted extraction artifact reference."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    material_id: str
    extraction_run_id: str | None = None
    artifact_type: str
    uri: str | None = None
    media_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class KGMaterialExtractionArtifactListResponse(BaseModel):
    """Read-side response for one material's extraction artifacts."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    material: KGMaterialRecord
    count: int
    artifacts: list[KGMaterialExtractionArtifactRecord] = Field(default_factory=list)
    claim_boundary: str = (
        "extraction artifacts are candidate-generation byproducts for review; "
        "they are not published KG state or verified facts"
    )


class KGMaterialStore(Protocol):
    """Persistence boundary for material-library runtime state."""

    def save_material_record(self, material: KGMaterialRecord) -> KGMaterialRecord:
        """Persist one material record and return the validated record."""

    def list_material_records(self, *, archived: bool | None = None) -> list[KGMaterialRecord]:
        """Return persisted material records, optionally restricted by archive state."""

    def get_material_record(self, material_id: str) -> KGMaterialRecord:
        """Return one material record."""

    def set_material_archived_at(
        self, material_id: str, archived_at: str | None
    ) -> KGMaterialRecord:
        """Change only archive state, retaining the source and processing history."""

    def lock_material_operations(
        self, material_ids: Sequence[str], *, wait: bool
    ) -> AbstractContextManager[None]:
        """Serialize lifecycle changes with selection and submission for the same IDs."""

    def material_has_active_task(self, material_id: str) -> bool:
        """Check queued/running material work, without limiting the history queried."""

    def save_source_chunks(
        self,
        material_id: str,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Persist parsed source chunks for a material."""

    def record_extraction_run(
        self,
        material_id: str,
        extraction: KGMaterialExtractionState,
        *,
        extraction_run_id: str | uuid.UUID | None = None,
        provider: str | None = None,
        parameters: dict[str, Any] | None = None,
        result_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist one extraction run metadata row."""

    def save_extraction_artifact(
        self,
        *,
        material_id: str,
        artifact_type: str,
        extraction_run_id: str | uuid.UUID | None = None,
        uri: str | None = None,
        media_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist one extraction artifact reference."""

    def list_source_chunks(self, material_id: str) -> list[dict[str, Any]]:
        """Return stored source chunks for one material."""

    def list_extraction_runs(self, material_id: str) -> list[dict[str, Any]]:
        """Return stored extraction runs for one material."""

    def list_extraction_artifacts(self, material_id: str) -> list[dict[str, Any]]:
        """Return stored extraction artifacts for one material."""


_FILE_MATERIAL_LOCKS: dict[tuple[Path, str], threading.Lock] = {}


class FileKGMaterialStore:
    """File-backed material store used for local/default workflows."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_SOURCE_KG_MATERIAL_DIR

    def save_material_record(self, material: KGMaterialRecord) -> KGMaterialRecord:
        """Persist one material record as metadata JSON."""
        _write_material_record(material)
        return material

    def list_material_records(self, *, archived: bool | None = None) -> list[KGMaterialRecord]:
        """Return material records from local metadata JSON files."""
        if not self.root.exists():
            return []
        materials = [
            _load_material_record(metadata_path)
            for metadata_path in sorted(self.root.glob("*/metadata.json"))
        ]
        if archived is not None:
            materials = [item for item in materials if (item.archived_at is not None) == archived]
        materials.sort(key=lambda item: item.archived_at or item.updated_at, reverse=True)
        return materials

    def get_material_record(self, material_id: str) -> KGMaterialRecord:
        """Return one file-backed material record."""
        metadata_path = (
            _material_dir(
                _safe_path_component(material_id, field_name="material_id"),
                material_root=self.root,
            )
            / "metadata.json"
        )
        if not metadata_path.is_file():
            raise MaterialNotFoundError(f"unknown material_id: {material_id}")
        return _load_material_record(metadata_path)

    def set_material_archived_at(
        self, material_id: str, archived_at: str | None
    ) -> KGMaterialRecord:
        material = self.get_material_record(material_id)
        return self.save_material_record(material.model_copy(update={"archived_at": archived_at}))

    @contextmanager
    def lock_material_operations(
        self, material_ids: Sequence[str], *, wait: bool
    ) -> Iterator[None]:
        root = self.root.resolve()
        with ExitStack() as locks:
            for material_id in material_ids:
                lock = _FILE_MATERIAL_LOCKS.setdefault((root, material_id), threading.Lock())
                if not lock.acquire(blocking=wait):
                    raise material_busy_error(material_id)
                locks.callback(lock.release)
            yield

    def material_has_active_task(self, material_id: str) -> bool:
        from kgtracevis.service.two_loop_tasks import file_material_has_active_task

        return file_material_has_active_task(material_id)

    def save_source_chunks(
        self,
        material_id: str,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Persist source chunks as a local JSONL sidecar."""
        material_id = _safe_path_component(material_id, field_name="material_id")
        record_dir = _material_dir(material_id, material_root=self.root)
        record_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(record_dir / "source_chunks.jsonl", chunks)
        return chunks

    def list_source_chunks(self, material_id: str) -> list[dict[str, Any]]:
        """Return stored source chunks for one material in source order."""
        material_id = _safe_path_component(material_id, field_name="material_id")
        return _read_jsonl_records(
            _material_dir(material_id, material_root=self.root) / "source_chunks.jsonl",
            sort_key="chunk_index",
            reverse=False,
        )

    def record_extraction_run(
        self,
        material_id: str,
        extraction: KGMaterialExtractionState,
        *,
        extraction_run_id: str | uuid.UUID | None = None,
        provider: str | None = None,
        parameters: dict[str, Any] | None = None,
        result_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append extraction run metadata to a local JSONL sidecar."""
        material_id = _safe_path_component(material_id, field_name="material_id")
        run_id = str(extraction_run_id or uuid.uuid4())
        payload = {
            "extraction_run_id": run_id,
            "material_id": material_id,
            "status": extraction.status,
            "provider": provider,
            "source_format": extraction.source_format,
            "structured_records_path": extraction.structured_records_path,
            "source_id": extraction.source_id,
            "extractor_name": extraction.extractor_name,
            "extractor_version": extraction.extractor_version,
            "record_count": extraction.record_count,
            "error_message": extraction.error_message,
            "extraction": extraction.model_dump(mode="json"),
            "parameters": parameters or {},
            "result_summary": result_summary or {},
            "recorded_at": _utc_now(),
        }
        _append_jsonl(
            _material_dir(material_id, material_root=self.root) / "extraction_runs.jsonl",
            payload,
        )
        return payload

    def list_extraction_runs(self, material_id: str) -> list[dict[str, Any]]:
        """Return stored extraction run metadata for one material."""
        material_id = _safe_path_component(material_id, field_name="material_id")
        return _read_jsonl_records(
            _material_dir(material_id, material_root=self.root) / "extraction_runs.jsonl",
            sort_key="recorded_at",
        )

    def save_extraction_artifact(
        self,
        *,
        material_id: str,
        artifact_type: str,
        extraction_run_id: str | uuid.UUID | None = None,
        uri: str | None = None,
        media_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an extraction artifact reference to a local JSONL sidecar."""
        material_id = _safe_path_component(material_id, field_name="material_id")
        artifact = {
            "artifact_id": str(uuid.uuid4()),
            "material_id": material_id,
            "extraction_run_id": str(extraction_run_id) if extraction_run_id else None,
            "artifact_type": artifact_type,
            "uri": uri,
            "media_type": media_type,
            "payload": payload or {},
            "created_at": _utc_now(),
        }
        _append_jsonl(
            _material_dir(material_id, material_root=self.root) / "extraction_artifacts.jsonl",
            artifact,
        )
        return artifact

    def list_extraction_artifacts(self, material_id: str) -> list[dict[str, Any]]:
        """Return stored extraction artifact references for one material."""
        material_id = _safe_path_component(material_id, field_name="material_id")
        return _read_jsonl_records(
            _material_dir(material_id, material_root=self.root) / "extraction_artifacts.jsonl",
            sort_key="created_at",
        )


_MATERIAL_STORE_OVERRIDE: KGMaterialStore | None = None


def configure_material_store_for_testing(store: KGMaterialStore | None) -> None:
    """Override the default runtime material store in tests."""
    global _MATERIAL_STORE_OVERRIDE
    _MATERIAL_STORE_OVERRIDE = store


def material_store(*, material_root: Path | None = None) -> KGMaterialStore:
    """Return the configured material store."""
    if material_root is not None:
        return FileKGMaterialStore(material_root)
    if _MATERIAL_STORE_OVERRIDE is not None:
        return _MATERIAL_STORE_OVERRIDE
    from kgtracevis.service.postgres import resolve_postgres_config

    config = resolve_postgres_config(
        env=os.environ,
        config_path=DEFAULT_MATERIAL_POSTGRES_CONFIG_PATH,
    )
    if config.dsn:
        from kgtracevis.service.postgres_material_store import PostgresMaterialStore

        return PostgresMaterialStore(config)
    return FileKGMaterialStore(DEFAULT_SOURCE_KG_MATERIAL_DIR)


@contextmanager
def material_operations(
    material_ids: Sequence[str],
    *,
    material_root: Path | None = None,
    wait: bool = True,
) -> Iterator[KGMaterialStore]:
    """Reserve source IDs in stable order; let unrelated materials proceed."""
    store = material_store(material_root=material_root)
    identities = sorted(
        {_safe_path_component(identity, field_name="material_id") for identity in material_ids}
    )
    with store.lock_material_operations(identities, wait=wait):
        yield store


def require_active_material(store: KGMaterialStore, material_id: str) -> KGMaterialRecord:
    material = store.get_material_record(material_id)
    if material.archived_at is not None:
        raise MaterialConflictError(f"「{material.title}」已移出素材库，请先恢复。")
    return material


def set_kg_material_archived(
    material_id: str,
    *,
    archived: bool,
    material_root: Path | None = None,
) -> KGMaterialRecord:
    """Move a material out of or back into the active library without deleting data."""
    with material_operations(
        [material_id], material_root=material_root, wait=not archived
    ) as store:
        material = store.get_material_record(material_id)
        if (material.archived_at is not None) == archived:
            return material
        if archived and store.material_has_active_task(material.material_id):
            raise material_busy_error(material.material_id)
        return store.set_material_archived_at(
            material.material_id, _utc_now() if archived else None
        )


def save_kg_material_upload(
    *,
    material_id: str,
    title: str,
    filename: str,
    content: bytes,
    scenario: str = "shared",
    material_type: MaterialType = "other",
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    material_root: Path | None = None,
    overwrite: bool = False,
) -> KGMaterialRecord:
    """Persist an uploaded source material and return its registry record."""
    request = KGMaterialUploadRequest(
        material_id=material_id,
        title=title,
        scenario=scenario,
        material_type=material_type,
        filename=filename,
        content_type=content_type,
        metadata=metadata or {},
    )
    if not content:
        raise ValueError("uploaded material file cannot be empty")
    if len(content) > MAX_MATERIAL_UPLOAD_BYTES:
        raise ValueError(
            f"uploaded material file exceeds {MAX_MATERIAL_UPLOAD_BYTES} bytes: {len(content)}"
        )
    with material_operations([request.material_id], material_root=material_root) as store:
        _check_registration(store, request.material_id, overwrite=overwrite)
        record_dir = _material_dir(request.material_id, material_root=material_root)
        # A user's metadata.json (or another sidecar name) is still an original.
        source_path = record_dir / "original" / _safe_upload_filename(request.filename)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(content)
        now = _utc_now()
        record = KGMaterialRecord(
            status="uploaded",
            material_id=request.material_id,
            title=request.title,
            scenario=request.scenario,
            material_type=request.material_type,
            source_kind="uploaded_file",
            source_uri=str(source_path),
            metadata_path=str(record_dir / "metadata.json"),
            registered_at=now,
            updated_at=now,
            original_filename=request.filename,
            content_type=request.content_type,
            size_bytes=len(content),
            metadata=request.metadata,
        )
        return store.save_material_record(record)


def register_kg_material(
    request: KGMaterialRegisterRequest,
    *,
    material_root: Path | None = None,
    overwrite: bool = False,
) -> KGMaterialRecord:
    """Register a source material reference."""
    with material_operations([request.material_id], material_root=material_root) as store:
        _check_registration(store, request.material_id, overwrite=overwrite)
        record_dir = _material_dir(request.material_id, material_root=material_root)
        record_dir.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        record = KGMaterialRecord(
            status="extracted" if request.extraction.status == "extracted" else "registered",
            material_id=request.material_id,
            title=request.title,
            scenario=request.scenario,
            material_type=request.material_type,
            source_kind=request.source_kind,
            source_uri=request.source_uri,
            metadata_path=str(record_dir / "metadata.json"),
            registered_at=now,
            updated_at=now,
            metadata=request.metadata,
            extraction=request.extraction,
        )
        return store.save_material_record(record)


def list_kg_materials(
    *, archived: bool = False, material_root: Path | None = None
) -> KGMaterialListResponse:
    """List either the active library or its recoverable archive."""
    root = material_root or DEFAULT_SOURCE_KG_MATERIAL_DIR
    materials = material_store(material_root=material_root).list_material_records(archived=archived)
    return KGMaterialListResponse(material_root=str(root), materials=materials)


def get_kg_material(
    material_id: str,
    *,
    material_root: Path | None = None,
) -> KGMaterialDetailResponse:
    """Return one persisted material-library record."""
    material = material_store(material_root=material_root).get_material_record(material_id)
    return KGMaterialDetailResponse(material=material)


def list_kg_material_chunks(
    material_id: str,
    *,
    material_root: Path | None = None,
) -> KGMaterialChunkListResponse:
    """Return stored source chunks for one material."""
    material = get_kg_material(material_id, material_root=material_root).material
    chunks = material_store(material_root=material_root).list_source_chunks(material.material_id)
    return KGMaterialChunkListResponse(
        material=material,
        count=len(chunks),
        chunks=[KGMaterialChunkRecord.model_validate(chunk) for chunk in chunks],
    )


def list_kg_material_extraction_runs(
    material_id: str,
    *,
    material_root: Path | None = None,
) -> KGMaterialExtractionRunListResponse:
    """Return extraction run history for one material."""
    material = get_kg_material(material_id, material_root=material_root).material
    runs = material_store(material_root=material_root).list_extraction_runs(material.material_id)
    return KGMaterialExtractionRunListResponse(
        material=material,
        count=len(runs),
        runs=[KGMaterialExtractionRunRecord.model_validate(run) for run in runs],
    )


def list_kg_material_extraction_artifacts(
    material_id: str,
    *,
    material_root: Path | None = None,
) -> KGMaterialExtractionArtifactListResponse:
    """Return extraction artifacts for one material."""
    material = get_kg_material(material_id, material_root=material_root).material
    artifacts = material_store(material_root=material_root).list_extraction_artifacts(
        material.material_id
    )
    return KGMaterialExtractionArtifactListResponse(
        material=material,
        count=len(artifacts),
        artifacts=[
            KGMaterialExtractionArtifactRecord.model_validate(artifact) for artifact in artifacts
        ],
    )


def extract_kg_material_to_structured_records(
    material_id: str,
    request: KGMaterialExtractionRunRequest,
    *,
    material_root: Path | None = None,
    **_: Any,
) -> KGMaterialExtractionRunResponse:
    """Fetch/parse real source content, persist spans, and hand the same units to the compiler."""
    from kgtracevis.source_kg_compiler.material_parser import parse_material

    store = material_store(material_root=material_root)
    material = require_active_material(store, material_id)
    if material.extraction.status == "extracted" and not request.overwrite:
        raise ValueError("material already parsed; pass overwrite=true to reparse")
    record_dir = Path(material.metadata_path).parent
    extraction_id = str(uuid.uuid4())
    output_dir = record_dir / "extractions" / extraction_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    bundle_path = output_dir / "source_units.json"
    now = _utc_now()
    try:
        source_path = (
            fetch_remote_material(
                url=material.source_uri,
                material_id=material_id,
                material_root=material_root,
                destination_dir=output_dir / "original",
            )
            if material.source_kind == "url"
            else Path(material.source_uri).expanduser()
        )
        if material.source_kind == "citation" or not source_path.is_file():
            raise ValueError("material has no readable local file or fetchable URL")
        bundle = parse_material(
            source_path,
            source_id=material_id,
            scenario=material.scenario,
            material_type=material.material_type,
            original_uri=material.source_uri,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )
        bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        chunks = [
            {
                "chunk_id": unit.unit_id,
                "material_id": material_id,
                "chunk_index": index,
                "source_locator": json.dumps(unit.source_span, ensure_ascii=False),
                "text_content": unit.content_text,
                "char_start": unit.source_span.get("char_start"),
                "char_end": unit.source_span.get("char_end"),
                "metadata": {
                    **unit.parser_metadata,
                    "source_span": unit.source_span,
                    "extraction_run_id": extraction_id,
                },
            }
            for index, unit in enumerate(bundle.units)
        ]
        store.save_source_chunks(material_id, chunks)
    except Exception as exc:
        state = KGMaterialExtractionState(
            status="failed",
            error_message=str(exc),
            error_count=1,
            chunk_count=0,
            extractor_name="rootlens.material_parser",
            extracted_at=now,
        )
        store.save_material_record(
            material.model_copy(
                update={
                    "status": "failed",
                    "updated_at": now,
                    "extraction": state,
                }
            )
        )
        store.record_extraction_run(
            material_id,
            state,
            extraction_run_id=extraction_id,
            provider="none",
            parameters=request.model_dump(mode="json"),
            result_summary={"error": str(exc)},
        )
        _write_json_object(manifest_path, {"status": "failed", "error": str(exc)})
        raise ValueError(f"material parsing failed: {exc}") from exc
    state = KGMaterialExtractionState(
        status="extracted",
        structured_records_path=bundle_path.as_posix(),
        source_format="json",
        source_id=material.material_id,
        extractor_name="rootlens.material_parser",
        document_understanding_mode="located_text",
        extractor_version="v1",
        prompt_version="none",
        extracted_at=now,
        record_count=len(bundle.units),
        chunk_count=len(bundle.units),
        error_count=0,
        extraction_manifest_path=manifest_path.as_posix(),
    )
    manifest = {
        "artifact_type": "rootlens_material_parse.v1",
        "material_id": material.material_id,
        "source_path": source_path.as_posix(),
        "source_units_path": bundle_path.as_posix(),
        "chunk_count": len(bundle.units),
        "parser": bundle.units[0].parser_metadata["parser"],
        "created_at": now,
        "claim_boundary": (
            "parsed source units with row/page/text spans; no knowledge generation has run"
        ),
    }
    _write_json_object(manifest_path, manifest)
    updated = material.model_copy(
        update={"status": "extracted", "updated_at": now, "extraction": state}
    )
    store.save_material_record(updated)
    extraction_run = store.record_extraction_run(
        updated.material_id,
        state,
        extraction_run_id=extraction_id,
        provider=request.provider,
        parameters=request.model_dump(mode="json"),
        result_summary={"source_path": source_path.as_posix(), "chunk_count": len(bundle.units)},
    )
    store.save_extraction_artifact(
        material_id=updated.material_id,
        extraction_run_id=extraction_run.get("extraction_run_id"),
        artifact_type="parsed_source_units",
        uri=bundle_path.as_posix(),
        media_type="application/json",
        payload={"source_format": state.source_format},
    )
    return KGMaterialExtractionRunResponse(
        material=updated,
        structured_records_path=bundle_path.as_posix(),
        record_count=len(bundle.units),
        extraction_manifest_path=manifest_path.as_posix(),
        chunk_count=len(bundle.units),
        error_count=0,
        extractor_name="rootlens.material_parser",
        claim_boundary="parsed source content with locations, ready for LLM knowledge construction",
    )


def prepare_kg_material_construction_build(
    request: KGMaterialSelectedBuildRequest,
    *,
    material_root: Path | None = None,
) -> KGMaterialBuildSourcesResponse:
    """Return compiler source inputs for selected materials."""
    store = material_store(material_root=material_root)
    materials = [
        require_active_material(store, material_id) for material_id in request.material_ids
    ]
    for index, material in enumerate(materials):
        if (
            material.source_kind == "url" or material.material_type in {"pdf", "webpage"}
        ) and material.extraction.status == "not_started":
            materials[index] = extract_kg_material_to_structured_records(
                material.material_id,
                KGMaterialExtractionRunRequest(),
                material_root=material_root,
            ).material
    sources = [_construction_source_from_material(material) for material in materials]
    construction_request = KGConstructionBuildRequest(
        sources=sources,
        output_name=request.output_name,
        overwrite=request.overwrite,
        run_id=request.run_id,
        target_contract=request.target_contract,
        capability_id=request.capability_id,
    )
    return KGMaterialBuildSourcesResponse(
        material_root=str(material_root or DEFAULT_SOURCE_KG_MATERIAL_DIR),
        request=request,
        materials=materials,
        sources=sources,
        construction_request=construction_request,
    )


def _construction_source_from_material(
    material: KGMaterialRecord,
) -> KGConstructionSourceInput:
    if material.extraction.status == "failed":
        raise ValueError(f"material parsing failed; retry extraction first: {material.material_id}")
    source_path = _compiler_source_path(material, must_exist=True)
    if source_path is None:
        raise ValueError(
            f"material is not backed by a local compiler-readable source: {material.material_id}"
        )
    return KGConstructionSourceInput(
        source_id=material.material_id,
        source_type="document",
        scenario=material.scenario,
        path=source_path.as_posix(),
        source_format=_source_format_from_path(source_path),
        metadata={
            "material_id": material.material_id,
            "material_title": material.title,
            "source_kind": material.source_kind,
            "material_type": material.material_type,
            **material.metadata,
        },
    )


def fetch_remote_material(
    *,
    url: str,
    material_id: str,
    material_root: Path | None = None,
    timeout_seconds: int = REMOTE_MATERIAL_FETCH_TIMEOUT_SECONDS,
    destination_dir: Path | None = None,
) -> Path:
    """Fetch a registered remote source into the local material directory."""
    _require_non_empty(url, field_name="url")
    if not _looks_like_url(url):
        raise ValueError("remote material fetch requires an http(s) URL")
    record_dir = destination_dir or _material_dir(material_id, material_root=material_root)
    record_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_upload_filename(Path(urlparse(url).path).name or "remote_material.html")
    output_path = record_dir / filename
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        with output_path.open("wb") as handle:
            while True:
                chunk = response.read(REMOTE_MATERIAL_FETCH_CHUNK_BYTES)
                if not chunk:
                    break
                handle.write(chunk)
                if output_path.stat().st_size > MAX_MATERIAL_UPLOAD_BYTES:
                    raise ValueError("remote material exceeds maximum upload size")
    return output_path


def _compiler_source_path(
    material: KGMaterialRecord,
    *,
    must_exist: bool,
) -> Path | None:
    candidates: list[str] = []
    if material.extraction.structured_records_path:
        candidates.append(material.extraction.structured_records_path)
    if material.source_kind in {"uploaded_file", "local_path"}:
        candidates.append(material.source_uri)
    for value in candidates:
        path = Path(value).expanduser()
        if path.is_file() or (not must_exist and not _looks_like_url(value)):
            return path
    return None


def _source_format_from_path(path: Path) -> ConstructionSourceFormat:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "csv"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return "text"


def _check_registration(store: KGMaterialStore, material_id: str, *, overwrite: bool) -> None:
    try:
        require_active_material(store, material_id)
    except MaterialNotFoundError:
        return
    if not overwrite:
        raise ValueError(
            f"material_id already exists; pass overwrite=true to replace: {material_id}"
        )


def _material_dir(material_id: str, *, material_root: Path | None = None) -> Path:
    return (material_root or DEFAULT_SOURCE_KG_MATERIAL_DIR) / _safe_path_component(
        material_id,
        field_name="material_id",
    )


def _write_material_record(material: KGMaterialRecord) -> None:
    path = Path(material.metadata_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary_path = Path(handle.name)
        try:
            json.dump(material.model_dump(mode="json"), handle, indent=2, sort_keys=True)
            handle.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def _load_material_record(path: Path) -> KGMaterialRecord:
    return KGMaterialRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_jsonl_records(
    path: Path,
    *,
    sort_key: str | None = None,
    reverse: bool = True,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL record must be an object: {path}")
        records.append(dict(payload))
    if sort_key is not None:
        records.sort(key=lambda item: item.get(sort_key) or 0, reverse=reverse)
    return records


def _safe_path_component(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} cannot be empty")
    if Path(text).name != text or text in {".", ".."}:
        raise ValueError(f"{field_name} must be a safe path component")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", text):
        raise ValueError(f"{field_name} may contain only letters, numbers, _, ., and -")
    return text


def _safe_upload_filename(value: str) -> str:
    name = Path(value).name
    if not name or name in {".", ".."}:
        raise ValueError("filename must be a safe file name")
    return name


def _require_non_empty(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")


def _looks_like_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "DEFAULT_SOURCE_KG_MATERIAL_DIR",
    "FileKGMaterialStore",
    "KGMaterialBuildSourcesResponse",
    "KGMaterialChunkListResponse",
    "KGMaterialChunkRecord",
    "KGMaterialDetailResponse",
    "KGMaterialExtractionArtifactListResponse",
    "KGMaterialExtractionArtifactRecord",
    "KGMaterialExtractionRunListResponse",
    "KGMaterialExtractionRunRecord",
    "KGMaterialExtractionRunRequest",
    "KGMaterialExtractionRunResponse",
    "KGMaterialExtractionState",
    "KGMaterialListResponse",
    "KGMaterialRecord",
    "KGMaterialRegisterRequest",
    "KGMaterialSelectedBuildRequest",
    "KGMaterialStore",
    "KGMaterialUploadRequest",
    "MaterialConflictError",
    "MaterialNotFoundError",
    "MaterialSourceKind",
    "MaterialStatus",
    "MaterialType",
    "configure_material_store_for_testing",
    "extract_kg_material_to_structured_records",
    "fetch_remote_material",
    "get_kg_material",
    "list_kg_material_chunks",
    "list_kg_material_extraction_artifacts",
    "list_kg_material_extraction_runs",
    "list_kg_materials",
    "material_operations",
    "material_store",
    "prepare_kg_material_construction_build",
    "register_kg_material",
    "require_active_material",
    "save_kg_material_upload",
    "set_kg_material_archived",
]
