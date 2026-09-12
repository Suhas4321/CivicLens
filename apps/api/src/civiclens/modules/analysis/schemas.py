from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["en", "kn", "hi", "mixed", "unknown"]
Category = Literal[
    "water_supply",
    "water_quality",
    "roads",
    "electrical_safety",
    "waste",
    "noise",
    "other",
    "unknown",
]
SafetyCode = Literal["POSSIBLE_WATER_CONTAMINATION", "EXPOSED_ELECTRICAL_HAZARD"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterpretationRequest(StrictModel):
    report_id: UUID
    text: str = Field(min_length=4, max_length=2000)
    language_hint: Language
    locality_label: str = Field(min_length=3, max_length=160)
    audio_data: bytes | None = Field(default=None, max_length=6 * 1024 * 1024)
    audio_content_type: Literal["audio/webm"] | None = None

    @model_validator(mode="after")
    def audio_fields_are_a_pair(self) -> InterpretationRequest:
        if (self.audio_data is None) != (self.audio_content_type is None):
            raise ValueError("audio bytes and content type must be supplied together")
        return self


class SafetySignalCandidate(StrictModel):
    code: SafetyCode
    confidence: Literal["supported", "uncertain"]
    contexts: list[str] = Field(default_factory=lambda: list[str](), max_length=4)
    reason: str = Field(min_length=4, max_length=240)


class ReportInterpretation(StrictModel):
    detected_language: Language
    category: Category
    subtype: str | None = Field(default=None, max_length=80)
    summary: str = Field(min_length=8, max_length=400)
    time_assertion: str | None = Field(default=None, max_length=160)
    place_assertion: str | None = Field(default=None, max_length=160)
    service_assertion: str | None = Field(default=None, max_length=240)
    safety_signal_candidates: list[SafetySignalCandidate] = Field(
        default_factory=lambda: list[SafetySignalCandidate](), max_length=4
    )
    uncertainties: list[str] = Field(default_factory=lambda: list[str](), max_length=8)


class InterpretationEnvelope(StrictModel):
    interpretation: ReportInterpretation
    provider: str
    configured_model: str
    returned_model: str | None
    prompt_version: Literal["report-interpretation-v1"]
    schema_version: Literal["report-interpretation-schema-v1"]
    result_class: Literal["stored_sample", "fresh_fixture", "fresh_ai"]
    latency_ms: int = Field(ge=0)
