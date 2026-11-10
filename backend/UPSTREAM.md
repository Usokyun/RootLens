# KGTraceVis import provenance

- Imported on 2026-11-10 (Asia/Shanghai).
- Local source: `/Users/macintosh/TrivalWork/KGTraceVis`.
- Source HEAD: `d7fa8f7ce43337085d4f25a4b91df82e16abf111`.
- Imported from the current working tree, including pending backend fixes and
  the untracked `tests/test_kg_studio_runtime.py`; not only clean HEAD.
- Python package name and HTTP contracts remain `kgtracevis`.
- This is a normal directory tracked by RootLens, not a symlink, nested Git repo
  or submodule. The original checkout is retained as a migration backup.

Included: Python source, scripts, dependency lock, configs, small KG seeds and
examples, tests, backend docs and small user-study configuration.

Excluded: `web/`, `web_legacy/`, paper/notebook assets, experiment outputs, Git
history and Agent/tool history. Databases, uploaded files, the local JDK/Neo4j
runtime and the Python environment were migrated separately into ignored paths;
they are not vendored source and are not distributed by Git.

Source code/schema semantics are preserved. RootLens adds root-level development
commands, local runtime management, backend documentation and a local-only
Compose binding. Migration verification is recorded in
`../.rootlens-cache/backend-migration-verification.json` on the current machine.
