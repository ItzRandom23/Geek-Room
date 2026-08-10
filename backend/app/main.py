import json
import logging
import re
import uuid
import csv
import io
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from .auth import create_access_token, get_current_user, hash_password, verify_password
from .config import get_settings
from .database import get_db, run_migrations
from .models import AnalysisJob, AuditEvent, AudioClip, Insight, Lap, Membership, Organization, Session, User
from .schemas import AnalysisRequest, AuthLogin, AuthRegister, LapInput, SessionCreate
from .services.ai import ProviderBundle, build_provider_bundle, emotion_model_status, normalize_language
from .services.analysis import Event, build_report, event_lap, overlapping_text
from .services.audio import audio_duration, resolve_audio, save_audio
from .services.csv_import import parse_lap_csv, validate_lap_rows
from .services.pdf_report import render_pdf_report
from .jobs import enqueue_analysis, serialize_job
from .storage import get_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pitsense")
settings = get_settings()
storage = get_storage()
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
def validate_startup_configuration():
    if settings.environment.lower() != "production":
        return
    required = {"AUTH_REQUIRED": settings.auth_required, "JWT_SECRET": settings.jwt_secret != "change-me-in-production", "DATABASE_URL": not settings.database_url.startswith("sqlite"), "REDIS_URL": bool(settings.redis_url), "STORAGE_BACKEND": settings.storage_backend.lower() == "s3", "S3_BUCKET": bool(settings.s3_bucket)}
    missing = [key for key, valid in required.items() if not valid]
    if missing:
        raise RuntimeError("Production configuration is incomplete: " + ", ".join(missing))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_startup_configuration()
    yield


run_migrations()
app = FastAPI(title="PitSense AI API", version="1.0.0", description="Race radio intelligence and lap-performance correlation API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
_rate_events: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    if request.method == "POST" and ("/audio" in request.url.path or request.url.path.endswith("/analyse")):
        bucket = "upload" if "/audio" in request.url.path else "analysis"
        limit = 30 if bucket == "upload" else 10
        key = f"{bucket}:{request.client.host if request.client else 'unknown'}"
        events = _rate_events[key]
        cutoff = time.monotonic() - 60
        while events and events[0] < cutoff:
            events.popleft()
        if len(events) >= limit:
            return JSONResponse(status_code=429, content={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please wait before retrying.", "retryable": True, "request_id": request_id}}, headers={"Retry-After": "60", "x-request-id": request_id})
        events.append(time.monotonic())
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["permissions-policy"] = "microphone=(), camera=()"
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 413: "UPLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA", 422: "VALIDATION_ERROR"}.get(exc.status_code, "REQUEST_FAILED")
    if detail.startswith("ANALYSIS_IN_PROGRESS:"):
        code = "ANALYSIS_IN_PROGRESS"
        detail = detail.split(":", 1)[1].strip()
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": detail, "retryable": exc.status_code >= 500, "request_id": getattr(request.state, "request_id", None)}}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.", "retryable": False, "request_id": getattr(request.state, "request_id", None), "fields": exc.errors()}})


def get_session_or_404(db: DbSession, session_id: int, user: User | None = None) -> Session:
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Analysis session not found.")
    if settings.auth_required:
        if user is None or session.organization_id is None:
            raise HTTPException(403, "You do not have access to this session.")
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == session.organization_id))
        if not membership:
            raise HTTPException(403, "You do not have access to this session.")
    return session


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "team"


def primary_organization(db: DbSession, user: User | None) -> Organization | None:
    if user is None:
        return None
    return db.scalar(select(Organization).join(Membership, Membership.organization_id == Organization.id).where(Membership.user_id == user.id).order_by(Organization.id))


def audit(db: DbSession, action: str, session: Session | None = None, user: User | None = None, metadata: dict | None = None) -> None:
    db.add(AuditEvent(organization_id=session.organization_id if session else None, user_id=user.id if user else None, session_id=session.id if session else None, action=action, metadata_json=json.dumps(metadata or {})))


