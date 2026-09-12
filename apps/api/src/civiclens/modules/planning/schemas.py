from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LaneItem(ApiModel):
    id: UUID
    title: str
    status: str
    category: str
    locality: str
    report_count: int = Field(ge=0)
    classification: Literal["synthetic_demo", "ai_derived"]
    explanation: str


class OfficerOverview(ApiModel):
    data_version: str
    environment_label: Literal["Demo Officer — Synthetic Environment"]
    disclosure: str
    safety_review: list[LaneItem]
    operational_incidents: list[LaneItem]
    planning_needs: list[LaneItem]


class IncidentSummary(ApiModel):
    id: UUID
    key: str
    title: str
    category: str
    locality: str
    event_start: datetime
    report_count: int
    relationship_state: str
    classification: Literal["synthetic_demo"]


class ReportEvidence(ApiModel):
    id: UUID
    public_id: str
    original_text: str
    language: str
    accepted_at: datetime
    locality: str
    interpretation_summary: str
    classification: Literal["synthetic_demo"]
    interpretation_classification: Literal["ai_derived"]


class IncidentDetail(ApiModel):
    data_version: str
    incident: IncidentSummary
    reports: list[ReportEvidence]
    relationship_explanation: dict[str, str | bool | int | float | None]
    decision_boundary: str


class EvidenceItem(ApiModel):
    key: str
    label: str
    classification: Literal["real_public", "derived_public", "synthetic_demo"]
    kind: str
    value: str | float | None
    unit: str | None
    geography: str
    geography_kind: str
    geography_vintage: str | None
    reference_period: str | None
    semantics: str
    source_url: str
    transformation: str | None
    contributes_to_rating: bool
    role: Literal["local_decision_evidence", "broader_context"]
    supported_inferences: list[str]
    prohibited_inferences: list[str]


class PriorityComponent(ApiModel):
    code: str
    label: str
    rating: int | None = Field(default=None, ge=0, le=3)
    rationale: str
    evidence_refs: list[str]


class PrioritySummary(ApiModel):
    eligible: bool
    band: Literal["high", "moderate", "lower", "not_comparable"]
    components: list[PriorityComponent]
    sensitivity_status: Literal["stable", "sensitive", "not_comparable"]
    sensitivity_profiles: list[str]
    abstention_codes: list[str]
    policy_notice: str


class CandidatePrerequisite(ApiModel):
    code: str
    state: Literal["unknown", "required", "satisfied", "not_applicable"]


class ProjectCandidate(ApiModel):
    id: UUID
    catalogue_key: str
    catalogue_version: str
    label: str
    conditional_wording: str
    lifecycle: str
    works_overlap_outcome: str
    works_overlap_evidence: list[str]
    prerequisites: list[CandidatePrerequisite]
    uncertainty: list[str]
    decision_boundary: str


class NeedSummary(ApiModel):
    id: UUID
    key: str
    title: str
    category: str
    geography: str
    geography_kind: str
    geography_membership_method: str
    lifecycle: str
    incident_count: int
    report_count: int
    priority_band: str
    classification: Literal["synthetic_demo"]


class NeedWorkspace(ApiModel):
    data_version: str
    need: NeedSummary
    hypothesis: str
    hypothesis_label: Literal["Suspected Civic Need"]
    alternative_hypotheses: list[str]
    incidents: list[IncidentSummary]
    evidence: list[EvidenceItem]
    priority: PrioritySummary
    candidate: ProjectCandidate
    evidence_notice: str
    human_decision_notice: str
