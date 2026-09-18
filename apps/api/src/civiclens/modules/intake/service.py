from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

from civiclens.bootstrap.settings import get_settings
from civiclens.domain.photo_integrity import Flag
from civiclens.infrastructure.db.session import build_engine, build_session_factory
from civiclens.infrastructure.media.photo_storage import StoredPhoto
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
        photo: StoredPhoto | None = None,
        photo_flags: tuple[Flag, ...] = (),
    ) -> ReportAccepted:
        accepted_at = datetime.now(UTC)
        record = self._repository.create_or_get(
            payload=payload,
            public_id=_new_public_id(),
            receipt_hash=_hash_capability(receipt_capability),
            idempotency_key=idempotency_key,
            request_fingerprint=_request_fingerprint(payload, voice, photo),
            accepted_at=accepted_at,
            voice=voice,
            photo=photo,
            photo_flags=photo_flags,
        )
        return ReportAccepted(
            public_id=record.public_id,
            status="received",
            accepted_at=record.accepted_at,
            # Read back off the stored record, not from the request. If some layer
            # below were to drop either of these, the receipt now says so instead of
            # cheerfully reporting what was sent -- which is exactly how the
            # coordinate loss stayed invisible for as long as it did.
            photo_received=record.photo_object_key is not None,
            service_code_recorded=record.service_code,
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


def _request_fingerprint(
    payload: ReportCreateRequest,
    voice: StoredVoice | None,
    photo: StoredPhoto | None,
) -> str:
    # The photo hash belongs here for the same reason the voice hash does: this
    # fingerprint is what the memory adapter uses to tell a retry from a different
    # report reusing an idempotency key. A photo left out would make two submissions
    # with identical text and different photos look like one, and the second
    # photo would be discarded.
    value = {
        "payload": payload.model_dump(),
        "voice_content_hash": voice.content_hash if voice else None,
        "photo_content_hash": photo.content_hash if photo else None,
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
