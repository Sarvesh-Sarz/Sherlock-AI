from app.models.tool_result import ToolStatus
from app.tools import disk


def test_disk_run_returns_success_with_expected_payload_shape() -> None:
    result = disk.run()

    assert result.tool_name == "disk"
    # In this environment psutil is expected to work, so assert success
    # rather than allowing either outcome — the failure path is exercised
    # explicitly below via monkeypatching.
    assert result.status == ToolStatus.SUCCESS
    assert result.collected_at is not None

    payload = result.payload
    expected_keys = {"total_gb", "used_gb", "free_gb", "usage_percent", "filesystem"}
    assert set(payload.keys()) == expected_keys

    for key in ("total_gb", "used_gb", "free_gb", "usage_percent"):
        assert isinstance(payload[key], (int, float))
        assert payload[key] >= 0

    # filesystem is a string on any conventionally-mounted system (this
    # sandbox included) — see test_disk_run_reports_none_filesystem_when_no_partition_matches
    # for the honestly-unknown case.
    assert payload["filesystem"] is None or isinstance(payload["filesystem"], str)

    # Sanity relationships that must hold on any real machine, not just
    # "some number came back".
    assert payload["used_gb"] <= payload["total_gb"]
    assert payload["free_gb"] <= payload["total_gb"]
    assert 0 <= payload["usage_percent"] <= 100


def test_disk_run_rounds_gb_values_to_two_decimal_places() -> None:
    payload = disk.run().payload

    for key in ("total_gb", "used_gb", "free_gb"):
        value = payload[key]
        # round(x, 2) can still produce e.g. 9.5 (one decimal digit) —
        # what matters is no more than 2 decimal places of precision,
        # not that the string always shows exactly two.
        assert round(value, 2) == value, f"{key}={value!r} has more than 2 decimal places"


def test_disk_run_returns_error_result_when_disk_usage_fails(monkeypatch) -> None:
    """A failure inside psutil must produce an error ToolResult, not raise."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated psutil failure")

    monkeypatch.setattr(disk.psutil, "disk_usage", _boom)

    result = disk.run()

    assert result.tool_name == "disk"
    assert result.status == ToolStatus.ERROR
    assert "simulated psutil failure" in result.payload["error"]


def test_disk_run_survives_disk_partitions_failing_independently(monkeypatch) -> None:
    """disk_usage() and disk_partitions() are two separate psutil calls —
    a failure in either one must be caught, not just the first.
    """

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated partitions failure")

    monkeypatch.setattr(disk.psutil, "disk_partitions", _boom)

    result = disk.run()

    assert result.status == ToolStatus.ERROR
    assert "simulated partitions failure" in result.payload["error"]


def test_disk_run_reports_none_filesystem_when_no_partition_matches(monkeypatch) -> None:
    """If no reported partition's mountpoint matches the target path
    exactly, filesystem type is honestly reported as unknown (None)
    rather than guessed — this must not be treated as a failure, since
    space usage was still collected successfully.
    """
    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda: [])

    result = disk.run()

    assert result.status == ToolStatus.SUCCESS
    assert result.payload["filesystem"] is None
