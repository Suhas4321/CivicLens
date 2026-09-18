import pytest

from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.modules.analysis.service import ReportAnalysisService
from civiclens.modules.demo_sessions.service import DemoSessionService
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.schemas import ReportCreateRequest
from civiclens.modules.intake.service import IntakeService
from civiclens.modules.workflow_reviews.schemas import WorkflowReviewCreate
from civiclens.modules.workflow_reviews.service import WorkflowReviewService
from civiclens.shared.errors import ConflictError


def _fresh_report(repository: MemoryIntakeRepository, description: str):
    accepted = IntakeService(repository).submit(
        ReportCreateRequest(
            description=description,
            language_hint="en",
            locality_label="Synthetic review locality",
            consent=True,
            synthetic_demo_confirmation=True,
        ),
        idempotency_key="workflow-review-report-0001",
        receipt_capability="workflow-review-capability-0001-secret",
    )
    ReportAnalysisService(repository, FixtureInterpreter()).process(accepted.public_id)
    return repository.get_by_public_id(accepted.public_id)


def test_relationship_review_is_append_only_stale_safe_and_session_isolated() -> None:
    repository = MemoryIntakeRepository()
    report = _fresh_report(
        repository,
        "Synthetic water pressure has been low in this lane for three mornings.",
    )
    sessions = DemoSessionService(ttl_minutes=120)
    first = sessions.create().session
    second = sessions.create().session
    service = WorkflowReviewService(repository)
    request = WorkflowReviewCreate(
        action="keep_separate",
        reason="Only one report exists and recurrence evidence is unavailable.",
        expected_version=1,
    )

    created = service.append(
        session=first,
        report_id=report.id,
        request=request,
        idempotency_key="workflow-review-action-0001",
    )
    replayed = service.append(
        session=first,
        report_id=report.id,
        request=request,
        idempotency_key="workflow-review-action-0001",
    )

    assert replayed.id == created.id
    assert len(created.evidence_digest) == 64
    assert service.history(session=second, report_id=report.id) == []
    with pytest.raises(ConflictError):
        service.append(
            session=first,
            report_id=report.id,
            request=request,
            idempotency_key="workflow-review-action-stale",
        )


def test_safety_and_relationship_actions_cannot_cross_lanes() -> None:
    repository = MemoryIntakeRepository()
    report = _fresh_report(
        repository,
        "Synthetic hospital water smells chemical and may be contaminated.",
    )
    session = DemoSessionService(ttl_minutes=120).create().session
    service = WorkflowReviewService(repository)

    with pytest.raises(ConflictError):
        service.append(
            session=session,
            report_id=report.id,
            request=WorkflowReviewCreate(
                action="keep_separate",
                reason="This action belongs to the relationship-review lane only.",
                expected_version=1,
            ),
            idempotency_key="workflow-review-wrong-lane-0001",
        )
