"""Contract tests run against every repository implementation, plus
SQLite-specific durability and safety tests."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_investigation_repository
from app.models.investigation import CaseStatus, Investigation
from app.models.investigation_plan import InvestigationPlan
from app.models.tool_result import ToolResult, ToolStatus
from app.models.trace import TraceEvent, TraceStage
from app.models.troubleshooting_session import (
    SessionStatus,
    StepAnswer,
    StepResult,
    TroubleshootingSession,
)
from app.repositories.investigation_repository import InMemoryInvestigationRepository
from app.repositories.sqlite_investigation_repository import (
    CorruptRecordError,
    SqliteInvestigationRepository,
)


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        yield InMemoryInvestigationRepository()
    else:
        repository = SqliteInvestigationRepository(tmp_path / "cases.db")
        yield repository
        repository.close()


def make_case(description="my laptop is slow", age_seconds=0) -> Investigation:
    case = Investigation.new(description)
    case.created_at = case.updated_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return case


def make_rich_case() -> Investigation:
    """A case exercising every nested field the repository must preserve."""
    now = datetime.now(timezone.utc)
    case = Investigation.new("my laptop is slow")
    case.set_plan(
        InvestigationPlan(
            problem_description=case.problem_description,
            tools_to_execute=["cpu", "memory"],
            matched_keywords=["slow"],
            created_at=now,
        )
    )
    case.add_evidence(
        ToolResult(
            tool_name="cpu",
            status=ToolStatus.SUCCESS,
            collected_at=now,
            payload={"usage_percent": 93.5, "cores": [1, 2], "nested": {"ok": True, "none": None}},
        )
    )
    case.add_evidence(
        ToolResult(tool_name="startup", status=ToolStatus.ERROR, collected_at=now, payload={"error": "boom"})
    )
    case.set_trace(
        [
            TraceEvent(stage=TraceStage.PLAN, message="Planned diagnostics: cpu.", details={"tools": ["cpu"]}),
            TraceEvent(
                stage=TraceStage.ASSESS,
                iteration=1,
                message="follow-up",
                details={"follow_up_tools": ["memory"], "iteration_limit_reached": False},
            ),
        ]
    )
    case.set_troubleshooting_session(
        TroubleshootingSession(
            case_id=case.case_id,
            status=SessionStatus.IN_PROGRESS,
            current_recommendation_index=0,
            current_step_index=1,
            answers=[
                StepAnswer(
                    recommendation_index=0,
                    step_index=0,
                    result=StepResult.COULD_NOT_COMPLETE,
                    answered_at=now,
                )
            ],
        )
    )
    case.mark_status(CaseStatus.RESOLVED)
    return case


# ---- Contract: every implementation ---------------------------------------

def test_get_unknown_case_returns_none(repo):
    assert repo.get("does-not-exist") is None


def test_add_then_get_returns_the_case(repo):
    case = make_case()
    repo.add(case)
    assert repo.get(case.case_id) == case


def test_update_persists_changes(repo):
    case = make_case()
    repo.add(case)
    case.mark_status(CaseStatus.FAILED)
    repo.update(case)
    assert repo.get(case.case_id).status is CaseStatus.FAILED


def test_list_recent_is_newest_first_and_limited(repo):
    oldest, middle, newest = make_case("old", 300), make_case("mid", 200), make_case("new", 100)
    for case in (middle, oldest, newest):
        repo.add(case)

    assert [s.problem_description for s in repo.list_recent()] == ["new", "mid", "old"]
    assert [s.problem_description for s in repo.list_recent(limit=2)] == ["new", "mid"]


def test_list_recent_on_empty_repository(repo):
    assert repo.list_recent() == []


def test_list_recent_summary_matches_case(repo):
    case = make_case()
    repo.add(case)
    (summary,) = repo.list_recent()
    assert summary == case.summary()


# ---- SQLite: fidelity and durability --------------------------------------

def test_sqlite_round_trips_every_nested_field(tmp_path):
    repo = SqliteInvestigationRepository(tmp_path / "cases.db")
    case = make_rich_case()
    repo.add(case)

    loaded = repo.get(case.case_id)
    assert loaded == case
    assert loaded.evidence[0].payload["nested"] == {"ok": True, "none": None}
    assert loaded.evidence[1].status is ToolStatus.ERROR  # failed evidence preserved
    assert [e.stage for e in loaded.trace] == [TraceStage.PLAN, TraceStage.ASSESS]
    assert loaded.troubleshooting_session.answers[0].result is StepResult.COULD_NOT_COMPLETE
    assert loaded.created_at.tzinfo is not None


def test_cases_survive_a_restart(tmp_path):
    path = tmp_path / "sherlock.db"
    first = SqliteInvestigationRepository(path)
    case = make_rich_case()
    first.add(case)
    first.close()

    second = SqliteInvestigationRepository(path)  # a new process would do exactly this
    assert second.get(case.case_id) == case
    assert [s.case_id for s in second.list_recent()] == [case.case_id]


def test_creates_missing_parent_directories(tmp_path):
    nested = tmp_path / "a" / "b" / "sherlock.db"
    SqliteInvestigationRepository(nested).close()
    assert nested.exists()


def test_get_returns_an_independent_copy(tmp_path):
    repo = SqliteInvestigationRepository(tmp_path / "cases.db")
    case = make_case()
    repo.add(case)

    fetched = repo.get(case.case_id)
    fetched.mark_status(CaseStatus.FAILED)  # no update() call

    assert repo.get(case.case_id).status is CaseStatus.RECEIVED


def test_corrupt_record_raises_a_clear_error_and_does_not_break_listing(tmp_path):
    path = tmp_path / "cases.db"
    repo = SqliteInvestigationRepository(path)
    good, bad = make_case("good"), make_case("bad")
    repo.add(good)
    repo.add(bad)
    repo._connection.execute("UPDATE investigations SET data = ? WHERE case_id = ?", ('{"nope": 1}', bad.case_id))
    repo._connection.commit()

    with pytest.raises(CorruptRecordError):
        repo.get(bad.case_id)
    assert repo.get(good.case_id) == good
    assert len(repo.list_recent()) == 2  # listing never parses the document


def test_refuses_a_database_from_a_newer_version(tmp_path):
    path = tmp_path / "future.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeError, match="schema version 99"):
        SqliteInvestigationRepository(path)


def test_concurrent_writers_from_many_threads(tmp_path):
    repo = SqliteInvestigationRepository(tmp_path / "cases.db")
    cases = [make_case(f"case {i}", age_seconds=i) for i in range(40)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(repo.add, cases))
    with ThreadPoolExecutor(max_workers=8) as pool:
        loaded = list(pool.map(lambda c: repo.get(c.case_id), cases))

    assert loaded == cases
    assert len(repo.list_recent(limit=100)) == 40


def test_memory_database_is_usable_from_another_thread():
    repo = SqliteInvestigationRepository(":memory:")
    case = make_case()
    result = {}
    thread = threading.Thread(target=lambda: (repo.add(case), result.setdefault("got", repo.get(case.case_id))))
    thread.start()
    thread.join()
    assert result["got"] == case


# ---- API: persistence and listing -----------------------------------------

def test_list_endpoint_starts_empty(client: TestClient):
    response = client.get("/investigation")
    assert response.status_code == 200
    assert response.json() == []


def test_list_endpoint_returns_newest_first_with_summaries_only(client: TestClient):
    first = client.post("/investigation/start", json={"problem_description": "first problem"}).json()
    second = client.post("/investigation/start", json={"problem_description": "second problem"}).json()

    rows = client.get("/investigation").json()
    assert [r["case_id"] for r in rows] == [second["case_id"], first["case_id"]]
    assert set(rows[0]) == {"case_id", "problem_description", "status", "created_at", "updated_at"}


def test_list_endpoint_validates_limit(client: TestClient):
    assert client.get("/investigation?limit=0").status_code == 422
    assert client.get("/investigation?limit=101").status_code == 422
    assert client.get("/investigation?limit=1").status_code == 200


def test_cases_survive_an_app_restart_through_the_api(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("SHERLOCK_DATABASE_PATH", str(tmp_path / "restart.db"))
    get_settings.cache_clear()
    get_investigation_repository.cache_clear()
    try:
        started = TestClient(create_app()).post(
            "/investigation/start", json={"problem_description": "my wifi is slow"}
        ).json()

        # "Restart": drop every cached singleton and build a brand-new app.
        get_investigation_repository().close()
        get_investigation_repository.cache_clear()
        get_settings.cache_clear()
        restarted = TestClient(create_app())

        fetched = restarted.get(f"/investigation/{started['case_id']}")
        assert fetched.status_code == 200
        assert fetched.json()["trace"] == started["trace"]
        assert [r["case_id"] for r in restarted.get("/investigation").json()] == [started["case_id"]]
    finally:
        get_investigation_repository().close()
        get_investigation_repository.cache_clear()
        monkeypatch.undo()
        get_settings.cache_clear()
