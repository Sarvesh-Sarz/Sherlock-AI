"""The shared command helper. The subprocess tests use the running Python
interpreter as the external program, so they exercise the real code path
(including CREATE_NO_WINDOW on Windows) on any OS."""

import json
import subprocess
import sys

import pytest

from app.tools import _command
from app.tools._command import CommandError, first_line, run_command, run_powershell_json


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=["x"], returncode=returncode, stdout=stdout, stderr=stderr)


# ---- run_command (real subprocesses) ---------------------------------------

def test_run_command_captures_output():
    result = run_command([sys.executable, "-c", "print('hello')"], timeout=20)
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"


def test_run_command_does_not_treat_nonzero_exit_as_an_error():
    result = run_command([sys.executable, "-c", "import sys; print('why'); sys.exit(3)"], timeout=20)
    assert result.returncode == 3
    assert "why" in result.stdout  # netsh explains failures on stdout


def test_run_command_closes_stdin_so_nothing_can_block_on_input():
    result = run_command([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"], timeout=20)
    assert result.stdout.strip() == "''"


def test_run_command_times_out_with_a_readable_message():
    with pytest.raises(CommandError, match="did not respond within 0.5 seconds"):
        run_command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.5)


def test_run_command_reports_a_missing_program():
    with pytest.raises(CommandError, match="could not be run"):
        run_command(["definitely-not-a-real-program-xyz"], timeout=5)


def test_run_command_never_uses_a_shell(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen.update(kwargs, args=args)
        return completed("ok")

    monkeypatch.setattr(_command.subprocess, "run", fake_run)
    run_command(["netsh", "wlan", "show", "interfaces"])
    assert isinstance(seen["args"], list)
    assert not seen.get("shell")
    assert seen["check"] is False
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["timeout"] > 0


# ---- run_powershell_json (run_command stubbed) ------------------------------

def stub(monkeypatch, result):
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(_command, "run_command", fake)
    return calls


def test_powershell_json_parses_output_and_forces_utf8(monkeypatch):
    calls = stub(monkeypatch, completed(json.dumps({"Name": "Realtek Audio"})))
    assert run_powershell_json("Get-Thing | ConvertTo-Json") == {"Name": "Realtek Audio"}
    args = calls[0]
    assert args[0] == "powershell.exe" and "-NoProfile" in args and "-NonInteractive" in args
    assert "UTF8" in args[-1] and args[-1].endswith("Get-Thing | ConvertTo-Json")


def test_powershell_json_returns_none_when_nothing_matched(monkeypatch):
    stub(monkeypatch, completed(""))
    assert run_powershell_json("x") is None


def test_powershell_cim_error_on_stderr_with_exit_zero_is_not_silent(monkeypatch):
    # The case that bit the old code: "Access denied" goes to stderr,
    # stdout is empty, and PowerShell still exits 0.
    stub(monkeypatch, completed("", "Get-CimInstance : Access denied\nAt line:1 char:1\n"))
    with pytest.raises(CommandError, match="Access denied"):
        run_powershell_json("x")


def test_powershell_nonzero_exit_uses_stderr_message(monkeypatch):
    stub(monkeypatch, completed("", "The term 'Nope' is not recognized\nmore", returncode=1))
    with pytest.raises(CommandError, match="not recognized"):
        run_powershell_json("x")


def test_powershell_nonzero_exit_without_output_names_the_code(monkeypatch):
    stub(monkeypatch, completed("", "", returncode=5))
    with pytest.raises(CommandError, match="code 5"):
        run_powershell_json("x")


def test_powershell_invalid_json_is_an_error(monkeypatch):
    stub(monkeypatch, completed("this is not json"))
    with pytest.raises(CommandError, match="not valid JSON"):
        run_powershell_json("x")


def test_powershell_timeout_propagates_as_command_error(monkeypatch):
    stub(monkeypatch, CommandError("powershell.exe did not respond within 15 seconds"))
    with pytest.raises(CommandError, match="did not respond"):
        run_powershell_json("x")


def test_first_line_helper():
    assert first_line("\n  \n  hello  \nworld") == "hello"
    assert first_line(None) == ""
    assert len(first_line("x" * 500)) == 200
