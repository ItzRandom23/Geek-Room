import io
import time
import uuid
import wave

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.ai import AudioEmotionProvider, EmotionWindowResult, ProviderBundle, SpeechToTextProvider, TextEmotionProvider, TranscriptSegmentResult, TranscriptionResult

client = TestClient(app)


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)
    return output.getvalue()


class FakeStt(SpeechToTextProvider):
    def transcribe(self, audio_path):
        return TranscriptionResult("all clear", [TranscriptSegmentResult(0, 1, "all clear")], "en", 0.9)


class FakeAudio(AudioEmotionProvider):
    def analyse(self, audio_path):
        return [EmotionWindowResult(0, 1, "calm", "neu", 0.9, {"calm": 0.9})]


class FakeText(TextEmotionProvider):
    def analyse(self, text):
        return {"calm": 0.9}


class SlowAudio(FakeAudio):
    def analyse(self, audio_path):
        time.sleep(0.25)
        return super().analyse(audio_path)


def test_audio_only_does_not_create_or_claim_laps(monkeypatch):
    monkeypatch.setattr("app.main.build_provider_bundle", lambda settings: ProviderBundle(FakeStt(), FakeAudio(), FakeText()))
    created = client.post("/api/sessions", json={"name": "Audio only", "driver_name": "Driver", "circuit_name": "Track"})
    session_id = created.json()["id"]
    upload = client.post(f"/api/sessions/{session_id}/audio", files={"audio": ("radio.wav", wav_bytes(), "audio/wav")})
    assert upload.status_code == 201
    assert client.get(f"/api/sessions/{session_id}").json()["lap_count"] == 0
    response = client.post(f"/api/sessions/{session_id}/analyse", json={"mode": "audio_only"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert job["status"] == "completed"
    assert job["report"]["correlation_available"] is False
    assert client.get(f"/api/sessions/{session_id}/exports/report.json").status_code == 200
    assert client.get(f"/api/sessions/{session_id}/exports/report.csv").status_code == 200
    pdf = client.get(f"/api/sessions/{session_id}/exports/report.pdf")
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")
    assert client.get(f"/api/sessions/{session_id}").json()["lap_count"] == 0
    client.delete(f"/api/sessions/{session_id}")


def test_cancelled_analysis_is_not_overwritten_by_worker(monkeypatch):
    monkeypatch.setattr("app.main.build_provider_bundle", lambda settings: ProviderBundle(FakeStt(), SlowAudio(), FakeText()))
    created = client.post("/api/sessions", json={"name": "Cancel run", "driver_name": "Driver", "circuit_name": "Track"})
    session_id = created.json()["id"]
    client.post(f"/api/sessions/{session_id}/audio", files={"audio": ("radio.wav", wav_bytes(), "audio/wav")})
    accepted = client.post(f"/api/sessions/{session_id}/analyse", json={"mode": "audio_only"}).json()
    cancelled = client.post(f"/api/sessions/{session_id}/analysis/cancel")
    assert cancelled.status_code == 200
    time.sleep(0.4)
    job = client.get(f"/api/jobs/{accepted['job_id']}").json()
    assert job["status"] == "cancelled"
    assert job["phase"] == "cancelled"
    client.delete(f"/api/sessions/{session_id}")


def test_authentication_isolates_organizations(monkeypatch):
    settings = get_settings()
    original = settings.auth_required
    settings.auth_required = True
    suffix = uuid.uuid4().hex[:8]
    try:
        first = client.post("/api/auth/register", json={"email": f"one-{suffix}@example.com", "password": "strong-pass-1", "full_name": "One", "organization_name": f"Team One {suffix}"})
        second = client.post("/api/auth/register", json={"email": f"two-{suffix}@example.com", "password": "strong-pass-2", "full_name": "Two", "organization_name": f"Team Two {suffix}"})
        assert first.status_code == 201 and second.status_code == 201
        first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
        second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
        first_session = client.post("/api/sessions", headers=first_headers, json={"name": "Private One", "driver_name": "One", "circuit_name": "Track"})
        second_session = client.post("/api/sessions", headers=second_headers, json={"name": "Private Two", "driver_name": "Two", "circuit_name": "Track"})
        assert first_session.status_code == 201 and second_session.status_code == 201
        assert client.get(f"/api/sessions/{second_session.json()['id']}", headers=first_headers).status_code == 403
        visible = client.get("/api/sessions", headers=first_headers).json()
        assert [item["id"] for item in visible] == [first_session.json()["id"]]
        client.delete(f"/api/sessions/{first_session.json()['id']}", headers=first_headers)
        client.delete(f"/api/sessions/{second_session.json()['id']}", headers=second_headers)
    finally:
        settings.auth_required = original
