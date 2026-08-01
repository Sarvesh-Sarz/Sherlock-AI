"""POST /investigation/start and GET /investigation/{case_id}."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_investigation_service
from app.schemas.investigation import (
    InvestigationRequest,
    InvestigationResponse,
    InvestigationStatus,
)
from app.services.investigation_service import InvestigationService

router = APIRouter()


@router.post(
    "/start",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new investigation",
)
def start_investigation(
    request: InvestigationRequest,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationResponse:
    investigation = service.start_investigation(request)
    return InvestigationResponse.from_domain(investigation)


@router.get(
    "/{case_id}",
    response_model=InvestigationStatus,
    summary="Get the current status of an investigation",
)
def get_investigation(
    case_id: str,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationStatus:
    investigation = service.get_investigation(case_id)
    if investigation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investigation found with case_id '{case_id}'.",
        )
    return InvestigationStatus.from_domain(investigation)
