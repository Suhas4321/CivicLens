from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image

from civiclens.domain.photo_integrity import (
    ExifFacts,
    dhash,
    hamming_distance,
    integrity_flags,
    read_exif,
)

SUBMITTED_AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
PIN_LAT = 0.0
PIN_LON = 0.0


def _jpeg_bytes(image: Image.Image, *, exif: Image.Exif | None = None) -> bytes:
    output = BytesIO()
    if exif is None:
        image.save(output, format="JPEG", quality=100)
    else:
        image.save(output, format="JPEG", quality=100, exif=exif)
    return output.getvalue()


def _gradient_image(*, descending: bool = False) -> Image.Image:
    image = Image.new("L", (90, 80))
    values = []
    for _y in range(image.height):
        for x in range(image.width):
            value = round(x * 255 / (image.width - 1))
            values.append(255 - value if descending else value)
    image.putdata(values)
    return image


def _facts(
    *,
    captured_at: datetime | None = SUBMITTED_AT,
    gps_lat: float | None = PIN_LAT,
    gps_lon: float | None = PIN_LON,
) -> ExifFacts:
    return ExifFacts(
        captured_at=captured_at,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        has_exif=True,
    )


def _codes(exif: ExifFacts) -> set[str]:
    return {flag.code for flag in integrity_flags(exif, PIN_LON, PIN_LAT, SUBMITTED_AT)}


def test_identical_images_have_zero_hamming_distance() -> None:
    image_bytes = _jpeg_bytes(_gradient_image())

    assert hamming_distance(dhash(image_bytes), dhash(image_bytes)) == 0


def test_one_pixel_shift_has_hamming_distance_below_eight() -> None:
    original = _gradient_image()
    shifted = Image.new("L", original.size)
    shifted.paste(original, (1, 0))

    distance = hamming_distance(dhash(_jpeg_bytes(original)), dhash(_jpeg_bytes(shifted)))

    assert distance < 8


def test_clearly_different_images_have_hamming_distance_above_sixteen() -> None:
    ascending = _jpeg_bytes(_gradient_image())
    descending = _jpeg_bytes(_gradient_image(descending=True))

    assert hamming_distance(dhash(ascending), dhash(descending)) > 16


def test_read_exif_extracts_capture_time_and_gps_from_memory() -> None:
    exif = Image.Exif()
    exif[36867] = "2026:09:15 11:30:00"
    exif[34853] = {
        1: "N",
        2: (12.0, 30.0, 0.0),
        3: "E",
        4: (77.0, 36.0, 0.0),
    }

    facts = read_exif(_jpeg_bytes(Image.new("RGB", (16, 16), "white"), exif=exif))

    assert facts.has_exif
    assert facts.captured_at == datetime(2026, 9, 15, 11, 30)
    assert facts.gps_lat == pytest.approx(12.5)
    assert facts.gps_lon == pytest.approx(77.6)


def test_photo_undated_flag() -> None:
    assert "PHOTO_UNDATED" in _codes(_facts(captured_at=None))


def test_photo_stale_flag() -> None:
    assert "PHOTO_STALE" in _codes(_facts(captured_at=SUBMITTED_AT - timedelta(days=8)))


def test_photo_future_dated_flag() -> None:
    assert "PHOTO_FUTURE_DATED" in _codes(_facts(captured_at=SUBMITTED_AT + timedelta(seconds=1)))


def test_exif_location_absent_flag() -> None:
    assert _codes(_facts(gps_lat=None, gps_lon=None)) == {"EXIF_LOCATION_ABSENT"}


def test_exif_location_match_flag() -> None:
    assert _codes(_facts(gps_lon=0.00045)) == {"EXIF_LOCATION_MATCH"}


def test_exif_location_near_flag() -> None:
    assert _codes(_facts(gps_lon=0.0045)) == {"EXIF_LOCATION_NEAR"}


def test_exif_location_far_flag() -> None:
    assert _codes(_facts(gps_lon=0.0135)) == {"EXIF_LOCATION_FAR"}


def test_location_detail_contains_only_a_hundred_metre_resolution() -> None:
    flags = integrity_flags(_facts(gps_lon=0.00138), PIN_LON, PIN_LAT, SUBMITTED_AT)
    location_flag = next(flag for flag in flags if flag.code.startswith("EXIF_LOCATION_"))

    assert location_flag.detail == "EXIF location is 200 m from the confirmed pin"
