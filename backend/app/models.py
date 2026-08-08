from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    driver_name: Mapped[str] = mapped_column(String(120))
    circuit_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(40), default="ready")
    is_demo: Mapped[bool] = mapped_column(default=False)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    analysis_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    analysis_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active_clip_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    audio_clips: Mapped[list["AudioClip"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    laps: Mapped[list["Lap"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    insights: Mapped[list["Insight"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AudioClip(Base):
    __tablename__ = "audio_clips"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="uploaded")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    session: Mapped[Session] = relationship(back_populates="audio_clips")
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(back_populates="clip", cascade="all, delete-orphan")
    emotion_results: Mapped[list["EmotionResult"]] = relationship(back_populates="clip", cascade="all, delete-orphan")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("audio_clips.id", ondelete="CASCADE"))
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    clip: Mapped[AudioClip] = relationship(back_populates="transcript_segments")


class EmotionResult(Base):
    __tablename__ = "emotion_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("audio_clips.id", ondelete="CASCADE"))
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("transcript_segments.id", ondelete="SET NULL"), nullable=True)
    normalized_label: Mapped[str] = mapped_column(String(40))
    raw_label: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    raw_output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    clip: Mapped[AudioClip] = relationship(back_populates="emotion_results")


class Lap(Base):
    __tablename__ = "laps"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    lap_number: Mapped[int] = mapped_column(Integer)
    lap_time_seconds: Mapped[float] = mapped_column(Float)
    start_timestamp_seconds: Mapped[float] = mapped_column(Float)
    end_timestamp_seconds: Mapped[float] = mapped_column(Float)
    session: Mapped[Session] = relationship(back_populates="laps")
    __table_args__ = (UniqueConstraint("session_id", "lap_number", name="uq_lap_session_number"), Index("ix_lap_session_time", "session_id", "start_timestamp_seconds"))


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    explanation: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    supporting_data_json: Mapped[str] = mapped_column(Text, default="{}")
    session: Mapped[Session] = relationship(back_populates="insights")


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(30), default="engineer")
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(30), default="audio_only")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retryable: Mapped[bool] = mapped_column(Boolean, default=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session: Mapped[Session] = relationship(back_populates="jobs")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(40))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
