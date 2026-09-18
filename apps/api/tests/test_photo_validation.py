"""Tests for ``civiclens.modules.intake.photo``.

The load-bearing test in this file is
``test_stored_bytes_carry_no_exif_at_all``. Everything else here protects the
service; that one protects the person who sent the photo. A phone photo's EXIF
contains the coordinates of wherever they were standing, and if the uploaded bytes
were stored verbatim those coordinates would live in the bucket and every backup of
it, regardless of what the database columns say.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import ExifTags, Image

from civiclens.domain.photo_integrity import integrity_flags
from civiclens.modules.intake.photo import (
    MAX_PHOTO_BYTES,
    MIN_PHOTO_EDGE,
    validate_photo,
)
from civiclens.shared.errors import MediaValidationError, PhotoValidationError

# A real location in JP Nagar, and a capture time. Chosen to be plausible rather
# than round, so a test asserting the values are gone cannot pass by accident
# against a zero-initialised field.
CAPTURE_LAT = 12.9081
CAPTURE_LON = 77.5831
CAPTURED_AT = datetime(2026, 9, 15, 8, 30, tzinfo=UTC)


def _photo_image(*, size: tuple[int, int] = (800, 600)) -> Image.Image:
    """A non-uniform image, so the perceptual hash has something to work with."""
    image = Image.new("RGB", size)
    width, height = size
    image.putdata(
        [
            (x * 255 // max(width - 1, 1), y * 255 // max(height - 1, 1), 128)
            for y in range(height)
            for x in range(width)
        ]
    )
    return image


def _exif_with_location() -> Image.Exif:
    exif = Image.Exif()
    exif[int(ExifTags.Base.DateTimeOriginal)] = CAPTURED_AT.strftime("%Y:%m:%d %H:%M:%S")
    gps = {
        int(ExifTags.GPS.GPSLatitudeRef): "N",
        int(ExifTags.GPS.GPSLatitude): _as_dms(CAPTURE_LAT),
        int(ExifTags.GPS.GPSLongitudeRef): "E",
        int(ExifTags.GPS.GPSLongitude): _as_dms(CAPTURE_LON),
    }
    exif[int(ExifTags.IFD.GPSInfo)] = gps
    return exif


def _as_dms(value: float) -> tuple[float, float, float]:
    degrees = int(value)
    minutes_float = (value - degrees) * 60
    minutes = int(minutes_float)
    return (float(degrees), float(minutes), round((minutes_float - minutes) * 60, 4))


def _jpeg(image: Image.Image, *, exif: Image.Exif | None = None) -> bytes:
    buffer = BytesIO()
    if exif is None:
        image.save(buffer, format="JPEG", quality=95)
    else:
        image.save(buffer, format="JPEG", quality=95, exif=exif)
    return buffer.getvalue()


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_a_plain_jpeg_is_accepted() -> None:
    result = validate_photo(_jpeg(_photo_image()), "image/jpeg")

    assert result.content_type == "image/jpeg"
    assert result.byte_size == len(result.data)
    assert result.width == 800
    assert result.height == 600
    assert len(result.perceptual_hash) == 16


def test_a_plain_png_is_accepted() -> None:
    result = validate_photo(_png(_photo_image()), "image/png")

    assert result.content_type == "image/png"
    assert result.data.startswith(b"\x89PNG")


def test_image_jpg_is_treated_as_image_jpeg() -> None:
    # Some Android browsers send this. Rejecting it would refuse a correct photo
    # over a spelling difference in a header.
    result = validate_photo(_jpeg(_photo_image()), "image/jpg")

    assert result.content_type == "image/jpeg"


# --- the privacy guarantee -------------------------------------------------


def test_stored_bytes_carry_no_exif_at_all() -> None:
    """The reporter's coordinates must not survive into what gets stored."""
    uploaded = _jpeg(_photo_image(), exif=_exif_with_location())
    # Guard the fixture itself: if the EXIF never made it into the upload, this
    # test would pass while proving nothing.
    assert len(Image.open(BytesIO(uploaded)).getexif()) > 0

    result = validate_photo(uploaded, "image/jpeg")

    stored_exif = Image.open(BytesIO(result.data)).getexif()
    assert len(stored_exif) == 0
    assert stored_exif.get_ifd(int(ExifTags.IFD.GPSInfo)) == {}
    # And not merely absent from the parsed metadata -- absent from the bytes. A
    # coordinate left in a segment Pillow does not parse back is still a coordinate
    # sitting in the object store.
    assert b"GPS" not in result.data


def test_exif_is_still_read_for_integrity_flags_before_being_dropped() -> None:
    result = validate_photo(_jpeg(_photo_image(), exif=_exif_with_location()), "image/jpeg")

    assert result.exif.gps_lat == pytest.approx(CAPTURE_LAT, abs=1e-4)
    assert result.exif.captured_at is not None
    # The point of keeping it this long: this pin is ~540 m from where the camera
    # was, and an officer is told "near" and no more -- never the metres, and never
    # the coordinates.
    codes = {
        flag.code for flag in integrity_flags(result.exif, 77.5781, CAPTURE_LAT, datetime.now(UTC))
    }
    assert "EXIF_LOCATION_NEAR" in codes
    # And a pin 1.5 km away is a different answer, so the flag is actually measuring
    # something rather than defaulting.
    far = {flag.code for flag in integrity_flags(result.exif, 77.5691, 12.9121, datetime.now(UTC))}
    assert "EXIF_LOCATION_FAR" in far


