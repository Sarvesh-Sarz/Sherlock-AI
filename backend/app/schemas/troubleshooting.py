"""API schemas for guided troubleshooting endpoints."""

from pydantic import BaseModel, Field

from app.models.troubleshooting_session import StepResult


class StartTroubleshootingRequest(BaseModel):
    """Request body for starting guided troubleshooting."""

    recommendation_index: int = Field(
        ...,
        ge=0,
        description="Index of the recommendation to troubleshoot.",
    )


class AnswerTroubleshootingStepRequest(BaseModel):
    """Request body for answering the current troubleshooting step."""

    result: StepResult