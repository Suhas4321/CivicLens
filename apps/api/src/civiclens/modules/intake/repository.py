from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from threading import Lock
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from civiclens.domain.photo_integrity import Flag
from civiclens.infrastructure.db.models import (
    ProcessingJobModel,
    ReportInterpretationModel,
    ReportMediaModel,
    ReportModel,
    SafetyReviewModel,
)
from civiclens.infrastructure.media.photo_storage import StoredPhoto
from civiclens.infrastructure.media.voice_storage import StoredVoice
from civiclens.modules.analysis.schemas import InterpretationEnvelope
from civiclens.modules.intake.schemas import ReportCreateRequest
from civiclens.modules.safety.evaluator import SafetyFinding
from civiclens.shared.errors import ConflictError, NotFoundError

VOICE = "voice"
PHOTO = "photo"


@dataclass(frozen=True)
class IntakeRecord:
    id: UUID
    public_id: str
    receipt_hash: str
    idempotency_key: str
    request_fingerprint: str
    accepted_at: datetime
    locality_label: str
    original_text: str
    language_hint: str
    processing_state: str
    # Where the reporter said the problem is. Optional because a reporter may
    # decline location, or be indoors with no fix, and a report without
    # coordinates is still a report -- `locality_label` carries it then.
    #
    # These are on the record, not only in the database, because the officer
    # surface reads fresh reports through `list_fresh()`. Without them here the
    # coordinates would be accepted by the endpoint, written to Postgres, and
    # still never reach the person deciding what to send a crew to -- which is
    # the same class of silent loss that kept them out of the endpoint.
    latitude: float | None = None
    longitude: float | None = None
    # "point" when the reporter's device gave a fix, "locality_label" when the
    # best we have is the name they typed. Grouping and dedup treat these very
    # differently, so the difference is recorded rather than inferred from
    # whether latitude happens to be null.
    location_precision: Literal["point", "locality_label"] = "locality_label"
    analysis_result_class: Literal["stored_sample", "fresh_fixture", "fresh_ai"] | None = None
    interpretation_category: str | None = None
    interpretation_summary: str | None = None
    safety_signal_codes: tuple[str, ...] = ()
    voice_object_key: str | None = None
    voice_content_type: str | None = None
    # The category the reporter chose, or None if they did not choose one. Carried on
    # the record because the officer surface routes by it, and because the statutory
    # deadline is derived from it -- `domain.sla.due_at` needs this exact code.
    service_code: str | None = None
    photo_object_key: str | None = None
    photo_content_type: str | None = None
    # Coarse EXIF conclusions, already reduced to flag codes. The raw EXIF is never
    # on this record and must never be added to it; see `domain.photo_integrity`.
    photo_integrity_codes: tuple[str, ...] = ()


class IntakeRepository(Protocol):
    def create_or_get(
        self,
        *,
        payload: ReportCreateRequest,
        public_id: str,
        receipt_hash: str,
        idempotency_key: str,
        request_fingerprint: str,
        accepted_at: datetime,
        voice: StoredVoice | None,
        photo: StoredPhoto | None = None,
        photo_flags: tuple[Flag, ...] = (),
    ) -> IntakeRecord: ...

    def get_by_public_id(self, public_id: str) -> IntakeRecord: ...

    def get_by_id(self, report_id: UUID) -> IntakeRecord: ...

    def list_fresh(self) -> list[IntakeRecord]: ...

    def complete_analysis(
        self,
        public_id: str,
        envelope: InterpretationEnvelope,
        findings: list[SafetyFinding],
    ) -> IntakeRecord: ...

    def fail_analysis(self, public_id: str, safe_error_code: str) -> IntakeRecord: ...


