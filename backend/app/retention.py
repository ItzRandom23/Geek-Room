"""Delete uploaded audio beyond the configured retention window.

Run this module from a daily scheduler, Kubernetes CronJob, or Render cron:
`python -m app.retention`.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import AudioClip
from .storage import get_storage


def cleanup_expired_audio() -> int:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
    storage = get_storage()
    db = SessionLocal()
    removed = 0
    try:
        clips = db.scalars(select(AudioClip).where(AudioClip.uploaded_at < cutoff)).all()
        for clip in clips:
            session = clip.session
            filename = clip.stored_filename
            db.delete(clip)
            db.flush()
            if session and session.active_clip_id == clip.id:
                replacement = max(session.audio_clips, key=lambda item: item.uploaded_at, default=None)
                session.active_clip_id = replacement.id if replacement else None
            storage.delete(filename)
            removed += 1
        db.commit()
        return removed
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Removed {cleanup_expired_audio()} expired audio clip(s).")
