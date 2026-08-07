"""Disk diagnostic tool.

Collects a snapshot of the system drive's disk usage using `psutil` —
space via `disk_usage()` and filesystem type via `disk_partitions()`
(the former doesn't report filesystem type itself). Follows the same
shape and failure handling as every other tool in this package (see
`app.tools.cpu` for the pattern this mirrors): a single
`run() -> ToolResult`, never raises.

Payload shape on success (sizes in gigabytes, rounded to 2 dp):

    {
        "total_gb": 251.98,
        "used_gb": 9.04,
        "free_gb": 9.49,
        "usage_percent": 48.8,
        "filesystem": "ext4",   # or None if undetectable
    }
"""

import logging
import os
from datetime import datetime, timezone

import psutil

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "disk"

_BYTES_PER_GB = 1024**3


def run() -> ToolResult:
    """Collect total, used, and free space for the system drive.

    Never raises: any failure while talking to `psutil` is caught and
    reported as an error `ToolResult` instead, so a failing sensor can't
    crash an investigation.

    Returns:
        A `ToolResult` with status=SUCCESS and disk metrics in
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
        logger.warning("disk tool failed to collect data: %s", exc, exc_info=True)
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.ERROR,
            collected_at=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        )


def _collect() -> dict[str, float | str | None]:
    """Gather raw disk metrics for the system drive, converted to gigabytes.

    Split out from `run()` so the try/except above has exactly one call
    to wrap, and so this function's return shape can be tested directly.

    "System drive" is simplified to the OS root — `/` on Linux/macOS,
    the current drive root (typically `C:\\`) on Windows — via
    `os.path.abspath(os.sep)`, the same idiom `psutil`'s own docs use.
    Sherlock investigates the machine it runs on, not arbitrary paths,
    so a single well-known target is enough; multi-drive/multi-volume
    reporting isn't attempted here.
    """
    target_path = os.path.abspath(os.sep)
    usage = psutil.disk_usage(target_path)

    return {
        "total_gb": _to_gb(usage.total),
        "used_gb": _to_gb(usage.used),
        "free_gb": _to_gb(usage.free),
        # disk_usage().percent is psutil's own usage calculation (matches
        # what `df` reports), not a naive used/total ratio — used as-is
        # rather than recomputed, same reasoning as memory.py's
        # virtual_memory().percent.
        "usage_percent": round(usage.percent, 2),
        "filesystem": _detect_filesystem(target_path),
    }


def _detect_filesystem(target_path: str) -> str | None:
    """Look up the filesystem type for `target_path`'s mount point.

    `psutil.disk_usage()` doesn't report filesystem type; only
    `psutil.disk_partitions()` does, keyed by mountpoint. Matched by
    exact mountpoint equality rather than longest-prefix matching, since
    `target_path` is always a drive/filesystem root — exactly what a
    partition's own mountpoint should equal on any conventionally
    mounted system. Returns None (rather than raising or guessing) if no
    partition reports that exact mountpoint, e.g. an unusual mount setup
    this simple lookup doesn't handle — "unknown" is a valid, honestly
    reported outcome here, the same way `cpu.py` reports an unsupported
    frequency reading as None rather than fabricating one.
    """
    for partition in psutil.disk_partitions():
        if partition.mountpoint == target_path:
            return partition.fstype
    return None


def _to_gb(value_bytes: int) -> float:
    """Convert a byte count to gigabytes, rounded to 2 decimal places."""
    return round(value_bytes / _BYTES_PER_GB, 2)
