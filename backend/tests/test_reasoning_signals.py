"""Deterministic interpretation of evidence, and the baseline reasoner on top of it."""

from datetime import datetime, timezone

import pytest

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import Confidence
from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.baseline_reasoner import BaselineReasoner
from app.reasoning.query_builder import build_research_queries
from app.reasoning.signals import detect_signals


def ev(name, payload, status=ToolStatus.SUCCESS):
    return ToolResult(tool_name=name, status=status, collected_at=datetime.now(timezone.utc), payload=payload)


def titles(evidence):
    return [s.title for s in detect_signals(evidence)]


def only(evidence):
    (signal,) = detect_signals(evidence)
    return signal


# ---- Wi-Fi -------------------------------------------------------------------

def test_disconnected_wifi_is_a_high_confidence_signal():
    signal = only([ev("wifi", {"connected": False, "ssid": None, "signal_percent": None})])
    assert signal.title == "Wi-Fi is not connected to a network"
    assert signal.confidence == Confidence.HIGH


@pytest.mark.parametrize("strength, confidence", [(35, Confidence.MEDIUM), (15, Confidence.HIGH)])
def test_weak_wifi_signal(strength, confidence):
    signal = only([ev("wifi", {"connected": True, "signal_percent": strength, "link_speed_mbps": 300})])
    assert signal.title == "Wi-Fi signal is weak"
    assert signal.confidence == confidence
    assert f"{strength}%" in signal.supporting_evidence[0]


def test_strong_wifi_produces_no_signal():
    assert titles([ev("wifi", {"connected": True, "signal_percent": 90, "link_speed_mbps": 433})]) == []


def test_low_link_speed_is_its_own_signal():
    assert titles([ev("wifi", {"connected": True, "signal_percent": 80, "link_speed_mbps": 24})]) == ["Wi-Fi link speed is low"]


def test_weak_signal_and_low_speed_both_reported():
    found = titles([ev("wifi", {"connected": True, "signal_percent": 30, "link_speed_mbps": 11})])
    assert found == ["Wi-Fi signal is weak", "Wi-Fi link speed is low"]


def test_disconnected_wifi_does_not_also_report_signal_or_speed():
    assert len(detect_signals([ev("wifi", {"connected": False, "signal_percent": 10, "link_speed_mbps": 1})])) == 1


@pytest.mark.parametrize("payload", [{}, {"connected": None}, {"connected": True}, {"connected": True, "signal_percent": "weak", "link_speed_mbps": None}])
def test_unknown_wifi_values_never_become_conclusions(payload):
    assert detect_signals([ev("wifi", payload)]) == []


# ---- Audio -------------------------------------------------------------------

HEALTHY_DEVICE = {"name": "Realtek Audio", "status": "OK", "error_code": 0}


def audio(**overrides):
    return ev("audio", {"device_count": 1, "working_device_count": 1, "audio_service_status": "running", "devices": [HEALTHY_DEVICE], **overrides})


def test_healthy_audio_produces_no_signal():
    assert detect_signals([audio()]) == []


@pytest.mark.parametrize("state", ["stopped", "Stopped", "paused"])
def test_stopped_audio_service_is_high_confidence(state):
    signal = only([audio(audio_service_status=state)])
    assert signal.title == "The Windows Audio service is not running"
    assert signal.confidence == Confidence.HIGH
    assert "services.msc" in signal.recommendation


@pytest.mark.parametrize("state", [None, "running", "start_pending", 5])
def test_unknown_or_running_service_state_is_not_a_signal(state):
    assert detect_signals([audio(audio_service_status=state)]) == []


def test_disabled_device_points_to_enable_in_device_manager():
    device = {"name": "USB Headset", "status": "Error", "error_code": 22}
    signal = only([audio(devices=[HEALTHY_DEVICE, device])])
    assert signal.title == "USB Headset reports a problem"
    assert "disabled" in signal.explanation
    assert "Enable device" in signal.recommendation
    assert signal.confidence == Confidence.HIGH


def test_missing_driver_points_to_reinstalling_it():
    signal = only([audio(devices=[{"name": "Audio", "status": "Error", "error_code": 28}])])
    assert "drivers for the device are not installed" in signal.explanation
    assert "driver" in signal.recommendation


def test_unknown_error_code_is_reported_without_inventing_a_meaning():
    signal = only([audio(devices=[{"name": "Audio", "status": "Error", "error_code": 99}])])
    assert "error code 99" in signal.explanation


