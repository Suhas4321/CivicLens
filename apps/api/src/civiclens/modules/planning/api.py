from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from civiclens.modules.planning.read_service import (
    GoldenDemoReadService,
    get_golden_demo_read_service,
)
from civiclens.modules.planning.schemas import (
    IncidentDetail,
    NeedSummary,
    NeedWorkspace,
    OfficerOverview,
)
from civiclens.shared.errors import NotFoundError

router = APIRouter(prefix="/officer", tags=["officer-demo"])
ReadService = Annotated[GoldenDemoReadService, Depends(get_golden_demo_read_service)]


@router.get("/overview", response_model=OfficerOverview)
async def overview(service: ReadService) -> OfficerOverview:
    return service.overview()


@router.get("/needs", response_model=list[NeedSummary])
async def needs(service: ReadService) -> list[NeedSummary]:
    return service.list_needs()


@router.get("/needs/{need_id}", response_model=NeedWorkspace)
async def need_workspace(need_id: UUID, service: ReadService) -> NeedWorkspace:
    try:
        return service.need_workspace(need_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.code) from exc


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
async def incident_detail(incident_id: UUID, service: ReadService) -> IncidentDetail:
    try:
        return service.incident_detail(incident_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.code) from exc
