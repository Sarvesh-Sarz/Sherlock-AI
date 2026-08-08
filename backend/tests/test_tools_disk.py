"""Tests for the disk diagnostic tool.

Uses fake psutil-shaped objects (plain namedtuples matching the public
attribute names `disk_partitions()`/`disk_usage()` document — `device`,
`mountpoint`, `fstype`, `opts` and `total`, `used`, `free`, `percent`)
rather than psutil's own private internal namedtuple classes, so these
tests aren't coupled to psutil version internals.
"""

from collections import namedtuple

from app.models.tool_result import ToolStatus
from app.tools import disk

_FakePartition = namedtuple("_FakePartition", ["device", "mountpoint", "fstype", "opts"])
_FakeUsage = namedtuple("_FakeUsage", ["total", "used", "free", "percent"])

_BYTES_PER_GB = 1024**3


def _partition(mountpoint: str, fstype: str = "NTFS", opts: str = "rw,fixed") -> _FakePartition:
    return _FakePartition(device=mountpoint, mountpoint=mountpoint, fstype=fstype, opts=opts)


def _usage(total_gb: float, used_gb: float, free_gb: float, percent: float) -> _FakeUsage:
    # Values are chosen in the tests to have <= 2 decimal places, so
    # this exact byte conversion round-trips cleanly through disk.py's
    # own round(x / _BYTES_PER_GB, 2).
    return _FakeUsage(
        total=int(total_gb * _BYTES_PER_GB),
        used=int(used_gb * _BYTES_PER_GB),
        free=int(free_gb * _BYTES_PER_GB),
        percent=percent,
    )


def test_disk_run_reports_every_usable_partition_separately(monkeypatch) -> None:
    """Regression test for the original bug report: a machine with two
    real partitions (C: and D:) must report both, not just one.
    """
    partitions = [_partition("D:\\"), _partition("C:\\")]  # deliberately out of order
    usages = {
        "C:\\": _usage(total_gb=172.0, used_gb=159.7, free_gb=12.3, percent=92.8),
        "D:\\": _usage(total_gb=195.2, used_gb=75.09, free_gb=120.11, percent=38.5),
    }

    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: partitions)
    monkeypatch.setattr(disk.psutil, "disk_usage", lambda path: usages[path])

    result = disk.run()

    assert result.status == ToolStatus.SUCCESS
    volumes = result.payload["volumes"]
    # Sorted by mountpoint regardless of enumeration order — C: before D:.
    assert [v["mountpoint"] for v in volumes] == ["C:\\", "D:\\"]

    c_drive = volumes[0]
    assert c_drive["total_gb"] == 172.0
    assert c_drive["used_gb"] == 159.7
    assert c_drive["free_gb"] == 12.3
    assert c_drive["usage_percent"] == 92.8
    assert c_drive["filesystem"] == "NTFS"

    d_drive = volumes[1]
    assert d_drive["total_gb"] == 195.2
    assert d_drive["used_gb"] == 75.09
    assert d_drive["free_gb"] == 120.11
    assert d_drive["usage_percent"] == 38.5


def test_disk_run_skips_a_failing_partition_but_still_returns_the_others(monkeypatch) -> None:
    """One volume raising on disk_usage() (e.g. ejected, permissions,
    not ready) must not stop the others from being reported, and must
    not turn the whole tool result into an error.
    """
    partitions = [_partition("C:\\"), _partition("D:\\")]

    def _fake_disk_usage(path: str) -> _FakeUsage:
        if path == "C:\\":
            raise OSError("[WinError 21] The device is not ready")
        return _usage(total_gb=195.2, used_gb=75.09, free_gb=120.11, percent=38.5)

    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: partitions)
    monkeypatch.setattr(disk.psutil, "disk_usage", _fake_disk_usage)

    result = disk.run()

    assert result.status == ToolStatus.SUCCESS
    volumes = result.payload["volumes"]
    assert [v["mountpoint"] for v in volumes] == ["D:\\"]


def test_disk_run_returns_empty_volumes_when_none_are_usable(monkeypatch) -> None:
    """No partitions at all is a valid outcome (e.g. a sandboxed
    environment) — SUCCESS with an empty list, not an error.
    """
    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: [])

    result = disk.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["volumes"] == []


