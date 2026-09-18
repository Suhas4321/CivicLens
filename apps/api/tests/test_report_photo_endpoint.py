"""HTTP-level tests for the photo and category fields on POST /api/v1/reports.

Separate file from ``test_report_intake_endpoint.py``, same reason for existing.
**FastAPI silently discards multipart fields it was not told about**, so an
undeclared ``photo`` or ``service_code`` would produce a 202, a receipt, and no
photo -- the exact shape of the coordinate bug. A test that calls ``IntakeService``
directly cannot see that; only a real multipart request through the real signature
can.

These tests also cover the two-media lookup. Before this change every read path in
the repository asked for "the media row for this report" without filtering on
``media_type``, which was correct only while voice was the sole medium. A report
carrying both now has two rows, and an unfiltered single-row query returns whichever
one the planner reaches first.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from civiclens.main import app
from civiclens.modules.intake import api as intake_api
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.service import IntakeService, get_intake_service

CAPABILITY = "photo-endpoint-capability-0123456789abcdef"


class _NoAnalysis:
    """Keeps the background interpreter out of these tests. See the intake tests."""

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


def _jpeg_bytes(*, size: tuple[int, int] = (800, 600)) -> bytes:
    width, height = size
    image = Image.new("RGB", size)
    image.putdata(
        [
            (x * 255 // max(width - 1, 1), y * 255 // max(height - 1, 1), 96)
            for y in range(height)
            for x in range(width)
        ]
    )
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def submit(
    client: TestClient,
    *,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    **overrides: object,
) -> object:
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
        files=files,
        headers={
            "Idempotency-Key": str(uuid4()),
            "X-Receipt-Capability": CAPABILITY,
        },
    )


def _photo_file(content_type: str = "image/jpeg") -> dict[str, tuple[str, bytes, str]]:
    return {"photo": ("street.jpg", _jpeg_bytes(), content_type)}


def test_a_photo_survives_the_request(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """The regression test for the field that must not be silently dropped."""
    response = submit(client, files=_photo_file())

    assert response.status_code == 202
    body = response.json()
    # The receipt says so explicitly. A reporter on a weak connection has no other
    # way to learn whether the attachment arrived, and "202" does not answer it.
    assert body["photo_received"] is True
    record = repository.get_by_public_id(body["public_id"])
    assert record.photo_object_key is not None
    assert record.photo_content_type == "image/jpeg"


def test_a_report_without_a_photo_says_so(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Text-only reports stay first-class; the flag is false, not absent."""
    response = submit(client)

    assert response.status_code == 202
    assert response.json()["photo_received"] is False
    assert repository.get_by_public_id(response.json()["public_id"]).photo_object_key is None


def test_the_chosen_category_round_trips(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """The code selects the agency and the statutory deadline, so it must arrive intact."""
    response = submit(client, service_code="SEWAGE_OVERFLOW")

    assert response.status_code == 202
    assert response.json()["service_code_recorded"] == "SEWAGE_OVERFLOW"
    assert repository.get_by_public_id(response.json()["public_id"]).service_code == (
        "SEWAGE_OVERFLOW"
    )


def test_no_category_is_allowed_and_not_defaulted(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """A reporter who cannot tell sewage from a burst main still gets to report it.

    What must not happen is a quiet default: the code carries the deadline, and
    inventing one would show somebody a promise nobody is held to.
    """
    response = submit(client)

    assert response.json()["service_code_recorded"] is None
    assert repository.get_by_public_id(response.json()["public_id"]).service_code is None


def test_an_unknown_category_is_refused_with_the_category_message(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Refused, not coerced to OTHER -- and told which field was wrong.

    The generic message would tell a reporter who mistyped a category that their
    coordinates are wrong, which is worse than saying nothing.
    """
    del repository
    response = submit(client, service_code="POTHOLE_OF_DOOM")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "REPORT_FIELDS_INVALID"
    assert "category" in detail["message"]
    assert "Latitude" not in detail["message"]


def test_a_photo_and_a_voice_note_both_survive_together(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Two media rows on one report, and each read path must find the right one.

    This is the test for the unfiltered media lookup: with both present, a query
    that asks only for "the media row for this report" can hand back the photo where
    the voice note was expected, with no error anywhere.
    """
    voice = _voice_bytes()
    if voice is None:
        pytest.skip("no local encoder available to build a voice fixture")
    response = submit(
        client,
        files={
            "photo": ("street.jpg", _jpeg_bytes(), "image/jpeg"),
            "voice": ("note.webm", voice, "audio/webm"),
        },
    )

    assert response.status_code == 202
    record = repository.get_by_public_id(response.json()["public_id"])
    assert record.photo_content_type == "image/jpeg"
    assert record.voice_object_key is not None
    assert record.photo_object_key != record.voice_object_key


def _voice_bytes() -> bytes | None:
    """Build a short silent recording, or None if this machine cannot encode one.

    Skipped rather than faked: ``validate_voice`` decodes the container to read the
    duration, so a stub would be rejected and the test would prove nothing about the
    two-media path it exists for.
    """
    try:
        import av
    except ImportError:  # pragma: no cover - depends on the local install
        return None
    buffer = BytesIO()
    try:
        with av.open(buffer, mode="w", format="webm") as container:
            stream = container.add_stream("libopus", rate=48000)
            frame = av.AudioFrame(format="s16", layout="mono", samples=48000)
            frame.sample_rate = 48000
            frame.pts = 0
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)
    except Exception:  # pragma: no cover - encoder availability varies
        return None
    return buffer.getvalue()


def test_a_photo_that_is_not_an_image_is_the_clients_fault(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    del repository
    response = submit(client, files={"photo": ("street.jpg", b"this is a sentence", "image/jpeg")})

    assert response.status_code == 422
    # And it says *photo*. Telling somebody their photograph is invalid voice media
    # is the kind of message that makes a person give up rather than retry.
    assert response.json()["detail"]["code"] == "INVALID_PHOTO_MEDIA"


def test_a_photo_rejection_never_quotes_the_file(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    del repository
    response = submit(
        client,
        files={"photo": ("street.jpg", b"\xff\xd8\xff\xe0RECOGNISABLE-abcdef", "image/jpeg")},
    )

    assert response.status_code == 422
    assert "RECOGNISABLE" not in response.text
