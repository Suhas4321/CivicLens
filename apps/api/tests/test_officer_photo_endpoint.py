"""The other half of the photo feature: an officer actually seeing it.

Upload, validation, EXIF stripping and storage were all in place and there was no
route that served the image back, which made the whole pipeline decorative -- the
photo exists so somebody can judge severity from a desk, and nothing let them look
at it.

Two tests here matter more than the rest.
``test_what_the_officer_receives_carries_no_exif_at_all`` follows a photograph the
whole way from the reporter's upload to the officer's screen and asserts the
coordinates are gone at the far end. ``test_photos_are_not_served_when_demo_mode_is_off``
asserts the route fails closed: there is no authentication anywhere on ``/officer``
yet, so the only thing standing between these photographs and the open internet is
that gate, and a gate with no test is a gate somebody removes during a refactor.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import ExifTags, Image

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.media.photo_storage import MemoryPhotoStorage
from civiclens.main import app
from civiclens.modules.intake import api as intake_api
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.service import (
    IntakeService,
    get_intake_repository,
    get_intake_service,
)
from civiclens.modules.planning import api as planning_api

CAPABILITY = "officer-photo-capability-0123456789abcdef"

# The pin the reporter confirms, and a capture point ~540 m away from it, which is
# inside the "near" band. Real coordinates in JP Nagar so the distance arithmetic is
# exercised on the geography this service is for.
PIN_LAT = 12.9081
PIN_LON = 77.5781
CAPTURE_LAT = 12.9081
CAPTURE_LON = 77.5831


class _NoAnalysis:
    """Keeps the background interpreter out of these tests. See the intake tests."""

    def process(self, public_id: str) -> None:
        del public_id


@pytest.fixture
def repository() -> Iterator[MemoryIntakeRepository]:
    store = MemoryIntakeRepository()
    # Both overrides point at one store on purpose. The officer route reads through
    # `get_intake_repository` and the submission writes through `get_intake_service`;
    # if those resolved to two different stores the test would pass its upload and
    # then fetch from an empty repository, which looks like a broken endpoint.
    app.dependency_overrides[get_intake_service] = lambda: IntakeService(store)
    app.dependency_overrides[get_intake_repository] = lambda: store
    yield store
    app.dependency_overrides.pop(get_intake_service, None)
    app.dependency_overrides.pop(get_intake_repository, None)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(intake_api, "get_report_analysis_service", _NoAnalysis)
    with TestClient(app) as test_client:
        yield test_client


def _photo_image(*, size: tuple[int, int] = (800, 600)) -> Image.Image:
    image = Image.new("RGB", size)
    width, height = size
    image.putdata(
        [
            (x * 255 // max(width - 1, 1), y * 255 // max(height - 1, 1), 96)
            for y in range(height)
            for x in range(width)
        ]
    )
    return image


def _as_dms(value: float) -> tuple[float, float, float]:
    degrees = int(value)
    minutes_float = (value - degrees) * 60
    minutes = int(minutes_float)
    return (float(degrees), float(minutes), round((minutes_float - minutes) * 60, 4))


def _located_jpeg() -> bytes:
    """A JPEG carrying the coordinates and the timestamp a phone camera would write."""
    exif = Image.Exif()
    exif[int(ExifTags.Base.DateTimeOriginal)] = datetime.now(UTC).strftime("%Y:%m:%d %H:%M:%S")
    exif[int(ExifTags.IFD.GPSInfo)] = {
        int(ExifTags.GPS.GPSLatitudeRef): "N",
        int(ExifTags.GPS.GPSLatitude): _as_dms(CAPTURE_LAT),
        int(ExifTags.GPS.GPSLongitudeRef): "E",
        int(ExifTags.GPS.GPSLongitude): _as_dms(CAPTURE_LON),
    }
    buffer = BytesIO()
    _photo_image().save(buffer, format="JPEG", quality=95, exif=exif)
    return buffer.getvalue()


def _plain_jpeg() -> bytes:
    buffer = BytesIO()
    _photo_image().save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def _submit(
    client: TestClient,
    *,
    photo: bytes | None = None,
    located: bool = True,
    **overrides: object,
) -> str:
    """Submit a report and return its public id."""
    data: dict[str, object] = {
        "description": "Sewage is flowing across the footpath outside the school gate.",
        "language_hint": "en",
        "locality_label": "Sarakki demo locality",
        "consent": "true",
        "synthetic_demo_confirmation": "true",
    }
    if located:
        data["latitude"] = str(PIN_LAT)
        data["longitude"] = str(PIN_LON)
    data.update(overrides)
    response = client.post(
        "/api/v1/reports",
        data=data,
        files={"photo": ("street.jpg", photo, "image/jpeg")} if photo is not None else None,
        headers={"Idempotency-Key": str(uuid4()), "X-Receipt-Capability": CAPABILITY},
    )
    assert response.status_code == 202, response.text
    return str(response.json()["public_id"])


def _photo_url(repository: MemoryIntakeRepository, public_id: str) -> str:
    return f"/api/v1/officer/reports/{repository.get_by_public_id(public_id).id}/photo"


def test_an_uploaded_photo_can_be_fetched_back(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    public_id = _submit(client, photo=_plain_jpeg())

    response = client.get(_photo_url(repository, public_id))

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    # Not just a 200 with a body -- a body a browser will render. If the stored bytes
    # were truncated or double-encoded somewhere in the pipeline this is where it
    # shows, and the alternative is an officer staring at a broken image icon.
    assert Image.open(BytesIO(response.content)).size == (800, 600)


def test_what_the_officer_receives_carries_no_exif_at_all(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """The privacy guarantee, asserted at the boundary the reporter cannot see.

    ``test_photo_validation.py`` already proves the re-encode strips EXIF. This
    proves nothing downstream puts it back or serves the original instead: the
    coordinates of wherever the reporter was standing must not come out of this
    endpoint, because from here they travel to a browser, a proxy log and whatever
    the officer's machine does with a downloaded image.
    """
    uploaded = _located_jpeg()
    # Guard the fixture. Without this the test would pass on a photo that never
    # carried coordinates in the first place, which proves nothing at all.
    assert len(Image.open(BytesIO(uploaded)).getexif()) > 0
    public_id = _submit(client, photo=uploaded)

    response = client.get(_photo_url(repository, public_id))

    assert response.status_code == 200
    assert response.content != uploaded, "the served bytes must be the re-encoded ones"
    assert len(Image.open(BytesIO(response.content)).getexif()) == 0
    # And absent from the bytes, not merely from what Pillow parses back. A
    # coordinate sitting in a segment no parser reads is still a coordinate that left
    # the building.
    assert b"GPS" not in response.content


def test_the_response_is_not_cached_and_not_sniffed(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    public_id = _submit(client, photo=_plain_jpeg())

    response = client.get(_photo_url(repository, public_id))

    # A ward office machine is shared, and a photograph of somebody's street left in
    # its disk cache outlives the session that fetched it.
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_photos_are_not_served_when_demo_mode_is_off(
    client: TestClient, repository: MemoryIntakeRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails closed, because ``/officer`` has no authentication at all.

    Every other officer route hands back synthetic seed data, so leaving them open
    costs nothing. This one hands back photographs that real people took. Turning off
    demo mode is the only supported way to run this service against anything other
    than synthetic data, so that switch is what the gate reads until there is a
    login to read instead.
    """
    public_id = _submit(client, photo=_plain_jpeg())
    url = _photo_url(repository, public_id)
    monkeypatch.setattr(
        planning_api,
        "get_settings",
        lambda: get_settings().model_copy(update={"demo_mode_enabled": False}),
    )

    response = client.get(url)

    assert response.status_code == 403
    assert response.json()["detail"] == "PHOTO_ACCESS_NOT_CONFIGURED"


