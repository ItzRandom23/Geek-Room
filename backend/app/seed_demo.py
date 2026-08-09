"""Create the explicit offline judging fixture. This is never used for normal uploads."""
import json
import math
import wave
from pathlib import Path
from sqlalchemy import select
from .config import get_settings
from .database import SessionLocal, run_migrations
from .models import AudioClip, EmotionResult, Insight, Lap, Session, TranscriptSegment
from .services.analysis import Event, build_report


def make_wav(path: Path, duration: float = 42.0, sample_rate: int = 16000):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for index in range(int(duration * sample_rate)):
        time = index / sample_rate
        carrier = 0.08 * math.sin(2 * math.pi * (220 + 25 * math.sin(time / 3)) * time)
        pulse = 0.02 * math.sin(2 * math.pi * 4 * time)
        value = max(-1, min(1, carrier + pulse))
        frames.extend(int(value * 32767).to_bytes(2, "little", signed=True))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)


def seed():
    settings = get_settings()
    run_migrations()
    db = SessionLocal()
    existing = db.scalar(select(Session).where(Session.is_demo.is_(True)))
    if existing:
        if existing.audio_clips and existing.active_clip_id is None:
            existing.active_clip_id = existing.audio_clips[-1].id
            existing.analysis_mode = "lap_correlated"
            existing.analysis_version = settings.analysis_version
            db.commit()
        db.close()
        print(f"Demo session already exists: {existing.id}")
        return existing.id
    audio_path = Path(settings.upload_dir).resolve() / "demo_radio.wav"
    make_wav(audio_path)
    session = Session(name="Demo • Silent Co-Driver", driver_name="A. Rao", circuit_name="Northstar GP", status="analysed", is_demo=True)
    db.add(session)
    db.flush()
    clip = AudioClip(session_id=session.id, original_filename="demo_radio.wav", stored_filename=audio_path.name, duration_seconds=42.0)
    db.add(clip)
    db.flush()
    session.active_clip_id = clip.id
    session.analysis_mode = "lap_correlated"
    session.analysis_version = settings.analysis_version
    transcript_rows = [
        (0.0, 4.8, "Car feels balanced, tyres are coming in nicely."),
        (7.2, 11.5, "Turn seven is okay, keep the plan."),
        (15.0, 19.0, "I have front lock and the car feels nervous on entry."),
        (22.0, 26.5, "Box now, there is smoke and I need a check."),
        (29.0, 33.0, "I am tired, the steering is heavy."),
        (36.0, 41.0, "Understood. We will keep it short and manage the tyres."),
    ]
    segments = []
    for start, end, text in transcript_rows:
        segment = TranscriptSegment(clip_id=clip.id, start_seconds=start, end_seconds=end, text=text)
        db.add(segment)
        segments.append(segment)
    db.flush()
    event_specs = [(2.0, 5.0, "calm", "neu", 0.94), (8.0, 12.0, "calm", "neu", 0.88), (15.0, 20.0, "stressed", "fear", 0.86), (22.0, 27.0, "urgent", "sur", 0.91), (29.0, 34.0, "tired", "sad", 0.64)]
    events = []
    for start, end, label, raw, confidence in event_specs:
        segment = next((row for row in segments if row.start_seconds <= start <= row.end_seconds), None)
        db.add(EmotionResult(clip_id=clip.id, segment_id=segment.id if segment else None, normalized_label=label, raw_label=raw, confidence=confidence, source="demo fixture", start_seconds=start, end_seconds=end, raw_output_json=json.dumps({"fixture": True, "raw_label": raw})))
        events.append(Event(label, confidence, start, end, segment.text if segment else "", "demo fixture"))
    lap_times = [92.4, 91.8, 92.1, 95.9, 96.4, 93.0, 92.5, 92.0]
    demo_timestamps = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 42.0]
    for number, lap_time in enumerate(lap_times, start=1):
        db.add(Lap(session_id=session.id, lap_number=number, lap_time_seconds=lap_time, start_timestamp_seconds=demo_timestamps[number - 1], end_timestamp_seconds=demo_timestamps[number]))
    db.flush()
    laps = list(db.scalars(select(Lap).where(Lap.session_id == session.id)).all())
    report = build_report(events, laps, " ".join(row[2] for row in transcript_rows))
    for item in report["recommendations"]:
        db.add(Insight(session_id=session.id, type=item["type"], severity=item["severity"], title=item["title"], explanation=item["explanation"], recommendation=item["recommendation"], supporting_data_json=json.dumps(item.get("supporting_data", {}))))
    demo_id = session.id
    db.commit()
    db.close()
    print(f"Created demo session: {demo_id}")
    return demo_id


if __name__ == "__main__":
    seed()
