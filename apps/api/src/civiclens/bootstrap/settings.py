from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration with safe local defaults."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["local", "test", "preview", "production"] = "local"
    app_version: str = "dev"
    public_base_url: str = "http://localhost:5173"
    allowed_web_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg://civiclens:civiclens@localhost:5432/civiclens"
    gcp_project_id: str = ""
    gcp_region: str = "asia-south1"
    gcs_media_bucket: str = ""
    cloud_tasks_queue: str = ""
    task_handler_audience: str = ""
    firebase_project_id: str = ""

    ai_backend: Literal["fake", "developer", "vertex"] = "fake"
    intake_backend: Literal["memory", "postgres"] = "memory"
    session_backend: Literal["memory", "postgres"] = "memory"
    decision_backend: Literal["memory", "postgres"] = "memory"
    voice_backend: Literal["memory", "gcs"] = "memory"
    gemini_model: str = "gemini-3.6-flash"
    gemini_api_key: SecretStr = SecretStr("")
    demo_mode_enabled: bool = True
    demo_seed_version: str = "v1"
    public_snapshot_version: str = "bengaluru-water-v1"
    report_retention_days: int = Field(default=7, ge=1, le=30)
    demo_session_ttl_minutes: int = Field(default=120, ge=15, le=1440)
    fresh_ai_daily_cap: int = Field(default=50, ge=0, le=1000)
    log_level: str = "INFO"

    schema_version: str = "20260912_0001"
    prompt_version: str = "report-interpretation-v1"
    rules_version: str = "civic-rules-v1"
    catalogue_version: str = "assessment-catalogue-v1"

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("PUBLIC_BASE_URL must use http or https")
        return value.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")
        return normalized

    @property
    def web_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.allowed_web_origins.split(",")
            if origin.strip()
        ]

    def validate_deployed_environment(self) -> list[str]:
        if self.app_env in {"preview", "production"}:
            required = {
                "GCP_PROJECT_ID": self.gcp_project_id,
                "FIREBASE_PROJECT_ID": self.firebase_project_id,
            }
            missing = [name for name, value in required.items() if not value]
            if self.intake_backend != "postgres":
                missing.append("INTAKE_BACKEND=postgres")
            if self.session_backend != "postgres":
                missing.append("SESSION_BACKEND=postgres")
            if self.decision_backend != "postgres":
                missing.append("DECISION_BACKEND=postgres")
            if self.voice_backend != "gcs":
                missing.append("VOICE_BACKEND=gcs")
            if not self.gcs_media_bucket:
                missing.append("GCS_MEDIA_BUCKET")
            if self.app_env == "production" and self.ai_backend != "vertex":
                missing.append("AI_BACKEND=vertex")
            if self.app_env == "production" and not self.gemini_model:
                missing.append("GEMINI_MODEL")
            return missing
        return []


@lru_cache
def get_settings() -> Settings:
    return Settings()
