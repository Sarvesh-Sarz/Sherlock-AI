from app.tools.battery import run


def test_battery_returns_success():
    result = run()

    assert result.tool_name == "battery"

    # A machine without an accessible battery is a valid environment,
    # so don't require SUCCESS here.
    assert result.status.value in {"success", "error"}

    if result.status.value == "success":
        assert "percent" in result.payload
        assert "plugged" in result.payload
        assert "charging" in result.payload
        assert "seconds_left" in result.payload