"""Aggregates every endpoint router into one, so `main.py` only ever
mounts a single router. Adding a new resource (e.g. `settings`) later
means adding one `include_router` line here, not touching `main.py`.
"""

from fastapi import APIRouter

from app.api.endpoints import health, investigation

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(
    investigation.router, prefix="/investigation", tags=["investigation"]
)
