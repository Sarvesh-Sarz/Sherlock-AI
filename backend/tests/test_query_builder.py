"""Tests for app.reasoning.query_builder — turning the complaint and
evidence into focused research queries, never the raw evidence payload
itself.
"""

from datetime import datetime, timezone

from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.query_builder import build_research_queries


def _result(tool_name: str, payload: dict) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.SUCCESS,
        collected_at=datetime.now(timezone.utc),
        payload=payload,
    )


def test_problem_description_alone_produces_a_general_query() -> None:
    queries = build_research_queries("My laptop takes 5 minutes to boot", [])

    assert queries == ["Windows My laptop takes 5 minutes to boot"]


def test_empty_problem_description_and_no_signals_produce_no_queries() -> None:
    evidence = [_result("cpu", {"usage_percent": 10.0})]

    assert build_research_queries("", evidence) == []


def test_a_disk_signal_produces_a_focused_query_not_the_raw_payload() -> None:
    evidence = [_result("disk", {"volumes": [{"mountpoint": "C:\\", "usage_percent": 96.0, "free_gb": 2.0}]})]

    queries = build_research_queries("", evidence)

    assert "Windows low disk space performance impact" in queries
    # The query is a fixed, human-written technical phrase — never the
    # mountpoint, the raw percentage, or anything else lifted directly
    # from the payload.
    assert not any("C:" in q for q in queries)
    assert not any("96" in q for q in queries)


def test_multiple_volumes_over_threshold_produce_one_deduplicated_query() -> None:
    evidence = [
        _result(
            "disk",
            {
                "volumes": [
                    {"mountpoint": "C:\\", "usage_percent": 90.0, "free_gb": 5.0},
                    {"mountpoint": "D:\\", "usage_percent": 92.0, "free_gb": 3.0},
                ]
            },
        )
    ]

    queries = build_research_queries("", evidence)

    assert queries == ["Windows low disk space performance impact"]


def test_multiple_kinds_of_signals_produce_multiple_queries_up_to_the_cap() -> None:
    evidence = [
        _result("disk", {"volumes": [{"mountpoint": "C:\\", "usage_percent": 96.0, "free_gb": 1.0}]}),
        _result("memory", {"usage_percent": 90.0}),
        _result("startup", {"total_entries": 20, "entries": [], "sources_unavailable": []}),
    ]

    queries = build_research_queries("", evidence)

    # All three signals fit within the cap (3) when there's no general
    # query competing for a slot.
    assert set(queries) == {
        "Windows low disk space performance impact",
        "Windows high memory usage performance impact",
        "Windows startup applications slow boot performance",
    }


def test_problem_description_and_evidence_signals_combine() -> None:
    evidence = [_result("disk", {"volumes": [{"mountpoint": "C:\\", "usage_percent": 96.0, "free_gb": 1.0}]})]

    queries = build_research_queries("My laptop becomes slow after startup", evidence)

    assert queries == [
        "Windows My laptop becomes slow after startup",
        "Windows low disk space performance impact",
    ]


def test_trailing_period_is_stripped_from_the_general_query() -> None:
    queries = build_research_queries("My wifi keeps disconnecting.", [])

    assert queries == ["Windows My wifi keeps disconnecting"]


def test_query_limit_is_preserved_and_the_general_query_competes_for_a_slot() -> None:
    """The cap stays at its existing value (3) even with the complaint
    added as a source — a rich evidence set can still push the general
    query (or one evidence query) out, exactly the same trade-off that
    already existed between evidence signals competing for slots.
    """
    evidence = [
        _result("disk", {"volumes": [{"mountpoint": "C:\\", "usage_percent": 96.0, "free_gb": 1.0}]}),
        _result("memory", {"usage_percent": 90.0}),
        _result("startup", {"total_entries": 20, "entries": [], "sources_unavailable": []}),
    ]

    queries = build_research_queries("My laptop becomes slow after startup", evidence)

    assert len(queries) == 3
    # The general query is built first, so it wins a slot; one evidence
    # signal (the last one considered) is the one that gets capped out.
    assert queries[0] == "Windows My laptop becomes slow after startup"


def test_queries_never_exceed_the_cap_even_with_no_general_query() -> None:
    evidence = [
        _result("disk", {"volumes": [{"mountpoint": "C:\\", "usage_percent": 96.0, "free_gb": 1.0}]}),
        _result("memory", {"usage_percent": 90.0}),
        _result("startup", {"total_entries": 20, "entries": [], "sources_unavailable": []}),
    ]

    queries = build_research_queries("", evidence)

    assert len(queries) <= 3