def test_unhealthy_status_without_error_code_is_medium():
    signal = only([audio(devices=[{"name": "Audio", "status": "Degraded", "error_code": 0}])])
    assert signal.confidence == Confidence.MEDIUM
    assert "Degraded" in signal.explanation


def test_zero_devices_is_reported():
    signal = only([audio(device_count=0, devices=[])])
    assert signal.title == "No audio devices were detected"


def test_nameless_device_still_gets_a_readable_title():
    signal = only([audio(devices=[{"name": None, "status": "Error", "error_code": 22}])])
    assert signal.title == "An audio device reports a problem"


# ---- Battery -----------------------------------------------------------------

def test_low_unplugged_battery_is_a_low_confidence_signal():
    signal = only([ev("battery", {"percent": 12.0, "plugged": False})])
    assert signal.confidence == Confidence.LOW
    assert "does not show the battery's overall health" in signal.explanation


@pytest.mark.parametrize(
    "payload",
    [{"percent": 12.0, "plugged": True}, {"percent": 60.0, "plugged": False}, {"percent": None, "plugged": False}, {"percent": 12.0}],
)
def test_other_battery_readings_are_not_signals(payload):
    assert detect_signals([ev("battery", payload)]) == []


# ---- Temperature ---------------------------------------------------------------

@pytest.mark.parametrize("temp, confidence", [(88.0, Confidence.MEDIUM), (97.5, Confidence.HIGH)])
def test_high_temperature(temp, confidence):
    signal = only([ev("temperature", {"source": "psutil", "current_temperature_c": temp})])
    assert signal.confidence == confidence


def test_normal_temperature_is_not_a_signal():
    assert detect_signals([ev("temperature", {"source": "psutil", "current_temperature_c": 62.0})]) == []


def test_acpi_readings_carry_the_not_always_the_cpu_caveat():
    acpi = only([ev("temperature", {"source": "windows_acpi", "current_temperature_c": 90.0})])
    direct = only([ev("temperature", {"source": "psutil", "current_temperature_c": 90.0})])
    assert "not always the CPU sensor" in acpi.explanation
    assert "not always the CPU sensor" not in direct.explanation


# ---- The rule that matters most: failed evidence is unknown, never a signal -----

@pytest.mark.parametrize(
    "name, payload",
    [
        ("wifi", {"connected": False}),
        ("audio", {"device_count": 0, "audio_service_status": "stopped", "devices": []}),
        ("battery", {"percent": 5.0, "plugged": False}),
        ("temperature", {"current_temperature_c": 120.0}),
    ],
)
def test_failed_tools_produce_no_signals(name, payload):
    assert detect_signals([ev(name, payload, ToolStatus.ERROR)]) == []


# ---- Baseline reasoner end to end ------------------------------------------------

def plan():
    return InvestigationPlan(
        problem_description="my wifi is slow",
        tools_to_execute=["wifi"],
        matched_keywords=["wifi"],
        created_at=datetime.now(timezone.utc),
    )


def test_weak_wifi_now_reaches_the_report_as_a_supported_hypothesis():
    evidence = [ev("wifi", {"connected": True, "signal_percent": 18, "link_speed_mbps": 150})]
    report = BaselineReasoner().investigate("c1", "my wifi is slow", plan(), evidence, [])

    assert "did not find a signal" not in report.summary  # the gap this change closes
    assert [h.title for h in report.hypotheses] == ["Wi-Fi signal is weak"]
    assert report.hypotheses[0].supporting_evidence == ["Wi-Fi signal strength: 18%."]
    assert report.confidence == Confidence.HIGH
    assert report.recommendations[0].title.startswith("Try moving closer")


def test_failed_wifi_still_yields_an_honest_no_finding_report():
    report = BaselineReasoner().investigate("c1", "my wifi is slow", plan(), [ev("wifi", {"error": "x"}, ToolStatus.ERROR)], [])
    assert report.hypotheses == []
    assert "did not find a signal" in report.summary


def test_new_signals_feed_research_queries():
    evidence = [ev("audio", {"device_count": 1, "audio_service_status": "stopped", "devices": [HEALTHY_DEVICE]})]
    assert "Windows Audio service not running no sound" in build_research_queries("no sound", evidence)


# ---- Network (connection beyond the router) ---------------------------------------

