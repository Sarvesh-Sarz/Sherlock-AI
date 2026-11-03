"""POST /investigation/start, GET /investigation, GET /investigation/{case_id}."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_investigation_service
from app.schemas.investigation import (
    InvestigationRequest,
    InvestigationResponse,
    InvestigationStatus,
    InvestigationSummary,
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
    "",
    response_model=list[InvestigationSummary],
    summary="List recent investigations, newest first",
)
def list_investigations(
    limit: int = Query(20, ge=1, le=100),
    service: InvestigationService = Depends(get_investigation_service),
) -> list[InvestigationSummary]:
    return [
        InvestigationSummary.from_domain(summary)
        for summary in service.list_recent_investigations(limit)
    ]


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
