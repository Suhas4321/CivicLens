from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from civiclens.bootstrap.policy import repository_root
from civiclens.infrastructure.db.seed_contracts import (
    PublicObservation,
    SeedReport,
    validate_demo_assets,
    validate_public_assets,
)
from civiclens.modules.planning.schemas import (
    CandidatePrerequisite,
    EvidenceItem,
    IncidentDetail,
    IncidentSummary,
    LaneItem,
    NeedSummary,
    NeedWorkspace,
    OfficerOverview,
    PriorityComponent,
    PrioritySummary,
    ProjectCandidate,
    ReportEvidence,
)
from civiclens.shared.errors import NotFoundError
from civiclens.shared.primitives import stable_id

COMPONENT_LABELS = {
    "scale_exposure": "Scale / exposure",
    "persistence_spread": "Persistence / spread",
    "service_disadvantage": "Service disadvantage",
    "consequence_if_unaddressed": "Consequence if unaddressed",
}

COMPONENT_RATIONALES = {
    "scale_exposure": "Uses compatible verified exposure evidence; never raw report count.",
    "persistence_spread": "Uses confirmed distinct incidents across time, not duplicate volume.",
    "service_disadvantage": "Requires compatible service evidence or a labelled demo finding.",
    "consequence_if_unaddressed": "Uses enduring consequences; acute safety stays separate.",
}


