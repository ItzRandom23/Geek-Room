import io
import wave
import time
from app.main import app
from app.services.ai import EmotionWindowResult, ProviderBundle, SpeechToTextProvider, AudioEmotionProvider, TextEmotionProvider, TranscriptSegmentResult, TranscriptionResult
from fastapi.testclient import TestClient


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
        return TranscriptionResult("front lock, nervous on entry", [TranscriptSegmentResult(0, 1, "front lock, nervous on entry")], "en", 0.9)


class FakeAudio(AudioEmotionProvider):
    def analyse(self, audio_path):
        return [EmotionWindowResult(0, 1, "stressed", "fear", 0.9, {"stressed": 0.9})]


class FakeText(TextEmotionProvider):
    def analyse(self, text):
        return {"stressed": 0.8}


def test_create_upload_laps_analyse_and_read_results(monkeypatch):
    monkeypatch.setattr("app.main.build_provider_bundle", lambda settings: ProviderBundle(FakeStt(), FakeAudio(), FakeText()))
    created = client.post("/api/sessions", json={"name": "E2E run", "driver_name": "Driver", "circuit_name": "Track"})
    assert created.status_code == 201
    session_id = created.json()["id"]
    audio = client.post(f"/api/sessions/{session_id}/audio", files={"audio": ("radio.wav", wav_bytes(), "audio/wav")})
    assert audio.status_code == 201
    csv = b"lap_number,lap_time_seconds,start_timestamp_seconds,end_timestamp_seconds\n1,90,0,1\n2,100,1,2\n"
    laps = client.post(f"/api/sessions/{session_id}/laps/csv", files={"csv_file": ("laps.csv", csv, "text/csv")})
    assert laps.status_code == 200
    analysed = client.post(f"/api/sessions/{session_id}/analyse")
    assert analysed.status_code == 202
    job_id = analysed.json()["job_id"]
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert job["status"] == "completed"
    assert job["report"]["primary_state"] == "stressed"
    detail = client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["transcript"][0]["text"] == "front lock, nervous on entry"
    assert detail.json()["report"]["recommendations"]
    client.delete(f"/api/sessions/{session_id}")