class MemoryIntakeRepository:
    """Process-local adapter for local demos and contract tests only."""

    def __init__(self) -> None:
        self._by_public_id: dict[str, IntakeRecord] = {}
        self._by_idempotency: dict[str, IntakeRecord] = {}
        self._lock = Lock()

    def create_or_get(
        self,
        *,
        payload: ReportCreateRequest,
        public_id: str,
        receipt_hash: str,
        idempotency_key: str,
        request_fingerprint: str,
        accepted_at: datetime,
        voice: StoredVoice | None,
        photo: StoredPhoto | None = None,
        photo_flags: tuple[Flag, ...] = (),
    ) -> IntakeRecord:
        with self._lock:
            existing = self._by_idempotency.get(idempotency_key)
            if existing:
                if (
                    existing.receipt_hash != receipt_hash
                    or existing.request_fingerprint != request_fingerprint
                ):
                    raise ConflictError("Idempotency key was already used")
                return existing

            record = IntakeRecord(
                id=uuid4(),
                public_id=public_id,
                receipt_hash=receipt_hash,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                accepted_at=accepted_at,
                locality_label=payload.locality_label,
                original_text=payload.description,
                language_hint=payload.language_hint,
                processing_state="received",
                latitude=payload.latitude,
                longitude=payload.longitude,
                # Mirrors the SQL adapter's rule exactly. Two adapters deriving
                # this differently would make the demo and the deployed system
                # group reports differently, which is the worst kind of
                # difference: invisible until somebody compares two screens.
                location_precision="point" if payload.latitude is not None else "locality_label",
                service_code=payload.service_code,
                voice_object_key=voice.object_key if voice else None,
                voice_content_type=voice.content_type if voice else None,
                photo_object_key=photo.object_key if photo else None,
                photo_content_type=photo.content_type if photo else None,
                photo_integrity_codes=tuple(flag.code for flag in photo_flags),
            )
            self._by_public_id[public_id] = record
            self._by_idempotency[idempotency_key] = record
            return record

    def get_by_public_id(self, public_id: str) -> IntakeRecord:
        try:
            return self._by_public_id[public_id]
        except KeyError as exc:
            raise NotFoundError("Receipt not found") from exc

    def get_by_id(self, report_id: UUID) -> IntakeRecord:
        with self._lock:
            for record in self._by_public_id.values():
                if record.id == report_id:
                    return record
        raise NotFoundError("Fresh report not found")

    def list_fresh(self) -> list[IntakeRecord]:
        with self._lock:
            return sorted(
                self._by_public_id.values(),
                key=lambda item: item.accepted_at,
                reverse=True,
            )

    def complete_analysis(
        self,
        public_id: str,
        envelope: InterpretationEnvelope,
        findings: list[SafetyFinding],
    ) -> IntakeRecord:
        with self._lock:
            current = self.get_by_public_id(public_id)
            if current.analysis_result_class is not None:
                return current
            completed = replace(
                current,
                processing_state="needs_review" if findings else "processed",
                analysis_result_class=envelope.result_class,
                interpretation_category=envelope.interpretation.category,
                interpretation_summary=envelope.interpretation.summary,
                safety_signal_codes=tuple(finding.signal_code for finding in findings),
            )
            self._by_public_id[public_id] = completed
            self._by_idempotency[current.idempotency_key] = completed
            return completed

    def fail_analysis(self, public_id: str, safe_error_code: str) -> IntakeRecord:
        del safe_error_code
        with self._lock:
            current = self.get_by_public_id(public_id)
            failed = replace(current, processing_state="needs_review")
            self._by_public_id[public_id] = failed
            self._by_idempotency[current.idempotency_key] = failed
            return failed


class SqlAlchemyIntakeRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_or_get(
        self,
        *,
        payload: ReportCreateRequest,
        public_id: str,
        receipt_hash: str,
        idempotency_key: str,
        request_fingerprint: str,
        accepted_at: datetime,
        voice: StoredVoice | None,
        photo: StoredPhoto | None = None,
        photo_flags: tuple[Flag, ...] = (),
    ) -> IntakeRecord:
        del request_fingerprint
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(ReportModel).where(ReportModel.idempotency_key == idempotency_key)
            )
            if existing:
                existing_voice = _media(session, existing.id, VOICE)
                existing_photo = _media(session, existing.id, PHOTO)
                if not _same_submission(
                    existing, existing_voice, existing_photo, payload, receipt_hash, voice, photo
                ):
                    raise ConflictError("Idempotency key was already used")
                return _record_from_model(existing, voice=existing_voice, photo=existing_photo)

            report_id = uuid4()
            report = ReportModel(
                id=report_id,
                logical_id=uuid4(),
                demo_session_id=None,
                public_id=public_id,
                receipt_hash=receipt_hash,
                idempotency_key=idempotency_key,
                source_channel=_source_channel(voice, photo),
                original_text=payload.description,
                service_code=payload.service_code,
                language_hint=payload.language_hint,
                accepted_at=accepted_at,
                consent_version="demo-v1",
                locality_label=payload.locality_label,
                geography_kind="citizen_supplied_locality",
                geography_source="citizen_claim",
                latitude=Decimal(str(payload.latitude)) if payload.latitude is not None else None,
                longitude=(
                    Decimal(str(payload.longitude)) if payload.longitude is not None else None
                ),
                location_precision="point" if payload.latitude is not None else "locality_label",
                processing_state="received",
                evidence_class="synthetic_demo",
                is_seed=False,
            )
            session.add(report)
            if voice is not None:
                session.add(
                    ReportMediaModel(
                        report_id=report_id,
                        media_type=VOICE,
                        object_key=voice.object_key,
                        content_hash=voice.content_hash,
                        content_type=voice.content_type,
                        byte_size=voice.byte_size,
                        duration_seconds=Decimal(str(voice.duration_seconds)),
                        validation_state="accepted",
                        retain_until=voice.retain_until,
                    )
                )
            if photo is not None:
                session.add(
                    ReportMediaModel(
                        report_id=report_id,
                        media_type=PHOTO,
                        object_key=photo.object_key,
                        content_hash=photo.content_hash,
                        content_type=photo.content_type,
                        byte_size=photo.byte_size,
                        # Left NULL, and the `duration_matches_media_type` constraint
                        # requires it to be. A photo has no duration, and a zero here
                        # would read as "a recording of no length".
                        duration_seconds=None,
                        perceptual_hash=photo.perceptual_hash,
                        integrity_flags=_flags_payload(photo_flags),
                        validation_state="accepted",
                        retain_until=photo.retain_until,
                    )
                )
            session.add(
                ProcessingJobModel(
                    report_id=report_id,
                    demo_session_id=None,
                    job_type="interpret_report",
                    state="queued",
                    attempt_count=0,
                    max_attempts=3,
                    available_at=accepted_at,
                    dedupe_key=f"interpret:{report_id}",
                )
            )
            session.flush()
            return _record_from_model(
                report,
                voice=_media(session, report_id, VOICE) if voice is not None else None,
                photo=_media(session, report_id, PHOTO) if photo is not None else None,
            )

    def get_by_public_id(self, public_id: str) -> IntakeRecord:
        with self._session_factory() as session:
            report = session.scalar(select(ReportModel).where(ReportModel.public_id == public_id))
            if report is None:
                raise NotFoundError("Receipt not found")
            interpretation = session.scalar(
                select(ReportInterpretationModel).where(
                    ReportInterpretationModel.report_id == report.id,
                    ReportInterpretationModel.is_active.is_(True),
                )
            )
            voice = _media(session, report.id, VOICE)
            photo = _media(session, report.id, PHOTO)
            findings = list(
                session.scalars(
                    select(SafetyReviewModel).where(SafetyReviewModel.report_id == report.id)
                )
            )
            return _record_from_model(report, interpretation, voice, findings, photo=photo)

    def get_by_id(self, report_id: UUID) -> IntakeRecord:
        with self._session_factory() as session:
            report = session.scalar(select(ReportModel).where(ReportModel.id == report_id))
            if report is None or report.is_seed:
                raise NotFoundError("Fresh report not found")
            interpretation = session.scalar(
                select(ReportInterpretationModel).where(
                    ReportInterpretationModel.report_id == report.id,
                    ReportInterpretationModel.is_active.is_(True),
                )
            )
            voice = _media(session, report.id, VOICE)
            photo = _media(session, report.id, PHOTO)
            findings = list(
                session.scalars(
                    select(SafetyReviewModel).where(SafetyReviewModel.report_id == report.id)
                )
            )
            return _record_from_model(report, interpretation, voice, findings, photo=photo)

    def list_fresh(self) -> list[IntakeRecord]:
        with self._session_factory() as session:
            reports = list(
                session.scalars(
                    select(ReportModel)
                    .where(ReportModel.is_seed.is_(False))
                    .order_by(ReportModel.accepted_at.desc())
                )
            )
            records: list[IntakeRecord] = []
            for report in reports:
                interpretation = session.scalar(
                    select(ReportInterpretationModel).where(
                        ReportInterpretationModel.report_id == report.id,
                        ReportInterpretationModel.is_active.is_(True),
                    )
                )
                voice = _media(session, report.id, VOICE)
                photo = _media(session, report.id, PHOTO)
                findings = list(
                    session.scalars(
                        select(SafetyReviewModel).where(SafetyReviewModel.report_id == report.id)
                    )
                )
                records.append(
                    _record_from_model(report, interpretation, voice, findings, photo=photo)
                )
            return records

    def complete_analysis(
        self,
        public_id: str,
        envelope: InterpretationEnvelope,
        findings: list[SafetyFinding],
    ) -> IntakeRecord:
        with self._session_factory.begin() as session:
            report = session.scalar(select(ReportModel).where(ReportModel.public_id == public_id))
            if report is None:
                raise NotFoundError("Receipt not found")
            existing = session.scalar(
                select(ReportInterpretationModel).where(
                    ReportInterpretationModel.report_id == report.id,
                    ReportInterpretationModel.is_active.is_(True),
                )
            )
            if existing is not None:
                voice = _media(session, report.id, VOICE)
                photo = _media(session, report.id, PHOTO)
                return _record_from_model(report, existing, voice, photo=photo)

            interpretation_id = uuid4()
            interpretation = ReportInterpretationModel(
                id=interpretation_id,
                report_id=report.id,
                version=1,
                is_active=True,
                result_state="needs_review" if findings else "succeeded",
                provider=envelope.provider,
                configured_model=envelope.configured_model,
                returned_model=envelope.returned_model,
                prompt_version=envelope.prompt_version,
                schema_version=envelope.schema_version,
                payload=envelope.interpretation.model_dump(mode="json"),
                evidence_class="ai_derived",
                latency_ms=envelope.latency_ms,
            )
            session.add(interpretation)
            for finding in findings:
                session.add(
                    SafetyReviewModel(
                        report_id=report.id,
                        interpretation_id=interpretation_id,
                        signal_code=finding.signal_code,
                        rule_version=finding.rule_version,
                        state="pending",
                        reason_code=finding.reason_code,
                    )
                )
            report.processing_state = "needs_review" if findings else "processed"
            jobs = session.scalars(
                select(ProcessingJobModel).where(ProcessingJobModel.report_id == report.id)
            )
            for job in jobs:
                job.state = "succeeded"
                job.attempt_count = min(job.attempt_count + 1, job.max_attempts)
            session.flush()
            voice = _media(session, report.id, VOICE)
            photo = _media(session, report.id, PHOTO)
            return _record_from_model(report, interpretation, voice, photo=photo)

    def fail_analysis(self, public_id: str, safe_error_code: str) -> IntakeRecord:
        with self._session_factory.begin() as session:
            report = session.scalar(select(ReportModel).where(ReportModel.public_id == public_id))
            if report is None:
                raise NotFoundError("Receipt not found")
            report.processing_state = "needs_review"
            jobs = session.scalars(
                select(ProcessingJobModel).where(ProcessingJobModel.report_id == report.id)
            )
            for job in jobs:
                job.attempt_count = min(job.attempt_count + 1, job.max_attempts)
                job.state = "retry_wait" if job.attempt_count < job.max_attempts else "dead_letter"
                job.safe_error_code = safe_error_code
            session.flush()
            return _record_from_model(report)


