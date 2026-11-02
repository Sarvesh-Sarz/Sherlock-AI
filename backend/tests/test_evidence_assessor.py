from datetime import datetime, timezone

from app.engine.evidence_assessor import EvidenceAssessor
from app.models.tool_result import ToolResult, ToolStatus


def make_result(name, payload, status=ToolStatus.SUCCESS):
    return ToolResult(
        tool_name=name,
        status=status,
        collected_at=datetime.now(timezone.utc),
        payload=payload,
    )


def assess(evidence, executed=(), complaint="check system"):
    return EvidenceAssessor().assess(complaint, evidence, executed_tools=executed)


# ---- CPU -----------------------------------------------------------------

def test_high_cpu_recommends_unexecuted_followups():
    result = assess([make_result("cpu", {"usage_percent": 93})], executed=["cpu"])
    assert "cpu" not in result.additional_tools
    assert {"memory", "startup"} <= set(result.additional_tools)
    assert all(r for r in result.reasons)


def test_normal_cpu_recommends_nothing():
    assert assess([make_result("cpu", {"usage_percent": 12})]).additional_tools == ()


def test_busy_cpu_far_below_max_frequency_suggests_temperature():
    payload = {"usage_percent": 70, "current_frequency": 1.2, "max_frequency": 4.7}
    result = assess([make_result("cpu", payload)], executed=["cpu"])
    assert result.additional_tools == ("temperature",)


def test_idle_cpu_low_frequency_is_normal_power_saving():
    payload = {"usage_percent": 3, "current_frequency": 0.8, "max_frequency": 4.7}
    assert assess([make_result("cpu", payload)]).additional_tools == ()


def test_unknown_frequency_does_not_suggest_temperature():
    payload = {"usage_percent": 70, "current_frequency": None, "max_frequency": None}
    assert assess([make_result("cpu", payload)]).additional_tools == ()


# ---- Memory (real keys: usage_percent, available_gb) ---------------------

def test_high_memory_usage_recommends_cpu_and_startup():
    result = assess([make_result("memory", {"usage_percent": 91.5, "available_gb": 1.4})],
                    executed=["memory"])
    assert set(result.additional_tools) == {"cpu", "startup"}


def test_low_available_memory_recommends_cpu():
    result = assess([make_result("memory", {"usage_percent": 70, "available_gb": 0.5})])
    assert result.additional_tools == ("cpu",)


def test_healthy_memory_recommends_nothing():
    result = assess([make_result("memory", {"usage_percent": 40, "available_gb": 9.0})])
    assert result.additional_tools == ()


# ---- Disk (real shape: volumes[]) ----------------------------------------

def test_full_volume_recommends_startup_and_memory():
    disk = {"volumes": [
        {"mountpoint": "C:\\", "usage_percent": 92.8, "free_gb": 12.3},
        {"mountpoint": "D:\\", "usage_percent": 38.5, "free_gb": 120.1},
    ]}
    result = assess([make_result("disk", disk)], executed=["disk"])
    assert set(result.additional_tools) == {"startup", "memory"}
    assert any("C:" in r for r in result.reasons)


def test_only_healthy_volumes_recommend_nothing():
    disk = {"volumes": [{"mountpoint": "C:\\", "usage_percent": 40.0}]}
    assert assess([make_result("disk", disk)]).additional_tools == ()


def test_empty_volume_list_is_unknown_not_a_signal():
    assert assess([make_result("disk", {"volumes": []})]).additional_tools == ()


def test_malformed_disk_payload_is_ignored():
    for bad in ({"volumes": "oops"}, {"volumes": [None, 5]}, {"volumes": [{"usage_percent": "high"}]}):
        assert assess([make_result("disk", bad)]).additional_tools == ()


# ---- Safety principles ---------------------------------------------------

def test_failed_evidence_is_unknown_and_triggers_nothing():
    for name, payload in (("cpu", {"usage_percent": 99}),
                          ("memory", {"usage_percent": 99, "available_gb": 0.1}),
                          ("disk", {"volumes": [{"usage_percent": 99}]})):
        result = assess([make_result(name, payload, ToolStatus.ERROR)])
        assert result.additional_tools == ()


def test_error_payload_without_metrics_is_ignored():
    assert assess([make_result("cpu", {"error": "boom"})]).additional_tools == ()


def test_out_of_range_or_nonfinite_values_are_ignored():
    for bad in (150, -5, float("nan"), float("inf"), True, "93"):
        assert assess([make_result("cpu", {"usage_percent": bad})]).additional_tools == ()


def test_never_recommends_already_executed_tools():
    result = assess([make_result("cpu", {"usage_percent": 95})], executed=["cpu", "memory", "startup"])
    assert result.additional_tools == ()


def test_no_duplicates_when_several_signals_agree():
    evidence = [
        make_result("cpu", {"usage_percent": 95}),
        make_result("memory", {"usage_percent": 95, "available_gb": 0.2}),
        make_result("disk", {"volumes": [{"mountpoint": "C:\\", "usage_percent": 95}]}),
    ]
    tools = assess(evidence, executed=["cpu", "memory", "disk"]).additional_tools
    assert tools == ("startup",)


def test_complaint_text_alone_never_adds_tools():
    # The Planner owns complaint -> tools. "wifi is slow" must not be
    # widened to cpu/memory/startup by the assessor.
    result = assess([], complaint="my wifi is slow and my disk is full")
    assert result.additional_tools == ()