def serialize_insight(item: Insight) -> dict:
    return {"id": item.id, "type": item.type, "severity": item.severity, "title": item.title, "explanation": item.explanation, "recommendation": item.recommendation, "supporting_data": json.loads(item.supporting_data_json or "{}")}


def active_clip(session: Session) -> AudioClip | None:
    if session.active_clip_id is not None:
        selected = next((clip for clip in session.audio_clips if clip.id == session.active_clip_id), None)
        if selected:
            return selected
    return max(session.audio_clips, key=lambda clip: clip.uploaded_at, default=None)


def _is_english(language: str | None) -> bool:
    return (language or "und").lower().split("-", 1)[0] == "en"


def ensure_session_mutable(db: DbSession, session: Session) -> None:
    active_job = db.scalar(select(AnalysisJob).where(AnalysisJob.session_id == session.id, AnalysisJob.status.in_(["queued", "running"])))
    if active_job:
        raise HTTPException(409, "ANALYSIS_IN_PROGRESS: Cancel the active analysis before changing audio or lap data.")


def build_current_report(session: Session, clip: AudioClip) -> dict:
    transcript_segments = sorted(clip.transcript_segments, key=lambda row: row.start_seconds)
    transcript = " ".join(segment.text for segment in transcript_segments).strip()
    events = [
        Event(
            item.normalized_label,
            item.confidence,
            item.start_seconds,
            item.end_seconds,
            overlapping_text(transcript_segments, item.start_seconds, item.end_seconds),
            item.source,
        )
        for item in sorted(clip.emotion_results, key=lambda row: row.start_seconds)
    ]
    mode = session.analysis_mode or ("lap_correlated" if session.laps else "audio_only")
    laps = sorted(session.laps, key=lambda row: row.lap_number) if mode == "lap_correlated" else []
    # Older rows used values such as "auto" before detection was persisted.
    # Keep that state unknown rather than presenting a fabricated language.
    language = normalize_language(clip.detected_language)
    report = build_report(
        events,
        laps,
        transcript,
        transcript_segments=transcript_segments,
        audio_duration_seconds=clip.duration_seconds,
        language=language,
        text_signals_applied=_is_english(language),
    )
    model_status = emotion_model_status(settings)
    report.update({
        "analysis_mode": mode,
        "correlation_available": bool(mode == "lap_correlated" and laps),
        "association_notice": "Associations are not proof of causation." if mode == "lap_correlated" and laps else "Audio-only analysis: no lap-performance conclusion was made.",
        "provenance": {
            "models": {"stt": settings.hf_stt_model, "audio_emotion": model_status["model"], "text_emotion": settings.hf_text_emotion_model},
            "language": language,
            "transcription_task": "transcribe",
            "text_signals_applied": _is_english(language),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_version": session.analysis_version or settings.analysis_version,
            "model_version": model_status["model_version"],
            "validation_accuracy": model_status["validation_accuracy"],
            "confidence_threshold": model_status["confidence_threshold"],
            "prediction_coverage": model_status["prediction_coverage"],
            "audio_analyzer": model_status.get("analyzer_provenance"),
            "legacy_report_rebuilt": True,
        },
    })
    return report


def make_report(session: Session) -> dict:
    completed_job = max((job for job in session.jobs if job.status == "completed" and job.result_json), key=lambda job: job.completed_at or job.created_at, default=None)
    if completed_job:
        try:
            stored = json.loads(completed_job.result_json)
            if stored.get("schema_version") == 2:
                return stored
        except json.JSONDecodeError:
            logger.warning("Stored report for job %s is invalid; rebuilding it.", completed_job.id)
    clip = active_clip(session)
    if clip is None:
        report = build_report([], [], "", language="und", text_signals_applied=False)
        report.update({"analysis_mode": session.analysis_mode or "audio_only", "correlation_available": False, "association_notice": "Audio-only analysis: no lap-performance conclusion was made."})
        return report
    return build_current_report(session, clip)


