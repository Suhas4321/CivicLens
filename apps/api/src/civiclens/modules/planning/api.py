from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.media.photo_storage import get_photo_storage
from civiclens.modules.intake.repository import IntakeRecord, IntakeRepository
from civiclens.modules.intake.service import get_intake_repository
from civiclens.modules.planning.read_service import (
    GoldenDemoReadService,
    get_golden_demo_read_service,
)
from civiclens.modules.planning.schemas import (
    IncidentDetail,
    IncidentSummary,
    LaneItem,
    NeedSummary,
    NeedWorkspace,
    OfficerOverview,
    ReportEvidence,
)
from civiclens.shared.errors import NotFoundError

router = APIRouter(prefix="/officer", tags=["officer-demo"])
ReadService = Annotated[GoldenDemoReadService, Depends(get_golden_demo_read_service)]
FreshRepository = Annotated[IntakeRepository, Depends(get_intake_repository)]


@router.get("/overview", response_model=OfficerOverview)
async def overview(service: ReadService, repository: FreshRepository) -> OfficerOverview:
    seeded = service.overview()
    safety = list(seeded.safety_review)
    operational = list(seeded.operational_incidents)
    for report in repository.list_fresh():
        item = _fresh_lane_item(report)
        if report.safety_signal_codes:
            safety.insert(0, item)
        else:
            operational.insert(0, item)
    return seeded.model_copy(update={"safety_review": safety, "operational_incidents": operational})


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
async def incident_detail(
    incident_id: UUID,
    service: ReadService,
    repository: FreshRepository,
) -> IncidentDetail:
    try:
        return service.incident_detail(incident_id)
    except NotFoundError:
        try:
            return _fresh_incident_detail(repository.get_by_id(incident_id))
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.code) from exc


@router.get(
    "/reports/{report_id}/photo",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}}, "description": "The stored photo"},
        403: {"description": "This deployment does not serve citizen photos"},
        404: {"description": "No such fresh report, or no photo on it"},
    },
)
async def report_photo(report_id: UUID, repository: FreshRepository) -> Response:
    """Serve the sanitised photo attached to a fresh report.

    The photo exists for one reason: so an officer can judge severity without
    driving to the street. Nothing here interprets the image -- no vision model, no
    scoring. It is handed over for a person to look at.

    **Gated on demo mode, because nothing on ``/officer`` is authenticated yet.**
    Every other officer route returns synthetic seed data, so an open door costs
    nothing; this one returns photographs that real people took and uploaded. Until
    there is a login, a deployment with ``DEMO_MODE_ENABLED=false`` -- which is the
    only way this service is meant to hold anything other than synthetic data --
    serves no photos at all. That makes the unsafe configuration impossible rather
    than merely discouraged in a document, and it fails closed: someone wiring up
    real intake has to add authentication before photos work, instead of
    discovering later that they had been public the whole time.
    """
    if not get_settings().demo_mode_enabled:
        # Refused before the lookup, so that a disabled deployment cannot be used to
        # test whether a given report id exists. 403 rather than 404 because the
        # request was understood and no credential the caller could supply would
        # change the answer -- there is no credential to supply.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="PHOTO_ACCESS_NOT_CONFIGURED"
        )

    try:
        report = repository.get_by_id(report_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.code) from exc

    if report.photo_object_key is None or report.photo_content_type is None:
        # Both checked, though the writer sets them together. Reading one and
        # trusting the other would turn a half-written row into a 500 here, and the
        # content type is what stops these bytes being sniffed as something else.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHOTO_NOT_ATTACHED")

    try:
        data = get_photo_storage().get(report.photo_object_key)
    except NotFoundError as exc:
        # The row can outlive the object: retention deletes photos on schedule, and
        # the memory backend loses them on restart. Neither is a fault.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHOTO_EXPIRED") from exc

    return Response(
        content=data,
        media_type=report.photo_content_type,
        headers={
            # Citizen evidence, so it is not left behind in the disk cache of a
            # shared machine in a ward office, or in any proxy between here and it.
            "Cache-Control": "no-store",
            # These bytes came from the public. They are re-encoded from decoded
            # pixels and can only be JPEG or PNG, but a browser that sniffs its own
            # answer could still decide otherwise, and pixel data can be made to
            # contain anything.
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


def _fresh_lane_item(report: IntakeRecord) -> LaneItem:
    category = report.interpretation_category or "unknown"
    safety = bool(report.safety_signal_codes)
    return LaneItem(
        id=report.id,
        title=(
            f"Fresh safety signal: {category.replace('_', ' ')}"
            if safety
            else f"Fresh report awaiting relationship review: {category.replace('_', ' ')}"
        ),
        status=(
            "pending_human_verification"
            if safety
            else "relationship_review"
            if report.analysis_result_class is not None
            else "analysis_pending"
        ),
        category=category,
        locality=report.locality_label,
        report_count=1,
        classification="ai_derived",
        explanation=(
            "A deterministic safety rule routed this single report for human verification."
            if safety
            else "One fresh report cannot establish a recurring need; an officer must review it."
        ),
        has_photo=report.photo_object_key is not None,
        service_code=report.service_code,
    )


def _fresh_incident_detail(report: IntakeRecord) -> IncidentDetail:
    category = report.interpretation_category or "unknown"
    safety = bool(report.safety_signal_codes)
    return IncidentDetail(
        data_version="fresh-analysis-v1",
        incident=IncidentSummary(
            id=report.id,
            key=f"fresh-{report.public_id}",
            title=(
                f"Fresh safety signal: {category.replace('_', ' ')}"
                if safety
                else f"Fresh report: {category.replace('_', ' ')}"
            ),
            category=category,
            locality=report.locality_label,
            event_start=report.accepted_at,
            report_count=1,
            relationship_state=(
                "pending_safety_verification" if safety else "pending_relationship_review"
            ),
            classification="synthetic_demo",
        ),
        reports=[
            ReportEvidence(
                id=report.id,
                public_id=report.public_id,
                original_text=report.original_text,
                language=report.language_hint,
                accepted_at=report.accepted_at,
                locality=report.locality_label,
                interpretation_summary=(
                    report.interpretation_summary
                    or "Structured interpretation is pending or requires manual review."
                ),
                classification="synthetic_demo",
                interpretation_classification="ai_derived",
                service_code=report.service_code,
                has_photo=report.photo_object_key is not None,
                # Already reduced to codes on the record. The raw EXIF never reached
                # it, so there is nothing here to accidentally forward.
                photo_integrity_flags=list(report.photo_integrity_codes),
            )
        ],
        relationship_explanation={
            "state": "human_review_required",
            "category": category,
            "report_count": 1,
            "safety_routed": safety,
            "rule": (
                "Safety routing is count-independent."
                if safety
                else "A single report remains separate until compatible evidence is reviewed."
            ),
        },
        decision_boundary=(
            "Verify or dismiss the safety signal. It is never assigned a planning priority."
            if safety
            else (
                "Confirm a relationship only with compatible category, time and location evidence. "
                "This report alone cannot create a Suspected Civic Need."
            )
        ),
    )
