import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
from .audio import load_audio_samples
from .labels import normalize_label, normalize_scores
from ..config import Settings


@dataclass
class TranscriptSegmentResult:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    transcript: str
    segments: list[TranscriptSegmentResult]
    language: str | None
    confidence: float | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmotionWindowResult:
    start: float
    end: float
    label: str
    raw_label: str
    confidence: float
    scores: dict[str, float]
    raw: dict[str, Any] = field(default_factory=dict)


class SpeechToTextProvider:
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        raise NotImplementedError


class AudioEmotionProvider:
    def analyse(self, audio_path: Path) -> list[EmotionWindowResult]:
        raise NotImplementedError


class TextEmotionProvider:
    def analyse(self, text: str) -> dict[str, float]:
        raise NotImplementedError


class HuggingFaceSpeechToText(SpeechToTextProvider):
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from transformers import pipeline
            kwargs = {"model": self.settings.hf_stt_model, "task": "automatic-speech-recognition"}
            if self.settings.hf_token:
                kwargs["token"] = self.settings.hf_token
            self._pipeline = pipeline(**kwargs)
        return self._pipeline

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        pipe = self._load()
        audio, sample_rate = load_audio_samples(audio_path, 16000)
        output = pipe({"array": audio, "sampling_rate": sample_rate}, return_timestamps=True)
        chunks = output.get("chunks", []) if isinstance(output, dict) else []
        segments = []
        for chunk in chunks:
            timestamp = chunk.get("timestamp") or (0, 0)
            start = float(timestamp[0] or 0)
            end = float(timestamp[1] if timestamp[1] is not None else start + 0.5)
            text = str(chunk.get("text", "")).strip()
            if text:
                segments.append(TranscriptSegmentResult(start, max(end, start + 0.05), text))
        transcript = str(output.get("text", "") if isinstance(output, dict) else output).strip()
        if not transcript and segments:
            transcript = " ".join(item.text for item in segments)
        language = output.get("language", "auto") if isinstance(output, dict) else "auto"
        return TranscriptionResult(transcript, segments, language, None, output if isinstance(output, dict) else {})


class HuggingFaceAudioEmotion(AudioEmotionProvider):
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from transformers import pipeline
            kwargs = {"model": self.settings.hf_audio_emotion_model, "task": "audio-classification"}
            if self.settings.hf_token:
                kwargs["token"] = self.settings.hf_token
            self._pipeline = pipeline(**kwargs)
        return self._pipeline

    def analyse(self, audio_path: Path) -> list[EmotionWindowResult]:
        pipe = self._load()
        audio, sample_rate = load_audio_samples(audio_path, 16000)
        duration = len(audio) / sample_rate if len(audio) else 0
        windows = []
        window_size = min(8.0, duration) if duration else 0
        step = max(4.0, window_size / 2) if window_size else 0
        starts = np.arange(0, duration, step) if step else [0]
        for start in starts:
            end = min(duration, float(start + window_size))
            sample = audio[int(start * sample_rate): int(end * sample_rate)]
            if len(sample) < 100:
                continue
            predictions = pipe({"array": sample, "sampling_rate": sample_rate}, top_k=None)
            predictions = predictions[0] if predictions and isinstance(predictions[0], list) else predictions
            raw_scores = {str(item["label"]): float(item["score"]) for item in predictions}
            normalized = normalize_scores(raw_scores)
            raw_label, raw_confidence = max(raw_scores.items(), key=lambda item: item[1])
            label = max(normalized.items(), key=lambda item: item[1])[0]
            windows.append(EmotionWindowResult(float(start), float(end), label, raw_label, float(raw_confidence), normalized, {"predictions": predictions}))
        return windows


class HuggingFaceTextEmotion(TextEmotionProvider):
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from transformers import pipeline
            kwargs = {"model": self.settings.hf_text_emotion_model, "task": "text-classification"}
            if self.settings.hf_token:
                kwargs["token"] = self.settings.hf_token
            self._pipeline = pipeline(**kwargs)
        return self._pipeline

    def analyse(self, text: str) -> dict[str, float]:
        if not text.strip():
            return {}
        output = self._load()(text, top_k=None)
        if output and isinstance(output[0], list):
            output = output[0]
        return normalize_scores({str(item["label"]): float(item["score"]) for item in output})


@dataclass
class ProviderBundle:
    stt: SpeechToTextProvider
    audio_emotion: AudioEmotionProvider
    text_emotion: TextEmotionProvider


def build_provider_bundle(settings: Settings) -> ProviderBundle:
    return ProviderBundle(HuggingFaceSpeechToText(settings), HuggingFaceAudioEmotion(settings), HuggingFaceTextEmotion(settings))


def json_default(value: Any):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(f"Unsupported value: {type(value)}")


def serialize_raw(value: Any) -> str:
    return json.dumps(value, default=json_default)
