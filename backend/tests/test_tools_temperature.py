from app.tools import temperature
from app.tools.temperature import run


def test_temperature_returns_valid_result(monkeypatch):
    # Still exercises the real PowerShell path on Windows, but bounded:
    # an unprivileged ACPI query can otherwise wait out the full tool
    # timeout and make the whole suite crawl.
    real = temperature.run_powershell_json
    monkeypatch.setattr(temperature, "run_powershell_json", lambda command, **kw: real(command, timeout=4))

    result = run()

    assert result.tool_name == "temperature"
    assert result.status.value in {"success", "error"}

    if result.status.value == "success":
        assert "source" in result.payload
        assert "sensor_count" in result.payload
        assert "current_temperature_c" in result.payload
        assert "sensors" in result.payload