"""Memory diagnostic tool.

Collects a snapshot of system memory using `psutil` — physical RAM via
`virtual_memory()` and swap via `swap_memory()`. Follows the same shape
and failure handling as every other tool in this package (see
`app.tools.cpu` for the pattern this mirrors): a single
`run() -> ToolResult`, never raises.

Payload shape on success (all sizes in gigabytes, rounded to 2 dp):

    {
        "total_gb": 15.86,
        "available_gb": 8.23,
        "used_gb": 7.63,
        "usage_percent": 48.1,
        "swap_total_gb": 2.0,
        "swap_used_gb": 0.12,
    }
"""

import logging
from datetime import datetime, timezone

import psutil

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "memory"

_BYTES_PER_GB = 1024**3


def run() -> ToolResult:
    """Collect physical and swap memory usage.

    Never raises: any failure while talking to `psutil` is caught and
    reported as an error `ToolResult` instead, so a failing sensor can't
    crash an investigation.

    Returns:
        A `ToolResult` with status=SUCCESS and memory metrics in
        `payload`, or status=ERROR with failure details in `payload`.
    """
    try:
        payload = _collect()
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.SUCCESS,
            collected_at=datetime.now(timezone.utc),
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 — deliberately broad, see app.tools.cpu.
        logger.warning("memory tool failed to collect data: %s", exc, exc_info=True)
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict[str, float]:
    """Gather raw memory metrics, converted to gigabytes.

    Split out from `run()` so the try/except above has exactly one call
    to wrap, and so this function's return shape can be tested directly.

    Unlike `cpu.cpu_freq()` (see `app.tools.cpu`), `psutil` doesn't have
    a "field unsupported on this platform" ambiguity for memory — a
    genuine `0` (e.g. no swap configured) is real information, not a
    stand-in for missing data, so no None-coalescing is needed here.
    """
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "total_gb": _to_gb(virtual.total),
        "available_gb": _to_gb(virtual.available),
        "used_gb": _to_gb(virtual.used),
        # virtual_memory().percent is psutil's own usage calculation
        # (matches what a system monitor reports), not a naive
        # used/total ratio — those can diverge once caches/buffers are
        # accounted for, so it's used as-is rather than recomputed.
        "usage_percent": round(virtual.percent, 2),
        "swap_total_gb": _to_gb(swap.total),
        "swap_used_gb": _to_gb(swap.used),
    }


def _to_gb(value_bytes: int) -> float:
    """Convert a byte count to gigabytes, rounded to 2 decimal places."""
    return round(value_bytes / _BYTES_PER_GB, 2)
