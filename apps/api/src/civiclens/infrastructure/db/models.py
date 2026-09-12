from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

from civiclens.infrastructure.db.base import Base

JsonObject = dict[str, Any]


def uuid_pk() -> MappedColumn[UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)


def created_at_column() -> MappedColumn[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class DemoSessionModel(Base):
    __tablename__ = "demo_session"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'expired', 'reset')", name="status_allowed"),
    )

    id: Mapped[UUID] = uuid_pk()
    external_subject_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportModel(Base):
    __tablename__ = "report"
    __table_args__ = (
        CheckConstraint(
            "processing_state IN ('received', 'sanitizing', 'analysing', 'processed', "
            "'needs_review', 'quarantined')",
            name="processing_state_allowed",
        ),
        CheckConstraint(
            "evidence_class IN ('synthetic_demo', 'citizen_claim')",
            name="evidence_class_allowed",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="longitude_range",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    logical_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), unique=True, nullable=False)
    demo_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demo_session.id", ondelete="CASCADE")
    )
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    source_channel: Mapped[str] = mapped_column(String(24), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    language_hint: Mapped[str | None] = mapped_column(String(24))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    locality_label: Mapped[str] = mapped_column(String(160), nullable=False)
    geography_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    geography_source: Mapped[str] = mapped_column(String(48), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    location_precision: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_state: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence_class: Mapped[str] = mapped_column(String(24), nullable=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_at_column()


class ReportMediaModel(Base):
    __tablename__ = "report_media"
    __table_args__ = (
        CheckConstraint("media_type = 'voice'", name="voice_only"),
        CheckConstraint(
            "validation_state IN ('pending', 'accepted', 'rejected', 'quarantined')",
            name="validation_state_allowed",
        ),
        CheckConstraint("byte_size BETWEEN 1 AND 6291456", name="byte_size_limit"),
        CheckConstraint("duration_seconds BETWEEN 0 AND 30", name="duration_limit"),
    )

    id: Mapped[UUID] = uuid_pk()
    report_id: Mapped[UUID] = mapped_column(ForeignKey("report.id", ondelete="CASCADE"))
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    validation_state: Mapped[str] = mapped_column(String(24), nullable=False)
    retain_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class ReportInterpretationModel(Base):
    __tablename__ = "report_interpretation"
    __table_args__ = (
        UniqueConstraint("report_id", "version"),
        CheckConstraint(
            "result_state IN ('stored_sample', 'succeeded', 'needs_review', 'failed')",
            name="result_state_allowed",
        ),
        CheckConstraint(
            "evidence_class = 'ai_derived'",
            name="ai_derived_only",
        ),
        Index(
            "uq_report_interpretation_active",
            "report_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    report_id: Mapped[UUID] = mapped_column(ForeignKey("report.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("report_interpretation.id"))
    result_state: Mapped[str] = mapped_column(String(24), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    configured_model: Mapped[str] = mapped_column(String(80), nullable=False)
    returned_model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(48), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    evidence_class: Mapped[str] = mapped_column(String(24), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_column()


class SafetyReviewModel(Base):
    __tablename__ = "safety_review"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'verified', 'referred', 'dismissed')",
            name="state_allowed",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    report_id: Mapped[UUID] = mapped_column(ForeignKey("report.id", ondelete="RESTRICT"))
    interpretation_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_interpretation.id", ondelete="RESTRICT")
    )
    demo_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demo_session.id", ondelete="CASCADE")
    )
    signal_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(48), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_column()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IncidentModel(Base):
    __tablename__ = "incident"
    __table_args__ = (
        UniqueConstraint("logical_id", "version"),
        CheckConstraint(
            "lifecycle IN ('proposed', 'confirmed', 'monitoring', 'closed')",
            name="lifecycle_allowed",
        ),
        Index(
            "uq_incident_logical_active",
            "logical_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    logical_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    demo_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demo_session.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(64))
    event_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locality_label: Mapped[str] = mapped_column(String(160), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lifecycle: Mapped[str] = mapped_column(String(24), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_class: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class IncidentReportLinkModel(Base):
    __tablename__ = "incident_report_link"
    __table_args__ = (
        UniqueConstraint("incident_id", "report_id", "version"),
        CheckConstraint(
            "relation_type IN ('suspected_duplicate', 'same_incident')",
            name="relation_type_allowed",
        ),
        CheckConstraint(
            "state IN ('proposed', 'confirmed', 'rejected', 'superseded')",
            name="state_allowed",
        ),
        Index(
            "uq_incident_report_link_active",
            "incident_id",
            "report_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incident.id", ondelete="RESTRICT"))
    report_id: Mapped[UUID] = mapped_column(ForeignKey("report.id", ondelete="RESTRICT"))
    demo_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demo_session.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_evidence: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    confidence_band: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class IncidentRelationshipModel(Base):
    __tablename__ = "incident_relationship"
    __table_args__ = (
        UniqueConstraint("source_incident_id", "target_incident_id", "version"),
        CheckConstraint("source_incident_id <> target_incident_id", name="not_self_link"),
        CheckConstraint("relation_type = 'recurrence'", name="recurrence_only"),
        CheckConstraint(
            "state IN ('proposed', 'confirmed', 'rejected', 'superseded')",
            name="state_allowed",
        ),
        Index(
            "uq_incident_relationship_active",
            "source_incident_id",
            "target_incident_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    source_incident_id: Mapped[UUID] = mapped_column(ForeignKey("incident.id", ondelete="RESTRICT"))
    target_incident_id: Mapped[UUID] = mapped_column(ForeignKey("incident.id", ondelete="RESTRICT"))
    demo_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demo_session.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    relation_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_evidence: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class SuspectedNeedModel(Base):
    __tablename__ = "suspected_need"
    __table_args__ = (
        UniqueConstraint("logical_id", "version"),
        CheckConstraint(
            "lifecycle IN ('emerging', 'monitoring', 'evidence_review', 'comparison_ready', "
            "'insufficient_evidence', 'candidate_review', 'referred', 'deferred', 'rejected')",
            name="lifecycle_allowed",
        ),
        Index(
            "uq_suspected_need_logical_active",
            "logical_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    logical_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    demo_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demo_session.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    geography_label: Mapped[str] = mapped_column(String(160), nullable=False)
    geography_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    geography_membership_method: Mapped[str] = mapped_column(String(80), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    alternative_state: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_class: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class NeedIncidentLinkModel(Base):
    __tablename__ = "need_incident_link"
    __table_args__ = (
        UniqueConstraint("need_id", "incident_id", "version"),
        Index(
            "uq_need_incident_link_active",
            "need_id",
            "incident_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    need_id: Mapped[UUID] = mapped_column(ForeignKey("suspected_need.id", ondelete="RESTRICT"))
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incident.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    relationship_reason: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class DatasetSnapshotModel(Base):
    __tablename__ = "dataset_snapshot"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('reviewed', 'limited_reuse', 'unverified')",
            name="review_status_allowed",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    version: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    publisher: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date)
    reference_date: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[date] = mapped_column(Date, nullable=False)
    normalized_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_format: Mapped[str] = mapped_column(String(48), nullable=False)
    license_status: Mapped[str] = mapped_column(String(80), nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False)
    manifest: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class PublicEvidenceModel(Base):
    __tablename__ = "public_evidence"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "evidence_key"),
        CheckConstraint(
            "evidence_class IN ('real_public', 'derived_public', 'synthetic_demo')",
            name="evidence_class_allowed",
        ),
        CheckConstraint("kind IN ('observation', 'work', 'context')", name="kind_allowed"),
        CheckConstraint(
            "semantics IN ('observed', 'projected', 'plan', 'administrative_status', "
            "'synthetic_verification')",
            name="semantics_allowed",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_snapshot.id", ondelete="RESTRICT")
    )
    evidence_key: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_class: Mapped[str] = mapped_column(String(24), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    value_text: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(48))
    geography_label: Mapped[str] = mapped_column(String(200), nullable=False)
    geography_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    geography_vintage: Mapped[str | None] = mapped_column(String(80))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    semantics: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    transformation: Mapped[str | None] = mapped_column(Text)
    supported_inferences: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    prohibited_inferences: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class PriorityAssessmentModel(Base):
    __tablename__ = "priority_assessment"
    __table_args__ = (
        UniqueConstraint("need_id", "version"),
        CheckConstraint(
            "priority_band IN ('high', 'moderate', 'lower', 'not_comparable')",
            name="priority_band_allowed",
        ),
        Index(
            "uq_priority_assessment_active",
            "need_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    need_id: Mapped[UUID] = mapped_column(ForeignKey("suspected_need.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    components: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    priority_band: Mapped[str] = mapped_column(String(24), nullable=False)
    completeness: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    sensitivity: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    abstention_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(48), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class ProjectCandidateModel(Base):
    __tablename__ = "project_candidate"
    __table_args__ = (
        UniqueConstraint("need_id", "version"),
        CheckConstraint(
            "lifecycle IN ('draft', 'review_ready', 'referred', 'deferred', 'rejected', "
            "'superseded')",
            name="lifecycle_allowed",
        ),
        Index(
            "uq_project_candidate_active",
            "need_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    need_id: Mapped[UUID] = mapped_column(ForeignKey("suspected_need.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    catalogue_key: Mapped[str] = mapped_column(String(80), nullable=False)
    catalogue_version: Mapped[str] = mapped_column(String(48), nullable=False)
    conditional_wording: Mapped[str] = mapped_column(Text, nullable=False)
    works_overlap: Mapped[JsonObject] = mapped_column(JSONB, nullable=False)
    prerequisites: Mapped[list[JsonObject]] = mapped_column(JSONB, nullable=False)
    uncertainty: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class HumanDecisionModel(Base):
    __tablename__ = "human_decision"
    __table_args__ = (
        CheckConstraint(
            "disposition IN ('refer', 'defer', 'reject')",
            name="disposition_allowed",
        ),
        CheckConstraint("actor_role = 'demo_officer'", name="actor_role_allowed"),
    )

    id: Mapped[UUID] = uuid_pk()
    demo_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("demo_session.id", ondelete="RESTRICT"), nullable=False
    )
    need_id: Mapped[UUID] = mapped_column(
        ForeignKey("suspected_need.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_candidate.id", ondelete="RESTRICT")
    )
    disposition: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(Text)
    next_step: Mapped[str | None] = mapped_column(Text)
    next_review_date: Mapped[date | None] = mapped_column(Date)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("human_decision.id"))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class ProcessingJobModel(Base):
    __tablename__ = "processing_job"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'leased', 'succeeded', 'retry_wait', 'dead_letter')",
            name="state_allowed",
        ),
        CheckConstraint("attempt_count BETWEEN 0 AND max_attempts", name="attempt_range"),
    )

    id: Mapped[UUID] = uuid_pk()
    report_id: Mapped[UUID] = mapped_column(ForeignKey("report.id", ondelete="CASCADE"))
    demo_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demo_session.id", ondelete="CASCADE")
    )
    job_type: Mapped[str] = mapped_column(String(48), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.now,
    )


CORE_MODEL_TYPES = (
    DemoSessionModel,
    ReportModel,
    ReportMediaModel,
    ReportInterpretationModel,
    SafetyReviewModel,
    IncidentModel,
    IncidentReportLinkModel,
    IncidentRelationshipModel,
    SuspectedNeedModel,
    NeedIncidentLinkModel,
    DatasetSnapshotModel,
    PublicEvidenceModel,
    PriorityAssessmentModel,
    ProjectCandidateModel,
    HumanDecisionModel,
    ProcessingJobModel,
)
