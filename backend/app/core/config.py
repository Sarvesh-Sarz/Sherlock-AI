"""Application configuration.

All runtime configuration lives here and is read from environment
variables (optionally via a `.env` file). Nothing else in the app should
call `os.environ` directly — inject `Settings` instead, so behavior stays
testable and every configurable value is documented in one place.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings.

    Values can be overridden via environment variables prefixed with
    `SHERLOCK_` (e.g. `SHERLOCK_ENVIRONMENT=production`), or via a
    `.env` file — see `.env.example`.
    """

    app_name: str = "Sherlock AI Backend"
    version: str = "0.1.0"
    environment: str = "development"

    # Origins allowed to call the API from a browser (the Electron/Tauri
    # shell or a local Vite dev server for the frontend).
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Optional. If unset, `app.api.deps.get_researcher` falls back to
    # `UnconfiguredResearcher` and Sherlock runs with zero external
    # research — a missing key is a normal, supported configuration,
    # not an error. See `.env.example`.
    tavily_api_key: str | None = None

    # Local LLM reasoning via Ollama (https://ollama.com). No API key —
    # Ollama runs locally, so "configured" just means "reachable at
    # this URL with this model available". If it isn't,
    # `app.api.deps.get_reasoner` falls back to the deterministic
    # `BaselineReasoner` automatically (see `FallbackReasoner`); these
    # defaults assume a locally-running default Ollama install, not a
    # requirement to have one.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SHERLOCK_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance.

    Cached so Settings is only parsed/validated once per process, and so
    it can be swapped via `app.dependency_overrides` in tests.
    """
    return Settings()
