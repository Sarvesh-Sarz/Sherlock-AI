import json

import pytest

from app.models.tool_result import ToolStatus
from app.tools import audio
from app.tools._command import CommandError

REALTEK = {
    "Name": "Realtek High Definition Audio",
    "Status": "OK",
    "Manufacturer": "Realtek",
    "PNPDeviceID": "HDAUDIO\\FUNC_01",
    "ConfigManagerErrorCode": 0,
}


@pytest.fixture(autouse=True)
def audio_service(monkeypatch):
    monkeypatch.setattr(audio, "_audio_service_status", lambda: "running")


def fake_powershell(monkeypatch, data):
    monkeypatch.setattr(audio, "run_powershell_json", lambda *a, **k: data)


def test_single_device_object_is_wrapped_into_a_list(monkeypatch):
    fake_powershell(monkeypatch, REALTEK)  # ConvertTo-Json emits a bare object for one device
    result = audio.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["device_count"] == 1
    assert result.payload["working_device_count"] == 1
    assert result.payload["audio_service_status"] == "running"
    assert result.payload["devices"][0]["name"] == "Realtek High Definition Audio"


def test_broken_device_is_counted_but_not_working(monkeypatch):
    broken = {**REALTEK, "Name": "USB Headset", "Status": "Error", "ConfigManagerErrorCode": 22}
    fake_powershell(monkeypatch, [REALTEK, broken])
    payload = audio.run().payload

    assert payload["device_count"] == 2
    assert payload["working_device_count"] == 1
    assert payload["devices"][1]["error_code"] == 22


def test_no_devices_is_an_error_not_an_empty_success(monkeypatch):
    fake_powershell(monkeypatch, None)
    result = audio.run()

    assert result.status == ToolStatus.ERROR
    assert "no audio devices" in result.payload["error"]


def test_powershell_failure_message_is_preserved(monkeypatch):
    def boom(*a, **k):
        raise CommandError("powershell.exe did not respond within 15 seconds")

    monkeypatch.setattr(audio, "run_powershell_json", boom)
    result = audio.run()

    assert result.status == ToolStatus.ERROR
    assert "did not respond" in result.payload["error"]


def test_unexpected_json_shape_is_an_error(monkeypatch):
    fake_powershell(monkeypatch, "oops")
    assert audio.run().status == ToolStatus.ERROR


def test_non_object_entries_are_skipped(monkeypatch):
    fake_powershell(monkeypatch, [REALTEK, None, 5])
    assert audio.run().payload["device_count"] == 1


def test_service_state_unreadable_is_none_not_healthy(monkeypatch):
    monkeypatch.undo()  # use the real helper, not the fixture's stub

    class NoServices:
        def win_service_get(self, name):
            raise AttributeError("not windows")

    monkeypatch.setattr(audio, "psutil", NoServices())
    assert audio._audio_service_status() is None


def test_service_state_is_read_through_psutil(monkeypatch):
    monkeypatch.undo()

    class Service:
        def status(self):
            return "stopped"

    class Psutil:
        def win_service_get(self, name):
            assert name == "Audiosrv"
            return Service()

    monkeypatch.setattr(audio, "psutil", Psutil())
    assert audio._audio_service_status() == "stopped"


def test_payload_is_json_serializable(monkeypatch):
    fake_powershell(monkeypatch, [REALTEK])
    json.dumps(audio.run().payload)