def test_a_disabled_deployment_does_not_reveal_which_reports_exist(
    client: TestClient, repository: MemoryIntakeRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal comes before the lookup, so the status code is not an oracle.

    If the gate ran after ``get_by_id`` a caller could tell a real report id from an
    invented one by whether they got 403 or 404, and walk the id space of a system
    with no login on it.
    """
    public_id = _submit(client, photo=_plain_jpeg())
    real = _photo_url(repository, public_id)
    invented = f"/api/v1/officer/reports/{uuid4()}/photo"
    monkeypatch.setattr(
        planning_api,
        "get_settings",
        lambda: get_settings().model_copy(update={"demo_mode_enabled": False}),
    )

    assert client.get(real).status_code == client.get(invented).status_code == 403


def test_a_report_with_no_photo_is_a_404(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    public_id = _submit(client)

    response = client.get(_photo_url(repository, public_id))

    assert response.status_code == 404
    # Distinct from "no such report", because the two mean different things to
    # whoever is reading the officer surface's error handling.
    assert response.json()["detail"] == "PHOTO_NOT_ATTACHED"


def test_an_unknown_report_is_a_404(client: TestClient, repository: MemoryIntakeRepository) -> None:
    del repository

    response = client.get(f"/api/v1/officer/reports/{uuid4()}/photo")

    assert response.status_code == 404


def test_a_photo_the_store_has_lost_is_a_404_not_a_500(
    client: TestClient, repository: MemoryIntakeRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row outlives the object, by design.

    Retention deletes photos on schedule while the report stays, and the memory
    backend loses every object when the process restarts. Both are normal, so an
    officer opening an old report has to be told the photo is gone rather than shown
    a server error that reads as "this service is broken".
    """
    public_id = _submit(client, photo=_plain_jpeg())
    url = _photo_url(repository, public_id)
    monkeypatch.setattr(planning_api, "get_photo_storage", MemoryPhotoStorage)

    response = client.get(url)

    assert response.status_code == 404
    assert response.json()["detail"] == "PHOTO_EXPIRED"


def test_the_officer_board_says_which_reports_have_a_photo(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Visible on the lane item, not only after opening the report.

    It changes the order an officer works in: the ones with a photo can be settled
    from a desk, and the rest need a phone call or a visit.
    """
    with_photo = _submit(client, photo=_plain_jpeg())
    without = _submit(client)

    board = client.get("/api/v1/officer/overview").json()
    items = {item["id"]: item for item in board["safety_review"] + board["operational_incidents"]}

    assert items[str(repository.get_by_public_id(with_photo).id)]["has_photo"] is True
    assert items[str(repository.get_by_public_id(without).id)]["has_photo"] is False


def test_the_chosen_category_reaches_the_officer(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """Because the category is what routes the item to BWSSB rather than BBMP.

    Kept separate from the interpreted ``category`` field: that one is the AI's
    reading of the text, this one is what the reporter chose, and when they disagree
    the officer needs to see both rather than a single value that quietly won.
    """
    public_id = _submit(client, photo=_plain_jpeg(), service_code="SEWAGE_OVERFLOW")
    report_id = str(repository.get_by_public_id(public_id).id)

    detail = client.get(f"/api/v1/officer/incidents/{report_id}").json()

    assert detail["reports"][0]["service_code"] == "SEWAGE_OVERFLOW"
    assert detail["reports"][0]["has_photo"] is True


def test_integrity_flags_reach_the_officer_as_codes_and_never_as_distances(
    client: TestClient, repository: MemoryIntakeRepository
) -> None:
    """ "Near" is the whole answer an officer gets.

    The flag detail stored in the database spells out a rounded distance, and
    publishing that would draw an approximate ring around wherever the reporter was
    standing -- reconstructing by arithmetic exactly what stripping the EXIF was for.
    So the API carries codes, and the words for them live in the client.
    """
    public_id = _submit(client, photo=_located_jpeg())
    report_id = str(repository.get_by_public_id(public_id).id)

    detail = client.get(f"/api/v1/officer/incidents/{report_id}").json()

    flags = detail["reports"][0]["photo_integrity_flags"]
    assert "EXIF_LOCATION_NEAR" in flags
    # No prose, no metres, no coordinates -- and asserted over the whole response
    # body, because a leak added to a neighbouring field would pass a check that
    # only looked at this one.
    assert all(flag == flag.upper() and " " not in flag for flag in flags)
    assert "m from" not in client.get(f"/api/v1/officer/incidents/{report_id}").text
