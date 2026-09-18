from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from civiclens.domain.categories import load_category_config

CATEGORY_CONFIG_VERSION = "bengaluru-south-v1"


@lru_cache
def _allowed_service_codes() -> frozenset[str]:
    """The codes a reporter may choose, read from versioned policy.

    Loaded from ``config/categories/<version>.json`` rather than restated as a
    ``Literal`` here, because the web form's category picker reads the same file
    through the ``@config`` alias. Two hand-maintained copies would drift, and the
    first symptom of that drift is a citizen shown a deadline the API does not hold
    anybody to.
    """
    return load_category_config(CATEGORY_CONFIG_VERSION).codes


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
    # What kind of problem this is, chosen by the reporter from the picker.
    #
    # Optional, not required, and that is a decision about who bears the cost of
    # uncertainty. A reporter who cannot tell whether a wet patch is a burst main or
    # sewage should still be able to send the report; making the field mandatory
    # would turn "I don't know which box this is" into "I cannot report this at
    # all". Omitted means the interpreter proposes a category and an officer
    # confirms it. What it must never mean is a silently assumed default, because
    # the code chosen here selects the agency and the statutory deadline.
    service_code: str | None = Field(default=None, max_length=48)
    consent: Literal[True]
    synthetic_demo_confirmation: Literal[True]

    @field_validator("service_code")
    @classmethod
    def service_code_is_known(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _allowed_service_codes():
            # Refused rather than coerced to OTHER. An unknown code means the client
            # and this catalogue version disagree, and quietly filing the report
            # under OTHER would strip the deadline the reporter was shown before
            # they pressed send.
            raise ValueError("service_code is not a known category")
        return value

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> ReportCreateRequest:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class ReportAccepted(BaseModel):
    public_id: str
    status: Literal["received"]
    accepted_at: datetime
    # Acknowledged explicitly instead of left for the client to assume.
    #
    # A reporter who attached a photo on a weak connection has no way to tell
    # whether it arrived, and "the request returned 202" does not answer that -- the
    # coordinate bug fixed in the previous change was exactly a 202 for data that
    # was thrown away. These two fields make the receipt state what the server
    # actually kept, so the same class of silent loss cannot recur unnoticed for
    # photos or for the category.
    photo_received: bool = False
    service_code_recorded: str | None = None
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