def test_disk_run_skips_a_drive_with_no_media_without_attempting_disk_usage(monkeypatch) -> None:
    """An empty CD-ROM/removable drive on Windows is listed by
    disk_partitions() with an empty fstype, and calling disk_usage() on
    it raises. It must be filtered out before disk_usage is even
    attempted, not surfaced as a volume with unknown data.
    """
    partitions = [_partition("C:\\"), _partition("E:\\", fstype="", opts="cdrom")]

    def _fake_disk_usage(path: str) -> _FakeUsage:
        assert path != "E:\\", "disk_usage should never be called for a drive with no media"
        return _usage(total_gb=172.0, used_gb=159.7, free_gb=12.3, percent=92.8)

    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: partitions)
    monkeypatch.setattr(disk.psutil, "disk_usage", _fake_disk_usage)

    result = disk.run()

    volumes = result.payload["volumes"]
    assert [v["mountpoint"] for v in volumes] == ["C:\\"]


def test_disk_run_skips_known_pseudo_filesystems(monkeypatch) -> None:
    """A partition reporting a well-known pseudo/virtual filesystem type
    (squashfs, tmpfs, ...) must be excluded even though its fstype is
    non-empty — real bug found in this project's own dev sandbox, not a
    hypothetical.
    """
    partitions = [_partition("C:\\"), _partition("/snap/core", fstype="squashfs")]

    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: partitions)
    monkeypatch.setattr(
        disk.psutil,
        "disk_usage",
        lambda path: _usage(total_gb=172.0, used_gb=159.7, free_gb=12.3, percent=92.8),
    )

    result = disk.run()

    volumes = result.payload["volumes"]
    assert [v["mountpoint"] for v in volumes] == ["C:\\"]


def test_disk_run_reports_each_volumes_own_filesystem_type(monkeypatch) -> None:
    partitions = [_partition("C:\\", fstype="NTFS"), _partition("/data", fstype="ext4")]

    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: partitions)
    monkeypatch.setattr(
        disk.psutil,
        "disk_usage",
        lambda path: _usage(total_gb=100.0, used_gb=50.0, free_gb=50.0, percent=50.0),
    )

    result = disk.run()

    filesystems = {v["mountpoint"]: v["filesystem"] for v in result.payload["volumes"]}
    assert filesystems["C:\\"] == "NTFS"
    assert filesystems["/data"] == "ext4"


def test_disk_run_rounds_gb_values_to_two_decimal_places(monkeypatch) -> None:
    partitions = [_partition("C:\\")]
    # Raw byte counts chosen to NOT divide evenly into gigabytes, so
    # rounding is actually exercised rather than accidentally exact.
    usage = _FakeUsage(total=184683593728, used=171540123456, free=13143470272, percent=92.876)

    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: partitions)
    monkeypatch.setattr(disk.psutil, "disk_usage", lambda path: usage)

    result = disk.run()

    volume = result.payload["volumes"][0]
    for key in ("total_gb", "used_gb", "free_gb", "usage_percent"):
        value = volume[key]
        assert round(value, 2) == value, f"{key}={value!r} has more than 2 decimal places"


def test_disk_run_payload_has_expected_shape(monkeypatch) -> None:
    partitions = [_partition("C:\\")]
    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: partitions)
    monkeypatch.setattr(
        disk.psutil,
        "disk_usage",
        lambda path: _usage(total_gb=100.0, used_gb=40.0, free_gb=60.0, percent=40.0),
    )

    result = disk.run()

    assert set(result.payload.keys()) == {"volumes"}
    volume = result.payload["volumes"][0]
    assert set(volume.keys()) == {
        "mountpoint",
        "total_gb",
        "used_gb",
        "free_gb",
        "usage_percent",
        "filesystem",
    }


def test_disk_run_returns_error_result_when_enumeration_fails(monkeypatch) -> None:
    """A failure enumerating volumes at all (not reading one of them —
    see the "skips a failing partition" test above) is a real tool
    failure and must produce an error ToolResult, not raise.
    """

    def _boom(all=False):
        raise OSError("simulated psutil failure")

    monkeypatch.setattr(disk.psutil, "disk_partitions", _boom)

    result = disk.run()

    assert result.tool_name == "disk"
    assert result.status == ToolStatus.ERROR
    assert "simulated psutil failure" in result.payload["error"]


def test_disk_run_against_real_psutil_returns_a_well_formed_result() -> None:
    """Integration-style smoke test against the real environment (no
    mocking) — proves the tool actually works end to end here, not just
    against fakes.
    """
    result = disk.run()

    assert result.tool_name == "disk"
    assert result.status == ToolStatus.SUCCESS
    assert isinstance(result.payload["volumes"], list)

    for volume in result.payload["volumes"]:
        assert isinstance(volume["mountpoint"], str) and volume["mountpoint"]
        assert volume["used_gb"] <= volume["total_gb"]
        assert volume["free_gb"] <= volume["total_gb"]
        assert 0 <= volume["usage_percent"] <= 100
        assert volume["filesystem"] is None or isinstance(volume["filesystem"], str)
