"""Shared pytest fixtures."""

import os

# Tests must never touch a real database file. Set before the app (and
# its cached settings) are imported.
os.environ["SHERLOCK_DATABASE_PATH"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_investigation_repository
from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    """A fresh TestClient per test, built from a fresh app instance.

    The repository is cached process-wide, so clear it to give every
    test its own empty in-memory database.
    """
    get_investigation_repository.cache_clear()
    return TestClient(create_app())
