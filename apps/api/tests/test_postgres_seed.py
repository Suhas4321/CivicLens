from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DatabaseError

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.infrastructure.db.models import (
    DatasetSnapshotModel,
    DemoSessionModel,
    HumanDecisionModel,
    IncidentModel,
    PriorityAssessmentModel,
    ProjectCandidateModel,
    PublicEvidenceModel,
    ReportModel,
    SuspectedNeedModel,
)
from civiclens.infrastructure.db.seed import seed_database
from civiclens.infrastructure.db.session import build_engine, build_session_factory
from civiclens.modules.analysis.service import ReportAnalysisService
from civiclens.modules.decisions.schemas import DecisionCreateRequest
from civiclens.modules.decisions.service import SqlHumanDecisionService
from civiclens.modules.demo_sessions.service import SqlDemoSessionService
from civiclens.modules.intake.repository import SqlAlchemyIntakeRepository
from civiclens.modules.intake.schemas import ReportCreateRequest
from civiclens.modules.intake.service import IntakeService
from civiclens.modules.planning.read_service import get_golden_demo_read_service
from civiclens.shared.primitives import stable_id

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="requires the dedicated PostgreSQL integration database",
)


def test_seed_is_complete_idempotent_and_decisions_are_append_only() -> None:
    settings = get_settings()
    engine = build_engine(settings)
    factory = build_session_factory(engine)

    with factory.begin() as session:
        result = seed_database(session)
        assert result.inserted is False
        assert session.scalar(select(func.count()).select_from(ReportModel)) == 60
        assert session.scalar(select(func.count()).select_from(IncidentModel)) == 8
        assert session.scalar(select(func.count()).select_from(SuspectedNeedModel)) == 2
        assert session.scalar(select(func.count()).select_from(PriorityAssessmentModel)) == 2
        assert session.scalar(select(func.count()).select_from(ProjectCandidateModel)) == 2
        assert session.scalar(select(func.count()).select_from(PublicEvidenceModel)) == 9
        assert session.scalar(select(func.count()).select_from(DatasetSnapshotModel)) == 1

    intake_repository = SqlAlchemyIntakeRepository(factory)
    intake = IntakeService(intake_repository)
    capability = "postgres-receipt-capability-0123456789abcdef"
    accepted = intake.submit(
        ReportCreateRequest(
            description="Synthetic PostgreSQL report about low water pressure for three days.",
            language_hint="en",
            locality_label="PostgreSQL demo locality",
            consent=True,
            synthetic_demo_confirmation=True,
        ),
        idempotency_key="postgres-intake-idempotency-0001",
        receipt_capability=capability,
    )
    ReportAnalysisService(intake_repository, FixtureInterpreter()).process(accepted.public_id)
    assert intake.receipt(accepted.public_id, receipt_capability=capability).status == "processed"

    created_session = SqlDemoSessionService(ttl_minutes=120).create()
    authenticated = SqlDemoSessionService(ttl_minutes=120).authenticate(
        created_session.session.id, created_session.access_token
    )
    need_id = get_golden_demo_read_service().overview().planning_needs[0].id
    durable_decisions = SqlHumanDecisionService()
    durable_decisions.append(
        session=authenticated,
        need_id=need_id,
        request=DecisionCreateRequest(
            disposition="refer",
            reason_code="FIELD_VERIFICATION",
            next_step="Verify the synthetic service evidence.",
            expected_entity_version=1,
        ),
        idempotency_key="postgres-decision-idempotency-0001",
    )
    assert len(durable_decisions.history(session=authenticated, need_id=need_id)) == 1

    session_id = stable_id("test-demo-session", "append-only")
    decision_id = stable_id("test-human-decision", "append-only")
    with factory.begin() as session:
        need_id = session.scalar(select(SuspectedNeedModel.id).limit(1))
        candidate_id = session.scalar(select(ProjectCandidateModel.id).limit(1))
        assert need_id is not None
        session.add(
            DemoSessionModel(
                id=session_id,
                external_subject_hash="a" * 64,
                status="active",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        session.add(
            HumanDecisionModel(
                id=decision_id,
                demo_session_id=session_id,
                need_id=need_id,
                candidate_id=candidate_id,
                disposition="defer",
                actor_subject_hash="a" * 64,
                actor_role="demo_officer",
                reason_code="MORE_EVIDENCE_REQUIRED",
                evidence_digest="b" * 64,
                expected_entity_version=1,
                idempotency_key="integration-append-only",
            )
        )

    with pytest.raises(DatabaseError), factory.begin() as session:
        decision = session.get(HumanDecisionModel, decision_id)
        assert decision is not None
        decision.reason_code = "ILLEGAL_UPDATE"
        session.flush()

    engine.dispose()
