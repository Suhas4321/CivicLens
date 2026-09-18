from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from civiclens.modules.decisions.service import authenticate_demo_session
from civiclens.modules.workflow_reviews.schemas import WorkflowReview, WorkflowReviewCreate
from civiclens.modules.workflow_reviews.service import (
    WorkflowReviewPort,
    get_workflow_review_service,
)
from civiclens.shared.errors import ConflictError, NotFoundError

router = APIRouter(prefix="/officer/reports", tags=["workflow-reviews"])
Service = Annotated[WorkflowReviewPort, Depends(get_workflow_review_service)]
SessionId = Annotated[UUID, Header(alias="X-Demo-Session-ID")]
Authorization = Annotated[str, Header(alias="Authorization", min_length=39, max_length=256)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)]


@router.post(
    "/{report_id}/reviews",
    response_model=WorkflowReview,
    status_code=status.HTTP_201_CREATED,
)
async def record_workflow_review(
    report_id: UUID,
    request: WorkflowReviewCreate,
    service: Service,
    session_id: SessionId,
    authorization: Authorization,
    idempotency_key: IdempotencyKey,
) -> WorkflowReview:
    try:
        session = authenticate_demo_session(session_id, authorization)
        return service.append(
            session=session,
            report_id=report_id,
            request=request,
            idempotency_key=idempotency_key,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/{report_id}/reviews", response_model=list[WorkflowReview])
async def workflow_review_history(
    report_id: UUID,
    service: Service,
    session_id: SessionId,
    authorization: Authorization,
) -> list[WorkflowReview]:
    try:
        session = authenticate_demo_session(session_id, authorization)
        return service.history(session=session, report_id=report_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
