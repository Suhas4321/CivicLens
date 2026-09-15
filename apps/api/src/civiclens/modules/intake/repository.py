from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from threading import Lock
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from civiclens.infrastructure.db.models import (
    ProcessingJobModel,
    ReportInterpretationModel,
    ReportMediaModel,
    ReportModel,
    SafetyReviewModel,
)
from civiclens.infrastructure.media.voice_storage import StoredVoice
from civiclens.modules.analysis.schemas import InterpretationEnvelope
from civiclens.modules.intake.schemas import ReportCreateRequest
from civiclens.modules.safety.evaluator import SafetyFinding
from civiclens.shared.errors import ConflictError, NotFoundError


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
                voice_object_key=voice.object_key if voice else None,
                voice_content_type=voice.content_type if voice else None,
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
    ) -> IntakeRecord:
        del request_fingerprint
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(ReportModel).where(ReportModel.idempotency_key == idempotency_key)
            )
            if existing:
                existing_voice = session.scalar(
                    select(ReportMediaModel).where(ReportMediaModel.report_id == existing.id)
                )
                if not _same_submission(existing, existing_voice, payload, receipt_hash, voice):
                    raise ConflictError("Idempotency key was already used")
                return _record_from_model(existing, voice=existing_voice)

            report_id = uuid4()
            report = ReportModel(
                id=report_id,
                logical_id=uuid4(),
                demo_session_id=None,
                public_id=public_id,
                receipt_hash=receipt_hash,
                idempotency_key=idempotency_key,
                source_channel="web_text_voice" if voice else "web_text",
                original_text=payload.description,
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
                        media_type="voice",
                        object_key=voice.object_key,
                        content_hash=voice.content_hash,
                        content_type=voice.content_type,
                        byte_size=voice.byte_size,
                        duration_seconds=Decimal(str(voice.duration_seconds)),
                        validation_state="accepted",
                        retain_until=voice.retain_until,
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
            voice_model = (
                session.scalar(
                    select(ReportMediaModel).where(ReportMediaModel.report_id == report_id)
                )
                if voice is not None
                else None
            )
            return _record_from_model(report, voice=voice_model)

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
            voice = session.scalar(
                select(ReportMediaModel).where(ReportMediaModel.report_id == report.id)
            )
            findings = list(
                session.scalars(
                    select(SafetyReviewModel).where(SafetyReviewModel.report_id == report.id)
                )
            )
            return _record_from_model(report, interpretation, voice, findings)

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
            voice = session.scalar(
                select(ReportMediaModel).where(ReportMediaModel.report_id == report.id)
            )
            findings = list(
                session.scalars(
                    select(SafetyReviewModel).where(SafetyReviewModel.report_id == report.id)
                )
            )
            return _record_from_model(report, interpretation, voice, findings)

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
                voice = session.scalar(
                    select(ReportMediaModel).where(ReportMediaModel.report_id == report.id)
                )
                findings = list(
                    session.scalars(
                        select(SafetyReviewModel).where(SafetyReviewModel.report_id == report.id)
                    )
                )
                records.append(_record_from_model(report, interpretation, voice, findings))
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
                voice = session.scalar(
                    select(ReportMediaModel).where(ReportMediaModel.report_id == report.id)
                )
                return _record_from_model(report, existing, voice)

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
            voice = session.scalar(
                select(ReportMediaModel).where(ReportMediaModel.report_id == report.id)
            )
            return _record_from_model(report, interpretation, voice)

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


def _same_submission(
    report: ReportModel,
    existing_voice: ReportMediaModel | None,
    payload: ReportCreateRequest,
    receipt_hash: str,
    voice: StoredVoice | None,
) -> bool:
    return (
        report.receipt_hash == receipt_hash
        and report.original_text == payload.description
        and report.language_hint == payload.language_hint
        and report.locality_label == payload.locality_label
        and _optional_float(report.latitude) == payload.latitude
        and _optional_float(report.longitude) == payload.longitude
        and (existing_voice.content_hash if existing_voice else None)
        == (voice.content_hash if voice else None)
    )


def _optional_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _record_from_model(
    report: ReportModel,
    interpretation: ReportInterpretationModel | None = None,
    voice: ReportMediaModel | None = None,
    findings: list[SafetyReviewModel] | None = None,
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
        voice_object_key=voice.object_key if voice else None,
        voice_content_type=voice.content_type if voice else None,
    )
