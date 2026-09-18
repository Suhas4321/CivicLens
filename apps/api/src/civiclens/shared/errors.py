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
    # Kept as the voice code rather than generalised, because it is already in the
    # published contract and in the web client's error handling. Photos get their
    # own subclass instead of a renamed parent.
    code = "INVALID_VOICE_MEDIA"


class PhotoValidationError(MediaValidationError):
    """A photo the system will not accept, with a reason safe to show a reporter.

    Subclasses ``MediaValidationError`` on purpose: the intake endpoint already
    translates that to a 422, so photo rejections get the right status without a
    second handler that could drift from the first. Only the ``code`` differs, and
    it has to — telling somebody their photo is an ``INVALID_VOICE_MEDIA`` is the
    kind of message that makes a person give up rather than retry.
    """

    code = "INVALID_PHOTO_MEDIA"
