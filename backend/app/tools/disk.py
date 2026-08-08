"""Disk diagnostic tool.

Collects disk usage for every usable local volume using `psutil` —
enumerated via `disk_partitions()`, with space and filesystem type read
independently for each one. Follows the same shape and failure handling
as every other tool in this package (see `app.tools.cpu` for the
pattern this mirrors): a single `run() -> ToolResult`, never raises.

Payload shape on success (sizes in gigabytes, rounded to 2 dp):

    {
        "volumes": [
            {
                "mountpoint": "C:\\",
                "total_gb": 172.0,
                "used_gb": 159.7,
                "free_gb": 12.3,
                "usage_percent": 92.8,
                "filesystem": "NTFS",
            },
            {
                "mountpoint": "D:\\",
                "total_gb": 195.2,
                "used_gb": 75.09,
                "free_gb": 120.11,
                "usage_percent": 38.5,
                "filesystem": "NTFS",
            },
        ]
    }

A machine with no usable local volumes (or every one of them failing
independently) reports `"volumes": []` on SUCCESS, not an error — see
`_collect`'s docstring.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import psutil

from app.models.tool_result import ToolResult, ToolStatus

logger = logging.getLogger(__name__)

TOOL_NAME = "disk"

_BYTES_PER_GB = 1024**3

# Value of `sdiskpart.opts` psutil/Windows uses for an optical drive.
# Checked in addition to an empty `fstype` (see `_is_usable_partition`)
# as defense in depth, not because it's expected to catch anything the
# fstype check wouldn't.
_CDROM_OPT = "cdrom"

# Well-known pseudo/virtual filesystem types that `disk_partitions(all=False)`
# can still surface despite its own "physical devices only" filtering
# (observed directly in this project's own dev sandbox: read-only
# squashfs mounts came through as real "volumes", one reporting 0.01 GB
# total and permanently 100% full). None of these ever appear as a
# Windows filesystem type (`NTFS`, `FAT32`, `exFAT`, `ReFS`), so this has
# no effect there — it exists for correctness on the Linux/macOS
# environments this tool is also developed and tested on.
_PSEUDO_FILESYSTEMS = frozenset(
    {
        "squashfs",
        "overlay",
        "overlayfs",
        "tmpfs",
        "devtmpfs",
        "proc",
        "sysfs",
        "cgroup",
        "cgroup2",
        "debugfs",
        "tracefs",
        "securityfs",
        "pstore",
        "bpf",
        "autofs",
        "mqueue",
        "hugetlbfs",
        "fusectl",
        "configfs",
        "binfmt_misc",
        "rpc_pipefs",
        "nsfs",
    }
)


def run() -> ToolResult:
    """Collect total, used, and free space for every usable local volume.

    Never raises: any failure enumerating or reading volumes via
    `psutil` is caught and reported as an error `ToolResult` instead, so
    a failing sensor can't crash an investigation. Note this is a
    coarser safety net than the per-volume handling inside `_collect` —
    see its docstring for why one bad volume doesn't reach this at all.

    Returns:
        A `ToolResult` with status=SUCCESS and a `volumes` list in
        `payload` (possibly empty — see module docstring), or
        status=ERROR with failure details in `payload` if enumerating
        volumes itself failed.
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


def _collect() -> dict[str, list[dict[str, float | str | None]]]:
    """Gather raw disk metrics for every usable local volume.

    Two failure modes, handled at two different levels on purpose:

    - Enumerating volumes at all (`psutil.disk_partitions()`) can fail
      outright — that's a real tool failure and propagates up to `run`'s
      try/except, producing an error ToolResult.
    - Reading *one* already-listed volume (`psutil.disk_usage()`) can
      fail independently of the others — e.g. a removable drive ejected
      between listing and reading, or a permissions issue. That volume
      is skipped, not the whole tool; every other volume still reports
      normally. This is what "one inaccessible volume must not fail the
      investigation" means in practice, and it's why this handling lives
      here rather than as a second layer of the outer try/except.
    """
    volumes: list[dict[str, float | str | None]] = []

    for partition in psutil.disk_partitions(all=False):
        if not _is_usable_partition(partition):
            continue

        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except OSError as exc:
            logger.warning(
                "disk tool could not read usage for %s: %s",
                partition.mountpoint,
                exc,
                exc_info=True,
            )
            continue

        volumes.append(
            {
                "mountpoint": partition.mountpoint,
                "total_gb": _to_gb(usage.total),
                "used_gb": _to_gb(usage.used),
                "free_gb": _to_gb(usage.free),
                # disk_usage().percent is psutil's own usage calculation
                # (matches what `df` reports), not a naive used/total
                # ratio — used as-is rather than recomputed, same
                # reasoning as memory.py's virtual_memory().percent.
                "usage_percent": round(usage.percent, 2),
                "filesystem": partition.fstype,
            }
        )

    # Deterministic, alphabetical-by-mountpoint order (C: before D:,
    # etc.) rather than whatever order the OS happened to enumerate
    # partitions in, since that order isn't guaranteed or meaningful.
    volumes.sort(key=lambda volume: str(volume["mountpoint"]))
    return {"volumes": volumes}


def _is_usable_partition(partition: Any) -> bool:
    """Filter out entries `disk_partitions()` lists that aren't a real,
    readable local volume.

    Typed as `Any` rather than psutil's actual return type
    (`psutil._common.sdiskpart`) deliberately — that type lives in a
    private module and isn't meant to be imported by callers. All this
    function relies on is duck typing: `.fstype` and `.opts` attributes,
    which is exactly what psutil's public docs guarantee a partition
    entry has.

    `psutil.disk_partitions(all=False)` already excludes most virtual
    and network filesystems — that's its own documented behavior, but
    not a complete guarantee (see `_PSEUDO_FILESYSTEMS`). What it
    reliably still lists on Windows is a removable/optical drive with no
    media inserted, which comes back with an empty `fstype` and *will*
    raise `OSError` on `disk_usage()` (this is the origin of the
    original bug report's class of symptom: a volume that's listed but
    not actually readable). Filtering it out here means `_collect`'s
    per-volume try/except never even has to fire for that common case.
    """
    if not partition.fstype:
        return False
    if partition.fstype.lower() in _PSEUDO_FILESYSTEMS:
        return False
    if _CDROM_OPT in partition.opts.split(","):
        return False
    return True


def _to_gb(value_bytes: int) -> float:
    """Convert a byte count to gigabytes, rounded to 2 decimal places."""
    return round(value_bytes / _BYTES_PER_GB, 2)
