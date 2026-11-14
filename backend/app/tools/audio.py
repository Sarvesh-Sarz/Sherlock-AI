"""Audio diagnostic tool.

Collects Windows audio-device information through PowerShell/WMI, plus
the state of the Windows Audio service (the most common reason for "no
sound" on an otherwise healthy machine).

Payload shape on success:

    {
        "device_count": 2,
        "working_device_count": 2,
        "audio_service_status": "running",   # None if it could not be read
        "devices": [{"name", "status", "manufacturer", "device_id", "error_code"}, ...],
    }
"""

import logging
from datetime import datetime, timezone

import psutil

from app.models.tool_result import ToolResult, ToolStatus
from app.tools._command import CommandError, run_powershell_json

AUDIO_SERVICE_NAME = "Audiosrv"

logger = logging.getLogger(__name__)

TOOL_NAME = "audio"


def run() -> ToolResult:
    """Collect current Windows audio-device information.

    Never raises: failures are returned as an error ToolResult.
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
            "audio tool failed to collect data: %s",
            exc,
        )

        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict:
    """Collect audio devices exposed by Windows."""

    command = (
        "Get-CimInstance Win32_SoundDevice "
        "| Select-Object Name,Status,Manufacturer,"
        "PNPDeviceID,ConfigManagerErrorCode "
        "| ConvertTo-Json -Compress"
    )

    try:
        data = run_powershell_json(command)
    except CommandError as exc:
        raise RuntimeError(f"Could not query Windows audio devices: {exc}") from exc

    if data is None:
        raise RuntimeError("Windows returned no audio devices")

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise RuntimeError("Windows returned invalid audio-device data")

    devices = []

    for item in data:
        if not isinstance(item, dict):
            continue
        devices.append(
            {
                "name": item.get("Name"),
                "status": item.get("Status"),
                "manufacturer": item.get("Manufacturer"),
                "device_id": item.get("PNPDeviceID"),
                "error_code": item.get("ConfigManagerErrorCode"),
            }
        )

    working_devices = [
        device
        for device in devices
        if device["status"] == "OK"
        and device["error_code"] in (None, 0)
    ]

    return {
        "device_count": len(devices),
        "working_device_count": len(working_devices),
        "audio_service_status": _audio_service_status(),
        "devices": devices,
    }


def _audio_service_status() -> str | None:
    """State of the Windows Audio service ("running", "stopped", ...).

    Read-only. Returns None when it cannot be determined (not Windows,
    or the service query is not permitted), which callers must treat as
    unknown, never as healthy.
    """
    try:
        return psutil.win_service_get(AUDIO_SERVICE_NAME).status()
    except Exception as exc:  # noqa: BLE001 - AttributeError off-Windows, access errors on it
        logger.info("could not read the %s service state: %s", AUDIO_SERVICE_NAME, exc)
        return None
