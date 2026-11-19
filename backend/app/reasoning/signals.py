"""Deterministic evidence interpretation, shared by hypothesis
generation and research-query construction.

A `Signal` is one deterministic observation worth investigating
further, derived from a single piece of evidence via a fixed threshold
rule — e.g. "a disk volume is over 85% full." `detect_signals` is the
one place "what counts as low disk space" (or high memory usage, or too
many startup entries) is defined; both `app.reasoning.baseline_reasoner`
(turns signals into hypotheses) and `app.reasoning.query_builder` (turns
signals into research queries) read from it, so the two can never
disagree about what evidence is worth acting on.

Purely internal to the reasoning package — not part of the API, and not
a domain model (see `app.models.investigation_report` for the
public-facing shapes this eventually feeds into).

Deliberately simple threshold rules, not scoring or ML: this is the
"smallest useful" deterministic baseline, not an attempt at the eventual
AI reasoning model.
"""

from dataclasses import dataclass

from app.models.investigation_report import Confidence
from app.models.tool_result import ToolResult, ToolStatus

_DISK_HIGH_USAGE_PERCENT = 85.0
_DISK_CRITICAL_USAGE_PERCENT = 95.0
_MEMORY_HIGH_USAGE_PERCENT = 85.0
_STARTUP_HIGH_ENTRY_COUNT = 10
_WIFI_WEAK_SIGNAL_PERCENT = 40
_WIFI_VERY_WEAK_SIGNAL_PERCENT = 20
_WIFI_LOW_LINK_SPEED_MBPS = 50
_NETWORK_SLOW_RESPONSE_MS = 500
_NETWORK_VERY_SLOW_RESPONSE_MS = 1500
_NETWORK_SLOW_DNS_MS = 300
_BATTERY_LOW_PERCENT = 20
_TEMPERATURE_HIGH_C = 85.0
_TEMPERATURE_CRITICAL_C = 95.0

# Windows Device Manager (ConfigManagerErrorCode) meanings for the codes
# most often seen on audio hardware, and which fix each one points to.
_DEVICE_ERROR_MEANINGS = {
    1: "the device is not configured correctly",
    10: "the device cannot start",
    22: "the device is disabled",
    24: "the device is not present or is missing drivers",
    28: "the drivers for the device are not installed",
    31: "Windows cannot load the drivers the device requires",
    43: "Windows stopped the device because it reported problems",
}
_DEVICE_DISABLED_CODE = 22


@dataclass
class Signal:
    """One deterministic, evidence-backed observation."""

    title: str
    explanation: str
    supporting_evidence: list[str]
    confidence: Confidence
    research_query: str
    recommendation: str


def detect_signals(evidence: list[ToolResult]) -> list[Signal]:
    """Derive signals from whatever evidence was actually collected.

    Only evidence with `status == SUCCESS` is considered — a tool that
    failed to collect anything has nothing to reason over, and doing so
    would mean inferring from data that was never actually observed.

    CPU is deliberately never turned into a signal: `app.tools.cpu`
    measures utilization over a ~0.1s window (see its own docstring), a
    single instantaneous snapshot, not sustained monitoring. Treating
    that as evidence of a persistent problem would overstate what was
    actually observed — the CPU snapshot is still included in a
    report's `evidence_used` as an observed fact, it just never becomes
    a hypothesis on its own here.
    """
    signals: list[Signal] = []
    for result in evidence:
        if result.status != ToolStatus.SUCCESS:
            continue

        if result.tool_name == "disk":
            signals.extend(_disk_signals(result))
        elif result.tool_name == "memory":
            signal = _memory_signal(result)
            if signal is not None:
                signals.append(signal)
        elif result.tool_name == "startup":
            signal = _startup_signal(result)
            if signal is not None:
                signals.append(signal)
        elif result.tool_name == "wifi":
            signals.extend(_wifi_signals(result))
        elif result.tool_name == "network":
            signals.extend(_network_signals(result))
        elif result.tool_name == "audio":
            signals.extend(_audio_signals(result))
        elif result.tool_name == "battery":
            signal = _battery_signal(result)
            if signal is not None:
                signals.append(signal)
        elif result.tool_name == "temperature":
            signal = _temperature_signal(result)
            if signal is not None:
                signals.append(signal)

    return signals


