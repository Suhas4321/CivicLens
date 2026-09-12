from __future__ import annotations

from time import perf_counter

from civiclens.modules.analysis.schemas import (
    InterpretationEnvelope,
    InterpretationRequest,
    ReportInterpretation,
    SafetySignalCandidate,
)


class FixtureInterpreter:
    """Deterministic synthetic-data adapter; never presented as a live model result."""

    def interpret(self, request: InterpretationRequest) -> InterpretationEnvelope:
        started = perf_counter()
        interpretation = _interpret_fixture(request)
        return InterpretationEnvelope(
            interpretation=interpretation,
            provider="fixture",
            configured_model="deterministic-fixture-v1",
            returned_model=None,
            prompt_version="report-interpretation-v1",
            schema_version="report-interpretation-schema-v1",
            result_class="fresh_fixture",
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
        )


def _interpret_fixture(request: InterpretationRequest) -> ReportInterpretation:
    text = request.text.casefold()
    if any(token in text for token in ("ignore previous", "system prompt", "highest priority")):
        return ReportInterpretation(
            detected_language=request.language_hint,
            category="unknown",
            summary="Report contains instruction-like text that is not treated as civic evidence.",
            place_assertion=request.locality_label,
            uncertainties=[
                "Instruction-like content quarantined from policy and priority logic",
                "Service category is unknown",
            ],
        )

    hospital = any(token in text for token in ("hospital", "ಆಸ್ಪತ್ರೆ", "अस्पताल"))
    water_quality = any(
        token in text
        for token in ("chemical", "contamin", "poison", "smells", "sick after drinking")
    )
    electrical = any(token in text for token in ("exposed wire", "live wire", "electric shock"))
    road = any(token in text for token in ("pothole", "road broken", "ಗುಂಡಿ", "सड़क"))
    water = any(token in text for token in ("water", "ನೀರು", "ನೀರಿನ", "पानी"))

    signals: list[SafetySignalCandidate] = []
    if water_quality:
        signals.append(
            SafetySignalCandidate(
                code="POSSIBLE_WATER_CONTAMINATION",
                confidence="supported" if hospital else "uncertain",
                contexts=["hospital"] if hospital else [],
                reason=(
                    "Reporter describes a possible water-quality hazard; verification is required."
                ),
            )
        )
    if electrical:
        signals.append(
            SafetySignalCandidate(
                code="EXPOSED_ELECTRICAL_HAZARD",
                confidence="supported",
                contexts=["public_space"],
                reason="Reporter describes a possible exposed electrical hazard.",
            )
        )

    if water_quality:
        category = "water_quality"
        subtype = "suspected_contamination"
    elif electrical:
        category = "electrical_safety"
        subtype = "possible_exposed_wire"
    elif road and water:
        category = "unknown"
        subtype = None
    elif road:
        category = "roads"
        subtype = "pothole"
    elif water:
        category = "water_supply"
        subtype = "supply_interruption_or_low_pressure"
    else:
        category = "unknown"
        subtype = None

    uncertainties = [
        "Reporter statement is not independently verified",
        "Technical cause is unknown",
    ]
    if category == "unknown":
        uncertainties.append("Controlled service category could not be determined")

    return ReportInterpretation(
        detected_language=request.language_hint,
        category=category,
        subtype=subtype,
        summary="Reporter states a synthetic civic symptom; no fact is independently verified.",
        place_assertion=request.locality_label,
        service_assertion=request.text[:240],
        safety_signal_candidates=signals,
        uncertainties=uncertainties,
    )
