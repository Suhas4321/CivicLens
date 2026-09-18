from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReportCreateRequest(BaseModel):
    # Four characters, not twenty.
    #
    # Twenty characters of prose is a real barrier for the people this is for: a
    # street vendor typing Kannada on a phone, or somebody who does not write
    # comfortably in any language. The category, the photo and the location now
    # carry the classification, the severity and the grouping, so the text only
    # has to be enough for the interpreter to check what the reporter meant.
    #
    # The floor is 4 because that is `analysis.schemas.InterpretationRequest.text`'s
    # own minimum. Keeping the two equal is deliberate: a report accepted here that
    # the interpreter then refuses would crash the analysis background task rather
    # than degrade, so these two numbers must move together.
    description: str = Field(min_length=4, max_length=2000)
    language_hint: Literal["en", "kn", "hi", "mixed"] = "en"
    locality_label: str = Field(min_length=3, max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    consent: Literal[True]
    synthetic_demo_confirmation: Literal[True]

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> ReportCreateRequest:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class ReportAccepted(BaseModel):
    public_id: str
    status: Literal["received"]
    accepted_at: datetime
    message: str


class ReceiptStatus(BaseModel):
    public_id: str
    status: Literal["received", "analysing", "processed", "needs_review"]
    accepted_at: datetime
    generalized_area: str
    evidence_class: Literal["synthetic_demo"]
    analysis_class: Literal["pending", "stored_sample", "fresh_fixture", "fresh_ai"]
    analysis_state: str
    message: str
