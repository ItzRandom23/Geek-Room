import io
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import get_settings
from app.database import Base, engine
from app.main import app
from app.database import SessionLocal
from app.models import AnalysisJob, AudioClip, Session


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_model_status_separates_validation_accuracy_from_prediction_confidence():
    response = client.get("/api/models/status")
    assert response.status_code == 200
    audio = response.json()["audio_emotion"]
    assert {"promoted", "model_version", "validation_accuracy", "confidence_threshold", "prediction_coverage"} <= set(audio)
    assert audio["analyzer_provenance"]["candidate_id"] == "baseline-superb"
    assert audio["analyzer_provenance"]["promotion_state"] == "baseline"


def test_benchmark_scorecard_is_safe_when_no_report_has_been_run():
    response = client.get("/api/models/benchmark")
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_rejects_path_traversal_filename():
    session = client.post("/api/sessions", json={"name": "Validation", "driver_name": "Test", "circuit_name": "Track"})
    assert session.status_code == 201
    response = client.post(f"/api/sessions/{session.json()['id']}/audio", files={"audio": ("../../evil.exe", b"bad", "application/octet-stream")})
    assert response.status_code == 415


def test_rejects_invalid_csv():
    session = client.post("/api/sessions", json={"name": "CSV", "driver_name": "Test", "circuit_name": "Track"})
    response = client.post(f"/api/sessions/{session.json()['id']}/laps/csv", files={"csv_file": ("laps.csv", b"not,the,right,columns\n1,2", "text/csv")})
    assert response.status_code == 422


def test_rejects_source_mutations_while_analysis_is_active():
    session = client.post("/api/sessions", json={"name": "Locked", "driver_name": "Test", "circuit_name": "Track"})
    session_id = session.json()["id"]
    db = SessionLocal()
    try:
        db.add(AnalysisJob(id=str(uuid.uuid4()), session_id=session_id, mode="audio_only", status="running", phase="transcribing", progress=24))
        db.commit()
    finally:
        db.close()
    response = client.post(f"/api/sessions/{session_id}/laps/manual", json=[{"lap_number": 1, "lap_time_seconds": 90, "start_timestamp_seconds": 0, "end_timestamp_seconds": 90}])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ANALYSIS_IN_PROGRESS"
    client.delete(f"/api/sessions/{session_id}")


def test_saving_laps_preserves_active_audio():
    created = client.post("/api/sessions", json={"name": "Preserve audio", "driver_name": "Test", "circuit_name": "Track"})
    session_id = created.json()["id"]
    db = SessionLocal()
    try:
        clip = AudioClip(session_id=session_id, original_filename="radio.wav", stored_filename="test-radio.wav", duration_seconds=90)
        db.add(clip)
        db.flush()
        session = db.get(Session, session_id)
        session.active_clip_id = clip.id
        session.status = "audio_ready"
        db.commit()
        clip_id = clip.id
    finally:
        db.close()
    response = client.post(f"/api/sessions/{session_id}/laps/manual", json=[{"lap_number": 1, "lap_time_seconds": 90, "start_timestamp_seconds": 0, "end_timestamp_seconds": 90}])
    assert response.status_code == 200
    detail = client.get(f"/api/sessions/{session_id}").json()
    assert detail["active_clip_id"] == clip_id
    assert detail["audio_count"] == 1
    assert detail["status"] == "audio_ready"
    client.delete(f"/api/sessions/{session_id}")
