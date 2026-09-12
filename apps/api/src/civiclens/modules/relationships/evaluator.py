from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from civiclens.bootstrap.policy import load_policy_bundle


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportFeatures(StrictModel):
    report_id: UUID
    category: str
    event_at: datetime
    locality_label: str
    latitude: float | None = None
    longitude: float | None = None

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> ReportFeatures:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("coordinates must be supplied together")
        return self


class SameIncidentDecision(StrictModel):
    relation_type: Literal["same_incident", "separate"]
    state: Literal["proposed", "abstained"]
    confidence_band: Literal["high", "review", "not_eligible"]
    feature_evidence: dict[str, str | float | bool | None]
    contradictions: list[str]
    rule_version: Literal["grouping-v1"] = "grouping-v1"


class IncidentFeatures(StrictModel):
    incident_id: UUID
    category: str
    event_start: datetime
    geography_group: str
    links_confirmed: bool


class RecurrenceDecision(StrictModel):
    relation_type: Literal["recurrence", "separate"]
    state: Literal["proposed", "abstained"]
    reason_evidence: dict[str, str | int | bool]
    contradictions: list[str]
    rule_version: Literal["grouping-v1"] = "grouping-v1"


def evaluate_same_incident(left: ReportFeatures, right: ReportFeatures) -> SameIncidentDecision:
    policy = load_policy_bundle().grouping.same_incident
    contradictions: list[str] = []
    if left.report_id == right.report_id:
        contradictions.append("SELF_LINK_PROHIBITED")
    if left.category == "unknown" or right.category == "unknown":
        contradictions.append("CATEGORY_UNKNOWN")
    if policy.requires_category_match and left.category != right.category:
        contradictions.append("CATEGORY_MISMATCH")

    hours_apart = abs((left.event_at - right.event_at).total_seconds()) / 3600
    if hours_apart > policy.max_hours:
        contradictions.append("OUTSIDE_TIME_WINDOW")

    distance_km: float | None = None
    same_locality = _normalize(left.locality_label) == _normalize(right.locality_label)
    if left.latitude is not None and right.latitude is not None:
        distance_km = haversine_km(
            left.latitude,
            left.longitude or 0,
            right.latitude,
            right.longitude or 0,
        )
        if distance_km > policy.max_distance_km:
            contradictions.append("OUTSIDE_DISTANCE_GATE")
        location_support = "coordinate_distance"
        confidence: Literal["high", "review", "not_eligible"] = "high"
    elif same_locality:
        location_support = "matching_reporter_locality_requires_review"
        confidence = "review"
    else:
        location_support = "insufficient_or_conflicting_location"
        confidence = "not_eligible"
        contradictions.append("LOCATION_NOT_SUPPORTED")

    evidence: dict[str, str | float | bool | None] = {
        "category_match": left.category == right.category,
        "hours_apart": round(hours_apart, 3),
        "distance_km": round(distance_km, 3) if distance_km is not None else None,
        "same_locality_label": same_locality,
        "location_support": location_support,
    }
    if contradictions:
        return SameIncidentDecision(
            relation_type="separate",
            state="abstained",
            confidence_band="not_eligible",
            feature_evidence=evidence,
            contradictions=sorted(contradictions),
        )
    return SameIncidentDecision(
        relation_type="same_incident",
        state="proposed",
        confidence_band=confidence,
        feature_evidence=evidence,
        contradictions=[],
    )


def evaluate_recurrence(
    left: IncidentFeatures,
    right: IncidentFeatures,
    *,
    alternative_hypotheses_reviewed: bool,
) -> RecurrenceDecision:
    policy = load_policy_bundle().grouping.recurrence
    contradictions: list[str] = []
    if left.incident_id == right.incident_id:
        contradictions.append("DISTINCT_INCIDENTS_REQUIRED")
    if left.category != right.category:
        contradictions.append("CATEGORY_MISMATCH")
    if _normalize(left.geography_group) != _normalize(right.geography_group):
        contradictions.append("GEOGRAPHY_GROUP_MISMATCH")
    days_apart = abs((left.event_start - right.event_start).total_seconds()) // 86400
    if days_apart > policy.max_days:
        contradictions.append("OUTSIDE_RECURRENCE_WINDOW")
    if policy.requires_confirmed_links and not (left.links_confirmed and right.links_confirmed):
        contradictions.append("INCIDENT_LINKS_NOT_CONFIRMED")
    if policy.requires_alternative_hypothesis_review and not alternative_hypotheses_reviewed:
        contradictions.append("ALTERNATIVE_HYPOTHESES_NOT_REVIEWED")

    evidence: dict[str, str | int | bool] = {
        "category_match": left.category == right.category,
        "days_apart": int(days_apart),
        "same_geography_group": _normalize(left.geography_group)
        == _normalize(right.geography_group),
        "links_confirmed": left.links_confirmed and right.links_confirmed,
        "alternative_hypotheses_reviewed": alternative_hypotheses_reviewed,
    }
    return RecurrenceDecision(
        relation_type="separate" if contradictions else "recurrence",
        state="abstained" if contradictions else "proposed",
        reason_evidence=evidence,
        contradictions=sorted(contradictions),
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    value = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return 2 * radius_km * asin(sqrt(value))


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