def serialize_session(session: Session, include_analysis: bool = False) -> dict:
    audio = []
    for item in session.audio_clips:
        duration = item.duration_seconds
        if duration is None:
            try:
                with storage.materialize(item.stored_filename) as path:
                    duration = audio_duration(path)
            except FileNotFoundError:
                duration = None
        audio.append({"id": item.id, "original_filename": item.original_filename, "duration_seconds": duration, "detected_language": item.detected_language, "sample_rate": item.sample_rate, "processing_status": item.processing_status, "active": item.id == session.active_clip_id, "uploaded_at": item.uploaded_at})
    laps = [{"id": item.id, "lap_number": item.lap_number, "lap_time_seconds": item.lap_time_seconds, "start_timestamp_seconds": item.start_timestamp_seconds, "end_timestamp_seconds": item.end_timestamp_seconds} for item in sorted(session.laps, key=lambda row: row.lap_number)]
    payload = {"id": session.id, "name": session.name, "driver_name": session.driver_name, "circuit_name": session.circuit_name, "created_at": session.created_at, "status": session.status, "is_demo": session.is_demo, "organization_id": session.organization_id, "analysis_mode": session.analysis_mode, "active_clip_id": session.active_clip_id, "audio_count": len(audio), "lap_count": len(laps), "audio": audio, "laps": laps}
    if include_analysis:
        clip = active_clip(session)
        transcript = [{"id": item.id, "start_seconds": item.start_seconds, "end_seconds": item.end_seconds, "text": item.text} for item in sorted(clip.transcript_segments if clip else [], key=lambda row: row.start_seconds)]
        emotions = [{"id": item.id, "normalized_label": item.normalized_label, "raw_label": item.raw_label, "confidence": item.confidence, "source": item.source, "start_seconds": item.start_seconds, "end_seconds": item.end_seconds} for item in sorted(clip.emotion_results if clip else [], key=lambda row: row.start_seconds)]
        payload.update({"transcript": transcript, "emotions": emotions, "insights": [serialize_insight(item) for item in session.insights], "report": make_report(session) if session.status == "analysed" else None})
    return payload


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "pitsense-backend", "version": app.version}


@app.get("/api/readiness")
def readiness(db: DbSession = Depends(get_db)):
    checks = {"database": "ok", "models_configured": bool(settings.hf_stt_model and settings.hf_audio_emotion_model)}
    try:
        db.execute(select(1))
    except Exception:
        checks["database"] = "error"
    if settings.redis_url:
        try:
            from redis import Redis
            Redis.from_url(settings.redis_url).ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
    ready = checks["database"] == "ok" and checks["models_configured"] and checks.get("redis", "ok") == "ok"
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ready" if ready else "not_ready", "checks": checks})


@app.get("/api/models/status")
def models_status():
    return {"stt": {"model": settings.hf_stt_model, "configured": bool(settings.hf_stt_model)}, "audio_emotion": emotion_model_status(settings), "text_emotion": {"model": settings.hf_text_emotion_model, "configured": bool(settings.hf_text_emotion_model)}, "hf_token_present": bool(settings.hf_token), "inference_location": "backend"}


@app.get("/api/models/benchmark")
def model_benchmark_scorecard():
    """Expose a safe, read-only comparison view of the latest benchmark."""
    path = Path(settings.emotion_calibration_dir) / "benchmark-report.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False, "reason": "No completed benchmark report is available."}
    candidates = []
    for identifier, value in (report.get("candidates") or {}).items():
        spec = value.get("candidate") or {}
        candidates.append({
            "candidate_id": identifier,
            "model_id": spec.get("model_id"),
            "revision": value.get("revision"),
            "license": spec.get("license_name"),
            "language_scope": spec.get("language_scope", []),
            "metrics": value.get("metrics", {}),
            "cross_domain_public": value.get("cross_domain_public"),
            "promotion": (report.get("promotion_decisions") or {}).get(identifier, {"passed": False}),
        })
    return {
        "available": True,
        "generated_at": report.get("generated_at"),
        "environment": report.get("environment"),
        "pilot": report.get("pilot"),
        "split_sizes": report.get("split_sizes"),
        "public_cross_domain_clips": report.get("public_cross_domain_clips", 0),
        "candidates": candidates,
    }


