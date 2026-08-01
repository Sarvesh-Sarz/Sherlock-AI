"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    """A fresh TestClient per test, built from a fresh app instance."""
    return TestClient(create_app())