def _media(session: Session, report_id: UUID, media_type: str) -> ReportMediaModel | None:
    """Fetch the one media row of a given type for a report, or None.

    The ``media_type`` filter is the whole point of this helper existing. Before
    photos there was exactly one media row per report, so every read path here said
    "the media row for this report" and was right by accident. With two rows that
    same query returns whichever one the planner reaches first -- so a report with a
    photo could hand back a photo where the code expected a voice note, with no
    error anywhere. Routing every lookup through here makes the type impossible to
    forget, and ``uq_report_media_one_per_type`` guarantees the answer is unique.
    """
    return session.scalar(
        select(ReportMediaModel).where(
            ReportMediaModel.report_id == report_id,
            ReportMediaModel.media_type == media_type,
        )
    )


def _source_channel(voice: StoredVoice | None, photo: StoredPhoto | None) -> str:
    """Describe what the reporter actually sent, for the audit trail."""
    suffixes = ("_voice" if voice else "") + ("_photo" if photo else "")
    return f"web_text{suffixes}"


def _flags_payload(flags: tuple[Flag, ...]) -> dict[str, object] | None:
    """Shape the integrity flags for the JSONB column.

    Wrapped in an object rather than stored as a bare array so that a later
    addition -- a rule version, say -- does not require rewriting existing rows or
    teaching readers to handle two different top-level JSON types.
    """
    if not flags:
        return None
    return {"flags": [{"code": flag.code, "detail": flag.detail} for flag in flags]}


