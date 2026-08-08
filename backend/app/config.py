from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./pitsense.db"
    hf_token: str | None = None
    hf_stt_model: str = "openai/whisper-tiny"
    hf_audio_emotion_model: str = "superb/wav2vec2-base-superb-er"
    hf_text_emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "./uploads"
    demo_mode: bool = True
    auth_required: bool = False
    jwt_secret: str = "change-me-in-production"
    jwt_expiry_minutes: int = 720
    redis_url: str | None = None
    auto_migrate: bool = True
    storage_backend: str = "local"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    retention_days: int = 30
    max_audio_duration_seconds: int = 900
    analysis_version: str = "2026.08.05"
    model_timeout_seconds: int = 300
    environment: str = "development"
    clamscan_command: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def cors_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_production_safe(self) -> bool:
        return bool(self.auth_required and self.jwt_secret != "change-me-in-production" and self.cors_list)


@lru_cache
def get_settings() -> Settings:
    return Settings()
