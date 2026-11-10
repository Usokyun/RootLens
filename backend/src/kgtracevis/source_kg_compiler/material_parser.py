"""Local, located material parsing shared by the library and source compiler."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from html.parser import HTMLParser
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from kgtracevis.source_kg_compiler.models import SourceUnit


class ParsedSourceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["rootlens-source-units.v1"] = "rootlens-source-units.v1"
    units: list[SourceUnit]


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "li", "tr"} and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        elif tag in {"p", "div", "li", "tr"} and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_material(
    path: Path,
    *,
    source_id: str,
    scenario: str,
    material_type: str = "other",
    original_uri: str | None = None,
    chunk_size: int = 8000,
    chunk_overlap: int = 800,
) -> ParsedSourceBundle:
    """Parse actual content; spans refer to source rows/pages or extracted text offsets."""
    if chunk_size < 64 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_size must be >= 64 and overlap smaller than chunk_size")
    if scenario not in {"mvtec", "wafer", "tep", "shared"}:
        raise ValueError(f"unsupported material scenario: {scenario}")
    kind = path.suffix.lower().lstrip(".")
    kind = {"txt": "text", "md": "markdown", "htm": "html"}.get(kind, kind)
    if kind not in {"text", "markdown", "csv", "json", "jsonl", "html", "pdf"}:
        kind = {"webpage": "html"}.get(material_type, material_type)
    sections: list[tuple[str, dict[str, Any]]] = []
    parser = "rootlens.material_parser.v1"
    if kind == "pdf":
        from docling_parse.pdf_parser import DoclingPdfParser

        parser = "docling-parse:" + version("docling-parse")
        document = DoclingPdfParser(loglevel="fatal").load(path_or_stream=str(path))
        try:
            for page_no, page in document.iterate_pages():
                cells = page.textline_cells
                text = "\n".join(cell.text for cell in cells)
                sections.append((text, {"type": "page", "page": page_no}))
        finally:
            document.unload()
    else:
        text = path.read_text(encoding="utf-8-sig")
        if kind == "html":
            html = _HTMLText()
            html.feed(text)
            text = "\n".join(
                line.strip() for line in "".join(html.parts).splitlines() if line.strip()
            )
            sections.append((text, {"type": "extracted_text"}))
        elif kind == "csv":
            reader = csv.DictReader(io.StringIO(text))
            previous_line = reader.line_num or 1
            for row_index, row in enumerate(reader, start=1):
                if None in row:
                    raise ValueError(f"CSV row {row_index} has more values than columns")
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=reader.fieldnames or [])
                writer.writeheader()
                writer.writerow(row)
                sections.append(
                    (
                        output.getvalue(),
                        {
                            "type": "row",
                            "row": row_index,
                            "start_line": previous_line + 1,
                            "end_line": reader.line_num,
                        },
                    )
                )
                previous_line = reader.line_num
        elif kind == "jsonl":
            for line_no, line in enumerate(text.splitlines(), start=1):
                if line.strip():
                    item = json.loads(line)
                    sections.append(
                        (
                            json.dumps(item, ensure_ascii=False),
                            {
                                "type": "record",
                                "start_line": line_no,
                                "end_line": line_no,
                            },
                        )
                    )
        elif kind == "json":
            data = json.loads(text)
            items = list(enumerate(data)) if isinstance(data, list) else [(None, data)]
            for index, item in items:
                sections.append(
                    (
                        json.dumps(item, ensure_ascii=False, indent=2),
                        {
                            "type": "json",
                            "json_path": "$" if index is None else f"$[{index}]",
                        },
                    )
                )
        elif kind in {"text", "markdown"}:
            sections.append((text, {"type": "text"}))
        else:
            raise ValueError(
                f"unsupported material format: {kind}; use TXT/MD/CSV/JSON/JSONL/HTML/PDF"
            )
    units = []
    for text, locator in sections:
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                split = text.rfind("\n", start + chunk_size // 2, end)
                if split > start:
                    end = split
            left = start + len(text[start:end]) - len(text[start:end].lstrip())
            right = end - (len(text[start:end]) - len(text[start:end].rstrip()))
            content = text[left:right]
            if content:
                span = {**locator, "char_start": left, "char_end": right}
                if locator["type"] in {"text", "extracted_text"}:
                    span.update(
                        start_line=text.count("\n", 0, left) + 1,
                        end_line=text.count("\n", 0, right) + 1,
                    )
                # Content identity is part of the compiler's existing card/reference contract.
                digest = hashlib.sha256(content.encode()).hexdigest()
                identity = f"{source_id}:{json.dumps(span, sort_keys=True)}:{digest}"
                units.append(
                    SourceUnit(
                        unit_id="su_" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                        source_id=source_id,
                        scenario=scenario,
                        material_path=original_uri or path.as_posix(),
                        content_text=content,
                        source_span=span,
                        content_hash=digest,
                        parser_metadata={
                            "parser": parser,
                            "source_format": kind,
                            "original_path": str(path),
                            "chunk_index": len(units),
                        },
                    )
                )
            if end == len(text):
                break
            start = max(start + 1, end - chunk_overlap)
    if not units:
        raise ValueError("material has no extractable text; scanned PDF/OCR is not enabled")
    return ParsedSourceBundle(units=units)


def read_parsed_bundle(path: Path) -> ParsedSourceBundle | None:
    """Recognize only the explicit interchange envelope, not arbitrary source JSON."""
    if path.suffix.lower() != ".json":
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None  # Legacy direct compiler inputs retain their original text interpretation.
    if isinstance(data, dict) and data.get("schema_version") == "rootlens-source-units.v1":
        return ParsedSourceBundle.model_validate(data)
    return None
