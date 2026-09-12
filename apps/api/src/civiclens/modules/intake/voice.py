from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

import av

from civiclens.shared.errors import MediaValidationError

MAX_VOICE_BYTES = 6 * 1024 * 1024
MAX_VOICE_SECONDS = 30.0
VOICE_CONTENT_TYPE = "audio/webm"


@dataclass(frozen=True)
class ValidatedVoice:
    data: bytes
    content_type: str
    content_hash: str
    byte_size: int
    duration_seconds: float


def validate_voice(data: bytes, content_type: str | None) -> ValidatedVoice:
    if not data or len(data) > MAX_VOICE_BYTES:
        raise MediaValidationError("Voice must be between 1 byte and 6 MB")
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type != VOICE_CONTENT_TYPE:
        raise MediaValidationError("Only WebM/Opus voice is accepted")
    if not data.startswith(b"\x1aE\xdf\xa3"):
        raise MediaValidationError("Voice container signature is invalid")

    try:
        with av.open(BytesIO(data), mode="r", format="webm") as container:
            audio_streams = [stream for stream in container.streams if stream.type == "audio"]
            if len(audio_streams) != 1 or any(
                stream.type == "video" for stream in container.streams
            ):
                raise MediaValidationError("Voice must contain exactly one audio stream")
            stream = audio_streams[0]
            if stream.codec_context.name != "opus":
                raise MediaValidationError("Voice codec must be Opus")

            duration_seconds = 0.0
            for decoded_frames, frame in enumerate(container.decode(audio=stream.index), start=1):
                if decoded_frames > 4000 or not frame.sample_rate:
                    raise MediaValidationError("Voice decode limits exceeded")
                duration_seconds += frame.samples / frame.sample_rate
                if duration_seconds > MAX_VOICE_SECONDS + 0.25:
                    raise MediaValidationError("Voice must be at most 30 seconds")
    except MediaValidationError:
        raise
    except Exception:
        raise MediaValidationError("Voice could not be decoded safely") from None

    if duration_seconds <= 0:
        raise MediaValidationError("Voice contains no decodable audio")
    return ValidatedVoice(
        data=data,
        content_type=VOICE_CONTENT_TYPE,
        content_hash=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        duration_seconds=round(duration_seconds, 2),
    )
