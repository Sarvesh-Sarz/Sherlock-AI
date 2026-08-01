"""CPU diagnostic tool.

Collects a snapshot of CPU utilization and capacity using `psutil`. This
is the first of several planned diagnostic tools (memory, disk, battery,
wifi, startup) that will all be invoked by the future Tool Manager and
all return a `ToolResult` (see `app.tools.__init__` for the shared
contract).

Payload shape on success:

    {
        "usage_percent": 18.2,       # float, 0-100
        "physical_cores": 6,         # int, or None if undetectable
        "logical_cores": 12,         # int, or None if undetectable
        "current_frequency": 3.82,   # float GHz, or None if unsupported
        "max_frequency": 4.70,       # float GHz, or None if unsupported
    }
"""

import logging
from datetime import datetime, timezone

import psutil

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "cpu"

# psutil.cpu_percent() compares two snapshots of CPU time. Called with no
# interval, its first call in a process returns a meaningless 0.0 because
# there's no prior snapshot yet. Passing a short blocking interval gives
# it one, at the cost of pausing this call for that long — acceptable
# here since it runs inline with a single API request, not in a hot loop.
_CPU_PERCENT_INTERVAL_SECONDS = 0.1


def run() -> ToolResult:
    """Collect CPU usage, core counts, and frequency.

    Never raises: any failure while talking to `psutil` is caught and
    reported as an error `ToolResult` instead, so a diagnostic sensor
    failing can't crash an investigation.

    Returns:
        A `ToolResult` with status=SUCCESS and CPU metrics in `payload`,
        or status=ERROR with failure details in `payload`.
    """
    try:
        payload = _collect()
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.SUCCESS,
            collected_at=datetime.now(timezone.utc),
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 — deliberately broad.
        # Any failure here (psutil unavailable, unsupported platform,
        # permission issues, etc.) must degrade to an error result, not
        # propagate and take the request down with it.
        logger.warning("cpu tool failed to collect data: %s", exc, exc_info=True)
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict[str, float | int | None]:
    """Gather raw CPU metrics.

    Split out from `run()` so the try/except above has exactly one call
    to wrap, and so this function's return shape can be tested directly
    without needing to simulate a psutil failure.
    """
    usage_percent = psutil.cpu_percent(interval=_CPU_PERCENT_INTERVAL_SECONDS)
    physical_cores = psutil.cpu_count(logical=False)
    logical_cores = psutil.cpu_count(logical=True)

    # cpu_freq() returns None entirely on some platforms, and can report
    # 0.0 for a field it doesn't support even when the call itself
    # succeeds (observed in this very environment: `max` comes back as
    # 0.0 in a virtualized/containerized CPU). Treat "no data" and "zero"
    # as the same thing here — a real CPU is never at 0 GHz — rather
    # than reporting a misleading 0.0 as if it were a measurement.
    freq = psutil.cpu_freq()
    current_frequency_ghz: float | None = None
    max_frequency_ghz: float | None = None
    if freq is not None:
        if freq.current:
            current_frequency_ghz = round(freq.current / 1000, 2)
        if freq.max:
            max_frequency_ghz = round(freq.max / 1000, 2)

    return {
        "usage_percent": usage_percent,
        "physical_cores": physical_cores,
        "logical_cores": logical_cores,
        "current_frequency": current_frequency_ghz,
        "max_frequency": max_frequency_ghz,
    }
