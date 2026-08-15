"""Background analysis execution.

Redis/RQ is used in production. A daemon thread is retained as a local
development fallback so the app works immediately without fabricated results.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from sqlalchemy import update

from .config import get_settings
from .database import SessionLocal
from .models import AnalysisJob, AudioClip, EmotionResult, Insight, Session, TranscriptSegment
from .services.analysis import Event, build_report, interval_overlap, overlapping_text, urgency_score
from .services.ai import emotion_model_status, normalize_language, serialize_raw
from .services.audio import resolve_audio
from .storage import get_storage

logger = logging.getLogger("pitsense.jobs")
settings = get_settings()
storage = get_storage()
_provider_bundle = None
_provider_factory = None

ANALYSIS_PHASE_PROGRESS = {
    "queued": 0,
    "decoding": 10,
    "transcribing": 24,
    "extracting_features": 46,
    "classifying": 68,
    "calibrating": 82,
    "correlating": 90,
    "completed": 100,
}


class AnalysisCancelled(RuntimeError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def _set_phase(db, job: AnalysisJob, session: Session, phase: str, progress: int) -> None:
    result = db.execute(
        update(AnalysisJob)
        .where(AnalysisJob.id == job.id, AnalysisJob.status.notin_(["cancelled", "completed"]))
        .values(status="running", phase=phase, progress=progress)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        raise AnalysisCancelled("Analysis was cancelled by the user.")
    session.status = "analysing"
    db.commit()
    db.refresh(job)


def _active_clip(session: Session) -> AudioClip | None:
    if session.active_clip_id is not None:
        selected = next((clip for clip in session.audio_clips if clip.id == session.active_clip_id), None)
        if selected:
            return selected
    return max(session.audio_clips, key=lambda clip: clip.uploaded_at, default=None)


def _is_english(language: str | None) -> bool:
    return (language or "und").lower().split("-", 1)[0] == "en"


def _analyzer_supports_language(model_status: dict, language: str | None) -> bool:
    scope = ((model_status.get("analyzer_provenance") or {}).get("language_scope") or [])
    if not scope:
        return True
    normalized = (language or "und").lower().split("-", 1)[0]
    return "multilingual" in scope or normalized in scope


def _related_segment(segments: list[TranscriptSegment], start: float, end: float) -> TranscriptSegment | None:
    candidates = [
        (interval_overlap(start, end, item.start_seconds, item.end_seconds), item)
        for item in segments
    ]
    overlapping = [item for overlap, item in candidates if overlap > 0]
    if overlapping:
        return max(overlapping, key=lambda item: interval_overlap(start, end, item.start_seconds, item.end_seconds))
    return None


def _run_inference(db, session: Session, clip: AudioClip, job: AnalysisJob) -> None:
    # Import through app.main at execution time so tests and deployments can
    # replace the provider factory without constructing models per request.
    from .main import build_provider_bundle

    with storage.materialize(clip.stored_filename) as path:
        return _run_inference_from_path(db, session, clip, path, job)


def _run_inference_from_path(db, session, clip, path, job: AnalysisJob | None = None) -> None:
    from .main import build_provider_bundle
    global _provider_bundle, _provider_factory
    if _provider_bundle is None or _provider_factory is not build_provider_bundle:
        _provider_bundle = build_provider_bundle(settings)
        _provider_factory = build_provider_bundle
    providers = _provider_bundle
    if job is not None:
        _set_phase(db, job, session, "transcribing", ANALYSIS_PHASE_PROGRESS["transcribing"])
    transcription = providers.stt.transcribe(path)
    if not transcription.transcript.strip():
        raise RuntimeError("EMPTY_TRANSCRIPT: Speech-to-text returned an empty transcript.")
    if job is not None:
        _set_phase(db, job, session, "extracting_features", ANALYSIS_PHASE_PROGRESS["extracting_features"])
    emotion_windows = providers.audio_emotion.analyse(path)

    for segment in list(clip.transcript_segments):
        db.delete(segment)
    for emotion in list(clip.emotion_results):
        db.delete(emotion)
    db.flush()

    segments = []
    if transcription.segments:
        for item in transcription.segments:
            segment = TranscriptSegment(
                clip_id=clip.id,
                start_seconds=item.start,
                end_seconds=max(item.end, item.start + 0.05),
                text=item.text,
            )
            db.add(segment)
            segments.append(segment)
    else:
        segment = TranscriptSegment(
            clip_id=clip.id,
            start_seconds=0,
            end_seconds=clip.duration_seconds or 1,
            text=transcription.transcript,
        )
        db.add(segment)
        segments.append(segment)
    db.flush()

    language = normalize_language(transcription.language)
    text_signals_applied = _is_english(language)
    model_status = emotion_model_status(settings)
    language_supported = _analyzer_supports_language(model_status, language)
    text_scores = {}
    if job is not None:
        _set_phase(db, job, session, "classifying", ANALYSIS_PHASE_PROGRESS["classifying"])
    if text_signals_applied:
        try:
            text_scores = providers.text_emotion.analyse(transcription.transcript)
        except Exception as exc:
            logger.warning("Optional text-emotion model unavailable: %s", type(exc).__name__)

    if job is not None:
        _set_phase(db, job, session, "calibrating", ANALYSIS_PHASE_PROGRESS["calibrating"])
    for window in emotion_windows:
        related = _related_segment(segments, window.start, window.end)
        # A vocal-state prediction without overlapping detected speech is most
        # likely engine noise, silence, or radio static rather than driver tone.
        if related is None:
            continue
        excerpt = overlapping_text(segments, window.start, window.end)
        urgency = urgency_score(excerpt) if text_signals_applied else 0.0
        if hasattr(providers.audio_emotion, "fuse"):
            label, confidence, fused_scores = providers.audio_emotion.fuse(window.scores, text_scores, urgency)
            source = "trained_audio+text"
        else:
            label = "urgent" if urgency >= 1 and window.label in {"stressed", "frustrated", "urgent"} else window.label
            confidence = window.confidence
            fused_scores = window.scores
            source = "audio-baseline"
        if not language_supported:
            # Do not turn an English-only model's output into a confident state
            # for speech in a language it was never qualified to evaluate.
            label = "uncertain"
            confidence = 0.0
            source += "+language-gate"
        raw = dict(window.raw)
        raw.update({
            "fused_scores": fused_scores,
            "text_scores": text_scores,
            "urgency": urgency,
            "transcription_language": language,
            "text_signals_applied": text_signals_applied,
            "language_supported": language_supported,
        })
        db.add(EmotionResult(
            clip_id=clip.id,
            segment_id=related.id if related else None,
            normalized_label=label,
            raw_label=window.raw_label,
            confidence=round(confidence, 4),
            source=source,
            start_seconds=window.start,
            end_seconds=window.end,
            raw_output_json=serialize_raw(raw),
        ))
    clip.detected_language = language
    clip.processing_status = "analysed"
    db.flush()


def _report(session: Session, mode: str, processing_time_ms: int | None = None) -> dict:
    clip = _active_clip(session)
    if clip is None:
        return build_report([], [], "", language="und", text_signals_applied=False)
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
    laps = sorted(session.laps, key=lambda row: row.lap_number) if mode == "lap_correlated" else []
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
    report["data_quality"].update({
        "language_supported": _analyzer_supports_language(model_status, language),
        "analyzer_validated": bool(model_status.get("promoted")),
    })
    report.update({
        "analysis_mode": mode,
        "correlation_available": bool(mode == "lap_correlated" and laps),
        "association_notice": "Associations are not proof of causation." if mode == "lap_correlated" and laps else "Audio-only analysis: no lap-performance conclusion was made.",
        "provenance": {
            "models": {
                "stt": settings.hf_stt_model,
                "audio_emotion": model_status["model"],
                "text_emotion": settings.hf_text_emotion_model,
            },
            "language": language,
            "transcription_task": "transcribe",
            "text_signals_applied": _is_english(language),
            "generated_at": now().isoformat(),
            "analysis_version": settings.analysis_version,
            "model_version": model_status["model_version"],
            "validation_accuracy": model_status["validation_accuracy"],
            "confidence_threshold": model_status["confidence_threshold"],
            "prediction_coverage": model_status["prediction_coverage"],
            "audio_analyzer": model_status.get("analyzer_provenance"),
            "processing_time_ms": processing_time_ms,
        },
    })
    return report


def _failure_code(exc: Exception) -> tuple[str, bool, str]:
    message = str(exc)
    upper = message.upper()
    if "EMPTY_TRANSCRIPT" in upper:
        return "EMPTY_TRANSCRIPT", False, "Speech-to-text returned an empty transcript."
    if "NO_LAP_DATA" in upper:
        return "NO_LAP_DATA", False, "Real lap data is required for lap correlation."
    if isinstance(exc, FileNotFoundError):
        return "AUDIO_UNAVAILABLE", False, "The uploaded audio is no longer available."
    if "DECODE" in upper or ("AUDIO" in upper and "MODEL" not in upper):
        return "AUDIO_DECODE_FAILURE", False, "The audio could not be decoded. Try WAV or a shorter compatible clip."
    if "TOKEN" in upper or "401" in upper:
        return "MISSING_HF_TOKEN", True, "The Hugging Face token is missing or invalid for this model."
    if "OUT OF MEMORY" in upper or "CUDA" in upper:
        return "OUT_OF_MEMORY", True, "The inference worker ran out of memory. Retry with a CPU worker or smaller audio clip."
    if "TIMEOUT" in upper:
        return "ANALYSIS_TIMEOUT", True, "Analysis exceeded the configured worker timeout."
    return "MODEL_UNAVAILABLE", True, "Hugging Face inference failed. Check model IDs, token, network, and dependencies."


def execute_analysis_job(job_id: str) -> None:
    db = SessionLocal()
    started_clock = time.monotonic()
    try:
        job = db.get(AnalysisJob, job_id)
        if not job or job.status in {"cancelled", "completed"}:
            return
        session = db.get(Session, job.session_id)
        clip = _active_clip(session) if session else None
        if not session or not clip:
            raise RuntimeError("AUDIO_UNAVAILABLE: Upload a radio audio clip before analysis.")
        job.attempts += 1
        job.started_at = now()
        _set_phase(db, job, session, "decoding", ANALYSIS_PHASE_PROGRESS["decoding"])
        if session.is_demo and settings.demo_mode and clip.transcript_segments:
            _set_phase(db, job, session, "transcribing", ANALYSIS_PHASE_PROGRESS["transcribing"])
            _set_phase(db, job, session, "extracting_features", ANALYSIS_PHASE_PROGRESS["extracting_features"])
            _set_phase(db, job, session, "classifying", ANALYSIS_PHASE_PROGRESS["classifying"])
            _set_phase(db, job, session, "calibrating", ANALYSIS_PHASE_PROGRESS["calibrating"])
        else:
            _run_inference(db, session, clip, job)
        mode = job.mode
        if mode == "lap_correlated" and not session.laps:
            raise RuntimeError("NO_LAP_DATA: Real lap data is required for lap correlation.")
        final_phase = "correlating" if mode == "lap_correlated" else "calibrating"
        _set_phase(db, job, session, final_phase, ANALYSIS_PHASE_PROGRESS["correlating"])
        for insight in list(session.insights):
            db.delete(insight)
        db.flush()
        elapsed_ms = round((time.monotonic() - started_clock) * 1000)
        report = _report(session, mode, elapsed_ms)
        for item in report["recommendations"]:
            db.add(Insight(session_id=session.id, type=item["type"], severity=item["severity"], title=item["title"], explanation=item["explanation"], recommendation=item["recommendation"], supporting_data_json=json.dumps(item.get("supporting_data", {}))))
        session.analysis_mode = mode
        session.analysis_version = report["provenance"].get("model_version") or settings.analysis_version
        session.status = "analysed"
        job.status = "completed"
        job.phase = "completed"
        job.progress = 100
        job.retryable = False
        job.result_json = json.dumps(report)
        job.processing_time_ms = elapsed_ms
        job.completed_at = now()
        db.commit()
    except AnalysisCancelled:
        db.rollback()
        job = db.get(AnalysisJob, job_id)
        if job:
            session = db.get(Session, job.session_id)
            job.status = "cancelled"
            job.phase = "cancelled"
            job.retryable = True
            job.processing_time_ms = round((time.monotonic() - started_clock) * 1000)
            if session:
                session.status = "audio_ready" if session.audio_clips else "ready"
            db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(AnalysisJob, job_id)
        if job:
            session = db.get(Session, job.session_id)
            code, retryable, message = _failure_code(exc)
            job.status = "failed"
            job.phase = "failed"
            job.error_code = code
            job.error_message = message
            job.retryable = retryable
            job.processing_time_ms = round((time.monotonic() - started_clock) * 1000)
            if session:
                session.status = "error"
            db.commit()
        logger.exception("Analysis job failed: %s", type(exc).__name__)
    finally:
        db.close()


def enqueue_analysis(job_id: str) -> str:
    if settings.redis_url:
        from redis import Redis
        from rq import Queue
        queue = Queue("pitsense-analysis", connection=Redis.from_url(settings.redis_url))
        queue.enqueue(execute_analysis_job, job_id, job_timeout=settings.model_timeout_seconds + 60, result_ttl=86400)
        return "redis"
    threading.Thread(target=execute_analysis_job, args=(job_id,), name=f"analysis-{job_id[:8]}", daemon=True).start()
    return "local"


def serialize_job(job: AnalysisJob) -> dict:
    return {
        "job_id": job.id,
        "session_id": job.session_id,
        "mode": job.mode,
        "status": job.status,
        "phase": job.phase,
        "progress": job.progress,
        "attempts": job.attempts,
        "retryable": job.retryable,
        "error": {"code": job.error_code, "message": job.error_message, "retryable": job.retryable} if job.error_code else None,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "processing_time_ms": job.processing_time_ms,
        "timeout_seconds": settings.model_timeout_seconds + 60,
    }