def test_a_photo_with_no_exif_is_accepted_and_reports_none() -> None:
    result = validate_photo(_jpeg(_photo_image()), "image/jpeg")

    # Screenshots and stripped photos are normal, not suspicious. The absence
    # becomes an officer-visible flag; it is not a reason to refuse the report.
    assert result.exif.gps_lat is None
    assert result.exif.captured_at is None


# --- refusals -------------------------------------------------------------


def test_bytes_that_are_not_an_image_are_refused() -> None:
    with pytest.raises(PhotoValidationError):
        validate_photo(b"this is not an image, it is a sentence", "image/jpeg")


def test_a_png_declared_as_jpeg_is_refused() -> None:
    # The declared type is the client's claim; the decoded format is the fact. A
    # mismatch means a broken client or somebody probing, and neither gets a 202.
    with pytest.raises(PhotoValidationError, match="do not match"):
        validate_photo(_png(_photo_image()), "image/jpeg")


def test_an_unsupported_content_type_is_refused() -> None:
    with pytest.raises(PhotoValidationError, match="JPEG and PNG"):
        validate_photo(_jpeg(_photo_image()), "image/heic")


def test_an_empty_upload_is_refused() -> None:
    with pytest.raises(PhotoValidationError, match="empty"):
        validate_photo(b"", "image/jpeg")


def test_an_oversized_upload_is_refused_without_being_decoded() -> None:
    with pytest.raises(PhotoValidationError, match="12 MB"):
        validate_photo(b"\xff\xd8\xff" + b"\x00" * MAX_PHOTO_BYTES, "image/jpeg")


def test_a_photo_too_small_to_show_the_problem_is_refused() -> None:
    tiny = MIN_PHOTO_EDGE - 1
    with pytest.raises(PhotoValidationError, match="too small"):
        validate_photo(_jpeg(_photo_image(size=(tiny, tiny))), "image/jpeg")


def test_a_decompression_bomb_is_refused_before_the_pixels_are_allocated() -> None:
    """A small file declaring a huge canvas must not be decoded.

    The file below is a few kilobytes and declares 48 megapixels -- above this
    service's 40 MP ceiling but below Pillow's own much larger one, so it is *our*
    check being exercised and not the library's. The check has to happen from the
    header, because once the decode is running the memory is already committed and
    the process is already in trouble.
    """
    bomb = BytesIO()
    Image.new("L", (8_000, 6_000)).save(bomb, format="PNG")

    with pytest.raises(PhotoValidationError, match="too large"):
        validate_photo(bomb.getvalue(), "image/png")


def test_a_canvas_past_pillows_own_ceiling_is_refused_as_too_large_too() -> None:
    """Pillow raises before reporting a size, and that must not become a 500.

    A gigapixel declaration trips Pillow's ``DecompressionBombError`` inside
    ``Image.open``, so the pixel-count check below it never runs. The reporter has to
    get the same refusal either way.
    """
    bomb = BytesIO()
    Image.new("L", (60_000, 44_000)).save(bomb, format="PNG")

    with pytest.raises(PhotoValidationError, match="too large"):
        validate_photo(bomb.getvalue(), "image/png")


def test_photo_errors_are_reported_as_photo_not_voice() -> None:
    # The endpoint translates `MediaValidationError` to a 422, so the subclass has
    # to keep that relationship -- while not telling a reporter their photo is
    # invalid *voice* media.
    with pytest.raises(MediaValidationError) as caught:
        validate_photo(b"not an image", "image/jpeg")

    assert caught.value.code == "INVALID_PHOTO_MEDIA"


def test_a_refusal_never_quotes_the_file_contents() -> None:
    # Pillow's decode errors quote header fragments, and the file is
    # citizen-supplied content that must not travel outward in an error string.
    secret = b"RECOGNISABLE-CONTENT-abcdef"
    with pytest.raises(PhotoValidationError) as caught:
        validate_photo(b"\xff\xd8\xff\xe0" + secret, "image/jpeg")

    assert b"RECOGNISABLE" not in str(caught.value).encode()


# --- determinism ----------------------------------------------------------


def test_the_same_upload_always_produces_the_same_hash() -> None:
    uploaded = _jpeg(_photo_image())

    first = validate_photo(uploaded, "image/jpeg")
    second = validate_photo(uploaded, "image/jpeg")

    # Idempotency depends on this: the object key is derived from the content hash,
    # so a re-encode that varied between runs would store the same photo twice
    # under different keys and break retry handling.
    assert first.content_hash == second.content_hash
    assert first.data == second.data


def test_two_photos_of_the_same_scene_have_close_perceptual_hashes() -> None:
    from civiclens.domain.photo_integrity import hamming_distance

    original = _photo_image()
    shifted = Image.new("RGB", original.size)
    shifted.paste(original, (2, 0))

    first = validate_photo(_jpeg(original), "image/jpeg")
    second = validate_photo(_jpeg(shifted), "image/jpeg")

    # This is what lets two reports of one pothole be recognised as one pothole
    # without any model looking at either image.
    assert hamming_distance(first.perceptual_hash, second.perceptual_hash) < 12


def test_a_rotated_photo_is_stored_upright() -> None:
    """Orientation lives in EXIF, and this pipeline deletes EXIF.

    So the rotation has to be baked into the pixels on the way through. Without
    that step every portrait phone upload would be stored sideways -- the metadata
    saying "turn this" having been removed along with the coordinates.
    """
    exif = Image.Exif()
    exif[int(ExifTags.Base.Orientation)] = 6  # rotate 90° clockwise when displaying
    uploaded = _jpeg(_photo_image(size=(800, 600)), exif=exif)

    result = validate_photo(uploaded, "image/jpeg")

    assert (result.width, result.height) == (600, 800)