class GoldenDemoReadService:
    """Read-only projection over the frozen seed assets used by the first vertical demo."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._reports, self._truth, self._manifest = validate_demo_assets(root)
        _, self._public_observations = validate_public_assets(root)
        self._reports_by_id = {str(report.logical_id): report for report in self._reports}
        self._incidents_by_id = {
            UUID(incident["id"]): incident for incident in self._truth["incidents"]
        }
        self._incidents_by_key = {
            incident["key"]: incident for incident in self._truth["incidents"]
        }
        self._needs_by_id = {UUID(need["id"]): need for need in self._truth["needs"]}

    def overview(self) -> OfficerOverview:
        hospital = next(report for report in self._reports if report.story == "hospital_safety")
        pothole = self._incidents_by_key["pothole-one"]
        planned = self._incidents_by_key["planned-water-one"]
        planning_needs = [self._need_lane_item(need) for need in self._truth["needs"]]
        return OfficerOverview(
            data_version=self._manifest.version,
            environment_label="Demo Officer — Synthetic Environment",
            disclosure=(
                "All citizen reports, local findings and decisions are synthetic. Dated public "
                "facts are context only within their stated geography and semantics."
            ),
            safety_review=[
                LaneItem(
                    id=stable_id("safety-review", hospital.public_id),
                    title="Possible water-quality hazard at a synthetic hospital",
                    status="Pending human verification",
                    category="water_quality",
                    locality=hospital.locality_label,
                    report_count=1,
                    classification="ai_derived",
                    explanation=(
                        "A dangerous single signal is reviewed immediately and never placed in "
                        "the planning ranking."
                    ),
                )
            ],
            operational_incidents=[
                self._incident_lane_item(
                    pothole,
                    "High report volume still represents one bounded operational incident.",
                ),
                self._incident_lane_item(
                    planned,
                    "A planned interruption remains operational; it does not prove recurrence.",
                ),
            ],
            planning_needs=planning_needs,
        )

    def list_needs(self) -> list[NeedSummary]:
        return [self._need_summary(need) for need in self._truth["needs"]]

    def need_workspace(self, need_id: UUID) -> NeedWorkspace:
        need = self._needs_by_id.get(need_id)
        if need is None:
            raise NotFoundError("Suspected need not found")
        priority_data = need["priority"]
        candidate_data = need["candidate"]
        incident_summaries = [
            self._incident_summary(self._incidents_by_key[key]) for key in need["incident_keys"]
        ]
        components = [
            PriorityComponent(
                code=code,
                label=COMPONENT_LABELS[code],
                rating=priority_data["components"][code]["rating"],
                rationale=COMPONENT_RATIONALES[code],
                evidence_refs=priority_data["components"][code]["evidence"],
            )
            for code in COMPONENT_LABELS
        ]
        evidence = [
            self._evidence_item(item, need["key"]) for item in self._select_evidence(need["key"])
        ]
        return NeedWorkspace(
            data_version=self._manifest.version,
            need=self._need_summary(need),
            hypothesis=need["hypothesis"],
            hypothesis_label="Suspected Civic Need",
            alternative_hypotheses=[
                "Planned or temporary interruption",
                "Pump or electricity interruption",
                "Isolated pipe failure or leakage",
                "Distribution or capacity constraint",
                "Maintenance backlog",
            ],
            incidents=incident_summaries,
            evidence=evidence,
            priority=PrioritySummary(
                eligible=priority_data["eligible"],
                band=priority_data["band"],
                components=components,
                sensitivity_status=priority_data["sensitivity"]["status"],
                sensitivity_profiles=priority_data["sensitivity"]["profiles"],
                abstention_codes=priority_data["abstention_codes"],
                policy_notice=(
                    "Prototype policy assumption: 30/25/25/20. Components are 0–3 or unknown; "
                    "unknown required evidence prevents comparison."
                ),
            ),
            candidate=ProjectCandidate(
                id=stable_id("project-candidate", need["key"]),
                catalogue_key=candidate_data["catalogue_key"],
                catalogue_version="assessment-catalogue-v1",
                label="Conditional assessment candidate",
                conditional_wording=candidate_data["conditional_wording"],
                lifecycle="review_ready",
                works_overlap_outcome=candidate_data["works_overlap"]["outcome"],
                works_overlap_evidence=candidate_data["works_overlap"]["evidence"],
                prerequisites=[
                    CandidatePrerequisite.model_validate(item)
                    for item in candidate_data["prerequisites"]
                ],
                uncertainty=[
                    "Technical cause is unknown.",
                    "Public program status does not prove local service outcomes.",
                ],
                decision_boundary=(
                    "This is a referral for assessment, not a construction project, budget, "
                    "procurement action or approval."
                ),
            ),
            evidence_notice=(
                "Report count is evidence volume, never unique citizens or affected population."
            ),
            human_decision_notice=(
                "Only a human Demo Officer may refer, defer or reject. The record freezes the "
                "reviewed evidence digest and never represents project approval."
            ),
        )

    def incident_detail(self, incident_id: UUID) -> IncidentDetail:
        incident = self._incidents_by_id.get(incident_id)
        if incident is None:
            raise NotFoundError("Incident not found")
        reports = [self._reports_by_id[report_id] for report_id in incident["report_ids"]]
        return IncidentDetail(
            data_version=self._manifest.version,
            incident=self._incident_summary(incident),
            reports=[self._report_evidence(report) for report in reports],
            relationship_explanation={
                "category_gate": "pass",
                "time_gate_hours": 72,
                "location_gate_km": 1.5,
                "contradiction_found": False,
                "review_state": "confirmed synthetic ground truth",
            },
            decision_boundary=(
                "This grouping is reviewable synthetic ground truth. Similar text alone cannot "
                "confirm an incident in a real deployment."
            ),
        )

    def _need_lane_item(self, need: dict[str, Any]) -> LaneItem:
        summary = self._need_summary(need)
        return LaneItem(
            id=summary.id,
            title=summary.title,
            status=f"{summary.priority_band.title()} planning attention",
            category=summary.category,
            locality=summary.geography,
            report_count=summary.report_count,
            classification="synthetic_demo",
            explanation=(
                "Distinct incidents recur; public context and evidence limits remain visible."
            ),
        )

    def _incident_lane_item(self, incident: dict[str, Any], explanation: str) -> LaneItem:
        summary = self._incident_summary(incident)
        return LaneItem(
            id=summary.id,
            title=summary.title,
            status="Operational incident",
            category=summary.category,
            locality=summary.locality,
            report_count=summary.report_count,
            classification="synthetic_demo",
            explanation=explanation,
        )

    def _need_summary(self, need: dict[str, Any]) -> NeedSummary:
        incidents = [self._incidents_by_key[key] for key in need["incident_keys"]]
        return NeedSummary(
            id=UUID(need["id"]),
            key=need["key"],
            title=(
                "Recurring water-service symptoms in Mahadevapura demo slice"
                if need["key"] == "maha-recurring-water"
                else "Recurring water-service symptoms in comparison demo slice"
            ),
            category=need["category"],
            geography=need["geography_label"],
            geography_kind=need["geography_kind"],
            geography_membership_method=need["geography_membership_method"],
            lifecycle=need["lifecycle"],
            incident_count=len(incidents),
            report_count=sum(len(incident["report_ids"]) for incident in incidents),
            priority_band=need["priority"]["band"],
            classification="synthetic_demo",
        )

    def _incident_summary(self, incident: dict[str, Any]) -> IncidentSummary:
        title = {
            "pothole-one": "One high-volume pothole incident",
            "planned-water-one": "Planned temporary water interruption",
            "remote-water-one": "Geographically separate water incident",
        }.get(incident["key"], f"Bounded incident · {incident['locality']}")
        return IncidentSummary(
            id=UUID(incident["id"]),
            key=incident["key"],
            title=title,
            category=incident["category"],
            locality=incident["locality"],
            event_start=incident["event_start"],
            report_count=len(incident["report_ids"]),
            relationship_state="confirmed synthetic ground truth",
            classification="synthetic_demo",
        )

    @staticmethod
    def _report_evidence(report: SeedReport) -> ReportEvidence:
        return ReportEvidence(
            id=report.logical_id,
            public_id=report.public_id,
            original_text=report.text,
            language=report.language,
            accepted_at=report.accepted_at,
            locality=report.locality_label,
            interpretation_summary=(
                "Stored sample interpretation: reporter states a synthetic civic symptom; "
                "technical cause is unknown."
            ),
            classification="synthetic_demo",
            interpretation_classification="ai_derived",
        )

    def _select_evidence(self, need_key: str) -> list[PublicObservation]:
        if need_key == "maha-recurring-water":
            return self._public_observations
        allowed = {
            "jica_project_zone_count",
            "synthetic_comparison_scope",
            "synthetic_comparison_finding",
        }
        return [item for item in self._public_observations if item.evidence_key in allowed]

    @staticmethod
    def _evidence_item(item: PublicObservation, need_key: str) -> EvidenceItem:
        contributes = item.evidence_class == "synthetic_demo" and (
            (need_key == "maha-recurring-water" and "primary_need" in item.evidence_key)
            or (need_key != "maha-recurring-water" and "comparison" in item.evidence_key)
        )
        if item.period_start and item.period_end:
            reference_period = (
                str(item.period_start)
                if item.period_start == item.period_end
                else f"{item.period_start} to {item.period_end}"
            )
        else:
            reference_period = None
        value: str | float | None = item.value_text
        if item.value_numeric is not None:
            value = item.value_numeric
        return EvidenceItem(
            key=item.evidence_key,
            label=item.label,
            classification=item.evidence_class,
            kind=item.kind,
            value=value,
            unit=item.unit,
            geography=item.geography_label,
            geography_kind=item.geography_kind,
            geography_vintage=item.geography_vintage,
            reference_period=reference_period,
            semantics=item.semantics,
            source_url=item.source_url,
            transformation=item.transformation,
            contributes_to_rating=contributes,
            role="local_decision_evidence" if contributes else "broader_context",
            supported_inferences=item.supported_inferences,
            prohibited_inferences=item.prohibited_inferences,
        )


@lru_cache
def get_golden_demo_read_service() -> GoldenDemoReadService:
    return GoldenDemoReadService(repository_root())
