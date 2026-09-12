from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import cast

from google import genai
from google.genai import errors, types

from civiclens.bootstrap.policy import load_policy_bundle, repository_root
from civiclens.bootstrap.settings import Settings
from civiclens.modules.analysis.schemas import (
    InterpretationEnvelope,
    InterpretationRequest,
    ReportInterpretation,
)
from civiclens.shared.errors import AIProviderError, ConfigurationError


class GoogleGenAIInterpreter:
    """Schema-constrained Gemini adapter with no tools or policy fields."""

    def __init__(self, settings: Settings, root: Path | None = None) -> None:
        if settings.ai_backend not in {"developer", "vertex"}:
            raise ConfigurationError("Google adapter requires developer or vertex backend")
        if not settings.gemini_model:
            raise ConfigurationError("GEMINI_MODEL is required")

        self._settings = settings
        prompt_root = (root or repository_root()) / "config/prompts/report-interpretation-v1"
        load_policy_bundle(root)
        self._system = (prompt_root / "system.md").read_text()
        self._task = (prompt_root / "task.md").read_text()
        http_options = types.HttpOptions(
            api_version="v1" if settings.ai_backend == "vertex" else None,
            timeout=20_000,
        )
        if settings.ai_backend == "vertex":
            self._client = genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_region,
                http_options=http_options,
            )
        else:
            api_key = settings.gemini_api_key.get_secret_value()
            if not api_key:
                raise ConfigurationError("GEMINI_API_KEY is required for developer backend")
            self._client = genai.Client(api_key=api_key, http_options=http_options)

    def interpret(self, request: InterpretationRequest) -> InterpretationEnvelope:
        started = perf_counter()
        text_content = (
            self._task
            + "\n\nUNTRUSTED_REPORT_JSON:\n"
            + json.dumps(
                {
                    "text": request.text,
                    "language_hint": request.language_hint,
                    "locality_label": request.locality_label,
                },
                ensure_ascii=False,
            )
        )
        contents: object = text_content
        if request.audio_data is not None and request.audio_content_type is not None:
            contents = [
                text_content,
                types.Part.from_bytes(
                    data=request.audio_data,
                    mime_type=request.audio_content_type,
                ),
            ]
        try:
            response = self._client.models.generate_content(  # pyright: ignore[reportUnknownMemberType]
                model=self._settings.gemini_model,
                contents=contents,  # pyright: ignore[reportArgumentType]
                config=types.GenerateContentConfig(
                    system_instruction=self._system,
                    temperature=0,
                    candidate_count=1,
                    max_output_tokens=1200,
                    response_mime_type="application/json",
                    response_schema=ReportInterpretation,
                    tools=[],
                ),
            )
        except errors.APIError as exc:
            safe_code = "RATE_LIMITED" if exc.code == 429 else "PROVIDER_UNAVAILABLE"
            raise AIProviderError(safe_code) from None
        except Exception:
            raise AIProviderError("PROVIDER_UNAVAILABLE") from None

        parsed = cast(object, response.parsed)
        try:
            interpretation = (
                parsed
                if isinstance(parsed, ReportInterpretation)
                else ReportInterpretation.model_validate(parsed)
            )
        except Exception:
            raise AIProviderError("INVALID_STRUCTURED_RESPONSE") from None

        return InterpretationEnvelope(
            interpretation=interpretation,
            provider="google-genai",
            configured_model=self._settings.gemini_model,
            returned_model=response.model_version,
            prompt_version="report-interpretation-v1",
            schema_version="report-interpretation-schema-v1",
            result_class="fresh_ai",
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
        )
