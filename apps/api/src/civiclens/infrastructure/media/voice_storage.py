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
from civiclens.modules.intake.voice import ValidatedVoice


@dataclass(frozen=True)
class StoredVoice:
    object_key: str
    content_hash: str
    content_type: str
    byte_size: int
    duration_seconds: float
    retain_until: datetime


class VoiceStorage(Protocol):
    def put(
        self, voice: ValidatedVoice, *, idempotency_key: str, retain_until: datetime
    ) -> StoredVoice: ...

    def get(self, object_key: str) -> bytes: ...


class MemoryVoiceStorage:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._lock = Lock()

    def put(
        self, voice: ValidatedVoice, *, idempotency_key: str, retain_until: datetime
    ) -> StoredVoice:
        object_key = _object_key(idempotency_key, voice.content_hash)
        with self._lock:
            self._objects.setdefault(object_key, voice.data)
        return _metadata(object_key, voice, retain_until)

    def get(self, object_key: str) -> bytes:
        return self._objects[object_key]


class GcsVoiceStorage:
    def __init__(self, bucket_name: str) -> None:
        self._bucket = storage.Client().bucket(  # pyright: ignore[reportUnknownMemberType]
            bucket_name
        )

    def put(
        self, voice: ValidatedVoice, *, idempotency_key: str, retain_until: datetime
    ) -> StoredVoice:
        object_key = _object_key(idempotency_key, voice.content_hash)
        blob = self._bucket.blob(object_key)  # pyright: ignore[reportUnknownMemberType]
        with suppress(PreconditionFailed):
            blob.upload_from_string(  # pyright: ignore[reportUnknownMemberType]
                voice.data,
                content_type=voice.content_type,
                if_generation_match=0,
                timeout=20,
            )
        return _metadata(object_key, voice, retain_until)

    def get(self, object_key: str) -> bytes:
        blob = self._bucket.blob(object_key)  # pyright: ignore[reportUnknownMemberType]
        return blob.download_as_bytes(  # pyright: ignore[reportUnknownMemberType]
            timeout=20
        )


def _object_key(idempotency_key: str, content_hash: str) -> str:
    digest = hashlib.sha256(f"{idempotency_key}:{content_hash}".encode()).hexdigest()
    return f"demo-voice/v1/{digest}.webm"


def _metadata(object_key: str, voice: ValidatedVoice, retain_until: datetime) -> StoredVoice:
    return StoredVoice(
        object_key=object_key,
        content_hash=voice.content_hash,
        content_type=voice.content_type,
        byte_size=voice.byte_size,
        duration_seconds=voice.duration_seconds,
        retain_until=retain_until,
    )


@lru_cache
def get_voice_storage() -> VoiceStorage:
    settings = get_settings()
    if settings.voice_backend == "gcs":
        return GcsVoiceStorage(settings.gcs_media_bucket)
    return MemoryVoiceStorage()
