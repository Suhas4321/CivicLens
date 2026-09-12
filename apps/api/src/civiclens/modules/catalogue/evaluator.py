from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from civiclens.bootstrap.policy import CatalogueItem, load_policy_bundle

PrerequisiteState = Literal["unknown", "required", "satisfied", "not_applicable"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateRequest(StrictModel):
    category: str
    pathway: Literal["suspected_need", "operational_pattern"]
    root_cause_verified: bool
    prerequisite_states: dict[str, PrerequisiteState] = Field(default_factory=dict)
    works_overlap: Literal["none", "possible", "confirmed"]


class CandidatePrerequisite(StrictModel):
    code: str
    state: PrerequisiteState


class ConditionalCandidate(StrictModel):
    catalogue_key: str
    candidate_type: Literal["assessment", "operational_review", "feasibility"]
    wording: str
    prerequisites: list[CandidatePrerequisite]
    works_overlap: Literal["none", "possible", "confirmed"]
    lifecycle: Literal["conditional"] = "conditional"
    decision_boundary: str = (
        "A human may refer this for feasibility; CivicLens does not approve it."
    )
    catalogue_version: Literal["assessment-catalogue-v1"] = "assessment-catalogue-v1"


class CandidateResult(StrictModel):
    candidate: ConditionalCandidate | None
    abstention_codes: list[str]


def generate_candidate(request: CandidateRequest) -> CandidateResult:
    catalogue = load_policy_bundle().catalogue
    eligible_items = [item for item in catalogue.items if request.category in item.categories]
    if not eligible_items:
        return CandidateResult(candidate=None, abstention_codes=["CATEGORY_OUTSIDE_CATALOGUE"])

    selected = _select_item(eligible_items, request)
    if selected is None:
        return CandidateResult(candidate=None, abstention_codes=["NO_PERMITTED_PATHWAY"])

    states = dict(request.prerequisite_states)
    if "verified_root_cause" in selected.prerequisites:
        states["verified_root_cause"] = "satisfied" if request.root_cause_verified else "required"
    prerequisites = [
        CandidatePrerequisite(code=code, state=states.get(code, "unknown"))
        for code in selected.prerequisites
    ]
    wording = selected.wording
    if request.works_overlap != "none":
        wording += " Verify the scope and status of potentially overlapping works."

    return CandidateResult(
        candidate=ConditionalCandidate(
            catalogue_key=selected.key,
            candidate_type=selected.candidate_type,
            wording=wording,
            prerequisites=prerequisites,
            works_overlap=request.works_overlap,
        ),
        abstention_codes=[],
    )


def _select_item(
    eligible_items: list[CatalogueItem], request: CandidateRequest
) -> CatalogueItem | None:
    by_key = {item.key: item for item in eligible_items}
    capital = by_key.get("capital_feasibility_referral")
    if request.pathway == "suspected_need":
        capital_ready = (
            request.root_cause_verified
            and capital is not None
            and all(
                request.prerequisite_states.get(code) == "satisfied"
                for code in capital.prerequisites
                if code != "verified_root_cause"
            )
        )
        if capital_ready:
            return capital
        return by_key.get("field_service_verification")
    return by_key.get("operational_coordination_review")
