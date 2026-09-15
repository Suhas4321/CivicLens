"""Pure, non-ML integrity checks for uploaded photos.

The citizen-confirmed pin is authoritative. Raw EXIF coordinates exist only in
the transient :class:`ExifFacts` value long enough to produce a coarse integrity
flag, after which callers must discard them. ``ExifFacts`` must never be
persisted, logged or returned from an API.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from typing import Protocol, cast, runtime_checkable

from PIL import ExifTags, Image

_DHASH_WIDTH = 9
_DHASH_HEIGHT = 8
_EARTH_RADIUS_M = 6_371_008.8
_DATE_TIME_ORIGINAL = int(ExifTags.Base.DateTimeOriginal)
_GPS_INFO = int(ExifTags.IFD.GPSInfo)
_GPS_LATITUDE_REF = int(ExifTags.GPS.GPSLatitudeRef)
_GPS_LATITUDE = int(ExifTags.GPS.GPSLatitude)
_GPS_LONGITUDE_REF = int(ExifTags.GPS.GPSLongitudeRef)
_GPS_LONGITUDE = int(ExifTags.GPS.GPSLongitude)


@runtime_checkable
class _SupportsFloat(Protocol):
    def __float__(self) -> float: ...


@dataclass(frozen=True)
class ExifFacts:
    captured_at: datetime | None
    gps_lat: float | None
    gps_lon: float | None
    has_exif: bool


@dataclass(frozen=True)
class Flag:
    code: str
    detail: str


def dhash(image_bytes: bytes) -> str:
    """Return the 64-bit horizontal difference hash as 16 lowercase hex characters."""
    with Image.open(BytesIO(image_bytes)) as image:
        grayscale = image.convert("L")
        resized = grayscale.resize(  # pyright: ignore[reportUnknownMemberType]
            (_DHASH_WIDTH, _DHASH_HEIGHT),
            Image.Resampling.LANCZOS,
        )
        hash_value = 0
        for y in range(_DHASH_HEIGHT):
            for x in range(_DHASH_WIDTH - 1):
                left = cast(int, resized.getpixel((x, y)))
                right = cast(int, resized.getpixel((x + 1, y)))
                hash_value = (hash_value << 1) | int(left > right)
    return f"{hash_value:016x}"


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Return the number of differing bits between two 64-bit hexadecimal hashes."""
    if len(hash_a) != 16 or len(hash_b) != 16:
        raise ValueError("difference hashes must contain exactly 16 hexadecimal characters")
    try:
        value_a = int(hash_a, 16)
        value_b = int(hash_b, 16)
    except ValueError as exc:
        raise ValueError("difference hashes must contain only hexadecimal characters") from exc
    return (value_a ^ value_b).bit_count()


def read_exif(image_bytes: bytes) -> ExifFacts:
    """Read only the capture time and GPS facts needed for transient integrity checks."""
    with Image.open(BytesIO(image_bytes)) as image:
        exif = image.getexif()
        has_exif = len(exif) > 0
        captured_at = _parse_exif_datetime(cast(object, exif.get(_DATE_TIME_ORIGINAL)))
        try:
            gps = cast(dict[int, object], exif.get_ifd(_GPS_INFO))
        except (KeyError, TypeError, ValueError):
            gps = {}

    gps_lat = _gps_coordinate(
        gps.get(_GPS_LATITUDE),
        gps.get(_GPS_LATITUDE_REF),
        negative_ref="S",
        maximum=90.0,
    )
    gps_lon = _gps_coordinate(
        gps.get(_GPS_LONGITUDE),
        gps.get(_GPS_LONGITUDE_REF),
        negative_ref="W",
        maximum=180.0,
    )
    if gps_lat is None or gps_lon is None:
        gps_lat = None
        gps_lon = None

    return ExifFacts(
        captured_at=captured_at,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        has_exif=has_exif,
    )


