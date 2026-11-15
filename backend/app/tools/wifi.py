"""Wi-Fi diagnostic tool.

Collects a snapshot of the active Windows Wi-Fi connection using
Windows `netsh`. The tool returns raw connection evidence for Sherlock
to reason about later.

Payload shape on success:

    {
        "connected": True,
        "ssid": "MyWiFi",
        "signal_percent": 72,
        "link_speed_mbps": 433,
        "interface": "Wi-Fi",
        "radio_type": "802.11ac",
        "authentication": "WPA2-Personal",
    }

If netsh does not report a connection state at all (no wireless
adapter, the WLAN service stopped, or a non-English Windows whose
labels differ), the tool returns an ERROR rather than guessing
`connected: False`. "Unknown" must never be recorded as "not connected".
"""

import logging
import re
import sys
from datetime import datetime, timezone

from app.models.tool_result import ToolResult, ToolStatus
from app.tools._command import first_line, run_command

logger = logging.getLogger(__name__)

TOOL_NAME = "wifi"

# netsh writes in the console's OEM code page when its output is piped;
# decoding it as UTF-8 garbles non-ASCII network names.
_NETSH_ENCODING = "oem" if sys.platform == "win32" else "utf-8"


def run() -> ToolResult:
    """Collect Wi-Fi connection information.

    Never raises: any failure while querying Windows networking is
    caught and returned as an error ToolResult.
    """
    try:
        payload = _collect()

        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.SUCCESS,
            collected_at=datetime.now(timezone.utc),
            payload=payload,
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "wifi tool failed to collect data: %s",
            exc,
            exc_info=True,
        )

        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict[str, object | None]:
    """Gather Wi-Fi connection evidence using Windows netsh."""
    result = run_command(
        ["netsh", "wlan", "show", "interfaces"],
        timeout=10,
        encoding=_NETSH_ENCODING,
    )

    # netsh explains its own failures on stdout ("There is no wireless
    # interface on the system.", "The Wireless AutoConfig Service
    # (wlansvc) is not running."), not stderr, so surface that text.
    output = result.stdout or ""

    if result.returncode != 0:
        raise RuntimeError(
            first_line(output) or first_line(result.stderr) or "netsh wlan command failed"
        )

    state = _parse_value(output, "State")

    if state is None:
        raise RuntimeError(
            "netsh did not report a Wi-Fi connection state; this can mean there is no "
            "wireless adapter, or that Windows is not set to English. "
            f"Output began: {first_line(output)!r}"
        )

    return {
        "connected": state.casefold() == "connected",
        "ssid": _parse_value(output, "SSID"),
        "signal_percent": _parse_signal(output),
        "link_speed_mbps": _parse_link_speed(output),
        "interface": _parse_value(output, "Name"),
        "radio_type": _parse_value(output, "Radio type"),
        "authentication": _parse_value(output, "Authentication"),
    }


def _parse_value(output: str, field: str) -> str | None:
    """Extract a value from a netsh field such as `SSID : MyNetwork`."""
    pattern = rf"^\s*{re.escape(field)}\s*:\s*(.+?)\s*$"

    match = re.search(pattern, output, re.MULTILINE | re.IGNORECASE)

    if not match:
        return None

    return match.group(1).strip()


def _parse_signal(output: str) -> int | None:
    """Extract signal strength as a percentage."""
    value = _parse_value(output, "Signal")

    if value is None:
        return None

    match = re.search(r"(\d+)\s*%", value)

    if not match:
        return None

    return int(match.group(1))


def _parse_link_speed(output: str) -> float | None:
    """Extract receive/transmit link speed in Mbps."""
    for field in ("Receive rate (Mbps)", "Transmit rate (Mbps)"):
        value = _parse_value(output, field)

        if value is None:
            continue

        try:
            return float(value)
        except ValueError:
            continue

    return None
