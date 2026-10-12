from app.tools.temperature import run


def test_temperature_returns_valid_result():
    result = run()

    assert result.tool_name == "temperature"
    assert result.status.value in {"success", "error"}

    if result.status.value == "success":
        assert "source" in result.payload
        assert "sensor_count" in result.payload
        assert "current_temperature_c" in result.payload
        assert "sensors" in result.payload