def _same_submission(
    report: ReportModel,
    existing_voice: ReportMediaModel | None,
    existing_photo: ReportMediaModel | None,
    payload: ReportCreateRequest,
    receipt_hash: str,
    voice: StoredVoice | None,
    photo: StoredPhoto | None,
) -> bool:
    """Is this retry the same submission, or a different one reusing the key?

    Every field a client can vary has to appear here. A field that is compared
    nowhere makes the idempotency check answer "same submission" for two genuinely
    different reports, and the second one is then silently dropped in favour of the
    first -- so `service_code` and the photo hash are checked for the same reason
    the coordinates are.
    """
    return (
        report.receipt_hash == receipt_hash
        and report.original_text == payload.description
        and report.language_hint == payload.language_hint
        and report.locality_label == payload.locality_label
        and report.service_code == payload.service_code
        and _optional_float(report.latitude) == payload.latitude
        and _optional_float(report.longitude) == payload.longitude
        and (existing_voice.content_hash if existing_voice else None)
        == (voice.content_hash if voice else None)
        and (existing_photo.content_hash if existing_photo else None)
        == (photo.content_hash if photo else None)
    )


def _optional_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _record_from_model(
    report: ReportModel,
    interpretation: ReportInterpretationModel | None = None,
    voice: ReportMediaModel | None = None,
    findings: list[SafetyReviewModel] | None = None,
    *,
    # Keyword-only, and appended rather than inserted next to `voice` where it would
    # read better. Several callers pass the first four positionally, so slotting a
    # parameter in among them would rebind `findings` to a photo at every one of
    # those call sites -- and both are optional model objects, so nothing would
    # complain.
    photo: ReportMediaModel | None = None,
) -> IntakeRecord:
    payload = interpretation.payload if interpretation is not None else {}
    return IntakeRecord(
        id=report.id,
        public_id=report.public_id,
        receipt_hash=report.receipt_hash,
        idempotency_key=report.idempotency_key or "",
        request_fingerprint="",
        accepted_at=report.accepted_at,
        locality_label=report.locality_label,
        original_text=report.original_text,
        language_hint=report.language_hint or "unknown",
        processing_state=report.processing_state,
        # Read back out, not just written in. The columns have been populated
        # since the first migration, but nothing ever mapped them onto the record,
        # so the coordinates were durable and unreadable at the same time.
        latitude=_optional_float(report.latitude),
        longitude=_optional_float(report.longitude),
        location_precision="point" if report.latitude is not None else "locality_label",
        analysis_result_class=(
            "stored_sample"
            if interpretation is not None and interpretation.provider == "fixture-seed"
            else "fresh_fixture"
            if interpretation is not None and interpretation.provider == "fixture"
            else "fresh_ai"
            if interpretation is not None
            else None
        ),
        interpretation_category=(
            str(payload.get("category")) if payload.get("category") is not None else None
        ),
        interpretation_summary=(
            str(payload.get("summary")) if payload.get("summary") is not None else None
        ),
        safety_signal_codes=tuple(finding.signal_code for finding in findings or []),
        service_code=report.service_code,
        voice_object_key=voice.object_key if voice else None,
        voice_content_type=voice.content_type if voice else None,
        photo_object_key=photo.object_key if photo else None,
        photo_content_type=photo.content_type if photo else None,
        photo_integrity_codes=_integrity_codes(photo),
    )


def _integrity_codes(photo: ReportMediaModel | None) -> tuple[str, ...]:
    """Read the flag codes back out of the JSONB column, tolerating anything odd.

    Defensive because this column is the one piece of the record whose shape is not
    enforced by the database. A row written by an older version, or by hand during an
    incident, must not be able to break the officer board -- an unreadable flag set
    is worth degrading to "no flags" for, and is not worth a 500.
    """
    if photo is None or not isinstance(photo.integrity_flags, dict):
        return ()
    flags = cast(object, photo.integrity_flags.get("flags"))
    if not isinstance(flags, list):
        return ()
    codes: list[str] = []
    for entry in cast(list[object], flags):
        if isinstance(entry, dict):
            code = cast(object, cast(dict[str, object], entry).get("code"))
            if code is not None:
                codes.append(str(code))
    return tuple(codes)
