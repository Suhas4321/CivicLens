from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from civiclens.bootstrap.policy import load_policy_bundle
from civiclens.modules.analysis.schemas import ReportInterpretation, SafetyCode


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafetyFinding(StrictModel):
    signal_code: SafetyCode
    state: Literal["pending"] = "pending"
    action: Literal["human_verification"] = "human_verification"
    reason_code: Literal["SUPPORTED_SIGNAL", "UNCERTAIN_SIGNAL", "HIGH_CONSEQUENCE_CONTEXT"]
    explanation: str = Field(min_length=8, max_length=300)
    rule_version: Literal["safety-v1"] = "safety-v1"


def evaluate_safety(interpretation: ReportInterpretation) -> list[SafetyFinding]:
    """Route controlled candidates to review; never calculate planning priority here."""

    policy = load_policy_bundle().safety
    configured = {signal.code: signal for signal in policy.signals}
    findings: list[SafetyFinding] = []

    for candidate in interpretation.safety_signal_candidates:
        signal = configured.get(candidate.code)
        if signal is None:
            continue
        high_contexts = set(signal.high_consequence_contexts)
        has_high_context = bool(high_contexts.intersection(candidate.contexts))
        if candidate.confidence == "uncertain" and not policy.uncertain_means_review:
            continue

        if has_high_context:
            reason_code = "HIGH_CONSEQUENCE_CONTEXT"
        elif candidate.confidence == "uncertain":
            reason_code = "UNCERTAIN_SIGNAL"
        else:
            reason_code = "SUPPORTED_SIGNAL"

        findings.append(
            SafetyFinding(
                signal_code=candidate.code,
                reason_code=reason_code,
                explanation=(
                    "Operational safety review is required regardless of report count or "
                    "planning priority. The underlying hazard remains unverified."
                ),
            )
        )
    return findings
