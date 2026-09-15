from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReviewAction = Literal[
    "confirm_bounded_incident",
    "keep_separate",
    "verify_safety",
    "refer_safety",
    "dismiss_safety",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowReviewCreate(StrictModel):
    action: ReviewAction
    reason: str = Field(min_length=8, max_length=600)
    expected_version: int = Field(ge=1)


class WorkflowReview(StrictModel):
    id: UUID
    session_id: UUID
    report_id: UUID
    action: ReviewAction
    reason: str
    evidence_digest: str
    expected_version: int
    entity_version_after: int
    supersedes_id: UUID | None
    created_at: datetime
    record_notice: str = (
        "Append-only synthetic review action. It does not verify the citizen claim or "
        "authorize an official response."
    )
