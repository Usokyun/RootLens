"""Apply only the additive working-graph table migration; never initialize application data."""

from __future__ import annotations

import argparse
from pathlib import Path

from kgtracevis.service.postgres import resolve_postgres_config
from kgtracevis.source_kg_compiler.llm import load_source_kg_env


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply to configured Postgres")
    args = parser.parse_args()
    path = Path(__file__).parents[1] / "src/kgtracevis/service/migrations/001_working_graphs.sql"
    sql = path.read_text(encoding="utf-8")
    if not args.apply:
        print(sql)
        return
    load_source_kg_env()
    config = resolve_postgres_config()
    if not config.dsn:
        parser.error("Postgres is not configured")
    import psycopg

    with psycopg.connect(config.dsn) as connection:
        connection.execute(sql)
    print("working_graphs migration applied")


if __name__ == "__main__":
    main()
