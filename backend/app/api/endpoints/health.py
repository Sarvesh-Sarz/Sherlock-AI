"""GET /health — service liveness check."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check whether the service is running",
)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.version,
        timestamp=datetime.now(timezone.utc),
    )
