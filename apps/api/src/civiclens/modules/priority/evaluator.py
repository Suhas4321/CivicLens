from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from civiclens.bootstrap.policy import load_policy_bundle

ComponentCode = Literal[
    "scale_exposure",
    "persistence_spread",
    "service_disadvantage",
    "consequence_if_unaddressed",
]
Band = Literal["high", "moderate", "lower", "not_comparable"]
COMPONENT_ORDER: tuple[ComponentCode, ...] = (
    "scale_exposure",
    "persistence_spread",
    "service_disadvantage",
    "consequence_if_unaddressed",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComponentRating(StrictModel):
    rating: int | None = Field(default=None, ge=0, le=3)
    evidence_refs: list[str]
    rationale: str

    @model_validator(mode="after")
    def known_rating_requires_evidence(self) -> ComponentRating:
        if self.rating is not None and not self.evidence_refs:
            raise ValueError("a known rating requires evidence references")
        return self


class PriorityInput(StrictModel):
    components: dict[ComponentCode, ComponentRating]

    @model_validator(mode="after")
    def exact_components(self) -> PriorityInput:
        if set(self.components) != set(COMPONENT_ORDER):
            raise ValueError("all four priority components are required exactly once")
        return self


class ProfileAssessment(StrictModel):
    profile: str
    score: float | None
    band: Band


class PriorityResult(StrictModel):
    eligible: bool
    band: Band
    profiles: list[ProfileAssessment]
    sensitivity_status: Literal["stable", "sensitive", "not_comparable"]
    abstention_codes: list[str]
    policy_version: Literal["priority-v1"] = "priority-v1"
    policy_notice: str = "Prototype policy assumptions; not an adopted government ranking policy."


def evaluate_priority(value: PriorityInput) -> PriorityResult:
    policy = load_policy_bundle().priority
    missing = [code for code in COMPONENT_ORDER if value.components[code].rating is None]
    if missing and policy.unknown_prevents_comparison:
        return PriorityResult(
            eligible=False,
            band="not_comparable",
            profiles=[
                ProfileAssessment(profile=profile.key, score=None, band="not_comparable")
                for profile in policy.profiles
            ],
            sensitivity_status="not_comparable",
            abstention_codes=[f"MISSING_{code.upper()}" for code in missing],
        )

    assessments: list[ProfileAssessment] = []
    for profile in policy.profiles:
        weighted_total = 0
        for code in COMPONENT_ORDER:
            rating = value.components[code].rating
            if rating is None:
                raise AssertionError("unknown rating passed eligibility gate")
            weighted_total += rating * profile.weights[code]
        score = round(weighted_total / 100, 3)
        assessments.append(ProfileAssessment(profile=profile.key, score=score, band=_band(score)))

    bands = {assessment.band for assessment in assessments}
    balanced = next(item for item in assessments if item.profile == "balanced")
    return PriorityResult(
        eligible=True,
        band=balanced.band,
        profiles=assessments,
        sensitivity_status="stable" if len(bands) == 1 else "sensitive",
        abstention_codes=[],
    )


def _band(score: float) -> Band:
    bands = load_policy_bundle().priority.bands
    if score >= bands.high_minimum:
        return "high"
    if score >= bands.moderate_minimum:
        return "moderate"
    return "lower"
