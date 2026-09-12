from __future__ import annotations

from civiclens.bootstrap.policy import repository_root
from civiclens.modules.planning.read_service import GoldenDemoReadService
from civiclens.shared.primitives import stable_id


def test_overview_keeps_safety_operations_and_planning_separate() -> None:
    service = GoldenDemoReadService(repository_root())
    overview = service.overview()

    assert len(overview.safety_review) == 1
    assert overview.safety_review[0].report_count == 1
    assert len(overview.operational_incidents) == 2
    assert overview.operational_incidents[0].report_count == 18
    assert len(overview.planning_needs) == 2
    assert all(item.category == "water_supply" for item in overview.planning_needs)


def test_primary_need_exposes_provenance_policy_and_conditional_candidate() -> None:
    service = GoldenDemoReadService(repository_root())
    workspace = service.need_workspace(stable_id("need", "maha-recurring-water"))

    assert workspace.hypothesis_label == "Suspected Civic Need"
    assert workspace.need.incident_count == 3
    assert workspace.need.report_count == 24
    assert workspace.priority.band == "high"
    assert [component.rating for component in workspace.priority.components] == [2, 3, 3, 2]
    plan_demand = next(
        item for item in workspace.evidence if item.key == "mahadevapura_stage_v_plan_demand"
    )
    assert plan_demand.semantics == "plan"
    assert plan_demand.contributes_to_rating is False
    synthetic_finding = next(
        item
        for item in workspace.evidence
        if item.key == "synthetic_field_verification_primary_need"
    )
    assert synthetic_finding.contributes_to_rating is True
    assert workspace.candidate.catalogue_key == "field_service_verification"
    assert "not a construction project" in workspace.candidate.decision_boundary


def test_high_volume_pothole_remains_one_operational_incident() -> None:
    service = GoldenDemoReadService(repository_root())
    incident = service.incident_detail(stable_id("incident", "pothole-one"))

    assert incident.incident.report_count == 18
    assert len(incident.reports) == 18
    assert all(report.classification == "synthetic_demo" for report in incident.reports)
