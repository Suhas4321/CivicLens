import asyncio

import pytest
from fastapi import HTTPException

from civiclens.api.health import live, ready, version
from civiclens.bootstrap.settings import Settings
from civiclens.main import app
from civiclens.modules.planning.api import need_workspace, overview
from civiclens.modules.planning.read_service import get_golden_demo_read_service


def test_health_and_version_contracts() -> None:
    settings = Settings()
    live_response = asyncio.run(live())
    version_response = asyncio.run(version(settings))

    assert live_response.model_dump() == {"status": "alive"}
    assert version_response.application == "civiclens-api"
    assert version_response.public_snapshot_version == "bengaluru-water-v1"


def test_unknown_route_is_absent_from_the_contract() -> None:
    assert "/api/v1/does-not-exist" not in app.openapi()["paths"]


def test_preview_readiness_fails_when_required_configuration_is_missing() -> None:
    settings = Settings(
        app_env="preview",
        gcp_project_id="",
        firebase_project_id="",
        intake_backend="memory",
    )

    with pytest.raises(HTTPException) as captured:
        asyncio.run(ready(settings))

    assert captured.value.status_code == 503
    assert captured.value.detail["code"] == "CONFIGURATION_INCOMPLETE"


def test_golden_demo_route_functions_serialize_the_seeded_lifecycle() -> None:
    service = get_golden_demo_read_service()
    overview_response = asyncio.run(overview(service))
    workspace = asyncio.run(need_workspace(overview_response.planning_needs[0].id, service))

    assert workspace.hypothesis_label == "Suspected Civic Need"
    assert workspace.candidate.catalogue_key == "field_service_verification"
