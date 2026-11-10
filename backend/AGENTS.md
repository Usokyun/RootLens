# RootLens Backend Instructions

This directory contains the in-repository KGTraceVis Python backend. Read the
root AGENTS.md and src/doc/backend-integration-current.md first; historical
upstream documents are background, not instructions to restore the old React UI.

## Boundaries

- Reusable analysis logic belongs in src/kgtracevis/. Scripts and API routes call
  it instead of duplicating linking, consistency, correction or path-ranking logic.
- Preserve the shared Evidence schema and the mvtec / tep / wafer scenarios.
- Never invent industrial causal facts. KG edges retain source, evidence,
  confidence, review_status and feedback counters.
- MVTec causes are plausible candidates, not verified factory root-cause labels.
- Preserve stable path, candidate and edge IDs for feedback and replay.
- Postgres stores runs, evidence, feedback and materials; Neo4j is the runtime KG.
- Do not add the old KGTraceVis web/web_legacy frontends to this repository.

## Development

- Python 3.10–3.12, one uv-managed package, package name kgtracevis.
- Start from RootLens with npm run dev:backend / dev:all. These commands set the
  backend working directory and use one Postgres config for all stores.
- Keep local dependencies, runtime data, model weights, databases, credentials
  and generated outputs ignored; keep only small seeds/examples in data/.
- Source configuration from configs/ and environment variables, not old absolute
  checkout paths. Preserve unrelated and uncommitted user changes.

## Verification

Run from this directory:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python scripts/run_examples.py
```

For changes to Neo4j behavior, use the import/examples-with-Neo4j checks only
against an explicitly designated test database. Never reimport seeds merely to
start an existing runtime. Document baseline failures separately from regressions.
