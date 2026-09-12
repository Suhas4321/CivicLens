from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NeedScope(StrictModel):
    geography_label: str
    geography_kind: str
    geography_vintage: str | None = None


class EvidenceDescriptor(StrictModel):
    evidence_key: str
    geography_label: str
    geography_kind: str
    geography_vintage: str | None = None
    semantics: Literal[
        "observed", "projected", "plan", "administrative_status", "synthetic_verification"
    ]
    role: Literal["local_decision_evidence", "broader_context"]


class CompatibilityResult(StrictModel):
    contributes_to_rating: bool
    reason_code: Literal[
        "COMPATIBLE_LOCAL_EVIDENCE",
        "BROADER_CONTEXT_ONLY",
        "GEOGRAPHY_MISMATCH",
        "VINTAGE_MISMATCH",
        "SEMANTICS_NOT_RATING_EVIDENCE",
    ]


def evaluate_compatibility(scope: NeedScope, evidence: EvidenceDescriptor) -> CompatibilityResult:
    if evidence.role == "broader_context":
        return CompatibilityResult(
            contributes_to_rating=False,
            reason_code="BROADER_CONTEXT_ONLY",
        )
    if (
        _normalize(scope.geography_label) != _normalize(evidence.geography_label)
        or scope.geography_kind != evidence.geography_kind
    ):
        return CompatibilityResult(
            contributes_to_rating=False,
            reason_code="GEOGRAPHY_MISMATCH",
        )
    if (
        scope.geography_vintage is not None
        and evidence.geography_vintage is not None
        and scope.geography_vintage != evidence.geography_vintage
    ):
        return CompatibilityResult(
            contributes_to_rating=False,
            reason_code="VINTAGE_MISMATCH",
        )
    if evidence.semantics in {"projected", "plan", "administrative_status"}:
        return CompatibilityResult(
            contributes_to_rating=False,
            reason_code="SEMANTICS_NOT_RATING_EVIDENCE",
        )
    return CompatibilityResult(
        contributes_to_rating=True,
        reason_code="COMPATIBLE_LOCAL_EVIDENCE",
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
