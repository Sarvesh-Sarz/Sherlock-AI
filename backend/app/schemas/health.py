"""Schema for the health check endpoint."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Reported service liveness and identity."""

    status: str
    service: str
    version: str
    timestamp: datetime
