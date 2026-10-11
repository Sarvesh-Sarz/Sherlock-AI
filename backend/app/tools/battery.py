"""Battery diagnostic tool.

Collects a snapshot of the current Windows battery state using psutil.

Payload shape on success:

    {
        "percent": 78.0,
        "plugged": True,
        "charging": False,
        "seconds_left": 5400,
    }

`seconds_left` is None when Windows/psutil cannot determine it.
"""

import logging
from datetime import datetime, timezone

import psutil

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "battery"


def run() -> ToolResult:
    """Collect current battery information.

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
            "battery tool failed to collect data: %s",
            exc,
            exc_info=True,
        )

        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict[str, float | bool | int | None]:
    """Gather raw battery metrics."""
    battery = psutil.sensors_battery()

    if battery is None:
        raise RuntimeError("Battery information is not available")

    seconds_left: int | None = None

    if (
        battery.secsleft != psutil.POWER_TIME_UNLIMITED
        and battery.secsleft != psutil.POWER_TIME_UNKNOWN
        and battery.secsleft >= 0
    ):
        seconds_left = int(battery.secsleft)

    return {
        "percent": float(battery.percent),
        "plugged": bool(battery.power_plugged),
        "charging": bool(battery.power_plugged and battery.percent < 100),
        "seconds_left": seconds_left,
    }