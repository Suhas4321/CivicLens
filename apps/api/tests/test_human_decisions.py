from datetime import date

import pytest

from civiclens.modules.decisions.schemas import DecisionCreateRequest
from civiclens.modules.decisions.service import HumanDecisionService
from civiclens.modules.demo_sessions.service import DemoSessionService
from civiclens.modules.planning.read_service import get_golden_demo_read_service
from civiclens.shared.errors import ConflictError, NotFoundError


def test_decisions_are_append_only_idempotent_stale_safe_and_session_isolated() -> None:
    sessions = DemoSessionService(ttl_minutes=120)
    first_session = sessions.create()
    second_session = sessions.create()
    service = HumanDecisionService()
    need_id = get_golden_demo_read_service().overview().planning_needs[0].id
    request = DecisionCreateRequest(
        disposition="refer",
        reason_code="FIELD_VERIFICATION",
        next_step="Ask the service team to verify pressure, continuity and active works scope.",
        expected_entity_version=1,
    )

    first = service.append(
        session=first_session.session,
        need_id=need_id,
        request=request,
        idempotency_key="decision-idempotency-0001",
    )
    retried = service.append(
        session=first_session.session,
        need_id=need_id,
        request=request,
        idempotency_key="decision-idempotency-0001",
    )

    assert retried.id == first.id
    assert len(first.evidence_digest) == 64
    assert service.history(session=second_session.session, need_id=need_id) == []

    with pytest.raises(ConflictError):
        service.append(
            session=first_session.session,
            need_id=need_id,
            request=request,
            idempotency_key="decision-idempotency-stale",
        )

    superseding = service.append(
        session=first_session.session,
        need_id=need_id,
        request=DecisionCreateRequest(
            disposition="defer",
            reason_code="EVIDENCE_GAP",
            next_review_date=date(2026, 10, 1),
            expected_entity_version=2,
        ),
        idempotency_key="decision-idempotency-0002",
    )
    assert superseding.supersedes_id == first.id
    assert len(service.history(session=first_session.session, need_id=need_id)) == 2

    with pytest.raises(NotFoundError):
        sessions.authenticate(first_session.session.id, "wrong-token")
