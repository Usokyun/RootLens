"""Manage already-provisioned local database runtimes under backend/runs/local_runtime.

This helper never downloads software, creates a cluster, imports KG data or
changes a system service. For a fresh machine, use backend/compose.yaml instead.
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runs" / "local_runtime"
NEO4J_PID = RUNTIME / "neo4j" / "console.pid"


def pg_ctl() -> str:
    """Find PostgreSQL tools via an explicit override or the existing installation."""
    override = os.environ.get("ROOTLENS_PG_CTL")
    if override:
        return override
    binary = shutil.which("pg_ctl")
    if binary:
        return binary
    config = shutil.which("pg_config")
    if config:
        result = subprocess.run([config, "--bindir"], capture_output=True, text=True, check=True)
        candidate = Path(result.stdout.strip()) / "pg_ctl"
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("PostgreSQL pg_ctl not found. Set ROOTLENS_PG_CTL or use Docker Compose.")


def neo4j_home() -> Path:
    """Locate the existing project-local Neo4j distribution."""
    homes = list((RUNTIME / "neo4j").glob("neo4j-community-*"))
    homes = [home for home in homes if (home / "bin" / "neo4j").is_file()]
    if len(homes) != 1:
        raise RuntimeError(
            "Expected one local Neo4j runtime; use backend/compose.yaml on a fresh machine."
        )
    return homes[0]


def neo4j_pid(home: Path) -> int | None:
    """Validate PID ownership before signaling a process; stale PID files are ignored."""
    try:
        pid = int(NEO4J_PID.read_text().strip())
        os.kill(pid, 0)
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=False
        ).stdout
        return pid if str(home) in command else None
    except (OSError, ValueError):
        return None


def port_open(port: int) -> bool:
    """Check a local connector without changing database state."""
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def manage_postgres(action: str) -> bool:
    """Operate only the project-owned existing Postgres cluster."""
    data = RUNTIME / "postgres" / "data"
    if not (data / "PG_VERSION").is_file():
        raise RuntimeError("No local Postgres cluster. Start databases with backend/compose.yaml.")
    command = [pg_ctl(), "-D", str(data)]
    running = subprocess.run([*command, "status"], capture_output=True).returncode == 0
    if action == "status":
        print(f"Postgres: {'running' if running else 'stopped'} ({data})")
        return running
    if action == "start" and not running:
        socket_dir = RUNTIME / "postgres" / "socket"
        socket_dir.mkdir(exist_ok=True)
        subprocess.run(
            [
                *command,
                "-l",
                str(RUNTIME / "postgres" / "postgres.log"),
                "-o",
                shlex.join(["-k", str(socket_dir)]),
                "-w",
                "start",
            ],
            check=True,
        )
    elif action == "stop" and running:
        subprocess.run([*command, "-m", "fast", "-w", "stop"], check=True)
    else:
        print(f"Postgres: already {'running' if running else 'stopped'}")
    return True


def manage_neo4j(action: str) -> bool:
    """Start/stop only the Neo4j process launched for this checkout."""
    home = neo4j_home()
    pid = neo4j_pid(home)
    if action == "status":
        print(f"Neo4j: {'running' if pid else 'stopped'} ({home})")
        return pid is not None
    if action == "stop":
        if pid is None:
            print("Neo4j: already stopped")
            return True
        if os.getpgid(pid) != pid:
            raise RuntimeError(
                "Neo4j process is not in its own process group; refusing to signal it."
            )
        os.killpg(pid, signal.SIGTERM)
        for _ in range(300):
            if neo4j_pid(home) is None:
                print("Neo4j: stopped")
                return True
            time.sleep(0.2)
        raise RuntimeError("Neo4j shutdown timed out; inspect its console.log.")
    if pid:
        print(f"Neo4j: already running (PID {pid})")
        return True
    if port_open(7687) or port_open(7474):
        raise RuntimeError(
            "Neo4j ports are occupied by another process; it was not stopped or reused."
        )
    env = dict(os.environ, NEO4J_HOME=str(home))
    java_homes = list((RUNTIME / "jdk").glob("*/Contents/Home"))
    if len(java_homes) == 1:
        env["JAVA_HOME"] = str(java_homes[0])
    log_path = RUNTIME / "neo4j" / "console.log"
    with log_path.open("ab") as log:
        child = subprocess.Popen(
            [str(home / "bin" / "neo4j"), "console"],
            cwd=home,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    NEO4J_PID.write_text(f"{child.pid}\n")
    for _ in range(300):
        if child.poll() is not None:
            raise RuntimeError(f"Neo4j exited during startup; inspect {log_path}.")
        if port_open(7687) and port_open(7474):
            print(f"Neo4j: running (PID {child.pid})")
            return True
        time.sleep(0.2)
    raise RuntimeError(f"Neo4j startup timed out; inspect {log_path}.")


def manage(action: str) -> int:
    """Manage local runtimes without touching globally installed database services."""
    if os.name != "posix":
        print("Local runtime management requires macOS/Linux. Use Docker Compose on Windows.")
        return 1
    try:
        operations = (
            [manage_neo4j, manage_postgres] if action == "stop" else [manage_postgres, manage_neo4j]
        )
        results = [operation(action) for operation in operations]
        return 0 if all(results) else 1
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Local database error: {exc}")
        return 1
