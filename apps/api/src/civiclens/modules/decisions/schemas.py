from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Disposition = Literal["refer", "defer", "reject"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DecisionCreateRequest(StrictModel):
    disposition: Disposition
    reason_code: Literal[
        "FIELD_VERIFICATION",
        "FEASIBILITY_REVIEW",
        "EVIDENCE_GAP",
        "WORKS_OVERLAP_REVIEW",
        "NOT_SUPPORTED",
    ]
    reason_text: str | None = Field(default=None, max_length=600)
    next_step: str | None = Field(default=None, max_length=300)
    next_review_date: date | None = None
    expected_entity_version: int = Field(ge=1)

    @model_validator(mode="after")
    def disposition_requirements(self) -> DecisionCreateRequest:
        if self.disposition == "refer" and not self.next_step:
            raise ValueError("a referral requires a next step")
        if self.disposition == "defer" and self.next_review_date is None:
            raise ValueError("a deferral requires a review date")
        return self


class HumanDecision(StrictModel):
    id: UUID
    session_id: UUID
    need_id: UUID
    candidate_id: UUID | None
    disposition: Disposition
    actor_role: Literal["demo_officer"] = "demo_officer"
    reason_code: str
    reason_text: str | None
    next_step: str | None
    next_review_date: date | None
    evidence_digest: str
    expected_entity_version: int
    entity_version_after: int
    supersedes_id: UUID | None
    created_at: datetime
    record_notice: str = (
        "Append-only synthetic demo decision. It records a human disposition, not project approval."
    )
