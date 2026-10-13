"""Audio diagnostic tool.

Collects Windows audio-device information through PowerShell/WMI.
"""

import json
import logging
import subprocess
from datetime import datetime, timezone

from app.models.tool_result import ToolResult, ToolStatus

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
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            f"Could not query Windows audio devices: {exc}"
        ) from exc

    if completed.returncode != 0:
        error = completed.stderr.strip() or "PowerShell command failed"
        raise RuntimeError(error)

    if not completed.stdout.strip():
        raise RuntimeError("Windows returned no audio devices")

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Windows returned invalid audio-device data"
        ) from exc

    if isinstance(data, dict):
        data = [data]

    devices = []

    for item in data:
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
        "devices": devices,
    }