"""Shared pytest fixtures."""

import os

# Tests must never touch a real database file. Set before the app (and
# its cached settings) are imported.
os.environ["SHERLOCK_DATABASE_PATH"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_investigation_repository
from app.main import create_app


@pytest.fixture(autouse=True)
def no_real_internet_in_tests(request, monkeypatch):
    """The network tool contacts a real server. Tests that start whole
    investigations must never do that (slow, flaky, offline CI), so its
    measurement is replaced with a fast failure. The tool's own tests
    run it for real against a local server and opt out of this."""
    if request.module.__name__.endswith("test_tools_network"):
        return

    from app.tools import network

    def offline(*args, **kwargs):
        raise OSError("real network access is disabled in tests")

    monkeypatch.setattr(network, "_measure_once", offline)


@pytest.fixture(autouse=True)
def no_real_ollama_in_tests(monkeypatch):
    """Investigations started through the API build the real reasoner, which
    would call whatever Ollama is running on the developer's machine: slow
    (a small model can take a minute or more) and non-deterministic. Make the
    model look unreachable instead. Tests that exercise the Ollama client
    install their own fake `httpx.post`, which takes precedence."""
    import httpx

    def unreachable(*args, **kwargs):
        raise httpx.ConnectError("Ollama is disabled in tests")

    monkeypatch.setattr("app.reasoning.ollama_reasoner.httpx.post", unreachable)


@pytest.fixture()
def client() -> TestClient:
    """A fresh TestClient per test, built from a fresh app instance.

    The repository is cached process-wide, so clear it to give every
    test its own empty in-memory database.
    """
    get_investigation_repository.cache_clear()
    return TestClient(create_app())
