"""Wi-Fi tool, driven by realistic `netsh wlan show interfaces` output."""

import subprocess

import pytest

from app.models.tool_result import ToolStatus
from app.tools import wifi
from app.tools._command import CommandError

CONNECTED = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201 160MHz
    GUID                   : 5b1f6a1e-0000-0000-0000-000000000000
    Physical address       : aa:bb:cc:dd:ee:ff
    Interface type         : Primary
    State                  : connected
    SSID                   : HomeNetwork
    AP BSSID               : 11:22:33:44:55:66
    Band                   : 5 GHz
    Network type           : Infrastructure
    Radio type             : 802.11ac
    Authentication         : WPA2-Personal
    Cipher                 : CCMP
    Connection mode        : Auto Connect
    Channel                : 44
    Receive rate (Mbps)    : 433.3
    Transmit rate (Mbps)   : 390
    Signal                 : 91%
    Profile                : HomeNetwork
"""

DISCONNECTED = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201 160MHz
    GUID                   : 5b1f6a1e-0000-0000-0000-000000000000
    Physical address       : aa:bb:cc:dd:ee:ff
    Interface type         : Primary
    State                  : disconnected
"""


def fake_netsh(monkeypatch, stdout="", returncode=0, stderr=""):
    monkeypatch.setattr(
        wifi,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, returncode, stdout, stderr),
    )


def test_connected_output_is_parsed_into_a_payload(monkeypatch):
    fake_netsh(monkeypatch, CONNECTED)
    result = wifi.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload == {
        "connected": True,
        "ssid": "HomeNetwork",  # not confused with the "AP BSSID" line
        "signal_percent": 91,
        "link_speed_mbps": 433.3,
        "interface": "Wi-Fi",
        "radio_type": "802.11ac",
        "authentication": "WPA2-Personal",
    }


def test_disconnected_adapter_is_a_successful_reading_of_not_connected(monkeypatch):
    fake_netsh(monkeypatch, DISCONNECTED)
    result = wifi.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["connected"] is False
    assert result.payload["ssid"] is None
    assert result.payload["signal_percent"] is None


def test_netsh_failure_surfaces_the_message_netsh_printed_on_stdout(monkeypatch):
    fake_netsh(monkeypatch, "The Wireless AutoConfig Service (wlansvc) is not running.\n", returncode=1)
    result = wifi.run()

    assert result.status == ToolStatus.ERROR
    assert "wlansvc" in result.payload["error"]


def test_no_wireless_adapter_is_an_error_not_a_claim_of_disconnection(monkeypatch):
    fake_netsh(monkeypatch, "There is no wireless interface on the system.\n", returncode=1)
    result = wifi.run()

    assert result.status == ToolStatus.ERROR
    assert "no wireless interface" in result.payload["error"]


def test_unrecognised_output_is_unknown_never_not_connected(monkeypatch):
    # e.g. a non-English Windows: labels differ, so no "State" line matches.
    localized = "    Nom                    : Wi-Fi\n    Etat                   : connecte\n"
    fake_netsh(monkeypatch, localized)
    result = wifi.run()

    assert result.status == ToolStatus.ERROR
    assert "connected" not in result.payload
    assert "did not report a Wi-Fi connection state" in result.payload["error"]
    assert "Nom" in result.payload["error"]  # shows what netsh actually printed


def test_timeout_is_reported_as_an_error(monkeypatch):
    def boom(*a, **k):
        raise CommandError("netsh did not respond within 10 seconds")

    monkeypatch.setattr(wifi, "run_command", boom)
    result = wifi.run()

    assert result.status == ToolStatus.ERROR
    assert "did not respond" in result.payload["error"]


@pytest.mark.parametrize(
    "line, expected",
    [("Receive rate (Mbps)    : 54", 54.0), ("Receive rate (Mbps)    : n/a\n    Transmit rate (Mbps)   : 72", 72.0)],
)
def test_link_speed_falls_back_to_transmit_rate(line, expected):
    assert wifi._parse_link_speed(line) == expected


def test_link_speed_unreadable_is_none():
    assert wifi._parse_link_speed("Receive rate (Mbps)    : fast") is None
    assert wifi._parse_signal("    Signal                 : strong") is None
