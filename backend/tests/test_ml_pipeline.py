import csv
from pathlib import Path

import numpy as np
import pytest

from app.jobs import ANALYSIS_PHASE_PROGRESS
from app.config import Settings
from app.services.ai import HuggingFaceAudioEmotion, HuggingFaceSpeechToText, normalize_language
from app.ml.emotion import (
    ManifestValidationError,
    passes_promotion_gate,
    read_manifest,
    select_confidence_threshold,
    speaker_group_split,
)


LABELS = ("calm", "stressed", "tired", "frustrated", "urgent")


def write_manifest(tmp_path: Path, duplicate_recording: bool = False) -> Path:
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["audio_path", "label", "speaker_id", "recording_id"])
        writer.writeheader()
        for speaker in range(10):
            for label in LABELS:
                audio = tmp_path / f"speaker-{speaker}-{label}.wav"
                audio.write_bytes(b"RIFF-test")
                recording = "duplicate" if duplicate_recording and speaker == 0 else f"recording-{speaker}-{label}"
                writer.writerow({"audio_path": audio.name, "label": label, "speaker_id": f"driver-{speaker}", "recording_id": recording})
    return manifest


def test_manifest_and_split_keep_speakers_isolated(tmp_path):
    dataset = read_manifest(write_manifest(tmp_path), min_clips=50, min_speakers=10)
    train, validation, test = speaker_group_split(dataset.items)
    groups = np.asarray([item.speaker_id for item in dataset.items])
    assert set(groups[train]).isdisjoint(groups[validation])
    assert set(groups[train]).isdisjoint(groups[test])
    assert set(groups[validation]).isdisjoint(groups[test])


def test_manifest_rejects_duplicate_recording_ids(tmp_path):
    with pytest.raises(ManifestValidationError, match="recording_id values must be unique"):
        read_manifest(write_manifest(tmp_path, duplicate_recording=True), min_clips=50, min_speakers=10)


def test_threshold_maximizes_coverage_at_target_accuracy():
    truth = ["calm", "calm", "stressed", "urgent"]
    probabilities = np.asarray([
        [0.99, 0.005, 0.005],
        [0.90, 0.05, 0.05],
        [0.10, 0.60, 0.30],
        [0.05, 0.55, 0.40],
    ])
    threshold, coverage = select_confidence_threshold(truth, probabilities, ["calm", "stressed", "urgent"], 0.99)
    assert threshold == 0.6
    assert coverage == 0.75


def test_promotion_gate_requires_both_balanced_accuracy_and_macro_f1():
    assert passes_promotion_gate({"balanced_accuracy": 0.99, "macro_f1": 0.995})
    assert not passes_promotion_gate({"balanced_accuracy": 0.99, "macro_f1": 0.98})


def test_analysis_phase_progress_is_monotonic():
    ordered = ["queued", "decoding", "transcribing", "extracting_features", "classifying", "calibrating", "correlating", "completed"]
    values = [ANALYSIS_PHASE_PROGRESS[phase] for phase in ordered]
    assert values == sorted(values)
    assert values[-1] == 100


def test_whisper_forces_configured_english_when_detection_says_spanish(monkeypatch, tmp_path):
    captured = {}

    class FakePipeline:
        def __call__(self, audio, **kwargs):
            captured["audio"] = audio
            captured.update(kwargs)
            return {"text": "  hello driver  ", "language": "<|es|>", "chunks": [{"text": "hello driver", "timestamp": (0.2, 1.3)}]}

    monkeypatch.setattr("app.services.ai.load_audio_samples", lambda _path, _rate: (np.zeros(1600, dtype=np.float32), 16000))
    provider = HuggingFaceSpeechToText(Settings(stt_language="en"))
    provider._pipeline = FakePipeline()
    result = provider.transcribe(tmp_path / "radio.wav")
    assert captured["return_language"] is True
    assert captured["generate_kwargs"] == {"task": "transcribe", "language": "en"}
    assert result.language == "en"
    assert result.segments[0].text == "hello driver"


def test_whisper_can_still_auto_detect_language(monkeypatch, tmp_path):
    captured = {}

    class FakePipeline:
        def __call__(self, _audio, **kwargs):
            captured.update(kwargs)
            return {"text": "hola", "language": "<|es|>", "chunks": []}

    monkeypatch.setattr("app.services.ai.load_audio_samples", lambda _path, _rate: (np.zeros(1600, dtype=np.float32), 16000))
    provider = HuggingFaceSpeechToText(Settings(stt_language="auto"))
    provider._pipeline = FakePipeline()
    result = provider.transcribe(tmp_path / "radio.wav")
    assert captured["generate_kwargs"] == {"task": "transcribe"}
    assert result.language == "es"


def test_unknown_whisper_language_remains_undetermined():
    assert normalize_language(None) == "und"
    assert normalize_language("auto") == "und"
    assert normalize_language("not-a-language") == "und"


def test_audio_baseline_rejects_ambiguous_prediction(monkeypatch, tmp_path):
    class FakePipeline:
        def __call__(self, _audio, **_kwargs):
            return [
                {"label": "neu", "score": 0.40},
                {"label": "hap", "score": 0.36},
                {"label": "ang", "score": 0.14},
                {"label": "sad", "score": 0.10},
            ]

    monkeypatch.setattr("app.services.ai.load_audio_samples", lambda _path, _rate: (np.zeros(16000, dtype=np.float32), 16000))
    provider = HuggingFaceAudioEmotion(Settings(emotion_confidence_threshold=0.35, emotion_margin_threshold=0.10))
    provider._pipeline = FakePipeline()
    result = provider.analyse(tmp_path / "radio.wav")
    assert result[0].label == "uncertain"
    assert result[0].raw["candidate_label"] == "calm"
    assert result[0].raw["accepted"] is False


def test_audio_baseline_preserves_supported_positive_state(monkeypatch, tmp_path):
    class FakePipeline:
        def __call__(self, _audio, **_kwargs):
            return [
                {"label": "hap", "score": 0.78},
                {"label": "neu", "score": 0.12},
                {"label": "ang", "score": 0.06},
                {"label": "sad", "score": 0.04},
            ]

    monkeypatch.setattr("app.services.ai.load_audio_samples", lambda _path, _rate: (np.zeros(16000, dtype=np.float32), 16000))
    provider = HuggingFaceAudioEmotion(Settings())
    provider._pipeline = FakePipeline()
    result = provider.analyse(tmp_path / "radio.wav")
    assert result[0].label == "positive"
    assert result[0].confidence == 0.78

