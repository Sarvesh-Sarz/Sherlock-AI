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
"""

import logging
import re
import subprocess
from datetime import datetime, timezone

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "wifi"


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
    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "netsh wlan command failed"
        )

    output = result.stdout

    return {
        "connected": _parse_connected(output),
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


def _parse_connected(output: str) -> bool:
    """Determine whether a Wi-Fi interface is currently connected."""
    return bool(
        re.search(
            r"^\s*State\s*:\s*connected\s*$",
            output,
            re.MULTILINE | re.IGNORECASE,
        )
    )


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
    receive = _parse_value(output, "Receive rate (Mbps)")

    if receive is not None:
        try:
            return float(receive)
        except ValueError:
            pass

    transmit = _parse_value(output, "Transmit rate (Mbps)")

    if transmit is not None:
        try:
            return float(transmit)
        except ValueError:
            pass

    return None