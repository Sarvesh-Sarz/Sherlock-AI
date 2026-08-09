"""Tests for the startup diagnostic tool.

Registry access is faked with a small stand-in object matching the
`winreg` names `startup.py` actually uses (`HKEY_CURRENT_USER`,
`HKEY_LOCAL_MACHINE`, `KEY_READ`, `OpenKey`, `EnumValue`) rather than
depending on `winreg` existing at all — it doesn't, on the non-Windows
machines this suite also needs to run on.

Startup-folder access is exercised against real temporary directories
(via pytest's `tmp_path`), with `APPDATA`/`PROGRAMDATA` pointed at them
and the real nested `Microsoft/Windows/Start Menu/Programs/Startup`
structure created underneath — `pathlib` behaves identically
cross-platform, so `_user_startup_folder`/`_common_startup_folder`'s
actual path-building logic is exercised rather than bypassed.

Tests never depend on the developer machine's actual startup
configuration.
"""

from pathlib import Path

import pytest

from app.models.tool_result import ToolStatus
from app.tools import startup


class _FakeRegistryKey:
    """Stands in for the object `winreg.OpenKey` returns."""

    def __init__(self, values: list[tuple[str, str]]) -> None:
        self.values = values

    def __enter__(self) -> "_FakeRegistryKey":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class _FakeWinreg:
    """Minimal stand-in for the `winreg` module.

    `hive_values` maps a hive constant to the (name, command) pairs
    `OpenKey`/`EnumValue` should report for it — a hive with no entry in
    this dict behaves exactly like a real, empty Run key. `hive_errors`
    maps a hive constant to an exception `OpenKey` should raise instead
    — used to simulate e.g. HKLM being denied by permissions.
    """

    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ = 0x20019

    def __init__(
        self,
        hive_values: dict[str, list[tuple[str, str]]] | None = None,
        hive_errors: dict[str, OSError] | None = None,
    ) -> None:
        self._hive_values = hive_values or {}
        self._hive_errors = hive_errors or {}

    def OpenKey(self, hive: str, path: str, reserved: int, access: int) -> _FakeRegistryKey:  # noqa: N802
        if hive in self._hive_errors:
            raise self._hive_errors[hive]
        return _FakeRegistryKey(self._hive_values.get(hive, []))

    def EnumValue(self, key: _FakeRegistryKey, index: int) -> tuple[str, str, int]:  # noqa: N802
        if index >= len(key.values):
            raise OSError("no more values")
        name, command = key.values[index]
        return name, command, 1  # 1 == REG_SZ; the value type isn't used by startup.py


def _use_fake_winreg(
    monkeypatch: pytest.MonkeyPatch,
    hive_values: dict[str, list[tuple[str, str]]] | None = None,
    hive_errors: dict[str, OSError] | None = None,
) -> None:
    monkeypatch.setattr(startup, "winreg", _FakeWinreg(hive_values=hive_values, hive_errors=hive_errors))


def _disable_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make both registry sources report as unavailable, so a test can
    focus purely on folder behavior.
    """
    monkeypatch.setattr(startup, "winreg", None)


def _disable_startup_folders(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make both folder sources report as unavailable, so a test can
    focus purely on registry behavior.
    """
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("PROGRAMDATA", raising=False)


def _set_user_startup_folder(monkeypatch: pytest.MonkeyPatch, base: Path, *filenames: str) -> Path:
    """Point APPDATA at `base` and create the real nested folder
    `_user_startup_folder()` would compute from it, so the actual
    path-building logic runs, not a stand-in.
    """
    monkeypatch.setenv("APPDATA", str(base))
    folder = base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    folder.mkdir(parents=True)
    for filename in filenames:
        (folder / filename).write_text("")
    return folder


def _set_common_startup_folder(monkeypatch: pytest.MonkeyPatch, base: Path, *filenames: str) -> Path:
    monkeypatch.setenv("PROGRAMDATA", str(base))
    folder = base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    folder.mkdir(parents=True)
    for filename in filenames:
        (folder / filename).write_text("")
    return folder


# --- Individual sources ------------------------------------------------


def test_collects_hkcu_run_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake_winreg(monkeypatch, hive_values={"HKCU": [("OneDrive", '"C:\\OneDrive.exe" /background')]})
    _disable_startup_folders(monkeypatch)

    result = startup.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["entries"] == [
        {"name": "OneDrive", "command": '"C:\\OneDrive.exe" /background', "source": "user_run"}
    ]


def test_collects_hklm_run_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake_winreg(monkeypatch, hive_values={"HKLM": [("Discord", "C:\\Discord.exe --processStart Discord.exe")]})
    _disable_startup_folders(monkeypatch)

    result = startup.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["entries"] == [
        {"name": "Discord", "command": "C:\\Discord.exe --processStart Discord.exe", "source": "machine_run"}
    ]


def test_collects_startup_folder_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _set_user_startup_folder(monkeypatch, tmp_path, "Spotify.lnk")
    monkeypatch.delenv("PROGRAMDATA", raising=False)
    _disable_registry(monkeypatch)

    result = startup.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["entries"] == [
        {"name": "Spotify", "command": str(folder / "Spotify.lnk"), "source": "user_startup_folder"}
    ]


