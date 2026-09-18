from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Imported rather than restated, so the contract the web client generates from
# `openapi.json` cannot drift from the values the grouping code actually produces.
from civiclens.modules.relationships.grouping import ConfidenceBand, JoinReason


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
    # On the lane item and not only in the detail view, because it changes what an
    # officer does next. "There is a photo" means this one can be judged from a
    # desk; the rest need a phone call or a visit, and that is the difference
    # between a morning that clears twenty items and one that clears four.
    has_photo: bool = False
    # The category the reporter chose, which is what routes the item to BWSSB,
    # BESCOM, BBMP or BMTC. Distinct from `category`, which is the AI's reading of
    # the text: when the two disagree the officer needs to see both, so neither
    # field may be derived from the other.
    service_code: str | None = None
    # How sure the system is that the reports counted together are one problem, and
    # ``None`` when there is only one report and therefore nothing being claimed. It
    # sits next to `report_count` because the two are read together: "3 reports" is a
    # different instruction depending on whether that 3 is established or proposed.
    grouping_confidence: ConfidenceBand | None = None


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


class GroupingJoin(ApiModel):
    """Why one report is counted inside a group, in the numbers that decided it.

    An officer who thinks two complaints were wrongly merged is owed the distance,
    the hours and the category match that merged them. A confidence band on its own
    is not something anybody can argue with, and "the system grouped them" is the
    answer that makes a person stop trusting the count instead of correcting it.

    Every field is nullable because the evidence available depends on what the two
    reports carried: a report located only by the name of a locality has no distance
    to give, and the intent verdict is absent until a model reads the descriptions.
    """

    reason: JoinReason
    same_category: bool | None = None
    hours_apart: float | None = None
    # Between this report and the first report in the group -- never between
    # neighbours in a chain, because every member is compared against that lead.
    distance_km: float | None = None
    same_locality_label: bool | None = None
    geometry_band: str | None = None
    intent_verdict: str | None = None
    # Differing bits out of 64 between the two attached photos. Content-derived, so
    # it says "these two photographs look like the same subject" and nothing about
    # where either was taken.
    photo_hash_distance: int | None = None


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
    service_code: str | None = None
    # Whether to offer the image, and nothing about the image itself. The bytes are
    # fetched from `GET /api/v1/officer/reports/{id}/photo`, a path the client
    # builds from this id. Deliberately not an absolute URL in the payload: behind a
    # proxy the host this process thinks it is serving is frequently not the host the
    # officer's browser reached, and a wrong absolute URL fails silently as a broken
    # image where a relative path cannot.
    has_photo: bool = False
    # Codes only -- never the flag details. The stored detail strings carry a
    # rounded distance ("EXIF location is 500 m from the confirmed pin"), and an
    # officer is told "near" or "far" and no more. Publishing the metres would
    # reconstruct an approximate ring around wherever the reporter was standing,
    # which is the thing the EXIF stripping exists to prevent.
    photo_integrity_flags: list[str] = Field(default_factory=list)
    # Present on every report in a grouped item, including the first one, whose
    # reason is ``lead``. ``None`` on the seeded incidents, where the links were
    # authored rather than derived.
    joined_by: GroupingJoin | None = None


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
