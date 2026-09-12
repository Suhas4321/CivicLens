from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from threading import Lock

from civiclens.bootstrap.settings import get_settings
from civiclens.infrastructure.ai.fake import FixtureInterpreter
from civiclens.infrastructure.ai.google_genai import GoogleGenAIInterpreter
from civiclens.infrastructure.media.voice_storage import VoiceStorage, get_voice_storage
from civiclens.modules.analysis.ports import AIInterpreter
from civiclens.modules.analysis.schemas import InterpretationRequest
from civiclens.modules.intake.repository import IntakeRecord, IntakeRepository
from civiclens.modules.intake.service import get_intake_repository
from civiclens.modules.safety.evaluator import SafetyFinding, evaluate_safety
from civiclens.shared.errors import AIProviderError


@dataclass(frozen=True)
class ProcessingResult:
    report: IntakeRecord
    safety_findings: tuple[SafetyFinding, ...]


class DailyCallBudget:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._day = datetime.now(UTC).date()
        self._used = 0
        self._lock = Lock()

    def try_consume(self, today: date | None = None) -> bool:
        current_day = today or datetime.now(UTC).date()
        with self._lock:
            if current_day != self._day:
                self._day = current_day
                self._used = 0
            if self._used >= self._limit:
                return False
            self._used += 1
            return True


class ReportAnalysisService:
    def __init__(
        self,
        repository: IntakeRepository,
        interpreter: AIInterpreter,
        call_budget: DailyCallBudget | None = None,
        voice_storage: VoiceStorage | None = None,
    ) -> None:
        self._repository = repository
        self._interpreter = interpreter
        self._call_budget = call_budget
        self._voice_storage = voice_storage

    def process(self, public_id: str) -> ProcessingResult:
        report = self._repository.get_by_public_id(public_id)
        if report.analysis_result_class is not None:
            return ProcessingResult(report=report, safety_findings=())
        if self._call_budget is not None and not self._call_budget.try_consume():
            failed = self._repository.fail_analysis(public_id, "DAILY_CAP_REACHED")
            return ProcessingResult(report=failed, safety_findings=())

        audio_data: bytes | None = None
        if report.voice_object_key is not None:
            if self._voice_storage is None:
                failed = self._repository.fail_analysis(public_id, "VOICE_STORAGE_UNAVAILABLE")
                return ProcessingResult(report=failed, safety_findings=())
            try:
                audio_data = self._voice_storage.get(report.voice_object_key)
            except Exception:
                failed = self._repository.fail_analysis(public_id, "VOICE_READ_FAILED")
                return ProcessingResult(report=failed, safety_findings=())

        request = InterpretationRequest.model_validate(
            {
                "report_id": report.id,
                "text": report.original_text,
                "language_hint": report.language_hint,
                "locality_label": report.locality_label,
                "audio_data": audio_data,
                "audio_content_type": report.voice_content_type,
            }
        )
        try:
            envelope = self._interpreter.interpret(request)
        except AIProviderError as exc:
            failed = self._repository.fail_analysis(public_id, exc.safe_error_code)
            return ProcessingResult(report=failed, safety_findings=())
        findings = evaluate_safety(envelope.interpretation)
        completed = self._repository.complete_analysis(public_id, envelope, findings)
        return ProcessingResult(report=completed, safety_findings=tuple(findings))


@lru_cache
def get_report_analysis_service() -> ReportAnalysisService:
    settings = get_settings()
    interpreter: AIInterpreter = (
        FixtureInterpreter() if settings.ai_backend == "fake" else GoogleGenAIInterpreter(settings)
    )
    budget = None if settings.ai_backend == "fake" else DailyCallBudget(settings.fresh_ai_daily_cap)
    return ReportAnalysisService(get_intake_repository(), interpreter, budget, get_voice_storage())
