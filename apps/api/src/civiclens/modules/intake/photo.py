"""Validate and sanitise an uploaded photo before anything durable happens to it.

A photo exists here for one reason: so an officer can judge severity from their
desk instead of sending somebody to look. That is the whole job. There is no
vision model and no classifier — the category the reporter picked decides the
agency and the deadline, and a photograph shows how bad it is without inference.

Two things this module does that are easy to get wrong.

**The stored bytes are not the uploaded bytes.** Phone photos carry EXIF, and EXIF
carries the precise coordinates of wherever the person was standing.
``domain.photo_integrity`` is explicit that those coordinates may exist only long
enough to produce a coarse flag and must never be persisted. Storing the original
file would persist them — in a bucket, in a backup, in anything that ever reads the
object — no matter what the database columns say. So the image is re-encoded from
decoded pixels, which drops every metadata block there is. EXIF facts are returned
separately, in memory, for the caller to reduce to flags and drop.

**A file is not what its content type claims.** ``content_type`` comes from the
client and is trivially wrong, by accident or otherwise. Acceptance here depends on
the bytes actually decoding as an image of a declared format, at a sane size.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Final

from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError

from civiclens.domain.photo_integrity import ExifFacts, dhash, read_exif
from civiclens.shared.errors import PhotoValidationError

# A modern phone photo at full resolution runs 3-8 MB, and the people this is for
# are least likely to own a phone that offers to shrink it first. The voice cap of
# 6 MB would reject ordinary submissions, so photos get their own, higher limit.
MAX_PHOTO_BYTES: Final = 12 * 1024 * 1024

# Guard against a decompression bomb: a few hundred kilobytes of PNG can declare a
# 30000x30000 canvas, which is ~3.6 GB once decoded. Checked from the header before
# any pixel is touched, because by the time the decode is running the memory is
# already gone. 40 MP is comfortably above any phone camera.
MAX_PHOTO_PIXELS: Final = 40_000_000
MIN_PHOTO_EDGE: Final = 200

# JPEG and PNG only. Between them they cover every phone camera and every
# screenshot. HEIC is deliberately absent: decoding it needs a native library that
# has had its own CVEs, and browsers transcode it on upload anyway.
_ACCEPTED_FORMATS: Final = {"JPEG": "image/jpeg", "PNG": "image/png"}
_ACCEPTED_CONTENT_TYPES: Final = frozenset(_ACCEPTED_FORMATS.values()) | {"image/jpg"}
_JPEG_QUALITY: Final = 85


@dataclass(frozen=True)
class ValidatedPhoto:
    """Sanitised image bytes plus the facts needed to store and check them.

    ``data`` is the re-encoded image, and it is what must be stored. ``exif`` is
    transient: the caller turns it into flags via
    :func:`civiclens.domain.photo_integrity.integrity_flags` and then lets it go. It
    is not part of the record and must not be logged or returned from an API.
    """

    data: bytes
    content_type: str
    content_hash: str
    byte_size: int
    perceptual_hash: str
    width: int
    height: int
    exif: ExifFacts


def validate_photo(data: bytes, content_type: str | None) -> ValidatedPhoto:
    """Return a sanitised photo, or raise :class:`PhotoValidationError`.

    The declared ``content_type`` is checked first as a cheap filter, but it is not
    trusted: the decoded format has to agree with it.
    """
    if not data:
        raise PhotoValidationError("Photo file is empty")
    if len(data) > MAX_PHOTO_BYTES:
        raise PhotoValidationError("Photo must be 12 MB or smaller")

    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type not in _ACCEPTED_CONTENT_TYPES:
        raise PhotoValidationError("Only JPEG and PNG photos are accepted")

    # The header is inspected before anything decodes a single pixel, and the order
    # here is not cosmetic. `read_exif` and `dhash` below both decode the image, so
    # calling either first would mean a file declaring a 60000x44000 canvas gets
    # expanded in memory before the size limit is ever consulted -- the exact attack
    # the limit exists to stop. Cheap, header-only checks come first; anything that
    # touches pixels comes after.
    image_format, declared_size = _inspect_header(data)
    resolved_type = _ACCEPTED_FORMATS[image_format]
    if resolved_type != normalized_type and not (
        resolved_type == "image/jpeg" and normalized_type == "image/jpg"
    ):
        # The bytes decoded fine, but as a different format than claimed. Refused
        # rather than silently corrected: a mismatch means either a broken client or
        # somebody probing what the server will accept, and neither should get a
        # success.
        raise PhotoValidationError("Photo contents do not match the declared file type")

    width, height = declared_size
    if width * height > MAX_PHOTO_PIXELS:
        raise PhotoValidationError("Photo resolution is too large to process")
    if min(width, height) < MIN_PHOTO_EDGE:
        # Not an aesthetic rule. Below roughly this size an officer cannot tell a
        # crack from a crater, so the photo would be stored, shown, and still leave
        # the severity decision unsupported.
        raise PhotoValidationError("Photo is too small to show the problem clearly")

    # Only now, with the dimensions known to be sane, is it safe to decode. Both of
    # these read the *original* bytes, and both must run before the re-encode, which
    # is precisely what destroys the EXIF they depend on.
    exif = _guarded(read_exif, data)
    perceptual_hash = _guarded(dhash, data)
    sanitized, final_width, final_height = _reencode_without_metadata(data, image_format)

    return ValidatedPhoto(
        data=sanitized,
        content_type=resolved_type,
        content_hash=hashlib.sha256(sanitized).hexdigest(),
        byte_size=len(sanitized),
        perceptual_hash=perceptual_hash,
        width=final_width,
        height=final_height,
        exif=exif,
    )


def _inspect_header(data: bytes) -> tuple[str, tuple[int, int]]:
    """Read format and dimensions without decoding the image.

    ``Image.open`` parses only the header, so ``.size`` is available here for the
    cost of a few bytes. That is what makes it safe to check a declared resolution
    before committing the memory to hold it.
    """
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = (image.format or "").upper()
            size = image.size
    except DecompressionBombError:
        # Pillow has its own, much larger ceiling and raises here rather than
        # returning a size, so this arrives instead of the pixel check below. Mapped
        # to the same refusal on purpose: from the reporter's side the reason is
        # identical, and Pillow's message quotes the declared pixel count from the
        # file, which is attacker-chosen content that should not travel outward.
        raise PhotoValidationError("Photo resolution is too large to process") from None
    except (UnidentifiedImageError, OSError, ValueError):
        raise PhotoValidationError("Photo could not be read as an image") from None
    if image_format not in _ACCEPTED_FORMATS:
        raise PhotoValidationError("Only JPEG and PNG photos are accepted")
    return image_format, size


def _guarded[T](operation: Callable[[bytes], T], data: bytes) -> T:
    """Run a Pillow-backed read, converting any decode failure into a refusal.

    ``read_exif`` and ``dhash`` live in the pure domain layer and raise whatever
    Pillow raises, which is correct for them -- they are not the boundary. This is
    the boundary, so a truncated or malformed file becomes a 422 the reporter can
    act on instead of a 500 nobody can.
    """
    try:
        return operation(data)
    except (UnidentifiedImageError, OSError, ValueError):
        raise PhotoValidationError("Photo could not be read as an image") from None


def _reencode_without_metadata(data: bytes, image_format: str) -> tuple[bytes, int, int]:
    """Decode, then write back out from pixels alone.

    Re-encoding rather than calling a strip-the-EXIF helper is deliberate. Helpers
    remove the blocks they know about; an image can carry location in EXIF, XMP,
    IPTC and a maker note, and a new container can add another next year. Writing
    from decoded pixels cannot carry any of them, because by then there is nothing
    left but pixels.
    """
    try:
        with Image.open(BytesIO(data)) as image:
            # Rotation lives in an EXIF tag, and this function is about to delete
            # every EXIF tag. Applying it first is what keeps a portrait photo
            # upright; skipping it would silently sideways every phone upload.
            upright = _apply_orientation(image)
            buffer = BytesIO()
            if image_format == "JPEG":
                upright.convert("RGB").save(
                    buffer, format="JPEG", quality=_JPEG_QUALITY, optimize=True
                )
            else:
                # PNG keeps its alpha channel: a screenshot with transparency
                # flattened onto black is unreadable.
                upright.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue(), upright.width, upright.height
    except PhotoValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError):
        # Deliberately not forwarding the underlying message. Pillow's decode
        # errors quote offsets and header fragments from the file, and the file is
        # citizen-supplied content that must not travel out in an error.
        raise PhotoValidationError("Photo could not be read as an image") from None


def _apply_orientation(image: Image.Image) -> Image.Image:
    from PIL import ImageOps

    # `exif_transpose` returns None only for inputs this function never sees (it is
    # given an open image), but the type says otherwise, so fall back rather than
    # assert.
    return ImageOps.exif_transpose(image) or image
