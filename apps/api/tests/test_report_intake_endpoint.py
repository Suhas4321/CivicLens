"""HTTP-level tests for POST /api/v1/reports.

Separate from ``test_report_intake.py`` on purpose. Those tests drive
``IntakeService`` directly, and that is why they never caught the bug this file
exists for: the endpoint declared no ``latitude``/``longitude`` form fields, and
**FastAPI silently discards multipart fields it was not told about**. The request
still returned 202, the reporter still got a receipt, and their coordinates were
dropped on the floor with nobody told. No service-level test can see that --
only a real request through the real signature can.

So the rule these tests encode is: every field a client is documented to send has
to be asserted at the HTTP boundary, not one layer below it.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from civiclens.main import app
from civiclens.modules.intake import api as intake_api
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.service import IntakeService, get_intake_service

CAPABILITY = "endpoint-receipt-capability-0123456789abcdef"


class _NoAnalysis:
    """Stops the accepted report from being handed to an interpreter.

    The endpoint queues analysis as a background task, and TestClient runs those
    synchronously. Left alone it would reach whichever AI backend the local
    environment is configured for -- so these tests would depend on a key, on the
    network, and on a daily budget, none of which they are about.
    """

    def process(self, public_id: str) -> None:
        del public_id


@pytest.fixture
def repository() -> Iterator[MemoryIntakeRepository]:
    store = MemoryIntakeRepository()
    app.dependency_overrides[get_intake_service] = lambda: IntakeService(store)
    yield store
    app.dependency_overrides.pop(get_intake_service, None)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(intake_api, "get_report_analysis_service", _NoAnalysis)
    with TestClient(app) as test_client:
        yield test_client


def submit(client: TestClient, **overrides: object) -> object:
    data: dict[str, object] = {
        "description": "Sewage is flowing across the footpath outside the school gate.",
        "language_hint": "en",
        "locality_label": "Sarakki demo locality",
        "consent": "true",
        "synthetic_demo_confirmation": "true",
    }
    data.update(overrides)
    return client.post(
        "/api/v1/reports",
        data={key: value for key, value in data.items() if value is not None},
        headers={
            "Idempotency-Key": str(uuid4()),
            "X-Receipt-Capability": CAPABILITY,
        },
    )


def test_coordinates_survive_the_request(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """The regression test for the dropped field.

    Before the fields were declared this assertion failed while the response was
    still 202 -- which is exactly what made the loss invisible.
    """
    response = submit(client, latitude="12.9081", longitude="77.5831")

    assert response.status_code == 202
    record = repository.get_by_public_id(response.json()["public_id"])
    assert record.latitude == pytest.approx(12.9081)
    assert record.longitude == pytest.approx(77.5831)
    assert record.location_precision == "point"


def test_a_report_without_coordinates_is_still_accepted(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Location is optional, and the record says so rather than leaving it implied.

    A reporter may decline location, or be indoors with no fix. The locality label
    they typed carries it then, and `location_precision` records which of the two
    happened so that grouping does not treat a typed name as a GPS point.
    """
    response = submit(client)

    assert response.status_code == 202
    record = repository.get_by_public_id(response.json()["public_id"])
    assert record.latitude is None
    assert record.longitude is None
    assert record.location_precision == "locality_label"


def test_half_a_coordinate_pair_is_the_clients_fault_not_a_crash(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """422, not 500.

    ``coordinates_are_a_pair`` runs inside the handler rather than while parsing
    the request, so an unguarded pydantic error would surface as a server fault
    for what is plainly a malformed submission.
    """
    del repository
    response = submit(client, latitude="12.9081")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "REPORT_FIELDS_INVALID"


def test_the_error_does_not_echo_the_report_text(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Report content must never leave the process in an error message.

    The pydantic message embeds the offending values, which is why it is replaced
    rather than forwarded.
    """
    del repository
    secret = "the house behind the blue gate on 7th Main"
    response = submit(client, description=secret, latitude="12.9081")

    assert response.status_code == 422
    assert secret not in response.text


def test_an_impossible_latitude_is_rejected(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    del repository
    assert submit(client, latitude="95.0", longitude="77.5831").status_code == 422


def test_four_characters_of_description_is_enough(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """The low-friction floor, asserted where a reporter meets it.

    Four, not twenty: the category, the photo and the location now carry the
    classification, the severity and the grouping, so demanding a paragraph of
    prose only excludes people who would rather not type. Four is also the
    minimum ``InterpretationRequest.text`` accepts, and the two must move
    together -- a report accepted here that the interpreter then refuses would
    crash the background task instead of degrading.
    """
    response = submit(client, description="ಗುಂಡಿ")

    assert response.status_code == 202
    assert repository.get_by_public_id(response.json()["public_id"]).original_text == "ಗುಂಡಿ"


def test_below_the_floor_is_refused(client: TestClient, repository: MemoryIntakeRepository) -> None:
    del repository
    assert submit(client, description="abc").status_code == 422


def test_consent_and_synthetic_confirmation_are_not_optional(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    del repository
    refused = submit(client, consent="false")

    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "DEMO_CONFIRMATION_REQUIRED"