def integrity_flags(
    exif: ExifFacts,
    pin_lon: float,
    pin_lat: float,
    submitted_at: datetime,
) -> tuple[Flag, ...]:
    """Reduce transient EXIF facts to non-precise, officer-visible flags."""
    flags: list[Flag] = []

    if exif.captured_at is None:
        flags.append(Flag("PHOTO_UNDATED", "Photo has no capture date"))
    else:
        captured_at, comparable_submitted_at = _align_timezones(
            exif.captured_at,
            submitted_at,
        )
        if captured_at > comparable_submitted_at:
            flags.append(Flag("PHOTO_FUTURE_DATED", "Photo capture date is after submission"))
        elif comparable_submitted_at - captured_at > timedelta(days=7):
            flags.append(
                Flag("PHOTO_STALE", "Photo was captured more than 7 days before submission")
            )

    if exif.gps_lat is None or exif.gps_lon is None:
        flags.append(Flag("EXIF_LOCATION_ABSENT", "Photo has no EXIF location"))
        return tuple(flags)

    distance_m = _haversine_metres(
        lon_a=exif.gps_lon,
        lat_a=exif.gps_lat,
        lon_b=pin_lon,
        lat_b=pin_lat,
    )
    rounded_distance_m = int(math.floor(distance_m / 100.0 + 0.5)) * 100
    detail = f"EXIF location is {rounded_distance_m} m from the confirmed pin"
    if distance_m <= 100.0:
        code = "EXIF_LOCATION_MATCH"
    elif distance_m <= 1_000.0:
        code = "EXIF_LOCATION_NEAR"
    else:
        code = "EXIF_LOCATION_FAR"
    flags.append(Flag(code, detail))
    return tuple(flags)


def _parse_exif_datetime(value: object) -> datetime | None:
    if isinstance(value, bytes):
        try:
            text = value.decode("ascii")
        except UnicodeDecodeError:
            return None
    elif isinstance(value, str):
        text = value
    else:
        return None
    try:
        return datetime.strptime(text.rstrip("\x00").strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _gps_coordinate(
    raw_values: object,
    raw_ref: object,
    *,
    negative_ref: str,
    maximum: float,
) -> float | None:
    if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
        return None
    values = cast(Sequence[object], raw_values)
    if len(values) != 3:
        return None

    parts = tuple(_as_float(value) for value in values)
    if any(value is None for value in parts):
        return None
    degrees, minutes, seconds = cast(tuple[float, float, float], parts)
    coordinate = degrees + minutes / 60.0 + seconds / 3_600.0
    if coordinate > maximum:
        return None

    ref = _gps_ref(raw_ref)
    if ref is None:
        return None
    if ref == negative_ref:
        coordinate = -coordinate
    return coordinate


def _as_float(value: object) -> float | None:
    if not isinstance(value, _SupportsFloat):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _gps_ref(value: object) -> str | None:
    if isinstance(value, bytes):
        try:
            text = value.decode("ascii")
        except UnicodeDecodeError:
            return None
    elif isinstance(value, str):
        text = value
    else:
        return None
    ref = text.rstrip("\x00").strip().upper()
    return ref if ref in {"N", "S", "E", "W"} else None


def _align_timezones(captured_at: datetime, submitted_at: datetime) -> tuple[datetime, datetime]:
    if captured_at.tzinfo is None and submitted_at.tzinfo is not None:
        captured_at = captured_at.replace(tzinfo=submitted_at.tzinfo)
    elif captured_at.tzinfo is not None and submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=captured_at.tzinfo)
    return captured_at, submitted_at


def _haversine_metres(*, lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    lat_a_rad = math.radians(lat_a)
    lat_b_rad = math.radians(lat_b)
    delta_lat = lat_b_rad - lat_a_rad
    delta_lon = math.radians(lon_b - lon_a)
    haversine = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat_a_rad) * math.cos(lat_b_rad) * math.sin(delta_lon / 2.0) ** 2
    )
    return 2.0 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(haversine)))
