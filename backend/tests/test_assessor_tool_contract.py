"""Guards against drift between real tool payloads and the assessor's rules.

The original assessor tests used invented payloads (e.g. `free_percent`)
that no real tool produced, so they passed while the rules never fired.
These tests run the real tools and assert the keys the assessor reads
actually exist.
"""
from app.engine.evidence_assessor import EvidenceAssessor
from app.models.tool_result import ToolStatus
from app.tools import cpu, disk, memory


def test_cpu_payload_has_keys_assessor_reads():
    result = cpu.run()
    assert result.status == ToolStatus.SUCCESS
    for key in ("usage_percent", "current_frequency", "max_frequency"):
        assert key in result.payload


def test_memory_payload_has_keys_assessor_reads():
    result = memory.run()
    assert result.status == ToolStatus.SUCCESS
    assert "usage_percent" in result.payload
    assert "available_gb" in result.payload


def test_disk_payload_has_volume_list_assessor_reads():
    result = disk.run()
    assert result.status == ToolStatus.SUCCESS
    assert isinstance(result.payload["volumes"], list)
    for volume in result.payload["volumes"]:
        assert "usage_percent" in volume


def test_assessor_accepts_real_tool_output_without_error():
    evidence = [cpu.run(), memory.run(), disk.run()]
    assessment = EvidenceAssessor().assess("check system", evidence, ["cpu", "memory", "disk"])
    assert isinstance(assessment.additional_tools, tuple)
