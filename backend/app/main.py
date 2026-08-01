"""FastAPI application factory and entrypoint.

Run locally with:

    uvicorn app.main:app --reload

`create_app` is a factory rather than a module-level side effect so
tests can build fresh app instances (with overridden settings or
dependencies) without importing a singleton.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Backend foundation for Sherlock AI — an AI-powered Windows "
            "diagnostic investigation tool. This build exposes placeholder "
            "endpoints only; no diagnostics, reasoning, or persistence are "
            "implemented yet."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app


app = create_app()
