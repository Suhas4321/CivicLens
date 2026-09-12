from datetime import UTC, datetime, timedelta
from io import BytesIO

import av
import pytest

from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.infrastructure.media.voice_storage import MemoryVoiceStorage
from civiclens.modules.analysis.service import ReportAnalysisService
from civiclens.modules.intake.repository import MemoryIntakeRepository
from civiclens.modules.intake.schemas import ReportCreateRequest
from civiclens.modules.intake.service import IntakeService
from civiclens.modules.intake.voice import MAX_VOICE_BYTES, validate_voice
from civiclens.shared.errors import MediaValidationError


def encoded_opus_silence() -> bytes:
    output = BytesIO()
    with av.open(output, "w", format="webm") as container:
        stream = container.add_stream("libopus", rate=48_000)
        stream.layout = "mono"
        for index in range(10):
            frame = av.AudioFrame(format="s16", layout="mono", samples=960)
            frame.sample_rate = 48_000
            frame.pts = index * 960
            frame.planes[0].update(bytes(frame.planes[0].buffer_size))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return output.getvalue()


def test_voice_is_decoded_bounded_stored_privately_and_available_to_analysis() -> None:
    validated = validate_voice(encoded_opus_silence(), "audio/webm;codecs=opus")
    storage = MemoryVoiceStorage()
    stored = storage.put(
        validated,
        idempotency_key="voice-idempotency-0001",
        retain_until=datetime.now(UTC) + timedelta(days=7),
    )
    repository = MemoryIntakeRepository()
    intake = IntakeService(repository)
    capability = "voice-receipt-capability-0123456789abcdef"
    accepted = intake.submit(
        ReportCreateRequest(
            description="Synthetic Kannada voice accompanies this low water pressure report.",
            language_hint="kn",
            locality_label="Synthetic voice locality",
            consent=True,
            synthetic_demo_confirmation=True,
        ),
        idempotency_key="voice-idempotency-0001",
        receipt_capability=capability,
        voice=stored,
    )

    result = ReportAnalysisService(repository, FixtureInterpreter(), voice_storage=storage).process(
        accepted.public_id
    )

    assert validated.duration_seconds <= 30
    assert result.report.processing_state == "processed"
    assert result.report.voice_object_key == stored.object_key
    assert storage.get(stored.object_key) == validated.data


def test_voice_rejects_wrong_container_and_oversize_before_storage() -> None:
    with pytest.raises(MediaValidationError):
        validate_voice(b"not-webm", "audio/webm")
    with pytest.raises(MediaValidationError):
        validate_voice(b"\x1aE\xdf\xa3" + bytes(MAX_VOICE_BYTES), "audio/webm")