def _disk_signals(result: ToolResult) -> list[Signal]:
    volumes = result.payload.get("volumes")
    if not isinstance(volumes, list):
        return []

    signals: list[Signal] = []
    for volume in volumes:
        if not isinstance(volume, dict):
            continue
        usage_percent = volume.get("usage_percent")
        if not isinstance(usage_percent, (int, float)) or usage_percent < _DISK_HIGH_USAGE_PERCENT:
            continue

        mountpoint = volume.get("mountpoint")
        mountpoint_label = mountpoint if isinstance(mountpoint, str) and mountpoint else "A local volume"
        free_gb = volume.get("free_gb")
        free_text = f", leaving {free_gb:.2f} GB free" if isinstance(free_gb, (int, float)) else ""
        is_critical = usage_percent >= _DISK_CRITICAL_USAGE_PERCENT

        signals.append(
            Signal(
                title=(
                    f"{mountpoint_label} is critically low on free space"
                    if is_critical
                    else f"{mountpoint_label} is running low on free space"
                ),
                explanation=(
                    f"{mountpoint_label} is using {usage_percent:.1f}% of its capacity{free_text}. "
                    "Very low free space on a system drive is a plausible contributing factor to "
                    "general slowdowns in Windows."
                ),
                supporting_evidence=[f"{mountpoint_label} usage: {usage_percent:.1f}%{free_text}."],
                confidence=Confidence.HIGH if is_critical else Confidence.MEDIUM,
                research_query="Windows low disk space performance impact",
                recommendation=(
                    f"Consider freeing up space on {mountpoint_label} "
                    "(for example, Disk Cleanup, or removing unused files or applications)."
                ),
            )
        )
    return signals


def _memory_signal(result: ToolResult) -> Signal | None:
    usage_percent = result.payload.get("usage_percent")
    if not isinstance(usage_percent, (int, float)) or usage_percent < _MEMORY_HIGH_USAGE_PERCENT:
        return None

    return Signal(
        title="High memory utilization",
        explanation=(
            f"System memory is at {usage_percent:.1f}% utilization at the time of measurement. "
            "Sustained high memory usage is a plausible contributing factor to slower application "
            "performance."
        ),
        supporting_evidence=[f"Memory usage: {usage_percent:.1f}%."],
        confidence=Confidence.HIGH if usage_percent >= 95 else Confidence.MEDIUM,
        research_query="Windows high memory usage performance impact",
        recommendation="Consider reviewing which applications are running and closing ones not in use.",
    )


def _startup_signal(result: ToolResult) -> Signal | None:
    total_entries = result.payload.get("total_entries")
    if not isinstance(total_entries, int) or total_entries < _STARTUP_HIGH_ENTRY_COUNT:
        return None

    return Signal(
        title="High number of startup entries",
        explanation=(
            f"{total_entries} programs are configured to start automatically at sign-in. A large "
            "number of startup entries is a plausible contributing factor to a slower startup."
        ),
        supporting_evidence=[f"{total_entries} startup entries detected."],
        confidence=Confidence.MEDIUM,
        research_query="Windows startup applications slow boot performance",
        recommendation=(
            "Consider reviewing Startup apps in Task Manager and disabling ones you don't need "
            "at every sign-in."
        ),
    )


