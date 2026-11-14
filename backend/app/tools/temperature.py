"""Temperature diagnostic tool.

Collects available temperature sensors on Windows.

The tool first tries psutil sensors and then falls back to the
Windows ACPI thermal-zone interface.
"""

import logging
from datetime import datetime, timezone

import psutil

from app.models.tool_result import ToolResult, ToolStatus
from app.tools._command import CommandError, run_powershell_json

logger = logging.getLogger(__name__)

TOOL_NAME = "temperature"


def run() -> ToolResult:
    """Collect available temperature information.

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
            "temperature tool failed to collect data: %s",
            exc,
        )

        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict:
    """Collect temperatures from available Windows sources."""

    sensors = _collect_psutil_temperatures()

    if sensors:
        return _build_payload(
            sensors=sensors,
            source="psutil",
        )

    reason: str | None = None

    try:
        sensors = _collect_windows_thermal_zones()
    except CommandError as exc:
        sensors = []
        reason = str(exc)

    if sensors:
        return _build_payload(
            sensors=sensors,
            source="windows_acpi",
        )

    message = "No temperature sensors are available on this Windows system"

    if reason:
        message += f" (ACPI thermal-zone query: {reason}"
        if "denied" in reason.casefold():
            message += "; reading it can require administrator rights"
        message += ")"

    raise RuntimeError(message)


def _collect_psutil_temperatures() -> list[dict]:
    """Try temperatures exposed by psutil."""
    try:
        raw = psutil.sensors_temperatures(fahrenheit=False)
    except (AttributeError, NotImplementedError):
        return []

    sensors: list[dict] = []

    for group_name, entries in raw.items():
        for entry in entries:
            if entry.current is None:
                continue

            sensors.append(
                {
                    "name": entry.label or group_name,
                    "temperature_c": float(entry.current),
                    "high_c": (
                        float(entry.high)
                        if entry.high is not None
                        else None
                    ),
                    "critical_c": (
                        float(entry.critical)
                        if entry.critical is not None
                        else None
                    ),
                }
            )

    return sensors


def _collect_windows_thermal_zones() -> list[dict]:
    """Read Windows ACPI thermal zones through PowerShell.

    Raises `CommandError` if the query itself fails; returns an empty
    list only when Windows genuinely reports no thermal zones. Note
    that an ACPI thermal zone is a board/chassis sensor and is not
    always the CPU die temperature.
    """

    command = (
        "Get-CimInstance "
        "-Namespace root/wmi "
        "-ClassName MSAcpi_ThermalZoneTemperature "
        "| Select-Object InstanceName,CurrentTemperature "
        "| ConvertTo-Json -Compress"
    )

    data = run_powershell_json(command)

    if data is None:
        return []

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return []

    sensors: list[dict] = []

    for item in data:
        if not isinstance(item, dict):
            continue

        raw_temperature = item.get("CurrentTemperature")

        if not isinstance(raw_temperature, (int, float)) or isinstance(raw_temperature, bool):
            continue

        # Windows reports temperature in tenths of Kelvin.
        temperature_c = (float(raw_temperature) / 10.0) - 273.15

        sensors.append(
            {
                "name": item.get("InstanceName") or "Thermal Zone",
                "temperature_c": round(temperature_c, 1),
                "high_c": None,
                "critical_c": None,
            }
        )

    return sensors


def _build_payload(
    *,
    sensors: list[dict],
    source: str,
) -> dict:
    temperatures = [
        sensor["temperature_c"]
        for sensor in sensors
    ]

    return {
        "source": source,
        "sensor_count": len(sensors),
        "current_temperature_c": max(temperatures),
        "sensors": sensors,
    }