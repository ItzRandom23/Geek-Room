import io
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import get_settings
from app.database import Base, engine
from app.main import app


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


def test_rejects_path_traversal_filename():
    session = client.post("/api/sessions", json={"name": "Validation", "driver_name": "Test", "circuit_name": "Track"})
    assert session.status_code == 201
    response = client.post(f"/api/sessions/{session.json()['id']}/audio", files={"audio": ("../../evil.exe", b"bad", "application/octet-stream")})
    assert response.status_code == 415


def test_rejects_invalid_csv():
    session = client.post("/api/sessions", json={"name": "CSV", "driver_name": "Test", "circuit_name": "Track"})
    response = client.post(f"/api/sessions/{session.json()['id']}/laps/csv", files={"csv_file": ("laps.csv", b"not,the,right,columns\n1,2", "text/csv")})
    assert response.status_code == 422