@app.post("/api/auth/register", status_code=201)
def register(payload: AuthRegister, db: DbSession = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with that email already exists.")
    slug = slugify(payload.organization_name)
    if db.scalar(select(Organization).where(Organization.slug == slug)):
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
    organization = Organization(name=payload.organization_name.strip(), slug=slug)
    db.add_all([user, organization])
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
    db.commit()
    return {"access_token": create_access_token(user, organization), "token_type": "bearer", "user": {"id": user.id, "email": user.email, "full_name": user.full_name}, "organization": {"id": organization.id, "name": organization.name, "role": "owner"}}


@app.post("/api/auth/login")
def login(payload: AuthLogin, db: DbSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    organization = primary_organization(db, user)
    if not organization:
        raise HTTPException(403, "Your account is not assigned to an organization.")
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == organization.id))
    return {"access_token": create_access_token(user, organization), "token_type": "bearer", "user": {"id": user.id, "email": user.email, "full_name": user.full_name}, "organization": {"id": organization.id, "name": organization.name, "role": membership.role if membership else "engineer"}}


@app.get("/api/me")
def me(user: User | None = Depends(get_current_user), db: DbSession = Depends(get_db)):
    if user is None:
        return {"authenticated": False}
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    organizations = [{"id": item.organization_id, "role": item.role, "name": db.get(Organization, item.organization_id).name} for item in memberships]
    return {"authenticated": True, "user": {"id": user.id, "email": user.email, "full_name": user.full_name}, "organizations": organizations}


@app.get("/api/organizations")
def organizations(user: User | None = Depends(get_current_user), db: DbSession = Depends(get_db)):
    if user is None:
        return []
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return [{"id": item.organization_id, "role": item.role, "name": db.get(Organization, item.organization_id).name} for item in memberships]


