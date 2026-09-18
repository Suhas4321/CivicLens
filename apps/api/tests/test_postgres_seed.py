from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.infrastructure.db.base import Base
from civiclens.infrastructure.db.models import (
    DatasetSnapshotModel,
    DemoSessionModel,
    HumanDecisionModel,
    IncidentModel,
    IncidentRelationshipModel,
    IncidentReportLinkModel,
    NeedIncidentLinkModel,
    PriorityAssessmentModel,
    ProcessingJobModel,
    ProjectCandidateModel,
    PublicEvidenceModel,
    ReportInterpretationModel,
    ReportModel,
    SafetyReviewModel,
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

# Every table the demo seed writes, and the number of rows it must leave in each.
# Counted from the frozen assets in `data/demo/v1`, and deliberately not read back out
# of `SeedResult`: the result object reports what the seed believes it wrote, and the
# failure this list exists to catch is a seed that believes it wrote a table it did not.
_EXPECTED_SEED_ROWS: tuple[tuple[type[Base], int], ...] = (
    (DatasetSnapshotModel, 1),
    (PublicEvidenceModel, 9),
    (ReportModel, 60),
    (ReportInterpretationModel, 60),
    (SafetyReviewModel, 1),
    (ProcessingJobModel, 60),
    (IncidentModel, 8),
    (IncidentReportLinkModel, 56),
    (IncidentRelationshipModel, 3),
    (SuspectedNeedModel, 2),
    (NeedIncidentLinkModel, 5),
    (PriorityAssessmentModel, 2),
    (ProjectCandidateModel, 2),
)

_PROBE_SCHEMA = "civiclens_seed_probe"


def test_seeding_an_empty_database_writes_every_table_in_foreign_key_order() -> None:
    """The insert path, which nothing else in the suite reaches.

    Every other test here runs against a database CI has already seeded, so
    ``seed_database`` returns from its ``existing_snapshot`` branch and the hundreds of
    INSERTs below it are never executed. A foreign key violation in that branch was
    therefore invisible to the whole suite and only appeared in the ``seed
    --confirm-demo`` step of the pipeline -- which is a bug report arriving by the
    slowest route available. One did: SQLAlchemy orders a flush by the dependencies it
    learns from ``relationship()`` declarations, these models declare none, and so
    ``incident_report_link`` rows were offered to PostgreSQL before the ``report`` rows
    they point at.

    The seed is run into a throwaway schema inside a transaction that is always rolled
    back. PostgreSQL makes DDL transactional, so the schema, its tables and every row
    written into them disappear together and the shared integration database is left
    exactly as it was found -- meaning this test costs nothing to run on every CI run
    and after every seed change, which is the only way it will catch the next one.
    """

    engine = build_engine(get_settings())
    factory = build_session_factory(engine)

    with engine.connect() as connection:
        outer = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{_PROBE_SCHEMA}"'))
            # The probe schema alone, with `public` deliberately left out. Tables are
            # created into the first schema on the path, so this is what sends them
            # somewhere harmless -- and excluding `public` means a table `create_all`
            # failed to make cannot be silently answered by the real seeded one, which
            # would turn a missing table into a passing assertion.
            connection.execute(text(f'SET LOCAL search_path TO "{_PROBE_SCHEMA}"'))
            Base.metadata.create_all(connection, checkfirst=False)

            # The application's own session factory, rebound to this connection. A
            # plain `Session` would be the wrong subject: the insert ordering this test
            # is here to protect lives in the session class the factory installs, so a
            # test that built its own session would pass while production broke.
            # `create_savepoint` nests the session's transaction boundaries inside the
            # one this test controls instead of ending it.
            with factory(bind=connection, join_transaction_mode="create_savepoint") as session:
                result = seed_database(session)

                assert result.inserted is True
                assert (result.reports, result.incidents, result.needs) == (60, 8, 2)
                assert result.public_evidence == 9
                for model, expected in _EXPECTED_SEED_ROWS:
                    written = session.scalar(select(func.count()).select_from(model))
                    assert written == expected, f"{model.__name__}: wrote {written}, not {expected}"
        finally:
            outer.rollback()


def test_seed_is_complete_idempotent_and_decisions_are_append_only() -> None:
    # Everything this test commits is keyed on one per-run token. The idempotency keys
    # and row ids below used to be fixed strings, which meant the test passed once
    # against a given database and then failed on a duplicate key -- fine in CI, where
    # the PostgreSQL container is new every run, and the reason nobody could re-run the
    # only tests that touch a foreign-key-enforcing database. Each run now leaves its
    # own rows behind, which is what an append-only audit schema is for.
    run = uuid4().hex
    settings = get_settings()
    engine = build_engine(settings)
    factory = build_session_factory(engine)

    with factory.begin() as session:
        result = seed_database(session)
        assert result.inserted is False
        # Seeded reports only. The unfiltered count was 60 the first time this ran
        # against a database and 61 every time after, because the intake exercise
        # further down this test leaves a report behind. CI never saw it -- its
        # PostgreSQL container is new each run -- so the suite silently stopped being
        # runnable twice on a developer's machine, which is most of why the seed's own
        # foreign key bug survived as long as it did.
        assert (
            session.scalar(
                select(func.count()).select_from(ReportModel).where(ReportModel.is_seed.is_(True))
            )
            == 60
        )
        assert session.scalar(select(func.count()).select_from(IncidentModel)) == 8
        assert session.scalar(select(func.count()).select_from(SuspectedNeedModel)) == 2
        assert session.scalar(select(func.count()).select_from(PriorityAssessmentModel)) == 2
        assert session.scalar(select(func.count()).select_from(ProjectCandidateModel)) == 2
        assert session.scalar(select(func.count()).select_from(PublicEvidenceModel)) == 9
        assert session.scalar(select(func.count()).select_from(DatasetSnapshotModel)) == 1

    intake_repository = SqlAlchemyIntakeRepository(factory)
    intake = IntakeService(intake_repository)
    # Per-run as well: this is hashed into `report.receipt_hash`, which is unique, so a
    # fixed capability is a second reason the test could only ever run once.
    capability = f"postgres-receipt-capability-{run}"
    accepted = intake.submit(
        ReportCreateRequest(
            description="Synthetic PostgreSQL report about low water pressure for three days.",
            language_hint="en",
            locality_label="PostgreSQL demo locality",
            consent=True,
            synthetic_demo_confirmation=True,
        ),
        idempotency_key=f"postgres-intake-{run}",
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
        idempotency_key=f"postgres-decision-{run}",
    )
    assert len(durable_decisions.history(session=authenticated, need_id=need_id)) == 1

    session_id = stable_id("test-demo-session", f"append-only:{run}")
    decision_id = stable_id("test-human-decision", f"append-only:{run}")
    # 64 hex characters, the width of the column, and unique per run:
    # `demo_session.external_subject_hash` carries a uniqueness constraint.
    subject_hash = run * 2
    with factory.begin() as session:
        need_id = session.scalar(select(SuspectedNeedModel.id).limit(1))
        candidate_id = session.scalar(select(ProjectCandidateModel.id).limit(1))
        assert need_id is not None
        session.add(
            DemoSessionModel(
                id=session_id,
                external_subject_hash=subject_hash,
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
                actor_subject_hash=subject_hash,
                actor_role="demo_officer",
                reason_code="MORE_EVIDENCE_REQUIRED",
                evidence_digest="b" * 64,
                expected_entity_version=1,
                idempotency_key=f"integration-append-only-{run}",
            )
        )

    with pytest.raises(DatabaseError), factory.begin() as session:
        decision = session.get(HumanDecisionModel, decision_id)
        assert decision is not None
        decision.reason_code = "ILLEGAL_UPDATE"
        session.flush()

    engine.dispose()
