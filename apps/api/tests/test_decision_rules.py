from datetime import UTC, datetime, timedelta
from uuid import uuid4

from civiclens.modules.catalogue.evaluator import CandidateRequest, generate_candidate
from civiclens.modules.evidence.compatibility import (
    EvidenceDescriptor,
    NeedScope,
    evaluate_compatibility,
)
from civiclens.modules.priority.evaluator import PriorityInput, evaluate_priority
from civiclens.modules.relationships.evaluator import (
    IncidentFeatures,
    ReportFeatures,
    evaluate_recurrence,
    evaluate_same_incident,
)


def report(
    *, latitude: float, longitude: float, event_at: datetime | None = None
) -> ReportFeatures:
    return ReportFeatures(
        report_id=uuid4(),
        category="water_supply",
        event_at=event_at or datetime(2026, 7, 1, 8, tzinfo=UTC),
        locality_label="Demo Locality M-A",
        latitude=latitude,
        longitude=longitude,
    )


def test_grouping_hard_gates_are_order_independent_and_favor_separation() -> None:
    left = report(latitude=12.9918, longitude=77.7162)
    nearby = report(latitude=12.9920, longitude=77.7161)
    remote = report(latitude=13.04, longitude=77.76)

    forward = evaluate_same_incident(left, nearby)
    reverse = evaluate_same_incident(nearby, left)
    separated = evaluate_same_incident(left, remote)

    assert forward.model_dump() == reverse.model_dump()
    assert forward.relation_type == "same_incident"
    assert separated.relation_type == "separate"
    assert "OUTSIDE_DISTANCE_GATE" in separated.contradictions


def test_recurrence_requires_distinct_confirmed_incidents_and_review() -> None:
    first = IncidentFeatures(
        incident_id=uuid4(),
        category="water_supply",
        event_start=datetime(2026, 6, 3, tzinfo=UTC),
        geography_group="Mahadevapura 23-village project zone",
        links_confirmed=True,
    )
    later = first.model_copy(
        update={
            "incident_id": uuid4(),
            "event_start": first.event_start + timedelta(days=27),
        }
    )

    proposed = evaluate_recurrence(first, later, alternative_hypotheses_reviewed=True)
    abstained = evaluate_recurrence(first, later, alternative_hypotheses_reviewed=False)

    assert proposed.relation_type == "recurrence"
    assert "ALTERNATIVE_HYPOTHESES_NOT_REVIEWED" in abstained.contradictions


def test_priority_reproduces_demo_bands_and_unknown_is_not_zero() -> None:
    primary = PriorityInput.model_validate(
        {
            "components": {
                "scale_exposure": {"rating": 2, "evidence_refs": ["field"], "rationale": "x"},
                "persistence_spread": {
                    "rating": 3,
                    "evidence_refs": ["three-incidents"],
                    "rationale": "x",
                },
                "service_disadvantage": {
                    "rating": 3,
                    "evidence_refs": ["field"],
                    "rationale": "x",
                },
                "consequence_if_unaddressed": {
                    "rating": 2,
                    "evidence_refs": ["rubric"],
                    "rationale": "x",
                },
            }
        }
    )
    comparison = primary.model_copy(deep=True)
    comparison.components["scale_exposure"].rating = 1
    comparison.components["persistence_spread"].rating = 2
    comparison.components["service_disadvantage"].rating = 1
    unknown = primary.model_copy(deep=True)
    unknown.components["scale_exposure"].rating = None
    unknown.components["scale_exposure"].evidence_refs = []

    assert evaluate_priority(primary).band == "high"
    assert evaluate_priority(comparison).band == "lower"
    abstained = evaluate_priority(unknown)
    assert abstained.band == "not_comparable"
    assert abstained.profiles[0].score is None


def test_public_context_cannot_silently_rate_a_local_need() -> None:
    scope = NeedScope(
        geography_label="Mahadevapura 23-village project zone",
        geography_kind="documented project grouping",
    )
    citywide = EvidenceDescriptor(
        evidence_key="city-population",
        geography_label="Bengaluru",
        geography_kind="city",
        semantics="projected",
        role="broader_context",
    )
    local_plan = citywide.model_copy(
        update={
            "evidence_key": "local-plan",
            "geography_label": scope.geography_label,
            "geography_kind": scope.geography_kind,
            "role": "local_decision_evidence",
            "semantics": "plan",
        }
    )

    assert evaluate_compatibility(scope, citywide).reason_code == "BROADER_CONTEXT_ONLY"
    assert evaluate_compatibility(scope, local_plan).reason_code == "SEMANTICS_NOT_RATING_EVIDENCE"


def test_unknown_cause_yields_assessment_not_capital_project() -> None:
    diagnostic = generate_candidate(
        CandidateRequest(
            category="water_supply",
            pathway="suspected_need",
            root_cause_verified=False,
            prerequisite_states={
                "declared_geography": "satisfied",
                "confirmed_recurrence": "satisfied",
                "evidence_gaps_visible": "satisfied",
            },
            works_overlap="possible",
        )
    )
    assert diagnostic.candidate is not None
    assert diagnostic.candidate.catalogue_key == "field_service_verification"
    assert diagnostic.candidate.lifecycle == "conditional"

    capital = generate_candidate(
        CandidateRequest(
            category="water_supply",
            pathway="suspected_need",
            root_cause_verified=True,
            prerequisite_states={
                "verified_service_gap": "satisfied",
                "existing_works_scope_checked": "satisfied",
                "non_capital_alternatives_reviewed": "satisfied",
            },
            works_overlap="confirmed",
        )
    )
    assert capital.candidate is not None
    assert capital.candidate.catalogue_key == "capital_feasibility_referral"