@app.post("/api/sessions", status_code=201)
def create_session(payload: SessionCreate, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    organization = primary_organization(db, user)
    if settings.auth_required and not organization:
        raise HTTPException(403, "Create or join an organization before creating sessions.")
    session = Session(name=payload.name.strip(), driver_name=payload.driver_name.strip(), circuit_name=payload.circuit_name.strip(), status="ready", organization_id=organization.id if organization else None, created_by_user_id=user.id if user else None)
    db.add(session)
    db.flush()
    audit(db, "session.created", session, user)
    db.commit()
    db.refresh(session)
    return serialize_session(session)


@app.get("/api/sessions")
def list_sessions(db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    query = select(Session).order_by(Session.created_at.desc())
    organization = primary_organization(db, user)
    if settings.auth_required:
        query = query.where(Session.organization_id == (organization.id if organization else -1))
    sessions = db.scalars(query).all()
    return [serialize_session(session) for session in sessions]


@app.get("/api/sessions/{session_id}")
def get_session(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    return serialize_session(session, include_analysis=True)


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    filenames = [clip.stored_filename for clip in session.audio_clips]
    audit(db, "session.deleted", session, user, {"audio_count": len(filenames)})
    db.delete(session)
    db.commit()
    for filename in filenames:
        if settings.storage_backend.lower() == "s3":
            storage.delete(filename)
        else:
            try:
                resolve_audio(settings.upload_dir, filename).unlink(missing_ok=True)
            except FileNotFoundError:
                pass


@app.post("/api/sessions/{session_id}/audio", status_code=201)
async def upload_audio(session_id: int, audio: UploadFile = File(...), db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    ensure_session_mutable(db, session)
    original, stored, duration = await save_audio(audio, settings.upload_dir, settings.max_upload_mb, settings.max_audio_duration_seconds)
    clip = AudioClip(session_id=session.id, original_filename=original, stored_filename=stored, duration_seconds=duration)
    local_path = resolve_audio(settings.upload_dir, stored)
    if settings.storage_backend.lower() == "s3":
        storage.put(local_path, stored)
        local_path.unlink(missing_ok=True)
    db.add(clip)
    db.flush()
    audit(db, "audio.uploaded", session, user, {"clip_id": clip.id, "extension": Path(original).suffix.lower(), "duration_seconds": duration})
    session.active_clip_id = clip.id
    session.analysis_mode = None
    session.status = "audio_ready"
    db.commit()
    db.refresh(clip)
    return {"id": clip.id, "original_filename": clip.original_filename, "duration_seconds": clip.duration_seconds, "uploaded_at": clip.uploaded_at}


@app.get("/api/sessions/{session_id}/audio/{clip_id}/file")
def stream_audio(session_id: int, clip_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    clip = db.scalar(select(AudioClip).where(AudioClip.id == clip_id, AudioClip.session_id == session_id))
    if not clip:
        raise HTTPException(404, "Audio clip not found.")
    audit(db, "audio.downloaded", session, user, {"clip_id": clip.id})
    db.commit()
    signed_url = storage.signed_url(clip.stored_filename)
    if signed_url:
        return RedirectResponse(signed_url, status_code=307)
    try:
        path = resolve_audio(settings.upload_dir, clip.stored_filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Stored audio is unavailable.") from exc
    return FileResponse(path, filename=clip.original_filename, media_type="audio/*")


@app.post("/api/sessions/{session_id}/audio/{clip_id}/replace", status_code=201)
async def replace_audio(session_id: int, clip_id: int, audio: UploadFile = File(...), db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    ensure_session_mutable(db, session)
    clip = db.scalar(select(AudioClip).where(AudioClip.id == clip_id, AudioClip.session_id == session_id))
    if not clip:
        raise HTTPException(404, "Audio clip not found.")
    old_key = clip.stored_filename
    old_path = None
    try:
        old_path = resolve_audio(settings.upload_dir, clip.stored_filename)
    except FileNotFoundError:
        pass
    original, stored, duration = await save_audio(audio, settings.upload_dir, settings.max_upload_mb, settings.max_audio_duration_seconds)
    local_path = resolve_audio(settings.upload_dir, stored)
    if settings.storage_backend.lower() == "s3":
        storage.put(local_path, stored)
        local_path.unlink(missing_ok=True)
    clip.original_filename = original
    clip.stored_filename = stored
    clip.duration_seconds = duration
    clip.detected_language = None
    clip.sample_rate = None
    clip.processing_status = "uploaded"
    session.active_clip_id = clip.id
    session.analysis_mode = None
    session.status = "audio_ready"
    audit(db, "audio.replaced", session, user, {"clip_id": clip.id, "extension": Path(original).suffix.lower()})
    db.commit()
    if settings.storage_backend.lower() == "s3":
        storage.delete(old_key)
    elif old_path:
        old_path.unlink(missing_ok=True)
    return {"id": clip.id, "original_filename": clip.original_filename, "duration_seconds": clip.duration_seconds, "uploaded_at": clip.uploaded_at}


@app.delete("/api/sessions/{session_id}/audio/{clip_id}", status_code=204)
def delete_audio(session_id: int, clip_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    ensure_session_mutable(db, session)
    clip = db.scalar(select(AudioClip).where(AudioClip.id == clip_id, AudioClip.session_id == session_id))
    if not clip:
        raise HTTPException(404, "Audio clip not found.")
    filename = clip.stored_filename
    db.delete(clip)
    db.flush()
    if session.active_clip_id == clip_id:
        replacement = max(session.audio_clips, key=lambda item: item.uploaded_at, default=None)
        session.active_clip_id = replacement.id if replacement else None
    session.status = "audio_ready" if session.active_clip_id else "ready"
    session.analysis_mode = None
    audit(db, "audio.deleted", session, user, {"clip_id": clip_id})
    db.commit()
    if settings.storage_backend.lower() == "s3":
        storage.delete(filename)
    else:
        try:
            resolve_audio(settings.upload_dir, filename).unlink(missing_ok=True)
        except FileNotFoundError:
            pass


@app.post("/api/sessions/{session_id}/laps/csv")
async def upload_laps_csv(session_id: int, csv_file: UploadFile = File(...), db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    ensure_session_mutable(db, session)
    rows = await parse_lap_csv(csv_file)
    db.query(Lap).filter(Lap.session_id == session.id).delete()
    db.add_all([Lap(session_id=session.id, **row) for row in rows])
    session.status = "ready"
    db.commit()
    return {"count": len(rows), "laps": rows}


@app.post("/api/sessions/{session_id}/laps/manual")
def upload_laps_manual(session_id: int, rows: list[LapInput], db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    ensure_session_mutable(db, session)
    if not rows:
        raise HTTPException(422, "At least one lap is required.")
    validate_lap_rows([row.model_dump() for row in rows])
    db.query(Lap).filter(Lap.session_id == session.id).delete()
    db.add_all([Lap(session_id=session.id, **row.model_dump()) for row in rows])
    session.status = "ready"
    db.commit()
    return {"count": len(rows)}


@app.get("/api/sessions/{session_id}/laps")
def get_laps(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    return serialize_session(session)["laps"]


@app.post("/api/sessions/{session_id}/analyse", status_code=202)
def analyse_session(session_id: int, payload: AnalysisRequest | None = None, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    if not session.audio_clips:
        raise HTTPException(422, "Upload a radio audio clip before analysis.")
    requested_mode = payload.mode if payload else "auto"
    mode = "lap_correlated" if requested_mode == "auto" and session.laps else "audio_only" if requested_mode == "auto" else requested_mode
    if mode == "lap_correlated" and not session.laps:
        raise HTTPException(422, "Real lap data is required for lap-performance correlation. Choose audio-only analysis or import lap data.")
    running = db.scalar(select(AnalysisJob).where(AnalysisJob.session_id == session.id, AnalysisJob.status.in_(["queued", "running"])))
    if running:
        return {"job_id": running.id, "status": running.status, "mode": running.mode}
    job = AnalysisJob(id=str(uuid.uuid4()), session_id=session.id, mode=mode, status="queued", phase="queued", progress=0)
    session.status = "queued"
    db.add(job)
    audit(db, "analysis.queued", session, user, {"job_id": job.id, "mode": mode})
    db.commit()
    try:
        queue = enqueue_analysis(job.id)
    except Exception as exc:
        job.status, job.phase, job.error_code, job.error_message, job.retryable = "failed", "failed", "QUEUE_UNAVAILABLE", "The analysis queue is unavailable. Please retry.", True
        session.status = "error"
        db.commit()
        logger.exception("Could not enqueue analysis job: %s", type(exc).__name__)
        raise HTTPException(503, "The analysis queue is unavailable. Please retry.") from exc
    response = serialize_job(job)
    response["queue"] = queue
    return response


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "Analysis job not found.")
    get_session_or_404(db, job.session_id, user)
    started_at = job.started_at.replace(tzinfo=timezone.utc) if job.started_at and job.started_at.tzinfo is None else job.started_at
    if job.status == "running" and started_at and (datetime.now(timezone.utc) - started_at).total_seconds() > settings.model_timeout_seconds + 60:
        job.status, job.phase, job.error_code, job.error_message, job.retryable = "failed", "failed", "ANALYSIS_TIMEOUT", "Analysis exceeded the configured worker timeout.", True
        session = db.get(Session, job.session_id)
        if session:
            session.status = "error"
        db.commit()
    response = serialize_job(job)
    if job.status == "completed" and job.result_json:
        response["report"] = json.loads(job.result_json)
    return response


@app.post("/api/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(404, "Analysis job not found.")
    get_session_or_404(db, job.session_id, user)
    if job.status != "failed" or not job.retryable:
        raise HTTPException(409, "This analysis job cannot be retried.")
    job.status, job.phase, job.progress = "queued", "queued", 0
    job.error_code, job.error_message = None, None
    db.commit()
    try:
        enqueue_analysis(job.id)
    except Exception as exc:
        job.status, job.phase, job.error_code, job.error_message = "failed", "failed", "QUEUE_UNAVAILABLE", "The analysis queue is unavailable. Please retry."
        db.commit()
        raise HTTPException(503, "The analysis queue is unavailable. Please retry.") from exc
    return serialize_job(job)


@app.post("/api/sessions/{session_id}/analysis/cancel")
def cancel_analysis(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.session_id == session.id, AnalysisJob.status.in_(["queued", "running"])).order_by(AnalysisJob.created_at.desc()))
    if not job:
        raise HTTPException(404, "No active analysis job found.")
    job.status = "cancelled"
    job.phase = "cancelled"
    job.retryable = True
    session.status = "audio_ready" if session.audio_clips else "ready"
    audit(db, "analysis.cancelled", session, user, {"job_id": job.id})
    db.commit()
    return serialize_job(job)


@app.get("/api/sessions/{session_id}/timeline")
def timeline(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    clip = active_clip(session)
    transcript = list(clip.transcript_segments) if clip else []
    events = []
    for item in sorted(clip.emotion_results if clip else [], key=lambda row: row.start_seconds):
        excerpt = overlapping_text(transcript, item.start_seconds, item.end_seconds)
        matched_lap = event_lap(session.laps, Event(item.normalized_label, item.confidence, item.start_seconds, item.end_seconds))
        events.append({"timestamp": item.start_seconds, "end_timestamp": item.end_seconds, "label": item.normalized_label, "confidence": item.confidence, "transcript": excerpt, "lap_number": matched_lap.lap_number if matched_lap else None, "recommendation": next((insight.recommendation for insight in session.insights if insight.severity in {"critical", "high"}), None)})
    return {"laps": serialize_session(session)["laps"], "events": sorted(events, key=lambda item: item["timestamp"]), "transcript": [{"id": item.id, "start_seconds": item.start_seconds, "end_seconds": item.end_seconds, "text": item.text} for item in sorted(transcript, key=lambda row: row.start_seconds)]}


@app.get("/api/sessions/{session_id}/report")
def get_report(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    if session.status != "analysed":
        raise HTTPException(409, "Session has not been analysed yet.")
    return make_report(session)


@app.get("/api/sessions/{session_id}/exports/report.json")
def export_report_json(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    if session.status != "analysed":
        raise HTTPException(409, "Session has not been analysed yet.")
    return Response(content=json.dumps(make_report(session), indent=2, default=str), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="pitsense-{session.id}-report.json"'})


@app.get("/api/sessions/{session_id}/exports/report.csv")
def export_report_csv(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    if session.status != "analysed":
        raise HTTPException(409, "Session has not been analysed yet.")
    report = make_report(session)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["row_type", "start_seconds", "end_seconds", "language", "label", "severity", "confidence", "matched_lap", "lap_number", "next_lap_number", "next_lap_delta_seconds", "deterioration", "transcript"])
    language = (report.get("summary") or {}).get("language") or (report.get("provenance") or {}).get("language") or "und"
    for row in report.get("timestamped_transcript", []):
        writer.writerow(["transcript", row.get("start_seconds"), row.get("end_seconds"), language, "", "", "", "", "", "", "", "", row.get("text", "")])
    correlations = {(row.get("event_timestamp"), row.get("label")): row for row in report.get("correlations", [])}
    for row in report.get("timestamped_events", []):
        correlation = correlations.get((row.get("start_seconds"), row.get("label")), {})
        writer.writerow(["event", row.get("start_seconds"), row.get("end_seconds"), language, row.get("label"), row.get("severity"), row.get("confidence"), correlation.get("matched", row.get("matched_lap")), correlation.get("lap_number", row.get("lap_number")), correlation.get("next_lap_number"), correlation.get("next_lap_delta_seconds"), correlation.get("deterioration"), row.get("transcript", "")])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="pitsense-{session.id}-report.csv"'})


@app.get("/api/sessions/{session_id}/exports/report.pdf")
def export_report_pdf(session_id: int, db: DbSession = Depends(get_db), user: User | None = Depends(get_current_user)):
    session = get_session_or_404(db, session_id, user)
    if session.status != "analysed":
        raise HTTPException(409, "Session has not been analysed yet.")
    try:
        payload = render_pdf_report(session, make_report(session))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return Response(content=payload, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="pitsense-{session.id}-report.pdf"'})
