from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from civiclens.bootstrap.policy import load_policy_bundle
from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.media.photo_storage import get_photo_storage
from civiclens.modules.intake.repository import IntakeRecord, IntakeRepository
from civiclens.modules.intake.service import get_intake_repository
from civiclens.modules.planning.read_service import (
    GoldenDemoReadService,
    get_golden_demo_read_service,
)
from civiclens.modules.planning.schemas import (
    GroupingJoin,
    IncidentDetail,
    IncidentSummary,
    LaneItem,
    NeedSummary,
    NeedWorkspace,
    OfficerOverview,
    ReportEvidence,
)
from civiclens.modules.relationships.evaluator import ReportFeatures
from civiclens.modules.relationships.grouping import (
    GroupingCandidate,
    GroupMember,
    ReportGroup,
    group_reports,
)
from civiclens.shared.errors import NotFoundError

router = APIRouter(prefix="/officer", tags=["officer-demo"])
ReadService = Annotated[GoldenDemoReadService, Depends(get_golden_demo_read_service)]
FreshRepository = Annotated[IntakeRepository, Depends(get_intake_repository)]


@router.get("/overview", response_model=OfficerOverview)
async def overview(service: ReadService, repository: FreshRepository) -> OfficerOverview:
    seeded = service.overview()
    records = {report.id: report for report in repository.list_fresh()}
    safety: list[LaneItem] = []
    operational: list[LaneItem] = []
    # Grouped, not listed. Forty reports of one flooded junction is one item and one
    # crew; as forty items it is a backlog nobody can work through, and the officer
    # ends up doing the deduplication by eye every morning.
    for group in _fresh_groups(records):
        lane = safety if group.safety_signalled else operational
        lane.append(_fresh_lane_item(group, records))
    # Fresh work ahead of the seeded demo data, newest group first, because a report
    # that arrived overnight is the thing the officer has not seen yet.
    return seeded.model_copy(
        update={
            "safety_review": safety + list(seeded.safety_review),
            "operational_incidents": operational + list(seeded.operational_incidents),
        }
    )


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
            return _fresh_incident_detail(repository, incident_id)
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


def _fresh_groups(records: Mapping[UUID, IntakeRecord]) -> list[ReportGroup]:
    """Run the grouping policy over every fresh report, newest group first.

    Derived on read rather than stored at submission time. The proposal then always
    reflects the policy in force now instead of whichever version happened to run the
    night a report arrived, it needs no migration and no write path, and there is
    nothing to repair when a rule changes. The cost is one pass over the fresh
    reports per request, which is the right trade at ward volume and the wrong one at
    city volume -- at that point these become rows in ``incident_report_links``,
    which is why that table already exists.
    """
    return group_reports([_grouping_candidate(record) for record in records.values()])


def _grouping_candidate(report: IntakeRecord) -> GroupingCandidate:
    # Coordinates are passed only as a pair. A record with one half -- which the
    # database permits -- would otherwise raise out of `ReportFeatures` and take the
    # whole officer board down with it, so the half is dropped and the report is
    # matched on its locality label instead.
    located = report.latitude is not None and report.longitude is not None
    return GroupingCandidate(
        features=ReportFeatures(
            report_id=report.id,
            # "unknown" until the interpreter has answered, and `evaluate_same_incident`
            # refuses to group on an unknown category. So a report groups with nothing
            # until it has been read, which is the safe order.
            category=report.interpretation_category or "unknown",
            event_at=report.accepted_at,
            locality_label=report.locality_label,
            latitude=report.latitude if located else None,
            longitude=report.longitude if located else None,
        ),
        safety_signalled=bool(report.safety_signal_codes),
        photo_hash=report.photo_perceptual_hash,
    )


def _group_containing(report_id: UUID, records: Mapping[UUID, IntakeRecord]) -> ReportGroup | None:
    """Find the group a report belongs to, whether or not it leads the group.

    An officer opens a report from a list that may show any member of a group, and
    what they need is the problem it is part of -- not a page about their click.
    """
    for group in _fresh_groups(records):
        if any(member.report_id == report_id for member in group.members):
            return group
    return None


def _fresh_lane_item(group: ReportGroup, records: Mapping[UUID, IntakeRecord]) -> LaneItem:
    lead = records[group.lead_report_id]
    members = [records[member.report_id] for member in group.members]
    subject = group.category.replace("_", " ")
    return LaneItem(
        id=group.lead_report_id,
        title=_fresh_title(group, subject),
        status=(
            "pending_human_verification"
            if group.safety_signalled
            else "relationship_review"
            if lead.analysis_result_class is not None
            else "analysis_pending"
        ),
        category=group.category,
        locality=lead.locality_label,
        report_count=group.report_count,
        classification="ai_derived",
        explanation=(
            "A deterministic safety rule routed this for human verification."
            if group.safety_signalled
            else group.explanation
        ),
        # Any member will do. The officer is deciding whether this item can be settled
        # from a desk, and one photograph of the flooded junction answers that for the
        # whole group.
        has_photo=any(record.photo_object_key is not None for record in members),
        service_code=_group_service_code(members),
        grouping_confidence=group.confidence_band,
    )


