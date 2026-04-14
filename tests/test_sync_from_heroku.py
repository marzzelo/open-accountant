import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_from_heroku.py"
MODULE_SPEC = importlib.util.spec_from_file_location("sync_from_heroku", MODULE_PATH)
sync_from_heroku = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(sync_from_heroku)


def test_resolve_heroku_cli_uses_shutil_which_result_on_windows(monkeypatch):
    calls = []

    def fake_which(command):
        calls.append(command)
        if command == "heroku":
            return r"C:\Program Files\heroku\bin\heroku.CMD"
        return None

    monkeypatch.setattr(sync_from_heroku.sys, "platform", "win32")
    monkeypatch.setattr(sync_from_heroku.shutil, "which", fake_which)

    assert sync_from_heroku._resolve_heroku_cli() == (
        r"C:\Program Files\heroku\bin\heroku.CMD"
    )
    assert calls == ["heroku"]


def test_resolve_heroku_cli_checks_windows_cmd_fallback(monkeypatch):
    calls = []

    def fake_which(command):
        calls.append(command)
        if command == "heroku.cmd":
            return r"C:\Program Files\heroku\bin\heroku.cmd"
        return None

    monkeypatch.setattr(sync_from_heroku.sys, "platform", "win32")
    monkeypatch.setattr(sync_from_heroku.shutil, "which", fake_which)

    assert sync_from_heroku._resolve_heroku_cli() == (
        r"C:\Program Files\heroku\bin\heroku.cmd"
    )
    assert calls == ["heroku", "heroku.cmd"]


def test_get_heroku_database_url_uses_noninteractive_stdin(monkeypatch):
    seen = {}

    class FakeResult:
        returncode = 0
        stdout = "postgres://example\n"
        stderr = ""

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen.update(kwargs)
        return FakeResult()

    monkeypatch.setattr(sync_from_heroku, "_resolve_heroku_cli", lambda: "heroku.cmd")
    monkeypatch.setattr(sync_from_heroku.subprocess, "run", fake_run)

    assert sync_from_heroku._get_heroku_database_url("open-accountant") == (
        "postgres://example"
    )
    assert seen["command"] == [
        "heroku.cmd",
        "config:get",
        "DATABASE_URL",
        "--app",
        "open-accountant",
    ]
    assert seen["stdin"] == sync_from_heroku.subprocess.DEVNULL


def test_get_heroku_database_url_reports_auth_failure(monkeypatch, capsys):
    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "Invalid credentials provided.\nError ID: unauthorized"

    monkeypatch.setattr(sync_from_heroku, "_resolve_heroku_cli", lambda: "heroku.cmd")
    monkeypatch.setattr(
        sync_from_heroku.subprocess, "run", lambda *args, **kwargs: FakeResult()
    )

    with pytest.raises(SystemExit) as exc_info:
        sync_from_heroku._get_heroku_database_url("open-accountant")

    assert exc_info.value.code == 1
    output = capsys.readouterr().out
    assert "Heroku CLI authentication failed" in output
    assert "heroku login" in output
