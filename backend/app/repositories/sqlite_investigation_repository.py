"""SQLite-backed investigation storage.

Each case is stored as one JSON document (the full `Investigation`:
plan, evidence, report, trace, troubleshooting session) plus a few
indexed columns used for listing. A document store fits here because a
case is always read and written as a whole, and its nested shape
(reports, hypotheses, traces) is still evolving; a normalized schema
would mean a migration for every model change.

Behavioral notes:
- `get()` returns a fresh copy on every call. Unlike the in-memory
  repository, mutating a returned object changes nothing until
  `update()` is called. The service already follows that rule.
- `add()` and `update()` are both upserts, matching the in-memory
  repository, so the two implementations are interchangeable.
- One connection guarded by a lock. FastAPI runs sync endpoints in a
  thread pool, and `:memory:` databases are per-connection, so a single
  shared connection is the simplest correct design for a local desktop
  app. WAL mode keeps writes durable and reads cheap for file databases.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.models.investigation import CaseStatus, CaseSummary, Investigation
from app.repositories.investigation_repository import InvestigationRepository

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_investigation_adapter = TypeAdapter(Investigation)


class CorruptRecordError(RuntimeError):
    """A stored case could not be read back into an `Investigation`."""


class SqliteInvestigationRepository(InvestigationRepository):
    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self._path = str(database_path)
        self._lock = threading.RLock()

        if self._path != ":memory:":
            Path(self._path).expanduser().parent.mkdir(parents=True, exist_ok=True)

        self._connection = sqlite3.connect(
            self._path if self._path == ":memory:" else str(Path(self._path).expanduser()),
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    # -- InvestigationRepository -------------------------------------------

    def add(self, investigation: Investigation) -> None:
        self._upsert(investigation)

    def update(self, investigation: Investigation) -> None:
        self._upsert(investigation)

    def get(self, case_id: str) -> Investigation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT data FROM investigations WHERE case_id = ?", (case_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            return _investigation_adapter.validate_json(row["data"])
        except ValidationError as exc:
            logger.error("Stored case %s could not be read: %s", case_id, exc)
            raise CorruptRecordError(
                f"Stored case '{case_id}' could not be read back; its data may be "
                "corrupt or written by an incompatible version."
            ) from exc

    def list_recent(self, limit: int = 20) -> list[CaseSummary]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT case_id, problem_description, status, created_at, updated_at "
                "FROM investigations ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            CaseSummary(
                case_id=row["case_id"],
                problem_description=row["problem_description"],
                status=CaseStatus(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # -- internals ----------------------------------------------------------

    def _initialize(self) -> None:
        with self._lock:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                self._connection.close()
                raise RuntimeError(
                    f"Database '{self._path}' uses schema version {version}, but this "
                    f"version of Sherlock only understands up to {SCHEMA_VERSION}. "
                    "Update Sherlock or point it at a different database."
                )
            if self._path != ":memory:":
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA synchronous=NORMAL")
            if version < 1:
                with self._connection:
                    self._connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS investigations (
                            case_id             TEXT PRIMARY KEY,
                            problem_description TEXT NOT NULL,
                            status              TEXT NOT NULL,
                            created_at          TEXT NOT NULL,
                            updated_at          TEXT NOT NULL,
                            data                TEXT NOT NULL
                        )
                        """
                    )
                    self._connection.execute(
                        "CREATE INDEX IF NOT EXISTS idx_investigations_created_at "
                        "ON investigations (created_at DESC)"
                    )
                    self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _upsert(self, investigation: Investigation) -> None:
        document = _investigation_adapter.dump_json(investigation).decode("utf-8")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO investigations
                    (case_id, problem_description, status, created_at, updated_at, data)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    problem_description = excluded.problem_description,
                    status              = excluded.status,
                    updated_at          = excluded.updated_at,
                    data                = excluded.data
                """,
                (
                    investigation.case_id,
                    investigation.problem_description,
                    investigation.status.value,
                    _iso(investigation.created_at),
                    _iso(investigation.updated_at),
                    document,
                ),
            )


def _iso(value: datetime) -> str:
    """Normalize to UTC so lexicographic order equals chronological order."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