def _number(value: object) -> float | None:
    """A real number, or None. Booleans are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _wifi_signals(result: ToolResult) -> list[Signal]:
    payload = result.payload
    signals: list[Signal] = []

    # `connected` is only ever False when netsh explicitly reported a
    # non-connected state; if it could not tell, the tool errors out and
    # this function is never reached (unknown is not "disconnected").
    if payload.get("connected") is False:
        return [
            Signal(
                title="Wi-Fi is not connected to a network",
                explanation=(
                    "Windows reported that the Wi-Fi adapter is not connected to any network "
                    "at the time of measurement, which would directly explain a missing or "
                    "unreliable internet connection."
                ),
                supporting_evidence=["Wi-Fi connection state: not connected."],
                confidence=Confidence.HIGH,
                research_query="Windows Wi-Fi not connecting troubleshooting",
                recommendation=(
                    "Check that Wi-Fi is turned on and airplane mode is off, then reconnect to "
                    "your network from the taskbar network icon."
                ),
            )
        ]

    if payload.get("connected") is not True:
        return signals

    strength = _number(payload.get("signal_percent"))
    if strength is not None and strength < _WIFI_WEAK_SIGNAL_PERCENT:
        signals.append(
            Signal(
                title="Wi-Fi signal is weak",
                explanation=(
                    f"Signal strength was {strength:.0f}% at the time of measurement. A weak "
                    "signal is a plausible contributing factor to slow or dropping connections."
                ),
                supporting_evidence=[f"Wi-Fi signal strength: {strength:.0f}%."],
                confidence=Confidence.HIGH if strength < _WIFI_VERY_WEAK_SIGNAL_PERCENT else Confidence.MEDIUM,
                research_query="Windows weak Wi-Fi signal slow internet",
                recommendation=(
                    "Try moving closer to your router or access point, and check for walls or "
                    "other obstacles between them."
                ),
            )
        )

    speed = _number(payload.get("link_speed_mbps"))
    if speed is not None and 0 < speed < _WIFI_LOW_LINK_SPEED_MBPS:
        signals.append(
            Signal(
                title="Wi-Fi link speed is low",
                explanation=(
                    f"The Wi-Fi link speed was {speed:g} Mbps at the time of measurement. That is "
                    "low for a modern connection and can indicate a weak signal, interference, or "
                    "an older Wi-Fi standard."
                ),
                supporting_evidence=[f"Wi-Fi link speed: {speed:g} Mbps."],
                confidence=Confidence.MEDIUM,
                research_query="Windows low Wi-Fi link speed",
                recommendation=(
                    "If your router supports it, try connecting on the 5 GHz band, and check "
                    "whether other devices nearby are congesting the channel."
                ),
            )
        )

    return signals


def _network_signals(result: ToolResult) -> list[Signal]:
    payload = result.payload
    signals: list[Signal] = []

    if payload.get("response_ok") is False:
        signals.append(
            Signal(
                title="The network did not return the expected response",
                explanation=(
                    "A request for Microsoft's connectivity-check page came back as something "
                    "else. That usually means the network is showing a sign-in page or is "
                    "routing web traffic through a proxy or filter, which can slow or block "
                    "browsing."
                ),
                supporting_evidence=["Connectivity-check response: not the expected page."],
                confidence=Confidence.MEDIUM,
                research_query="Windows captive portal proxy slow internet",
                recommendation=(
                    "Open a web page to see whether the network asks you to sign in. On a work "
                    "or school network, ask its IT team whether a proxy or content filter is in use."
                ),
            )
        )

    attempted = _number(payload.get("attempted"))
    failed = _number(payload.get("failed_samples"))
    if attempted and failed and failed > 0:
        signals.append(
            Signal(
                title="Some internet connection checks failed",
                explanation=(
                    f"{failed:.0f} of {attempted:.0f} connection checks failed even though others "
                    "succeeded. An intermittent connection like that is a plausible cause of "
                    "pages that hang or load unevenly."
                ),
                supporting_evidence=[f"{failed:.0f} of {attempted:.0f} connection checks failed."],
                confidence=Confidence.MEDIUM,
                research_query="Windows intermittent internet connection drops",
                recommendation=(
                    "Note whether the problem comes and goes at certain times or places, and try "
                    "restarting your router if it is your own network."
                ),
            )
        )

    response = _number(payload.get("first_byte_ms"))
    if response is not None and response >= _NETWORK_SLOW_RESPONSE_MS:
        signals.append(
            Signal(
                title="Internet responses are slow",
                explanation=(
                    f"A tiny request took {response:.0f} ms to start receiving a reply. Responses "
                    "this slow suggest congestion or a slow connection beyond the Wi-Fi link, "
                    "and are a plausible cause of slow-feeling browsing."
                ),
                supporting_evidence=[f"Time to first response: {response:.0f} ms."],
                confidence=Confidence.HIGH if response >= _NETWORK_VERY_SLOW_RESPONSE_MS else Confidence.MEDIUM,
                research_query="slow internet high latency Windows Wi-Fi",
                recommendation=(
                    "Try the same website on another device on the same network. If it is slow "
                    "there too, the problem is the network or internet service, not this PC."
                ),
            )
        )

    dns = _number(payload.get("dns_ms"))
    if dns is not None and dns >= _NETWORK_SLOW_DNS_MS:
        signals.append(
            Signal(
                title="Looking up website names is slow",
                explanation=(
                    f"Resolving a website name took {dns:.0f} ms. Slow name lookups add a delay "
                    "to every new site you open, even when the connection itself is fast."
                ),
                supporting_evidence=[f"DNS lookup time: {dns:.0f} ms."],
                confidence=Confidence.MEDIUM,
                research_query="Windows slow DNS lookup change DNS server",
                recommendation=(
                    "If this is your own network, consider switching your DNS server to a public "
                    "one such as 1.1.1.1 or 8.8.8.8 in your network adapter settings. On a work "
                    "or school network, leave DNS as it is and ask IT."
                ),
            )
        )

    return signals


def _audio_signals(result: ToolResult) -> list[Signal]:
    payload = result.payload
    signals: list[Signal] = []

    service_status = payload.get("audio_service_status")
    if isinstance(service_status, str) and service_status.casefold() in {"stopped", "paused"}:
        signals.append(
            Signal(
                title="The Windows Audio service is not running",
                explanation=(
                    f"The Windows Audio service reported its state as '{service_status}'. With "
                    "this service not running, Windows cannot play or record sound, which would "
                    "directly explain missing audio."
                ),
                supporting_evidence=[f"Windows Audio service state: {service_status}."],
                confidence=Confidence.HIGH,
                research_query="Windows Audio service not running no sound",
                recommendation=(
                    "Open Services (services.msc), find 'Windows Audio', and start it, setting "
                    "its Startup type to Automatic."
                ),
            )
        )

    devices = payload.get("devices")
    device_count = payload.get("device_count")
    if device_count == 0:
        signals.append(
            Signal(
                title="No audio devices were detected",
                explanation=(
                    "Windows reported no audio devices at the time of measurement, so there is "
                    "nothing for it to play sound through or record from."
                ),
                supporting_evidence=["Audio devices detected: 0."],
                confidence=Confidence.HIGH,
                research_query="Windows no audio devices found",
                recommendation=(
                    "Open Device Manager and check 'Sound, video and game controllers'; if the "
                    "audio device is missing, reinstall the audio driver from your PC maker."
                ),
            )
        )

    if not isinstance(devices, list):
        return signals

    for device in devices:
        if not isinstance(device, dict):
            continue
        name = device.get("name") if isinstance(device.get("name"), str) and device.get("name") else "An audio device"
        code = device.get("error_code")
        status = device.get("status")

        if isinstance(code, int) and not isinstance(code, bool) and code != 0:
            meaning = _DEVICE_ERROR_MEANINGS.get(code)
            detail = f"{meaning} (error code {code})" if meaning else f"error code {code}"
            if code == _DEVICE_DISABLED_CODE:
                recommendation = (
                    "Open Device Manager, find the device under 'Sound, video and game "
                    "controllers', right-click it, and choose Enable device."
                )
            else:
                recommendation = (
                    "Open Device Manager and update or reinstall the audio driver for this "
                    "device, ideally from your PC maker's support page."
                )
            signals.append(
                Signal(
                    title=f"{name} reports a problem",
                    explanation=(
                        f"Windows reports that {detail}. A device in this state is a plausible "
                        "cause of missing or distorted audio."
                    ),
                    supporting_evidence=[f"{name}: Device Manager {detail}."],
                    confidence=Confidence.HIGH,
                    research_query=f"Windows audio device error code {code}",
                    recommendation=recommendation,
                )
            )
        elif isinstance(status, str) and status and status != "OK":
            signals.append(
                Signal(
                    title=f"{name} is not reporting a healthy status",
                    explanation=(
                        f"Windows reports the status '{status}' for this device instead of 'OK', "
                        "which is a plausible contributing factor to audio problems."
                    ),
                    supporting_evidence=[f"{name}: status '{status}'."],
                    confidence=Confidence.MEDIUM,
                    research_query="Windows audio device status not OK",
                    recommendation=(
                        "Open Device Manager and check this device's properties; updating or "
                        "reinstalling its driver often resolves this."
                    ),
                )
            )

    return signals


def _battery_signal(result: ToolResult) -> Signal | None:
    percent = _number(result.payload.get("percent"))
    if percent is None or percent > _BATTERY_LOW_PERCENT or result.payload.get("plugged") is not False:
        return None

    return Signal(
        title="Battery is low and the PC is unplugged",
        explanation=(
            f"The battery was at {percent:.0f}% and running without external power at the time "
            "of measurement. A very low battery can cause the PC to slow down, dim the screen, "
            "or shut off. This reading alone does not show the battery's overall health."
        ),
        supporting_evidence=[f"Battery: {percent:.0f}%, not plugged in."],
        confidence=Confidence.LOW,
        research_query="Windows laptop battery drains fast",
        recommendation="Plug in the charger and see whether the problem continues while charging.",
    )


def _temperature_signal(result: ToolResult) -> Signal | None:
    temperature = _number(result.payload.get("current_temperature_c"))
    if temperature is None or temperature < _TEMPERATURE_HIGH_C:
        return None

    caveat = ""
    if result.payload.get("source") == "windows_acpi":
        caveat = " This reading comes from a Windows thermal zone, which is not always the CPU sensor."

    return Signal(
        title="A temperature sensor is reading high",
        explanation=(
            f"The hottest sensor read {temperature:.1f} C at the time of measurement. Sustained "
            f"high temperatures can make a PC throttle its speed and feel slow.{caveat}"
        ),
        supporting_evidence=[f"Hottest sensor: {temperature:.1f} C."],
        confidence=Confidence.HIGH if temperature >= _TEMPERATURE_CRITICAL_C else Confidence.MEDIUM,
        research_query="Windows laptop overheating thermal throttling",
        recommendation=(
            "Make sure the vents are not blocked, use the PC on a hard flat surface, and clean "
            "out dust if it has been a long time."
        ),
    )
