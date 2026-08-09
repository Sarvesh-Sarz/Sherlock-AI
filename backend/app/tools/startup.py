"""Startup diagnostic tool.

Collects evidence about what's configured to run automatically on
Windows sign-in, from the sources readable without administrator
privileges:

1. HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
2. HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
3. The current user's Startup folder
4. The common (all-users) Startup folder

Follows the same shape and failure handling as every other tool in this
package (see `app.tools.cpu` for the pattern this mirrors): a single
`run() -> ToolResult`, never raises. Strictly read-only — nothing here
ever writes to the registry or filesystem, executes, or modifies a
startup entry.

This tool only *collects* evidence. It never labels an entry as slow,
heavy, or responsible for anything — that judgment belongs to a future
Reasoner, not here.

Payload shape on success:

    {
        "total_entries": 3,
        "entries": [
            {"name": "OneDrive", "command": "\"C:\\...\\OneDrive.exe\" /background", "source": "user_run"},
            {"name": "Discord", "command": "C:\\...\\Discord.exe --processStart Discord.exe", "source": "machine_run"},
            {"name": "Spotify", "command": "C:\\...\\Startup\\Spotify.lnk", "source": "user_startup_folder"},
        ],
        "sources_unavailable": [
            {"source": "common_startup_folder", "reason": "..."},
        ],
    }

`sources_unavailable` lists any of the four sources that couldn't be
read (e.g. HKLM commonly needs elevated permissions) — see `_collect`'s
docstring for why this, rather than silent omission, is how a partial
collection is represented here.
"""

import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "startup"

_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

# `winreg` is Windows-only stdlib. Importing it unconditionally would
# make this module fail to import at all on Linux/macOS — breaking
# ToolManager's registry (`from app.tools import ... startup`) on every
# non-Windows dev/test machine, this project's own included. Falling
# back to None keeps the module importable everywhere; `_read_run_key`
# below turns "winreg isn't available" into the same OSError-based
# per-source failure every other unavailable source produces, and tests
# substitute a fake in place of this name (see tests/test_tools_startup.py).
try:
    import winreg
except ImportError:  # pragma: no cover - exercised only on non-Windows
    winreg = None  # type: ignore[assignment]


def run() -> ToolResult:
    """Collect startup-entry evidence from all four sources.

    Never raises: any failure is caught and reported as an error
    `ToolResult` instead, so a failing sensor can't crash an
    investigation.

    Returns:
        A `ToolResult` with status=SUCCESS and startup evidence in
        `payload` (see module docstring — possibly with some sources
        unavailable), or status=ERROR if every source failed, or
        something else entirely unexpected occurred.
    """
    try:
        payload = _collect()
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.SUCCESS,
            collected_at=datetime.now(timezone.utc),
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 — deliberately broad, see app.tools.cpu.
        logger.warning("startup tool failed to collect data: %s", exc, exc_info=True)
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict[str, Any]:
    """Gather startup entries from every source, tolerating per-source failure.

    Each source is read independently: one failing (e.g. HKLM requiring
    elevated permissions this process doesn't have) doesn't stop the
    others from being collected, and is recorded in
    `sources_unavailable` rather than silently dropped — unlike a
    disk volume going away mid-enumeration (see `app.tools.disk`), a
    registry/folder read failing here *is* itself diagnostically
    meaningful (e.g. "Sherlock couldn't check HKLM"), so it's surfaced
    rather than hidden.

    If every source fails, this raises instead of returning a
    misleadingly-empty result: "0 entries because nothing could be
    read" and "0 entries because none are configured" are different
    facts, and only the second one is safe to represent as a normal,
    successful, empty `ToolResult`. The former propagates to `run()`'s
    try/except and becomes an error result instead.
    """
    entries: list[dict[str, str]] = []
    sources_unavailable: list[dict[str, str]] = []

    for source, collect_source in _SOURCES:
        try:
            entries.extend(collect_source())
        except OSError as exc:
            logger.warning("startup tool could not read %s: %s", source, exc, exc_info=True)
            sources_unavailable.append({"source": source, "reason": str(exc)})

    if len(sources_unavailable) == len(_SOURCES):
        failures = "; ".join(f"{item['source']} ({item['reason']})" for item in sources_unavailable)
        raise RuntimeError(f"All {len(_SOURCES)} startup sources failed: {failures}")

    return {
        "total_entries": len(entries),
        "entries": entries,
        "sources_unavailable": sources_unavailable,
    }