def test_startup_folder_ignores_subdirectories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _set_user_startup_folder(monkeypatch, tmp_path, "Spotify.lnk")
    (folder / "SomeSubfolder").mkdir()
    monkeypatch.delenv("PROGRAMDATA", raising=False)
    _disable_registry(monkeypatch)

    result = startup.run()

    names = [entry["name"] for entry in result.payload["entries"]]
    assert names == ["Spotify"]


# --- Multiple sources combined -----------------------------------------


def test_combines_all_four_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_fake_winreg(
        monkeypatch,
        hive_values={"HKCU": [("OneDrive", "onedrive.exe")], "HKLM": [("Discord", "discord.exe")]},
    )
    _set_user_startup_folder(monkeypatch, tmp_path / "user", "Spotify.lnk")
    _set_common_startup_folder(monkeypatch, tmp_path / "common", "Zoom.lnk")

    result = startup.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["total_entries"] == 4
    sources = {entry["source"] for entry in result.payload["entries"]}
    assert sources == {"user_run", "machine_run", "user_startup_folder", "common_startup_folder"}
    assert result.payload["sources_unavailable"] == []


# --- Empty configuration -------------------------------------------------


def test_empty_startup_configuration_is_a_successful_empty_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every source readable, none of them have anything configured —
    genuinely zero entries, and that's a normal SUCCESS, not an error.
    """
    _use_fake_winreg(monkeypatch, hive_values={"HKCU": [], "HKLM": []})
    _set_user_startup_folder(monkeypatch, tmp_path / "user")
    _set_common_startup_folder(monkeypatch, tmp_path / "common")

    result = startup.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["total_entries"] == 0
    assert result.payload["entries"] == []
    assert result.payload["sources_unavailable"] == []


# --- Partial failure -----------------------------------------------------


def test_one_source_failing_does_not_affect_the_others(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The task's own example: HKCU works, HKLM fails on permissions,
    the user Startup folder works.
    """
    _use_fake_winreg(
        monkeypatch,
        hive_values={"HKCU": [("OneDrive", "onedrive.exe")]},
        hive_errors={"HKLM": PermissionError("Access is denied")},
    )
    _set_user_startup_folder(monkeypatch, tmp_path, "Spotify.lnk")
    monkeypatch.delenv("PROGRAMDATA", raising=False)

    result = startup.run()

    assert result.status == ToolStatus.SUCCESS
    entries = result.payload["entries"]
    assert {e["source"] for e in entries} == {"user_run", "user_startup_folder"}

    unavailable = result.payload["sources_unavailable"]
    assert len(unavailable) == 2  # machine_run (denied) + common_startup_folder (no PROGRAMDATA)
    machine_run_failure = next(item for item in unavailable if item["source"] == "machine_run")
    assert "Access is denied" in machine_run_failure["reason"]


# --- Complete failure ------------------------------------------------------


def test_complete_collection_failure_returns_error_not_empty_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """If literally nothing could be read, that must not look identical
    to "this machine has zero startup entries" — it's an error.
    """
    _disable_registry(monkeypatch)
    _disable_startup_folders(monkeypatch)

    result = startup.run()

    assert result.status == ToolStatus.ERROR
    assert result.tool_name == "startup"
    assert "All 4 startup sources failed" in result.payload["error"]


def test_run_never_raises_even_on_a_completely_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> list[dict[str, str]]:
        raise ValueError("something nobody anticipated")

    monkeypatch.setattr(startup, "_SOURCES", [("user_run", _boom)])

    # Should not raise. A ValueError isn't even an OSError, so this also
    # exercises run()'s own outer safety net, not just _collect's
    # per-source OSError handling.
    result = startup.run()

    assert result.status == ToolStatus.ERROR
    assert "something nobody anticipated" in result.payload["error"]


# --- Result shape ----------------------------------------------------------


def test_result_has_expected_tool_result_structure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_fake_winreg(monkeypatch, hive_values={"HKCU": [("OneDrive", "onedrive.exe")], "HKLM": []})
    _set_user_startup_folder(monkeypatch, tmp_path)
    monkeypatch.delenv("PROGRAMDATA", raising=False)

    result = startup.run()

    assert result.tool_name == "startup"
    assert result.status == ToolStatus.SUCCESS
    assert result.collected_at is not None
    assert set(result.payload.keys()) == {"total_entries", "entries", "sources_unavailable"}

    entry = result.payload["entries"][0]
    assert set(entry.keys()) == {"name", "command", "source"}


def test_each_entry_records_its_originating_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_fake_winreg(monkeypatch, hive_values={"HKCU": [("A", "a.exe")], "HKLM": [("B", "b.exe")]})
    _set_user_startup_folder(monkeypatch, tmp_path / "user", "C.lnk")
    _set_common_startup_folder(monkeypatch, tmp_path / "common", "D.lnk")

    result = startup.run()

    by_name = {entry["name"]: entry["source"] for entry in result.payload["entries"]}
    assert by_name == {
        "A": "user_run",
        "B": "machine_run",
        "C": "user_startup_folder",
        "D": "common_startup_folder",
    }


def test_run_entries_are_sorted_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake_winreg(monkeypatch, hive_values={"HKCU": [("Zoom", "zoom.exe"), ("Adobe", "adobe.exe")]})
    _disable_startup_folders(monkeypatch)

    result = startup.run()

    names = [entry["name"] for entry in result.payload["entries"]]
    assert names == ["Adobe", "Zoom"]
