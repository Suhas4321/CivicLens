from __future__ import annotations


class DomainError(Exception):
    """Expected domain failure safe to translate at an application boundary."""

    code = "DOMAIN_ERROR"


class ConfigurationError(DomainError):
    code = "CONFIGURATION_ERROR"


class ConflictError(DomainError):
    code = "CONFLICT"


class NotFoundError(DomainError):
    code = "NOT_FOUND"


class AIProviderError(DomainError):
    code = "AI_PROVIDER_ERROR"

    def __init__(self, safe_error_code: str) -> None:
        super().__init__(safe_error_code)
        self.safe_error_code = safe_error_code


class MediaValidationError(DomainError):
    code = "INVALID_VOICE_MEDIA"
