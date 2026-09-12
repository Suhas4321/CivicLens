from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.db.session import build_engine, build_session_factory
from civiclens.infrastructure.media.voice_storage import StoredVoice
from civiclens.modules.intake.repository import (
    IntakeRecord,
    IntakeRepository,
    MemoryIntakeRepository,
    SqlAlchemyIntakeRepository,
)
from civiclens.modules.intake.schemas import ReceiptStatus, ReportAccepted, ReportCreateRequest
from civiclens.shared.errors import NotFoundError


class IntakeService:
    def __init__(self, repository: IntakeRepository) -> None:
        self._repository = repository

    def submit(
        self,
        payload: ReportCreateRequest,
        *,
        idempotency_key: str,
        receipt_capability: str,
        voice: StoredVoice | None = None,
    ) -> ReportAccepted:
        accepted_at = datetime.now(UTC)
        record = self._repository.create_or_get(
            payload=payload,
            public_id=_new_public_id(),
            receipt_hash=_hash_capability(receipt_capability),
            idempotency_key=idempotency_key,
            request_fingerprint=_request_fingerprint(payload, voice),
            accepted_at=accepted_at,
            voice=voice,
        )
        return ReportAccepted(
            public_id=record.public_id,
            status="received",
            accepted_at=record.accepted_at,
            message="Report received. Analysis has been queued for this demo.",
        )

    def receipt(self, public_id: str, *, receipt_capability: str) -> ReceiptStatus:
        try:
            record = self._repository.get_by_public_id(public_id)
        except NotFoundError:
            raise
        if not hmac.compare_digest(record.receipt_hash, _hash_capability(receipt_capability)):
            # Deliberately indistinguishable from an unknown receipt identifier.
            raise NotFoundError("Receipt not found")
        return ReceiptStatus(
            public_id=record.public_id,
            status=_public_status(record),
            accepted_at=record.accepted_at,
            generalized_area=record.locality_label,
            evidence_class="synthetic_demo",
            analysis_class=record.analysis_result_class or "pending",
            analysis_state=_analysis_state(record),
            message="This submission is isolated demo evidence and is not an official complaint.",
        )


def _public_status(
    record: IntakeRecord,
) -> Literal["received", "analysing", "processed", "needs_review"]:
    if record.processing_state in {"received", "sanitizing"}:
        return "received"
    if record.processing_state == "analysing":
        return "analysing"
    if record.processing_state == "processed":
        return "processed"
    return "needs_review"


def _analysis_state(record: IntakeRecord) -> str:
    if record.processing_state == "processed":
        return "Structured interpretation complete"
    if record.processing_state == "needs_review":
        return "Separated for human review"
    if record.processing_state == "analysing":
        return "Structured interpretation in progress"
    return "Queued for structured interpretation"


def _hash_capability(capability: str) -> str:
    return hashlib.sha256(capability.encode("utf-8")).hexdigest()


def _request_fingerprint(payload: ReportCreateRequest, voice: StoredVoice | None) -> str:
    value = {
        "payload": payload.model_dump(),
        "voice_content_hash": voice.content_hash if voice else None,
    }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _new_public_id() -> str:
    return f"CL-{secrets.token_urlsafe(9)}"


@lru_cache
def get_intake_repository() -> IntakeRepository:
    settings = get_settings()
    if settings.intake_backend == "postgres":
        engine = build_engine(settings)
        return SqlAlchemyIntakeRepository(build_session_factory(engine))
    return MemoryIntakeRepository()


@lru_cache
def get_intake_service() -> IntakeService:
    return IntakeService(get_intake_repository())