def _collect_user_run() -> list[dict[str, str]]:
    if winreg is None:
        raise OSError("winreg is not available on this platform")
    return _read_run_key(winreg.HKEY_CURRENT_USER, "user_run")


def _collect_machine_run() -> list[dict[str, str]]:
    if winreg is None:
        raise OSError("winreg is not available on this platform")
    return _read_run_key(winreg.HKEY_LOCAL_MACHINE, "machine_run")


def _collect_user_startup_folder() -> list[dict[str, str]]:
    folder = _user_startup_folder()
    if folder is None:
        raise OSError("APPDATA environment variable is not set")
    return _read_startup_folder(folder, "user_startup_folder")


def _collect_common_startup_folder() -> list[dict[str, str]]:
    folder = _common_startup_folder()
    if folder is None:
        raise OSError("PROGRAMDATA environment variable is not set")
    return _read_startup_folder(folder, "common_startup_folder")


# The four sources this tool checks, in the order they're reported.
# Adding a fifth source (there isn't one planned) would mean adding one
# more (name, collector) pair here — nothing else in this module.
_SOURCES: list[tuple[str, Callable[[], list[dict[str, str]]]]] = [
    ("user_run", _collect_user_run),
    ("machine_run", _collect_machine_run),
    ("user_startup_folder", _collect_user_startup_folder),
    ("common_startup_folder", _collect_common_startup_folder),
]


def _read_run_key(hive: Any, source: str) -> list[dict[str, str]]:
    """Enumerate every value under a Run key for the given registry hive.

    `winreg.OpenKey` raising `OSError` here (`FileNotFoundError` if the
    key doesn't exist at all, `PermissionError` if access is denied —
    both real, expected outcomes; HKLM commonly needs elevated
    permissions) propagates to the caller, which records it in
    `sources_unavailable`.

    `winreg.EnumValue` raising `OSError` once `index` runs past the
    last value is the normal, documented way to detect the end of
    enumeration — not a real failure — so it's caught locally to end
    the loop, deliberately not the same `OSError` the caller is
    watching for.
    """
    entries: list[dict[str, str]] = []
    with winreg.OpenKey(hive, _RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
        index = 0
        while True:
            try:
                name, command, _value_type = winreg.EnumValue(key, index)
            except OSError:
                break
            entries.append({"name": name, "command": str(command), "source": source})
            index += 1

    entries.sort(key=lambda entry: entry["name"].lower())
    return entries


def _read_startup_folder(folder: Path, source: str) -> list[dict[str, str]]:
    """List every file directly inside a Startup folder.

    A `.lnk` shortcut's actual target command can't be resolved with
    the standard library alone — that requires parsing the binary Shell
    Link format, or the pywin32/COM APIs this project doesn't depend on
    — so `command` here is the shortcut/file's own path, not the
    program it points to. That's still genuine, honestly-labeled
    evidence ("something here is configured to start"), not a
    fabricated best-guess at what it launches.

    `folder.iterdir()` raising `OSError` (`FileNotFoundError` if the
    folder doesn't exist, `PermissionError` if inaccessible) propagates
    to the caller, same as `_read_run_key`'s `OpenKey` failures.
    Subdirectories are skipped — Startup folders don't meaningfully
    nest, and Windows doesn't autostart anything inside one.
    """
    return [
        {"name": item.stem, "command": str(item), "source": source}
        for item in sorted(folder.iterdir())
        if item.is_file()
    ]


def _user_startup_folder() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _common_startup_folder() -> Path | None:
    program_data = os.environ.get("PROGRAMDATA")
    if not program_data:
        return None
    return Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
