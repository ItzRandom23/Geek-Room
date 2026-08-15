from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    driver_name: str = Field(min_length=1, max_length=120)
    circuit_name: str = Field(min_length=1, max_length=120)


class AuthRegister(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    organization_name: str = Field(min_length=1, max_length=160)


class AuthLogin(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=5, max_length=255)


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AnalysisRequest(BaseModel):
    mode: str = Field(default="auto", pattern="^(auto|audio_only|lap_correlated)$")


class SessionSummary(BaseModel):
    id: int
    name: str
    driver_name: str
    circuit_name: str
    created_at: datetime
    status: str
    is_demo: bool = False
    audio_count: int = 0
    lap_count: int = 0


class LapInput(BaseModel):
    lap_number: int = Field(gt=0)
    lap_time_seconds: float = Field(gt=0, lt=1000)
    start_timestamp_seconds: float = Field(ge=0)
    end_timestamp_seconds: float = Field(gt=0)


class AudioInfo(BaseModel):
    id: int
    original_filename: str
    duration_seconds: float | None
    uploaded_at: datetime


class TranscriptItem(BaseModel):
    id: int
    start_seconds: float
    end_seconds: float
    text: str


class EmotionItem(BaseModel):
    id: int
    normalized_label: str
    raw_label: str
    confidence: float
    source: str
    start_seconds: float
    end_seconds: float


class LapItem(BaseModel):
    id: int
    lap_number: int
    lap_time_seconds: float
    start_timestamp_seconds: float
    end_timestamp_seconds: float


class InsightItem(BaseModel):
    id: int
    type: str
    severity: str
    title: str
    explanation: str
    recommendation: str
    supporting_data: dict


class SessionDetail(SessionSummary):
    audio: list[AudioInfo] = []
    laps: list[LapItem] = []
    transcript: list[TranscriptItem] = []
    emotions: list[EmotionItem] = []
    insights: list[InsightItem] = []
    report: dict | None = None
