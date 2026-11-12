"""Validated graph-workspace draft payloads; never writes to the runtime graph."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GraphEditPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["node", "edge"]
    operation: Literal["upsert", "disable"]
    id: str = Field(min_length=1, max_length=500)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    source: str = Field(min_length=1, max_length=4000)
    evidence: str = Field(min_length=1, max_length=20000)
    note: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def validate_edit(self) -> "GraphEditPayload":
        if not all(value.strip() for value in (self.id, self.source, self.evidence, self.note)):
            raise ValueError("draft edits require identity, source, evidence and reason")
        if self.before is not None and self.before.get("id") != self.id:
            raise ValueError("original snapshot identity mismatch")
        if self.operation == "disable" and self.after is not None:
            raise ValueError("disabled objects cannot carry replacement payloads")
        if self.operation == "upsert":
            if not self.after or self.after.get("id") != self.id:
                raise ValueError("draft payload identity mismatch")
            if self.kind == "node":
                if not all(str(self.after.get(k) or "").strip() for k in ("name", "kind")):
                    raise ValueError("node name and kind are required")
            else:
                import re

                if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(self.after.get("relation") or "")):
                    raise ValueError("relation must be uppercase snake case")
                if not self.after.get("source") or not self.after.get("target"):
                    raise ValueError("edge endpoints are required")
                confidence = self.after.get("confidence")
                if (
                    isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not 0 <= confidence <= 1
                ):
                    raise ValueError("edge confidence must be between 0 and 1")
        return self


class GraphWorkspacePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    scope: str = Field(min_length=1, max_length=2000)
    changes: list[GraphEditPayload] = Field(max_length=1000)

    @model_validator(mode="after")
    def validate_unique_objects(self) -> "GraphWorkspacePatch":
        identities = [(edit.kind, edit.id) for edit in self.changes]
        if len(identities) != len(set(identities)):
            raise ValueError("one net change per object is required")
        return self
