from datetime import datetime, timezone
from app.engine.evidence_assessor import EvidenceAssessor
from app.models.tool_result import ToolResult, ToolStatus

def make_result(name, payload, status=ToolStatus.SUCCESS):
    return ToolResult(tool_name=name, status=status,
                      collected_at=datetime.now(timezone.utc), payload=payload)

def test_high_cpu_recommends_unexecuted_followups():
    result = EvidenceAssessor().assess("high CPU", [make_result("cpu", {"usage_percent": 93})],
                                       executed_tools=["cpu"])
    assert "cpu" not in result.additional_tools
    assert "memory" in result.additional_tools
    assert "startup" in result.additional_tools
    assert result.reasons

def test_failed_evidence_does_not_trigger_signal_rules():
    result = EvidenceAssessor().assess("check system",
        [make_result("cpu", {"usage_percent": 99}, ToolStatus.ERROR)])
    assert result.additional_tools == ()

def test_low_disk_space_recommends_startup_once():
    result = EvidenceAssessor().assess("check storage",
        [make_result("disk", {"free_percent": 8})], executed_tools=["disk"])
    assert result.additional_tools == ("startup",)

def test_complaint_recommendations_have_no_duplicates():
    result = EvidenceAssessor().assess("laptop is slow and disk is full", [])
    assert len(result.additional_tools) == len(set(result.additional_tools))
    assert {"cpu", "memory", "startup", "disk"} <= set(result.additional_tools)
