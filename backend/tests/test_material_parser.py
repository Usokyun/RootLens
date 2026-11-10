from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from kgtracevis.service.kg_materials import (
    KGMaterialExtractionRunRequest,
    KGMaterialRegisterRequest,
    KGMaterialSelectedBuildRequest,
    extract_kg_material_to_structured_records,
    get_kg_material,
    list_kg_material_chunks,
    list_kg_material_extraction_runs,
    prepare_kg_material_construction_build,
    register_kg_material,
)
from kgtracevis.source_kg_compiler.compiler import load_source_units
from kgtracevis.source_kg_compiler.material_parser import parse_material


@pytest.mark.parametrize(
    "suffix,text,count,locator",
    [
        (".txt", "  A material\nSecond line.  ", 1, "text"),
        (".md", "# Notes\nA crack is visible.", 1, "text"),
        (".csv", "head,relation,tail\nA,HAS_DEFECT,B\nB,HAS_PLAUSIBLE_CAUSE,C\n", 2, "row"),
        (".json", '[{"a":1},{"a":2}]', 2, "json"),
        (".jsonl", '{"a":1}\n\n{"a":2}\n', 2, "record"),
        (
            ".html",
            "<h1>Notes</h1><script>hidden()</script><p>Visible crack.</p>",
            1,
            "extracted_text",
        ),
    ],
)
def test_actual_content_and_location(suffix, text, count, locator, tmp_path):
    path = tmp_path / ("input" + suffix)
    path.write_text(text)
    parsed = parse_material(path, source_id="material", scenario="mvtec")
    assert len(parsed.units) == count
    assert all(u.source_span["type"] == locator for u in parsed.units)
    assert all(u.source_id == "material" and u.scenario == "mvtec" for u in parsed.units)
    assert "hidden()" not in "\n".join(u.content_text for u in parsed.units)
    if suffix == ".txt":
        unit = parsed.units[0]
        assert (
            text[unit.source_span["char_start"] : unit.source_span["char_end"]] == unit.content_text
        )
    bundle = tmp_path / "units.json"
    bundle.write_text(parsed.model_dump_json())
    assert load_source_units((bundle,), chunk_size=64, chunk_overlap=0) == parsed.units


def test_text_layer_pdf_uses_docling_and_keeps_page_number():
    pytest.importorskip("docling_parse")
    parsed = parse_material(
        Path("tests/fixtures/materials/dummy.pdf"), source_id="w3c", scenario="shared"
    )
    assert "Dummy PDF file" in parsed.units[0].content_text
    assert parsed.units[0].source_span["page"] == 1
    assert parsed.units[0].parser_metadata["parser"].startswith("docling-parse:")


def test_url_fetch_parse_failure_retry_and_compiler_handoff(tmp_path):
    root = tmp_path / "library"
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/notes.html"
        register_kg_material(
            KGMaterialRegisterRequest(
                material_id="url_1",
                title="URL",
                source_uri=url,
                source_kind="url",
                material_type="webpage",
                scenario="mvtec",
            ),
            material_root=root,
        )
        with pytest.raises(ValueError, match="parsing failed"):
            extract_kg_material_to_structured_records(
                "url_1", KGMaterialExtractionRunRequest(), material_root=root
            )
        assert get_kg_material("url_1", material_root=root).material.status == "failed"
        (tmp_path / "notes.html").write_text(
            "<h1>Capsule</h1><p>Punctures are localized openings.</p>"
        )
        result = extract_kg_material_to_structured_records(
            "url_1", KGMaterialExtractionRunRequest(), material_root=root
        )
        assert result.chunk_count == 1
        chunks = list_kg_material_chunks("url_1", material_root=root).chunks
        assert "localized openings" in chunks[0].text_content
        prepared = prepare_kg_material_construction_build(
            KGMaterialSelectedBuildRequest(material_ids=["url_1"]),
            material_root=root,
        )
        units = load_source_units((Path(prepared.sources[0].path),))
        assert units[0].unit_id == chunks[0].chunk_id
        assert units[0].material_path == url
        assert list_kg_material_extraction_runs("url_1", material_root=root).count == 2
        manifest = json.loads(Path(result.extraction_manifest_path).read_text())
        assert manifest["chunk_count"] == len(units)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
