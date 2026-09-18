"""Durable storage for sanitised photos.

Deliberately a near-copy of :mod:`civiclens.infrastructure.media.voice_storage`
rather than a shared generic adapter. The two media types differ in the things a
shared abstraction would have to hide — content types, size limits, key prefixes,
and whether a duration exists at all — so factoring them together would produce a
parameter bag that is harder to read than either file. If a third medium ever
appears, that is the moment to generalise, with three examples to generalise from.

The bytes written here are the re-encoded ones from ``intake.photo``, never the
uploaded originals, so no EXIF location reaches the bucket. See that module.
"""

from __future__ import annotations

import hashlib
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from threading import Lock
from typing import Protocol

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage  # pyright: ignore[reportMissingTypeStubs]

from civiclens.bootstrap.settings import get_settings
from civiclens.modules.intake.photo import ValidatedPhoto

_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png"}


@dataclass(frozen=True)
class StoredPhoto:
    object_key: str
    content_hash: str
    content_type: str
    byte_size: int
    # Carried through to the database so officers can be shown "this looks like a
    # photo already on file" without a second image ever being fetched and compared.
    perceptual_hash: str
    retain_until: datetime


class PhotoStorage(Protocol):
    def put(
        self, photo: ValidatedPhoto, *, idempotency_key: str, retain_until: datetime
    ) -> StoredPhoto: ...

    def get(self, object_key: str) -> bytes: ...


class MemoryPhotoStorage:
    """Process-local storage for local demos and tests."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._lock = Lock()

    def put(
        self, photo: ValidatedPhoto, *, idempotency_key: str, retain_until: datetime
    ) -> StoredPhoto:
        object_key = _object_key(idempotency_key, photo)
        with self._lock:
            # `setdefault`, so a retried submission under the same idempotency key
            # cannot overwrite the bytes the first attempt already stored.
            self._objects.setdefault(object_key, photo.data)
        return _metadata(object_key, photo, retain_until)

    def get(self, object_key: str) -> bytes:
        return self._objects[object_key]


class GcsPhotoStorage:
    def __init__(self, bucket_name: str) -> None:
        self._bucket = storage.Client().bucket(  # pyright: ignore[reportUnknownMemberType]
            bucket_name
        )

    def put(
        self, photo: ValidatedPhoto, *, idempotency_key: str, retain_until: datetime
    ) -> StoredPhoto:
        object_key = _object_key(idempotency_key, photo)
        blob = self._bucket.blob(object_key)  # pyright: ignore[reportUnknownMemberType]
        # `if_generation_match=0` means "only if this object does not exist", so a
        # retry is a no-op instead of a rewrite, and `PreconditionFailed` is the
        # success case rather than an error.
        with suppress(PreconditionFailed):
            blob.upload_from_string(  # pyright: ignore[reportUnknownMemberType]
                photo.data,
                content_type=photo.content_type,
                if_generation_match=0,
                timeout=30,
            )
        return _metadata(object_key, photo, retain_until)

    def get(self, object_key: str) -> bytes:
        blob = self._bucket.blob(object_key)  # pyright: ignore[reportUnknownMemberType]
        return blob.download_as_bytes(  # pyright: ignore[reportUnknownMemberType]
            timeout=30
        )


def _object_key(idempotency_key: str, photo: ValidatedPhoto) -> str:
    # Hashed rather than readable. The key ends up in logs, bucket listings and
    # error traces, and anything derived from the report would leak there; a digest
    # is still stable for idempotency while carrying nothing about the report.
    digest = hashlib.sha256(f"{idempotency_key}:{photo.content_hash}".encode()).hexdigest()
    return f"demo-photo/v1/{digest}.{_EXTENSIONS[photo.content_type]}"


def _metadata(object_key: str, photo: ValidatedPhoto, retain_until: datetime) -> StoredPhoto:
    return StoredPhoto(
        object_key=object_key,
        content_hash=photo.content_hash,
        content_type=photo.content_type,
        byte_size=photo.byte_size,
        perceptual_hash=photo.perceptual_hash,
        retain_until=retain_until,
    )


@lru_cache
def get_photo_storage() -> PhotoStorage:
    settings = get_settings()
    if settings.photo_backend == "gcs":
        return GcsPhotoStorage(settings.gcs_media_bucket)
    return MemoryPhotoStorage()