def net(**overrides):
    payload = {
        "host": "www.msftconnecttest.com", "attempted": 3, "successful": 3, "failed_samples": 0,
        "dns_ms": 30.0, "connect_ms": 40.0, "first_byte_ms": 80.0, "response_ok": True,
    }
    return ev("network", {**payload, **overrides})


def test_a_healthy_connection_produces_no_signal():
    assert detect_signals([net()]) == []


@pytest.mark.parametrize("ms, confidence", [(700.0, Confidence.MEDIUM), (2400.0, Confidence.HIGH)])
def test_slow_internet_responses(ms, confidence):
    signal = only([net(first_byte_ms=ms)])
    assert signal.title == "Internet responses are slow"
    assert signal.confidence == confidence
    assert "another device" in signal.recommendation  # separates "this PC" from "the network"


def test_slow_dns_is_its_own_signal_and_is_careful_on_managed_networks():
    signal = only([net(dns_ms=650.0)])
    assert signal.title == "Looking up website names is slow"
    assert "work or school network" in signal.recommendation


def test_unexpected_response_suggests_a_portal_or_proxy():
    signal = only([net(response_ok=False)])
    assert signal.title == "The network did not return the expected response"
    assert "proxy" in signal.explanation and signal.confidence == Confidence.MEDIUM


def test_partial_failures_are_reported_with_counts():
    signal = only([net(successful=2, failed_samples=1)])
    assert signal.title == "Some internet connection checks failed"
    assert "1 of 3" in signal.explanation


@pytest.mark.parametrize(
    "overrides",
    [{"first_byte_ms": None}, {"first_byte_ms": "slow"}, {"dns_ms": True}, {"attempted": None, "failed_samples": None}, {"response_ok": None}],
)
def test_missing_or_malformed_network_values_are_not_conclusions(overrides):
    assert detect_signals([net(**overrides)]) == []


def test_a_failed_network_check_is_unknown_not_a_slow_connection():
    assert detect_signals([ev("network", {"error": "timed out"}, ToolStatus.ERROR)]) == []


# ---- The case from the user's own machine: healthy Wi-Fi link, slow internet -------------

def wifi_ev(**overrides):
    return ev("wifi", {"connected": True, "signal_percent": 88, "link_speed_mbps": 200.0, **overrides})


def summary_for(complaint, evidence):
    return BaselineReasoner().investigate("c1", complaint, plan(), evidence, []).summary


def test_healthy_wifi_link_with_an_internet_complaint_explains_link_rate_vs_internet_speed():
    summary = summary_for("my wifi speed is only 6 mbps", [wifi_ev()])

    assert "88% signal, 200 Mbps link rate" in summary
    assert "not the speed of your internet connection" in summary
    assert "beyond the Wi-Fi link" in summary


def test_the_note_is_added_even_when_other_findings_exist():
    summary = summary_for("my internet is slow", [wifi_ev(), net(dns_ms=700.0)])

    assert "possible contributing factor" in summary  # the DNS finding
    assert "not the speed of your internet connection" in summary


def test_no_reassurance_when_the_wifi_link_is_actually_weak():
    summary = summary_for("my wifi is slow", [wifi_ev(signal_percent=25)])
    assert "looked healthy" not in summary


def test_no_reassurance_when_the_link_rate_is_low():
    summary = summary_for("my wifi is slow", [wifi_ev(link_speed_mbps=20.0)])
    assert "looked healthy" not in summary


def test_no_reassurance_from_a_failed_or_disconnected_wifi_reading():
    assert "looked healthy" not in summary_for("my wifi is slow", [ev("wifi", {"error": "x"}, ToolStatus.ERROR)])
    assert "looked healthy" not in summary_for("my wifi is slow", [ev("wifi", {"connected": False})])


def test_no_note_for_complaints_that_are_not_about_the_connection():
    assert "looked healthy" not in summary_for("my laptop is slow", [wifi_ev()])


def test_no_note_when_link_values_are_missing():
    assert "looked healthy" not in summary_for("my wifi is slow", [wifi_ev(signal_percent=None)])


def test_a_failed_reading_never_reassures_even_if_its_payload_looks_healthy():
    # Only the status check can stop this one: the values themselves are perfect.
    healthy_but_failed = ev(
        "wifi", {"connected": True, "signal_percent": 95, "link_speed_mbps": 400.0}, ToolStatus.ERROR
    )
    assert "looked healthy" not in summary_for("my wifi is slow", [healthy_but_failed])
