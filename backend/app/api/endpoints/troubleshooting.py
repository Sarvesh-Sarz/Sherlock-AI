"""API endpoints for guided troubleshooting."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_investigation_service
from app.models.troubleshooting_session import TroubleshootingSession
from app.schemas.troubleshooting import (
    AnswerTroubleshootingStepRequest,
    StartTroubleshootingRequest,
)
from app.services.investigation_service import InvestigationService


router = APIRouter()


@router.post(
    "/{case_id}/troubleshooting/start",
    response_model=TroubleshootingSession,
    status_code=status.HTTP_201_CREATED,
    summary="Start guided troubleshooting",
)
def start_troubleshooting(
    case_id: str,
    request: StartTroubleshootingRequest,
    service: InvestigationService = Depends(get_investigation_service),
) -> TroubleshootingSession:
    """Start a guided troubleshooting session."""

    try:
        return service.start_troubleshooting(
            case_id=case_id,
            recommendation_index=request.recommendation_index,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.post(
    "/{case_id}/troubleshooting/answer",
    response_model=TroubleshootingSession,
    summary="Answer a troubleshooting step",
)
def answer_troubleshooting_step(
    case_id: str,
    request: AnswerTroubleshootingStepRequest,
    service: InvestigationService = Depends(get_investigation_service),
) -> TroubleshootingSession:
    """Record the user's answer to the current troubleshooting step."""

    try:
        return service.answer_troubleshooting_step(
            case_id=case_id,
            result=request.result,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/{case_id}/troubleshooting",
    response_model=TroubleshootingSession,
    summary="Get troubleshooting session",
)
def get_troubleshooting(
    case_id: str,
    service: InvestigationService = Depends(get_investigation_service),
) -> TroubleshootingSession:
    """Get the current troubleshooting session."""

    investigation = service.get_investigation(case_id)

    if investigation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investigation found with case_id '{case_id}'.",
        )

    if investigation.troubleshooting_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No troubleshooting session has been started.",
        )

    return investigation.troubleshooting_session