def _fresh_title(group: ReportGroup, subject: str) -> str:
    if group.safety_signalled:
        return (
            f"Fresh safety signals: {subject} ({group.report_count} reports)"
            if group.is_grouped
            else f"Fresh safety signal: {subject}"
        )
    if group.is_grouped:
        return f"Fresh reports proposed as one problem: {subject} ({group.report_count} reports)"
    return f"Fresh report awaiting relationship review: {subject}"


def _group_service_code(members: Sequence[IntakeRecord]) -> str | None:
    # The first reporter's choice, falling back to the first member who made one. The
    # item has to be routed to a department, and "the earliest person who named one"
    # is a rule an officer can follow when two reporters disagree -- whereas taking
    # only the lead's would drop the routing entirely whenever the first reporter
    # skipped the question.
    return next((record.service_code for record in members if record.service_code), None)


def _fresh_incident_detail(repository: IntakeRepository, report_id: UUID) -> IncidentDetail:
    # Looked up first, so an unknown id is a 404 from one query rather than after a
    # full grouping pass, and so the error code is the repository's own.
    clicked = repository.get_by_id(report_id)
    records = {report.id: report for report in repository.list_fresh()}
    group = _group_containing(report_id, records)
    if group is None:
        # `get_by_id` found it and `list_fresh` did not. Not reachable today -- both
        # read the same non-seed reports -- so rather than trust that to stay true,
        # the report is shown on its own instead of 404-ing something that exists.
        records = {clicked.id: clicked}
        group = group_reports([_grouping_candidate(clicked)])[0]

    lead = records[group.lead_report_id]
    members = [records[member.report_id] for member in group.members]
    joins = {member.report_id: member for member in group.members}
    safety = group.safety_signalled
    return IncidentDetail(
        data_version="fresh-analysis-v1",
        incident=IncidentSummary(
            # The group's lead, not the report that was clicked. Opening any member of
            # a group shows the same page, because there is one problem here and one
            # decision to make about it.
            id=group.lead_report_id,
            key=f"fresh-{lead.public_id}",
            title=_fresh_title(group, group.category.replace("_", " ")),
            category=group.category,
            locality=lead.locality_label,
            # The first report, so the statutory clock is not reset by a duplicate.
            event_start=group.first_reported_at,
            report_count=group.report_count,
            relationship_state=(
                "pending_safety_verification" if safety else "pending_relationship_review"
            ),
            classification="synthetic_demo",
        ),
        reports=[
            _report_evidence(record, joins[record.id] if group.is_grouped else None)
            for record in members
        ],
        relationship_explanation={
            "state": "human_review_required",
            "category": group.category,
            "report_count": group.report_count,
            "safety_routed": safety,
            "grouped": group.is_grouped,
            "confidence_band": group.confidence_band,
            # Which version of the rules produced this proposal. A grouping an officer
            # disputes six weeks from now was made by whatever was in force then.
            "rule_version": load_policy_bundle().grouping.version,
            "rule": _grouping_rule(group),
            "explanation": group.explanation,
        },
        decision_boundary=_grouping_decision_boundary(group),
    )


def _grouping_rule(group: ReportGroup) -> str:
    if group.safety_signalled:
        return "Safety routing is count-independent."
    if group.is_grouped:
        return (
            "Every report here was matched against the first report, never chained "
            "through a neighbour, so the group cannot be wider than the distance gate."
        )
    return "A single report remains separate until compatible evidence is reviewed."


def _grouping_decision_boundary(group: ReportGroup) -> str:
    if group.safety_signalled:
        return "Verify or dismiss the safety signal. It is never assigned a planning priority."
    if group.is_grouped:
        return (
            "Confirm this grouping or separate the reports that do not belong. The report "
            "count is what raises the priority, so merging two problems hides one of them "
            "and splitting one problem starves it."
        )
    return (
        "Confirm a relationship only with compatible category, time and location evidence. "
        "This report alone cannot create a Suspected Civic Need."
    )


def _report_evidence(report: IntakeRecord, member: GroupMember | None) -> ReportEvidence:
    return ReportEvidence(
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
        joined_by=_grouping_join(member) if member is not None else None,
    )


def _grouping_join(member: GroupMember) -> GroupingJoin:
    """Republish the gate's own evidence, narrowed to the fields the API declares.

    The evidence dict is deliberately open-ended so the evaluator can record whatever
    it used; this is the point where only the named, non-identifying parts of it cross
    into a response.
    """
    evidence = member.evidence
    distance = _number(evidence, "photo_hash_distance")
    return GroupingJoin(
        reason=member.joined_by,
        same_category=_flag(evidence, "category_match"),
        hours_apart=_number(evidence, "hours_apart"),
        distance_km=_number(evidence, "distance_km"),
        same_locality_label=_flag(evidence, "same_locality_label"),
        geometry_band=_text(evidence, "geometry_band"),
        intent_verdict=_text(evidence, "intent_verdict"),
        photo_hash_distance=int(distance) if distance is not None else None,
    )


def _number(evidence: Mapping[str, str | float | bool | None], key: str) -> float | None:
    value = evidence.get(key)
    # `bool` is an `int`, and `category_match: True` becoming `1.0` in a numeric field
    # is the kind of nonsense that only shows up on somebody's screen.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _flag(evidence: Mapping[str, str | float | bool | None], key: str) -> bool | None:
    value = evidence.get(key)
    return value if isinstance(value, bool) else None


def _text(evidence: Mapping[str, str | float | bool | None], key: str) -> str | None:
    value = evidence.get(key)
    return value if isinstance(value, str) else None
