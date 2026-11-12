"""Resolve registered knowledge sources within the backend's source-document boundary."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def get_registered_source(source_id: str, *, root: Path | None = None) -> dict[str, Any]:
    base = (root or Path.cwd()).resolve()
    registry = base / "data/kg/source_registry.csv"
    if not registry.is_file():
        raise ValueError("Source registry is unavailable")
    with registry.open(encoding="utf-8", newline="") as handle:
        entry = next((r for r in csv.DictReader(handle) if r.get("source_id") == source_id), None)
    if entry is None:
        raise ValueError("Unknown registered source")
    location = entry.get("path_or_url", "")
    response: dict[str, Any] = {
        "source_id": source_id,
        "title": entry.get("title", source_id),
        "source_type": entry.get("type", ""),
        "location": location,
        "notes": entry.get("notes", ""),
        "available": False,
        "excerpt": None,
        "line_start": None,
        "line_end": None,
    }
    # Registry values are data, never arbitrary file-read authority. No external fetches.
    if location.startswith(("https://", "http://")):
        return response
    path = (base / location).resolve()
    allowed = (base / "docs/sources").resolve()
    if (
        not path.is_relative_to(allowed)
        or path.suffix.lower() not in {".md", ".txt"}
        or not path.is_file()
    ):
        return response
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if f"`{source_id}`" in line), None)
    if start is None:
        # Do not invent an exact source locator; report a document-level preview.
        start, end = 0, min(len(lines), 120)
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith(("- ", "## "))),
            min(start + 24, len(lines)),
        )
    response.update(
        available=True,
        excerpt="\n".join(lines[start:end])[:12000],
        line_start=start + 1,
        line_end=end,
    )
    return response
