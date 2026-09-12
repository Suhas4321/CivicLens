from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import select

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.db.models import DemoSessionModel, HumanDecisionModel
from civiclens.infrastructure.db.session import build_engine, build_session_factory
from civiclens.modules.decisions.schemas import DecisionCreateRequest, Disposition, HumanDecision
from civiclens.modules.demo_sessions.service import DemoSession, get_demo_session_service
from civiclens.modules.planning.read_service import get_golden_demo_read_service
from civiclens.shared.errors import ConflictError, NotFoundError


@dataclass(frozen=True)
class StoredDecision:
    response: HumanDecision
    request_fingerprint: str
    idempotency_key: str


class HumanDecisionPort(Protocol):
    def append(
        self,
        *,
        session: DemoSession,
        need_id: UUID,
        request: DecisionCreateRequest,
        idempotency_key: str,
    ) -> HumanDecision: ...

    def history(self, *, session: DemoSession, need_id: UUID) -> list[HumanDecision]: ...


class HumanDecisionService:
    def __init__(self) -> None:
        self._by_session_need: dict[tuple[UUID, UUID], list[StoredDecision]] = {}
        self._by_idempotency: dict[tuple[UUID, str], StoredDecision] = {}
        self._lock = Lock()

    def append(
        self,
        *,
        session: DemoSession,
        need_id: UUID,
        request: DecisionCreateRequest,
        idempotency_key: str,
    ) -> HumanDecision:
        workspace = get_golden_demo_read_service().need_workspace(need_id)
        fingerprint = _fingerprint(request)
        candidate_id = workspace.candidate.id
        evidence_digest = _digest(workspace.model_dump(mode="json"))
        key = (session.id, need_id)

        with self._lock:
            existing = self._by_idempotency.get((session.id, idempotency_key))
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ConflictError("Idempotency key was already used")
                return existing.response

            history = self._by_session_need.setdefault(key, [])
            current_version = history[-1].response.entity_version_after if history else 1
            if request.expected_entity_version != current_version:
                raise ConflictError("Decision is stale; review the current evidence and retry")

            response = HumanDecision(
                id=uuid4(),
                session_id=session.id,
                need_id=need_id,
                candidate_id=candidate_id,
                disposition=request.disposition,
                reason_code=request.reason_code,
                reason_text=request.reason_text,
                next_step=request.next_step,
                next_review_date=request.next_review_date,
                evidence_digest=evidence_digest,
                expected_entity_version=current_version,
                entity_version_after=current_version + 1,
                supersedes_id=history[-1].response.id if history else None,
                created_at=datetime.now(UTC),
            )
            stored = StoredDecision(
                response=response,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            history.append(stored)
            self._by_idempotency[(session.id, idempotency_key)] = stored
            return response

    def history(self, *, session: DemoSession, need_id: UUID) -> list[HumanDecision]:
        with self._lock:
            return [item.response for item in self._by_session_need.get((session.id, need_id), [])]


class SqlHumanDecisionService:
    def __init__(self) -> None:
        self._session_factory = build_session_factory(build_engine(get_settings()))

    def append(
        self,
        *,
        session: DemoSession,
        need_id: UUID,
        request: DecisionCreateRequest,
        idempotency_key: str,
    ) -> HumanDecision:
        workspace = get_golden_demo_read_service().need_workspace(need_id)
        evidence_digest = _digest(workspace.model_dump(mode="json"))
        with self._session_factory.begin() as database:
            locked_session = database.scalar(
                select(DemoSessionModel).where(DemoSessionModel.id == session.id).with_for_update()
            )
            if locked_session is None or locked_session.status != "active":
                raise NotFoundError("Demo session not found")

            existing = database.scalar(
                select(HumanDecisionModel).where(
                    HumanDecisionModel.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.demo_session_id != session.id or not _same_request(existing, request):
                    raise ConflictError("Idempotency key was already used")
                return _response_from_model(existing)

            previous = database.scalar(
                select(HumanDecisionModel)
                .where(
                    HumanDecisionModel.demo_session_id == session.id,
                    HumanDecisionModel.need_id == need_id,
                )
                .order_by(HumanDecisionModel.created_at.desc(), HumanDecisionModel.id.desc())
                .limit(1)
            )
            current_version = previous.expected_entity_version + 1 if previous else 1
            if request.expected_entity_version != current_version:
                raise ConflictError("Decision is stale; review the current evidence and retry")

            model = HumanDecisionModel(
                id=uuid4(),
                demo_session_id=session.id,
                need_id=need_id,
                candidate_id=workspace.candidate.id,
                disposition=request.disposition,
                actor_subject_hash=session.subject_hash,
                actor_role="demo_officer",
                reason_code=request.reason_code,
                reason_text=request.reason_text,
                next_step=request.next_step,
                next_review_date=request.next_review_date,
                evidence_digest=evidence_digest,
                expected_entity_version=current_version,
                supersedes_id=previous.id if previous else None,
                idempotency_key=idempotency_key,
                created_at=datetime.now(UTC),
            )
            database.add(model)
            database.flush()
            return _response_from_model(model)

    def history(self, *, session: DemoSession, need_id: UUID) -> list[HumanDecision]:
        with self._session_factory() as database:
            models = database.scalars(
                select(HumanDecisionModel)
                .where(
                    HumanDecisionModel.demo_session_id == session.id,
                    HumanDecisionModel.need_id == need_id,
                )
                .order_by(HumanDecisionModel.created_at, HumanDecisionModel.id)
            )
            return [_response_from_model(model) for model in models]


def _fingerprint(request: DecisionCreateRequest) -> str:
    return _digest(request.model_dump(mode="json"))


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _same_request(model: HumanDecisionModel, request: DecisionCreateRequest) -> bool:
    return (
        model.disposition == request.disposition
        and model.reason_code == request.reason_code
        and model.reason_text == request.reason_text
        and model.next_step == request.next_step
        and model.next_review_date == request.next_review_date
        and model.expected_entity_version == request.expected_entity_version
    )


def _response_from_model(model: HumanDecisionModel) -> HumanDecision:
    return HumanDecision(
        id=model.id,
        session_id=model.demo_session_id,
        need_id=model.need_id,
        candidate_id=model.candidate_id,
        disposition=cast(Disposition, model.disposition),
        reason_code=model.reason_code,
        reason_text=model.reason_text,
        next_step=model.next_step,
        next_review_date=model.next_review_date,
        evidence_digest=model.evidence_digest,
        expected_entity_version=model.expected_entity_version,
        entity_version_after=model.expected_entity_version + 1,
        supersedes_id=model.supersedes_id,
        created_at=model.created_at,
    )


@lru_cache
def get_human_decision_service() -> HumanDecisionPort:
    if get_settings().decision_backend == "postgres":
        return SqlHumanDecisionService()
    return HumanDecisionService()


def authenticate_demo_session(session_id: UUID, authorization: str) -> DemoSession:
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise NotFoundError("Demo session not found")
    return get_demo_session_service().authenticate(session_id, authorization[len(prefix) :])
