from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

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
