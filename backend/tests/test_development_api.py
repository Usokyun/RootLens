"""Manual launchd control has explicit ownership, logs and no secret/model retry copying."""

from types import SimpleNamespace

import pytest

from scripts import development_api as service


def test_launchd_status_distinguishes_never_exited_from_real_exit():
    running = service.parse_job_status(
        "\tstate = running\n\tpid = 1234\n\tlast exit code = (never exited)\n"
    )
    assert running == {"state": "running", "pid": 1234, "last_exit_code": "(never exited)"}
    assert service.parse_job_status("last exit code = 1\n")["last_exit_code"] == 1


def test_job_is_manual_session_scoped_and_does_not_copy_api_secrets(tmp_path):
    config = service.job_config(
        "com.rootlens.dev.example",
        tmp_path,
        "127.0.0.1",
        8012,
        {
            "KGTRACE_POSTGRES_DSN": "postgresql://test-only",
            "NEO4J_URI": "bolt://test-only",
            "OPENAI_API_KEY": "never-copy",
            "DEEPSEEK_API_KEY": "never-copy-either",
        },
    )
    assert config["KeepAlive"] is False
    assert config["RunAtLoad"] is True
    assert config["ProgramArguments"][1].endswith("scripts/dev.py")
    assert config["EnvironmentVariables"]["ROOTLENS_API_PORT"] == "8012"
    assert "OPENAI_API_KEY" not in config["EnvironmentVariables"]
    assert "DEEPSEEK_API_KEY" not in config["EnvironmentVariables"]
    assert str(tmp_path) in config["StandardOutPath"]


def test_names_cannot_escape_project_service_namespace():
    for name in ("../../ssh", "other service", "", "UPPER"):
        with pytest.raises(ValueError):
            service.runtime(name)


def test_manual_restart_reuses_explicit_test_connections_not_model_secrets(tmp_path):
    config = service.job_config(
        "com.rootlens.dev.example",
        tmp_path,
        "127.0.0.1",
        8012,
        {},
        previous_env={
            "KGTRACE_POSTGRES_DSN": "postgresql://saved-test-only",
            "NEO4J_URI": "bolt://saved-test-only",
            "OPENAI_API_KEY": "must-not-copy",
        },
    )
    assert config["EnvironmentVariables"]["KGTRACE_POSTGRES_DSN"] == "postgresql://saved-test-only"
    assert config["EnvironmentVariables"]["NEO4J_URI"] == "bolt://saved-test-only"
    assert "OPENAI_API_KEY" not in config["EnvironmentVariables"]


def test_stop_only_targets_named_launchd_job(monkeypatch):
    calls = []
    states = iter(
        [{"registered": True}, {"registered": True, "state": "SIGTERMed"}, {"registered": False}]
    )
    monkeypatch.setattr(service, "status", lambda name: next(states))
    waits = []
    monkeypatch.setattr(service.time, "sleep", lambda seconds: waits.append(seconds))
    monkeypatch.setattr(
        service, "command", lambda *args: calls.append(args) or SimpleNamespace(returncode=0)
    )
    assert service.stop("two-loop-api")["registered"] is False
    assert calls == [("bootout", f"gui/{service.os.getuid()}/com.rootlens.dev.two-loop-api")]
    assert waits == [0.1]


def test_stop_permission_error_is_reported_without_kill_or_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "status", lambda name: {"registered": True})
    monkeypatch.setattr(
        service,
        "command",
        lambda *args: (
            calls.append(args) or SimpleNamespace(returncode=1, stderr="permission denied")
        ),
    )
    with pytest.raises(RuntimeError, match="permission denied"):
        service.stop("two-loop-api")
    assert len(calls) == 1
