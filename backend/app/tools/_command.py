"""Constrained subprocess helpers shared by the Windows diagnostic tools.

Every external command a tool runs goes through here so the safety rules
live in one place instead of being re-implemented (or forgotten) per tool:

- Fixed argument lists only; never `shell=True`, never user input.
- A hard timeout, so a hung PowerShell or netsh cannot hang an investigation.
- No console window. Without CREATE_NO_WINDOW, a backend launched from a
  GUI app (the packaged Tauri build) flashes a black console window for
  every command.
- stdin closed, so a command can never block waiting for input.
- Read-only by construction: callers pass queries (`Get-CimInstance`,
  `netsh ... show`), and nothing in this module writes or configures.

Failures are raised as `CommandError` with a message written to be shown
to the user as-is ("PowerShell did not respond within 15 seconds"),
because a tool's error message becomes part of the evidence and trace.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

# Used only when the `subprocess` module does not define it (non-Windows).
_CREATE_NO_WINDOW = 0x08000000

# PowerShell's own cold start plus the first CIM query regularly takes
# several seconds on a laptop with antivirus; 5s produced false timeouts.
DEFAULT_TIMEOUT_SECONDS = 15.0

_POWERSHELL_UTF8_PREFIX = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "


class CommandError(RuntimeError):
    """An external diagnostic command could not produce usable output."""


def run_command(
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    encoding: str = "utf-8",
) -> subprocess.CompletedProcess[str]:
    """Run a fixed command line and return the completed process.

    Raises `CommandError` if the program is missing or times out. A
    non-zero exit status is *not* an error here: callers decide what it
    means, because some tools (netsh) explain failures on stdout.
    """
    extra: dict[str, Any] = {}
    if sys.platform == "win32":
        extra["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", _CREATE_NO_WINDOW)

    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
            **extra,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"{args[0]} did not respond within {timeout:g} seconds") from exc
    except OSError as exc:
        raise CommandError(f"{args[0]} could not be run: {exc}") from exc


def run_powershell_json(command: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any | None:
    """Run a read-only PowerShell query that ends in `ConvertTo-Json`.

    Returns the parsed JSON, or None if the query legitimately printed
    nothing (for example, no matching devices). Raises `CommandError`
    for every real failure, including the case PowerShell makes easy to
    miss: a CIM error such as "Access denied" is written to stderr while
    the process still exits 0 with empty stdout.
    """
    completed = run_command(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_UTF8_PREFIX + command],
        timeout=timeout,
    )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        raise CommandError(first_line(stderr) or first_line(stdout) or f"PowerShell exited with code {completed.returncode}")

    if not stdout:
        if stderr:
            raise CommandError(first_line(stderr))
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CommandError("PowerShell returned output that was not valid JSON") from exc


def first_line(text: str | None, limit: int = 200) -> str:
    """First non-empty line of `text`, trimmed, for use in error messages."""
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return ""
