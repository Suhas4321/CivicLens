from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from civiclens.bootstrap.policy import PriorityProfile, load_policy_bundle, repository_root
from civiclens.infrastructure.db import models as _models  # noqa: F401
from civiclens.infrastructure.db.base import Base
from civiclens.infrastructure.db.seed_contracts import (
    load_json,
    validate_demo_assets,
    validate_public_assets,
)
from civiclens.shared.primitives import stable_id


def test_policy_bundle_preserves_governance_boundaries() -> None:
    bundle = load_policy_bundle()

    assert bundle.priority.unknown_prevents_comparison is True
    assert bundle.priority.profiles[0].weights == {
        "scale_exposure": 30,
        "persistence_spread": 25,
        "service_disadvantage": 25,
        "consequence_if_unaddressed": 20,
    }
    capital = next(
        item for item in bundle.catalogue.items if item.key == "capital_feasibility_referral"
    )
    assert capital.requires_verified_cause is True

    with pytest.raises(ValidationError):
        PriorityProfile(key="invalid", weights={"scale_exposure": 100})


def test_demo_assets_are_frozen_partitioned_and_reproducible() -> None:
    root = repository_root()
    reports, truth, manifest = validate_demo_assets(root)
    tuning = load_json(root / "data" / "tuning" / "v1" / "reports.json")
    held_out = load_json(root / "data" / "held-out" / "v1" / "reports.json")

    assert len(reports) == 60
    assert Counter(report.language for report in reports) == manifest.language_mix
    assert Counter(report.story for report in reports) == {
        "mahadevapura_water": 24,
        "comparison_water": 12,
        "pothole": 18,
        "hospital_safety": 1,
        "noise": 5,
    }
    tuning_ids = {item["logical_id"] for item in tuning}
    held_out_ids = {item["logical_id"] for item in held_out}
    assert tuning_ids.isdisjoint(held_out_ids)
    assert tuning_ids | held_out_ids == {str(report.logical_id) for report in reports}
    assert truth["incidents_expected"] == 8
    assert truth["suspected_needs_expected"] == 2
    assert stable_id("report", "report-001") == reports[0].logical_id


def test_public_snapshot_is_complete_and_never_claims_local_reliability() -> None:
    manifest, observations = validate_public_assets(repository_root())

    assert manifest.version == "bengaluru-water-v1"
    assert manifest.license_status.startswith("not established")
    assert len(observations) == 9
    assert all(item.source_url and item.geography_kind for item in observations)
    assert all(item.supported_inferences and item.prohibited_inferences for item in observations)
    plan_demand = next(
        item for item in observations if item.evidence_key == "mahadevapura_stage_v_plan_demand"
    )
    assert plan_demand.semantics == "plan"
    assert "Continuity" in plan_demand.prohibited_inferences


def test_exactly_sixteen_core_tables_compile_for_postgresql() -> None:
    assert len(Base.metadata.tables) == 16
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f"CREATE TABLE {table.name}" in ddl
