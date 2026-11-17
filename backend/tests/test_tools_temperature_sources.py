"""Where temperature readings come from, and why a failure is reported."""

import pytest

from app.models.tool_result import ToolStatus
from app.tools import temperature
from app.tools._command import CommandError


class Entry:
    def __init__(self, current, label="", high=None, critical=None):
        self.current, self.label, self.high, self.critical = current, label, high, critical


def no_psutil_sensors(monkeypatch):
    monkeypatch.setattr(temperature.psutil, "sensors_temperatures", lambda fahrenheit=False: {}, raising=False)


def test_psutil_sensors_are_preferred(monkeypatch):
    monkeypatch.setattr(
        temperature.psutil,
        "sensors_temperatures",
        lambda fahrenheit=False: {"coretemp": [Entry(61.0, "Package", high=100.0), Entry(None)]},
        raising=False,
    )
    monkeypatch.setattr(temperature, "run_powershell_json", lambda *a, **k: pytest.fail("should not be called"))
    payload = temperature.run().payload

    assert payload["source"] == "psutil"
    assert payload["sensor_count"] == 1  # the sensor with no reading is skipped
    assert payload["current_temperature_c"] == 61.0


def test_falls_back_to_acpi_when_psutil_has_no_sensors_api(monkeypatch):
    # psutil has no sensors_temperatures at all on Windows.
    monkeypatch.delattr(temperature.psutil, "sensors_temperatures", raising=False)
    monkeypatch.setattr(
        temperature, "run_powershell_json", lambda *a, **k: {"InstanceName": "ACPI\\TZ0", "CurrentTemperature": 3281}
    )
    payload = temperature.run().payload

    assert payload["source"] == "windows_acpi"
    assert payload["sensors"][0]["name"] == "ACPI\\TZ0"
    assert payload["current_temperature_c"] == pytest.approx(54.95, abs=0.06)  # tenths of Kelvin -> C


def test_acpi_entries_without_a_numeric_reading_are_skipped(monkeypatch):
    no_psutil_sensors(monkeypatch)
    monkeypatch.setattr(
        temperature,
        "run_powershell_json",
        lambda *a, **k: [{"InstanceName": "a", "CurrentTemperature": None}, {"InstanceName": "b", "CurrentTemperature": True}, "x"],
    )
    result = temperature.run()
    assert result.status == ToolStatus.ERROR


def test_access_denied_is_explained_as_a_permissions_limit(monkeypatch):
    no_psutil_sensors(monkeypatch)

    def denied(*a, **k):
        raise CommandError("Get-CimInstance : Access denied")

    monkeypatch.setattr(temperature, "run_powershell_json", denied)
    result = temperature.run()

    assert result.status == ToolStatus.ERROR  # unknown, not a normal reading
    assert "Access denied" in result.payload["error"]
    assert "administrator" in result.payload["error"]


def test_timeout_reason_is_reported_without_an_admin_hint(monkeypatch):
    no_psutil_sensors(monkeypatch)

    def slow(*a, **k):
        raise CommandError("powershell.exe did not respond within 15 seconds")

    monkeypatch.setattr(temperature, "run_powershell_json", slow)
    error = temperature.run().payload["error"]

    assert "did not respond" in error
    assert "administrator" not in error


def test_genuinely_no_sensors_gives_the_plain_message(monkeypatch):
    no_psutil_sensors(monkeypatch)
    monkeypatch.setattr(temperature, "run_powershell_json", lambda *a, **k: None)
    error = temperature.run().payload["error"]

    assert error == "No temperature sensors are available on this Windows system"
