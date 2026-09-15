from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from civiclens.modules.demo_sessions.service import DemoSession
from civiclens.modules.intake.repository import IntakeRepository
from civiclens.modules.intake.service import get_intake_repository
from civiclens.modules.workflow_reviews.schemas import WorkflowReview, WorkflowReviewCreate
from civiclens.shared.errors import ConflictError


@dataclass(frozen=True)
class StoredReview:
    response: WorkflowReview
    request_fingerprint: str


class WorkflowReviewPort(Protocol):
    def append(
        self,
        *,
        session: DemoSession,
        report_id: UUID,
        request: WorkflowReviewCreate,
        idempotency_key: str,
    ) -> WorkflowReview: ...

    def history(self, *, session: DemoSession, report_id: UUID) -> list[WorkflowReview]: ...


class WorkflowReviewService:
    def __init__(self, repository: IntakeRepository) -> None:
        self._repository = repository
        self._by_session_report: dict[tuple[UUID, UUID], list[StoredReview]] = {}
        self._by_idempotency: dict[tuple[UUID, str], StoredReview] = {}
        self._lock = Lock()

    def append(
        self,
        *,
        session: DemoSession,
        report_id: UUID,
        request: WorkflowReviewCreate,
        idempotency_key: str,
    ) -> WorkflowReview:
        report = self._repository.get_by_id(report_id)
        safety_action = request.action in {"verify_safety", "refer_safety", "dismiss_safety"}
        if safety_action != bool(report.safety_signal_codes):
            raise ConflictError("Review action does not match the report lane")

        evidence = {
            "report_id": str(report.id),
            "accepted_at": report.accepted_at.isoformat(),
            "processing_state": report.processing_state,
            "category": report.interpretation_category,
            "safety_signal_codes": list(report.safety_signal_codes),
        }
        fingerprint = _digest(request.model_dump(mode="json"))
        key = (session.id, report_id)
        with self._lock:
            existing = self._by_idempotency.get((session.id, idempotency_key))
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ConflictError("Idempotency key was already used")
                return existing.response

            history = self._by_session_report.setdefault(key, [])
            current_version = history[-1].response.entity_version_after if history else 1
            if request.expected_version != current_version:
                raise ConflictError("Review is stale; refresh the evidence and retry")

            response = WorkflowReview(
                id=uuid4(),
                session_id=session.id,
                report_id=report_id,
                action=request.action,
                reason=request.reason,
                evidence_digest=_digest(evidence),
                expected_version=current_version,
                entity_version_after=current_version + 1,
                supersedes_id=history[-1].response.id if history else None,
                created_at=datetime.now(UTC),
            )
            stored = StoredReview(response=response, request_fingerprint=fingerprint)
            history.append(stored)
            self._by_idempotency[(session.id, idempotency_key)] = stored
            return response

    def history(self, *, session: DemoSession, report_id: UUID) -> list[WorkflowReview]:
        self._repository.get_by_id(report_id)
        with self._lock:
            return [
                stored.response
                for stored in self._by_session_report.get((session.id, report_id), [])
            ]


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@lru_cache
def get_workflow_review_service() -> WorkflowReviewPort:
    return WorkflowReviewService(get_intake_repository())
