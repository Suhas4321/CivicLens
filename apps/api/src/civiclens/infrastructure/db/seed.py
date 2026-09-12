from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from civiclens.bootstrap.policy import load_policy_bundle, repository_root
from civiclens.bootstrap.settings import Settings, get_settings
from civiclens.infrastructure.db.models import (
    DatasetSnapshotModel,
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
from civiclens.infrastructure.db.seed_contracts import (
    SeedReport,
    validate_demo_assets,
    validate_public_assets,
)
from civiclens.infrastructure.db.session import build_engine, build_session_factory
from civiclens.shared.errors import ConfigurationError
from civiclens.shared.primitives import stable_id


@dataclass(frozen=True)
class SeedResult:
    inserted: bool
    reports: int
    incidents: int
    needs: int
    public_evidence: int


def _receipt_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _interpretation_payload(report: SeedReport) -> dict[str, Any]:
    return {
        "detected_languages": [report.language],
        "transcript": {"text": report.text, "confidence": "stored_sample"},
        "translation": {
            "text": report.text if report.language == "en" else "Stored sample translation",
            "target_language": "en",
            "confidence": "stored_sample",
        },
        "category": {
            "code": report.expected.category,
            "support": "synthetic ground truth" if report.expected.category else "unknown",
        },
        "place": {"text": report.locality_label, "support": "reporter-stated"},
        "safety_signals": (
            [{"code": report.expected.safety_signal, "state": "present"}]
            if report.expected.safety_signal
            else []
        ),
        "summary": "Reporter states a synthetic civic symptom; no fact is independently verified.",
        "uncertainties": ["Synthetic Demo evidence", "Technical cause unknown"],
    }


def _insert_public_snapshot(session: Session, root: Path) -> int:
    manifest, observations = validate_public_assets(root)
    snapshot_id = stable_id("dataset-snapshot", manifest.version)
    session.add(
        DatasetSnapshotModel(
            id=snapshot_id,
            version=manifest.version,
            publisher=manifest.publisher,
            source_url=manifest.primary_source_url,
            publication_date=manifest.publication_date,
            reference_date=manifest.reference_date,
            retrieved_at=manifest.retrieved_at,
            normalized_sha256=manifest.normalized_sha256,
            source_format=manifest.source_format,
            license_status=manifest.license_status,
            review_status=manifest.review_status,
            manifest=manifest.model_dump(mode="json"),
        )
    )
    for item in observations:
        session.add(
            PublicEvidenceModel(
                id=stable_id("public-evidence", item.evidence_key),
                snapshot_id=snapshot_id,
                evidence_key=item.evidence_key,
                evidence_class=item.evidence_class,
                kind=item.kind,
                label=item.label,
                value_numeric=(
                    Decimal(str(item.value_numeric)) if item.value_numeric is not None else None
                ),
                value_text=item.value_text,
                unit=item.unit,
                geography_label=item.geography_label,
                geography_kind=item.geography_kind,
                geography_vintage=item.geography_vintage,
                period_start=item.period_start,
                period_end=item.period_end,
                semantics=item.semantics,
                source_url=item.source_url,
                transformation=item.transformation,
                supported_inferences=item.supported_inferences,
                prohibited_inferences=item.prohibited_inferences,
            )
        )
    return len(observations)


def _insert_reports(session: Session, reports: list[SeedReport]) -> dict[str, UUID]:
    report_ids: dict[str, UUID] = {}
    for report in reports:
        report_id = report.logical_id
        report_ids[str(report.logical_id)] = report_id
        processing_state = (
            "quarantined"
            if report.expected.outcome == "quarantine_prompt_injection_no_policy_effect"
            else "needs_review"
            if report.expected.category is None
            else "processed"
        )
        session.add(
            ReportModel(
                id=report_id,
                logical_id=report.logical_id,
                public_id=report.public_id,
                receipt_hash=_receipt_hash(report.receipt_seed),
                source_channel="synthetic_seed",
                original_text=report.text,
                language_hint=report.language,
                accepted_at=report.accepted_at,
                consent_version="synthetic-demo-v1",
                locality_label=report.locality_label,
                geography_kind=report.geography_kind,
                geography_source=report.geography_source,
                latitude=Decimal(str(report.latitude)) if report.latitude is not None else None,
                longitude=Decimal(str(report.longitude)) if report.longitude is not None else None,
                location_precision=report.location_precision,
                processing_state=processing_state,
                evidence_class="synthetic_demo",
                is_seed=True,
            )
        )
        interpretation_id = stable_id("interpretation", report.public_id)
        session.add(
            ReportInterpretationModel(
                id=interpretation_id,
                report_id=report_id,
                version=1,
                is_active=True,
                result_state=(
                    "needs_review" if report.expected.category is None else "stored_sample"
                ),
                provider="fixture",
                configured_model="stored-sample-v1",
                returned_model="stored-sample-v1",
                prompt_version="report-interpretation-v1",
                schema_version="report-interpretation-schema-v1",
                payload=_interpretation_payload(report),
                evidence_class="ai_derived",
                latency_ms=0,
            )
        )
        if report.expected.safety_signal:
            session.add(
                SafetyReviewModel(
                    id=stable_id("safety-review", report.public_id),
                    report_id=report_id,
                    interpretation_id=interpretation_id,
                    signal_code=report.expected.safety_signal,
                    rule_version="safety-v1",
                    state="pending",
                )
            )
        session.add(
            ProcessingJobModel(
                id=stable_id("processing-job", report.public_id),
                report_id=report_id,
                job_type="interpret_and_relate",
                state="succeeded",
                attempt_count=1,
                max_attempts=3,
                available_at=report.accepted_at,
                dedupe_key=f"seed:{report.public_id}:interpretation:v1",
            )
        )
    return report_ids


def _insert_incidents(
    session: Session, truth: dict[str, Any], report_ids: dict[str, UUID]
) -> dict[str, UUID]:
    incident_ids: dict[str, UUID] = {}
    for incident in truth["incidents"]:
        incident_id = UUID(incident["id"])
        incident_ids[incident["key"]] = incident_id
        event_start = datetime.fromisoformat(incident["event_start"])
        session.add(
            IncidentModel(
                id=incident_id,
                logical_id=incident_id,
                version=1,
                is_active=True,
                category=incident["category"],
                event_start=event_start,
                event_end=event_start + timedelta(hours=3),
                locality_label=incident["locality"],
                lifecycle=incident["lifecycle"],
                rule_version="grouping-v1",
                evidence_class="synthetic_demo",
            )
        )
        for logical_report_id in incident["report_ids"]:
            report_id = report_ids[logical_report_id]
            session.add(
                IncidentReportLinkModel(
                    id=stable_id("incident-report-link", f"{incident['key']}:{logical_report_id}"),
                    incident_id=incident_id,
                    report_id=report_id,
                    version=1,
                    is_active=True,
                    relation_type="same_incident",
                    feature_evidence={
                        "category_gate": "pass",
                        "time_gate": "pass",
                        "location_gate": "pass",
                        "source": "synthetic_ground_truth",
                    },
                    confidence_band="reviewed_ground_truth",
                    state="confirmed",
                    rule_version="grouping-v1",
                )
            )
    for source_key, target_key in truth["recurrence_relationships"]:
        session.add(
            IncidentRelationshipModel(
                id=stable_id("incident-relationship", f"{source_key}:{target_key}"),
                source_incident_id=incident_ids[source_key],
                target_incident_id=incident_ids[target_key],
                version=1,
                is_active=True,
                relation_type="recurrence",
                reason_evidence={
                    "category_gate": "pass",
                    "distinct_incidents": True,
                    "within_days": 90,
                    "source": "synthetic_ground_truth",
                },
                state="confirmed",
                rule_version="grouping-v1",
            )
        )
    return incident_ids


def _insert_needs(session: Session, truth: dict[str, Any], incident_ids: dict[str, UUID]) -> int:
    for need in truth["needs"]:
        need_id = UUID(need["id"])
        session.add(
            SuspectedNeedModel(
                id=need_id,
                logical_id=need_id,
                version=1,
                entity_version=1,
                is_active=True,
                category=need["category"],
                geography_label=need["geography_label"],
                geography_kind=need["geography_kind"],
                geography_membership_method=need["geography_membership_method"],
                hypothesis=need["hypothesis"],
                alternative_state={
                    "reviewed": True,
                    "root_cause": "unknown",
                    "unresolved": ["planned interruption", "distribution constraint", "leakage"],
                },
                lifecycle=need["lifecycle"],
                evidence_class="synthetic_demo",
            )
        )
        for incident_key in need["incident_keys"]:
            session.add(
                NeedIncidentLinkModel(
                    id=stable_id("need-incident-link", f"{need['key']}:{incident_key}"),
                    need_id=need_id,
                    incident_id=incident_ids[incident_key],
                    version=1,
                    is_active=True,
                    relationship_reason={
                        "type": "confirmed_recurrence",
                        "source": "synthetic_ground_truth",
                    },
                )
            )
        priority = need["priority"]
        evidence_refs = sorted(
            {
                reference
                for component in priority["components"].values()
                for reference in component["evidence"]
            }
        )
        session.add(
            PriorityAssessmentModel(
                id=stable_id("priority-assessment", need["key"]),
                need_id=need_id,
                version=1,
                is_active=True,
                eligible=priority["eligible"],
                components=priority["components"],
                evidence_refs=evidence_refs,
                priority_band=priority["band"],
                completeness={"known_components": 4, "total_components": 4},
                sensitivity=priority["sensitivity"],
                abstention_codes=priority["abstention_codes"],
                rule_version="priority-v1",
                profile_version="balanced",
            )
        )
        candidate = need["candidate"]
        session.add(
            ProjectCandidateModel(
                id=stable_id("project-candidate", need["key"]),
                need_id=need_id,
                version=1,
                is_active=True,
                catalogue_key=candidate["catalogue_key"],
                catalogue_version="assessment-catalogue-v1",
                conditional_wording=candidate["conditional_wording"],
                works_overlap=candidate["works_overlap"],
                prerequisites=candidate["prerequisites"],
                uncertainty=["Technical cause unknown", "Local service outcome is Synthetic Demo"],
                lifecycle="review_ready",
            )
        )
    return len(truth["needs"])


def seed_database(session: Session, root: Path | None = None) -> SeedResult:
    assets_root = root or repository_root()
    load_policy_bundle(assets_root)
    reports, truth, _manifest = validate_demo_assets(assets_root)
    _public_manifest, public_observations = validate_public_assets(assets_root)

    existing_snapshot = session.scalar(
        select(DatasetSnapshotModel).where(DatasetSnapshotModel.version == "bengaluru-water-v1")
    )
    if existing_snapshot is not None:
        report_count = session.scalar(
            select(func.count()).select_from(ReportModel).where(ReportModel.is_seed.is_(True))
        )
        incident_count = session.scalar(select(func.count()).select_from(IncidentModel))
        need_count = session.scalar(select(func.count()).select_from(SuspectedNeedModel))
        if (report_count, incident_count, need_count) != (60, 8, 2):
            raise ConfigurationError(
                "Existing demo seed is incomplete; refusing to patch it in place"
            )
        return SeedResult(False, 60, 8, 2, len(public_observations))

    public_count = _insert_public_snapshot(session, assets_root)
    report_ids = _insert_reports(session, reports)
    incident_ids = _insert_incidents(session, truth, report_ids)
    need_count = _insert_needs(session, truth, incident_ids)
    session.flush()
    return SeedResult(True, len(reports), len(incident_ids), need_count, public_count)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the immutable CivicLens demo seed")
    parser.add_argument("--confirm-demo", action="store_true")
    args = parser.parse_args()
    settings: Settings = get_settings()
    if not args.confirm_demo:
        raise SystemExit("Refusing to seed without --confirm-demo")
    if not settings.demo_mode_enabled or settings.app_env == "production":
        raise SystemExit("Demo seeding is disabled in this environment")

    engine = build_engine(settings)
    factory = build_session_factory(engine)
    with factory.begin() as session:
        result = seed_database(session)
    print(
        f"seed inserted={result.inserted} reports={result.reports} "
        f"incidents={result.incidents} needs={result.needs} public={result.public_evidence}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
