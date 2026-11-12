"""Generate the small, reproducible RootLens visual fixture (no database access)."""

import csv
import json
from pathlib import Path

from kgtracevis.demo_assets import generate_visual_fixtures
from kgtracevis.service.source_provenance import get_registered_source

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "public" / "demo-evidence"
    generate_visual_fixtures(target)
    backend_root = Path(__file__).resolve().parents[1]
    with (backend_root / "data/kg/source_registry.csv").open(encoding="utf-8") as stream:
        catalog = {
            row["source_id"]: get_registered_source(row["source_id"], root=backend_root)
            for row in csv.DictReader(stream)
        }
    (target / "knowledge-sources.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(target)
    materials, chunks = [], []
    for scenario, title, source_id in [
        ("mvtec", "视觉缺陷 · 来源与知识边界", "manual_curation"),
        ("tep", "过程故障 · 知识来源索引", "tep_kg_variable_mapping"),
        ("wafer", "晶圆缺陷 · 参考与排查规则", "wafer_thesis"),
    ]:
        path = f"docs/sources/{scenario}_sources.md"
        text = (backend_root / path).read_text(encoding="utf-8")
        lines = text.splitlines()
        material_id = f"demo-source-{scenario}"
        materials.append(
            {
                "material_id": material_id,
                "title": title,
                "scenario": scenario,
                "status": "extracted",
                "source_type": "markdown",
                "source_kind": "bundled_reference",
                "source_uri": path,
                "path": path,
                "source_id": source_id,
                "processing_status": "已打包",
                "extraction_status": "extracted",
                "chunk_count": 1,
                "notes": "随演示打包的仓库来源说明；不是私有原始文档或已验证根因。",
                "metadata": {"bundled": True},
                "claim_boundary": "reference notes only; not verified factory RCA",
            }
        )
        chunks.append(
            {
                "chunk_id": f"{material_id}:document",
                "material_id": material_id,
                "chunk_index": 0,
                "source_locator": f"{path}:1-{len(lines)}",
                "text_content": text,
                "char_start": 0,
                "char_end": len(text),
                "metadata": {"scope": "document", "bundled": True},
                "created_at": None,
            }
        )
    (target / "materials.json").write_text(
        json.dumps({"materials": materials, "chunks": chunks}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
