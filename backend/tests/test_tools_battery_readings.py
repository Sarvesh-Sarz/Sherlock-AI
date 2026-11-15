from collections import namedtuple

import psutil
import pytest

from app.models.tool_result import ToolStatus
from app.tools import battery

Battery = namedtuple("Battery", "percent secsleft power_plugged")


def use(monkeypatch, reading):
    monkeypatch.setattr(battery.psutil, "sensors_battery", lambda: reading, raising=False)


def test_desktop_without_a_battery_is_an_error_not_zero_percent(monkeypatch):
    use(monkeypatch, None)
    result = battery.run()
    assert result.status == ToolStatus.ERROR
    assert "not available" in result.payload["error"]


def test_unplugged_reading(monkeypatch):
    use(monkeypatch, Battery(63.0, 5400, False))
    payload = battery.run().payload
    assert payload == {"percent": 63.0, "plugged": False, "charging": False, "seconds_left": 5400}


@pytest.mark.parametrize("secs", [psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED, -5])
def test_unknown_time_remaining_is_none_not_a_fake_number(monkeypatch, secs):
    use(monkeypatch, Battery(80.0, secs, True))
    assert battery.run().payload["seconds_left"] is None


def test_full_and_plugged_is_not_charging(monkeypatch):
    use(monkeypatch, Battery(100.0, psutil.POWER_TIME_UNLIMITED, True))
    assert battery.run().payload["charging"] is False
