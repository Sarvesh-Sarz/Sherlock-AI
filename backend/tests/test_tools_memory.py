from app.models.tool_result import ToolStatus
from app.tools import memory


def test_memory_run_returns_success_with_expected_payload_shape() -> None:
    result = memory.run()

    assert result.tool_name == "memory"
    # In this environment psutil is expected to work, so assert success
    # rather than allowing either outcome — the failure path is exercised
    # explicitly below via monkeypatching.
    assert result.status == ToolStatus.SUCCESS
    assert result.collected_at is not None

    payload = result.payload
    expected_keys = {
        "total_gb",
        "available_gb",
        "used_gb",
        "usage_percent",
        "swap_total_gb",
        "swap_used_gb",
    }
    assert set(payload.keys()) == expected_keys

    for key in expected_keys:
        assert isinstance(payload[key], (int, float))
        assert payload[key] >= 0

    # Sanity relationships that must hold on any real machine, not just
    # "some number came back".
    assert payload["available_gb"] <= payload["total_gb"]
    assert payload["used_gb"] <= payload["total_gb"]
    assert payload["swap_used_gb"] <= payload["swap_total_gb"]
    assert 0 <= payload["usage_percent"] <= 100


def test_memory_run_rounds_values_to_two_decimal_places() -> None:
    payload = memory.run().payload

    for key, value in payload.items():
        # round(x, 2) can still produce e.g. 3.9 (one decimal digit) —
        # what matters is no more than 2 decimal places of precision,
        # not that the string always shows exactly two.
        assert round(value, 2) == value, f"{key}={value!r} has more than 2 decimal places"


def test_memory_run_returns_error_result_when_psutil_fails(monkeypatch) -> None:
    """A failure inside psutil must produce an error ToolResult, not raise."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated psutil failure")

    monkeypatch.setattr(memory.psutil, "virtual_memory", _boom)

    result = memory.run()

    assert result.tool_name == "memory"
    assert result.status == ToolStatus.ERROR
    assert "simulated psutil failure" in result.payload["error"]


def test_memory_run_survives_swap_memory_failing_independently(monkeypatch) -> None:
    """virtual_memory() and swap_memory() are two separate psutil calls —
    a failure in either one must be caught, not just the first.
    """

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated swap failure")

    monkeypatch.setattr(memory.psutil, "swap_memory", _boom)

    result = memory.run()

    assert result.status == ToolStatus.ERROR
    assert "simulated swap failure" in result.payload["error"]
