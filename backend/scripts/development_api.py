"""Manually manage a project API with launchd, independent of an agent/tool session.

The plist lives in ignored runs/, not ~/Library/LaunchAgents. Starting a job is
explicit and lasts for the current login session; it is not a login/boot install.
The API never automatically restarts paid tasks. Only the selected named job is
stopped, never a process discovered by port.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BACKEND = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = BACKEND / "runs/development_services"
ALLOWED_ENV = (
    "KGTRACE_POSTGRES_DSN",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
    "KGTRACEVIS_MVTEC_DEVICE",
    "KGTRACEVIS_WM811K_DEVICE",
)


def runtime(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,63}", name):
        raise ValueError("name must use lowercase letters, digits, dots or hyphens")
    root = RUNTIME_ROOT / name
    return root, f"com.rootlens.dev.{name}", f"gui/{os.getuid()}/com.rootlens.dev.{name}"


def command(*args):
    return subprocess.run(["/bin/launchctl", *args], text=True, capture_output=True, check=False)


def parse_job_status(output):
    fields = {}
    for name in ("state", "pid", "last exit code", "last terminating signal"):
        match = re.search(r"^\s*" + name + r" = ([^\n]+)", output, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            fields[name.replace(" ", "_")] = int(value) if value.isdigit() else value
    return fields


def status(name):
    root, label, target = runtime(name)
    manifest = root / "service.json"
    record = json.loads(manifest.read_text()) if manifest.is_file() else {}
    result = command("print", target)
    fields = parse_job_status(result.stdout) if result.returncode == 0 else {"state": "not_loaded"}
    if fields.get("pid") and manifest.is_file() and record.get("pid") != fields["pid"]:
        record["pid"] = fields["pid"]
        manifest.write_text(json.dumps(record, indent=2))
    return {
        "name": name,
        "label": label,
        "registered": result.returncode == 0,
        "backend": str(BACKEND),
        "log_path": str(root / "api.log"),
        "host": record.get("host"),
        "port": record.get("port"),
        **fields,
    }


def job_config(label, root, host, port, env, *, previous_env=None):
    selected = {key: value for key, value in (previous_env or {}).items() if key in ALLOWED_ENV}
    selected.update({key: env[key] for key in ALLOWED_ENV if env.get(key)})
    selected.update(ROOTLENS_API_HOST=host, ROOTLENS_API_PORT=str(port), PYTHONUNBUFFERED="1")
    return {
        "Label": label,
        "ProgramArguments": [sys.executable, str(BACKEND / "scripts/dev.py"), "serve"],
        "WorkingDirectory": str(BACKEND),
        "EnvironmentVariables": selected,
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(root / "api.log"),
        "StandardErrorPath": str(root / "api.log"),
    }


def start(name, *, host, port):
    root, label, target = runtime(name)
    current = status(name)
    if current.get("pid") and current.get("state") == "running":
        return current
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex((host, port)) == 0:
            raise RuntimeError(f"{host}:{port} is occupied; no process was stopped")
    if current["registered"]:
        stop(name)
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    plist = root / "service.plist"
    previous_env = {}
    if plist.is_file():
        with plist.open("rb") as handle:
            previous_env = plistlib.load(handle).get("EnvironmentVariables", {})
    with plist.open("wb") as handle:
        plistlib.dump(
            job_config(label, root, host, port, os.environ, previous_env=previous_env), handle
        )
    plist.chmod(0o600)  # DB connection settings stay local, never printed or committed.
    record = {
        "name": name,
        "label": label,
        "target": target,
        "backend": str(BACKEND),
        "host": host,
        "port": port,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "plist_path": str(plist),
        "log_path": str(root / "api.log"),
    }
    (root / "service.json").write_text(json.dumps(record, indent=2))
    with (root / "api.log").open("a") as handle:
        handle.write("\n=== explicit start " + record["started_at"] + " ===\n")
    result = command("bootstrap", f"gui/{os.getuid()}", str(plist))
    if result.returncode:
        raise RuntimeError("launchd bootstrap failed: " + result.stderr.strip())
    for _ in range(100):
        current = status(name)
        if current.get("state") == "running" and current.get("pid"):
            try:
                health(name)
                record["pid"] = current["pid"]
                (root / "service.json").write_text(json.dumps(record, indent=2))
                return current
            except (RuntimeError, URLError):
                pass
        exit_code = current.get("last_exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            raise RuntimeError(f"API exited: {current}; inspect its persisted log")
        time.sleep(0.1)
    raise RuntimeError("API has not become healthy; inspect " + str(root / "api.log"))


def stop(name):
    current = status(name)
    if not current["registered"]:
        return current
    _, _, target = runtime(name)
    result = command("bootout", target)
    if result.returncode:
        raise RuntimeError("Unable to stop the named job: " + result.stderr.strip())
    for _ in range(100):
        current = status(name)
        if not current["registered"]:
            return current
        time.sleep(0.1)
    raise RuntimeError("Named job is still unloading; inspect its status before restarting")


def get_json(base, path):
    with urlopen(base + path, timeout=10) as response:
        return json.load(response)


def health(name, *, run_id=None, task_id=None):
    root, _, _ = runtime(name)
    record = json.loads((root / "service.json").read_text())
    base = f"http://{record['host']}:{record['port']}"
    if get_json(base, "/api/health").get("status") != "ok":
        raise RuntimeError("API health is not ok")
    result = {"status": "ok", "url": base, "checked_at": datetime.now(timezone.utc).isoformat()}
    if task_id:
        task = get_json(base, "/api/tasks/" + task_id)
        result["task"] = {"task_id": task["task_id"], "status": task["status"]}
    if run_id:
        run = get_json(base, "/api/analyses/" + run_id)
        result["run"] = {"run_id": run["run_id"], "case_count": run["case_count"]}
        frames = get_json(base, run["evidence_download_url"])
        result["frame_count"] = len(frames["frames"])
        media = [
            v
            for c in run["cases"]
            for v in c.get("visual_evidence", [])
            if v.get("available") and v.get("url")
        ]
        for item in media:
            with urlopen(base + item["url"], timeout=10) as response:
                if not response.read(16):
                    raise RuntimeError("Media preview is empty")
        result["readable_media_count"] = len(media)
    (root / "last-health.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status", "health"])
    parser.add_argument("--name", default="rootlens-api")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--run-id")
    parser.add_argument("--task-id")
    args = parser.parse_args()
    try:
        if args.action == "start":
            result = start(args.name, host=args.host, port=args.port)
        elif args.action == "stop":
            result = stop(args.name)
        elif args.action == "status":
            result = status(args.name)
        else:
            result = health(args.name, run_id=args.run_id, task_id=args.task_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, ValueError, OSError, HTTPError, URLError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
