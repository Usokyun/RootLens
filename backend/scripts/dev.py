"""RootLens development commands; always run against the in-repository backend."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def configure_environment() -> None:
    """Use one backend working directory and one Postgres config for every store."""
    from dotenv import load_dotenv

    from kgtracevis.kg.import_neo4j import resolve_neo4j_config
    from kgtracevis.service.postgres import resolve_postgres_config

    os.chdir(BACKEND_ROOT)
    load_dotenv(BACKEND_ROOT / ".env.local")
    load_dotenv(BACKEND_ROOT / ".env")
    postgres_file = Path("configs/database.yaml")
    postgres = resolve_postgres_config(
        config_path=postgres_file if postgres_file.is_file() else "configs/database.example.yaml"
    )
    if postgres.dsn:
        os.environ["KGTRACE_POSTGRES_DSN"] = postgres.dsn
    neo4j_file = Path("configs/neo4j.yaml")
    neo4j = resolve_neo4j_config(
        config_path=neo4j_file if neo4j_file.is_file() else "configs/neo4j.example.yaml"
    )
    for name, value in {
        "NEO4J_URI": neo4j.uri,
        "NEO4J_USER": neo4j.user,
        "NEO4J_PASSWORD": neo4j.password,
        "NEO4J_DATABASE": neo4j.database,
    }.items():
        os.environ[name] = value


def check_databases() -> int:
    """Probe real database connections and required application tables, without writes."""
    import psycopg
    from neo4j import GraphDatabase

    from kgtracevis.kg.import_neo4j import resolve_neo4j_config

    result: dict[str, object] = {"backend_root": str(BACKEND_ROOT)}
    failed = False
    try:
        with psycopg.connect(os.environ["KGTRACE_POSTGRES_DSN"], connect_timeout=5) as connection:
            result["postgres"] = {
                "status": "ok",
                "runs": connection.execute("SELECT count(*) FROM analysis_runs").fetchone()[0],
                "feedback": connection.execute("SELECT count(*) FROM feedback_records").fetchone()[
                    0
                ],
                "materials": connection.execute("SELECT count(*) FROM source_materials").fetchone()[
                    0
                ],
            }
    except Exception as exc:
        failed = True
        result["postgres"] = {"status": "error", "error": str(exc)}
    try:
        config = resolve_neo4j_config()
        with GraphDatabase.driver(
            config.uri, auth=(config.user, config.password), connection_timeout=5
        ) as driver:
            driver.verify_connectivity()
            with driver.session(database=config.database) as session:
                nodes = session.run("MATCH (n:KGEntity) RETURN count(n) AS count").single()["count"]
                edges = session.run(
                    "MATCH (:KGEntity)-[r]->(:KGEntity) RETURN count(r) AS count"
                ).single()["count"]
            result["neo4j"] = {"status": "ok", "nodes": nodes, "edges": edges}
    except Exception as exc:
        failed = True
        result["neo4j"] = {"status": "error", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(failed)


def require_empty_databases() -> None:
    """Refuse seed initialization when either database already holds app data."""
    import psycopg
    from neo4j import GraphDatabase

    from kgtracevis.kg.import_neo4j import resolve_neo4j_config

    with psycopg.connect(os.environ["KGTRACE_POSTGRES_DSN"], connect_timeout=5) as connection:
        for table in ["analysis_runs", "feedback_records", "source_materials"]:
            exists = connection.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0]
            if (
                exists
                and connection.execute("SELECT EXISTS (SELECT 1 FROM " + table + ")").fetchone()[0]
            ):
                raise SystemExit(
                    "Initialization refused: existing application data found. "
                    "Use backend:check / dev:backend; "
                    "do not reimport seeds to start an existing database."
                )
    config = resolve_neo4j_config()
    with GraphDatabase.driver(
        config.uri, auth=(config.user, config.password), connection_timeout=5
    ) as driver:
        with driver.session(database=config.database) as session:
            if session.run("MATCH (n:KGEntity) RETURN n LIMIT 1").single() is not None:
                raise SystemExit(
                    "Initialization refused: the Neo4j runtime KG is not empty. "
                    "Existing knowledge was not overwritten."
                )


def main() -> int:
    """Dispatch explicit development actions without starting databases implicitly."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["serve", "check", "init", "test", "db-start", "db-stop", "db-status"]
    )
    args, extra = parser.parse_known_args()
    if extra and args.command != "test":
        parser.error("unrecognized arguments: " + " ".join(extra))
    os.chdir(BACKEND_ROOT)
    if args.command.startswith("db-"):
        from scripts.local_databases import manage

        return manage(args.command.removeprefix("db-"))
    if args.command == "test":
        # Do not inject app connection defaults into isolated regression tests.
        return subprocess.call([sys.executable, "-m", "pytest", *extra], cwd=BACKEND_ROOT)
    configure_environment()
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "kgtracevis.service.api:app",
            host=os.environ.get("ROOTLENS_API_HOST", "127.0.0.1"),
            port=int(os.environ.get("ROOTLENS_API_PORT", "8000")),
        )
        return 0
    if args.command == "check":
        return check_databases()
    require_empty_databases()
    print("Initializing schema and importing seed KG into empty databases.")
    for script in ["init_postgres.py", "import_kg.py"]:
        result = subprocess.call(
            [sys.executable, str(BACKEND_ROOT / "scripts" / script)], cwd=BACKEND_ROOT
        )
        if result:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
