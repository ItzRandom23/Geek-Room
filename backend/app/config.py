from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./pitsense.db"
    hf_token: str | None = None
    hf_stt_model: str = "openai/whisper-small"
    stt_language: str = "auto"
    hf_audio_emotion_model: str = "superb/wav2vec2-base-superb-er"
    hf_text_emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    hf_embedding_model: str = "microsoft/wavlm-base-plus"
    emotion_confidence_threshold: float = 0.70
    emotion_margin_threshold: float = 0.20
    emotion_artifact_dir: str = "./artifacts/emotion"
    emotion_target_accuracy: float = 0.99
    emotion_calibration_dir: str = "./artifacts/emotion/benchmark"
    benchmark_promotion_manifest: str = "./artifacts/emotion/benchmark/promotion.json"
    benchmark_signing_key: str | None = None
    benchmark_minimum_language_clips: int = 100
    benchmark_minimum_language_speakers: int = 10
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    upload_dir: str = "./uploads"
    demo_mode: bool = True
    auth_required: bool = True
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
    analysis_version: str = "2026.08.09"
    model_timeout_seconds: int = 900
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
