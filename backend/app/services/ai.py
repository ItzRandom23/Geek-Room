import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
from .audio import load_audio_samples
from .labels import normalize_label, normalize_scores
from ..config import Settings
from ..ml.emotion import TRAINED_LABELS, WavLMFeatureExtractor, load_promoted_metadata, passes_promotion_gate, promoted_paths


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


class PromotedRaceRadioEmotion(AudioEmotionProvider):
    """CPU runtime for an artifact that passed the speaker-held-out release gate."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.artifact_root = Path(settings.emotion_artifact_dir)
        self.metadata = load_promoted_metadata(self.artifact_root) or {}
        self._artifact = None
        self._extractor = None

    def _load(self):
        if self._artifact is None:
            import joblib

            model_path, _ = promoted_paths(self.artifact_root)
            artifact = joblib.load(model_path)
            metadata = artifact.get("metadata") or self.metadata
            if not metadata.get("promoted") or not passes_promotion_gate(metadata.get("test_metrics", {}), self.settings.emotion_target_accuracy):
                raise RuntimeError("The promoted emotion artifact does not satisfy the configured release gate.")
            self.metadata = metadata
            self._artifact = artifact
            self._extractor = WavLMFeatureExtractor(metadata.get("encoder_model", self.settings.hf_embedding_model))
        return self._artifact, self._extractor

    def analyse(self, audio_path: Path) -> list[EmotionWindowResult]:
        artifact, extractor = self._load()
        classifier = artifact["audio_classifier"]
        windows = []
        for start, end, features in extractor.extract_windows(audio_path):
            probabilities = classifier.predict_proba(features.reshape(1, -1))[0]
            raw_scores = {str(label): float(score) for label, score in zip(classifier.classes_, probabilities)}
            scores = {label: raw_scores.get(label, 0.0) for label in TRAINED_LABELS}
            scores["uncertain"] = 0.0
            label = max(TRAINED_LABELS, key=lambda item: scores[item])
            confidence = scores[label]
            windows.append(EmotionWindowResult(
                start,
                end,
                label,
                label,
                confidence,
                scores,
                {"audio_probabilities": raw_scores, "model_version": self.metadata.get("model_version")},
            ))
        return windows

    def fuse(self, audio_scores: dict[str, float], text_scores: dict[str, float], urgency: float) -> tuple[str, float, dict[str, float]]:
        artifact, _ = self._load()
        fusion = artifact["fusion_classifier"]
        audio_order = self.metadata.get("audio_class_order", list(TRAINED_LABELS))
        vector = np.asarray(
            [audio_scores.get(label, 0.0) for label in audio_order]
            + [text_scores.get(label, 0.0) for label in TRAINED_LABELS]
            + [urgency],
            dtype=np.float32,
        ).reshape(1, -1)
        probabilities = fusion.predict_proba(vector)[0]
        scores = {label: float(score) for label, score in zip(fusion.classes_, probabilities)}
        label = max(TRAINED_LABELS, key=lambda item: scores.get(item, 0.0))
        confidence = scores.get(label, 0.0)
        if confidence < float(self.metadata.get("confidence_threshold", 1.0)):
            label = "uncertain"
        scores["uncertain"] = max(0.0, 1.0 - confidence) if label == "uncertain" else 0.0
        return label, confidence, scores


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
    metadata = load_promoted_metadata(Path(settings.emotion_artifact_dir))
    audio_provider: AudioEmotionProvider
    if metadata and passes_promotion_gate(metadata.get("test_metrics", {}), settings.emotion_target_accuracy):
        audio_provider = PromotedRaceRadioEmotion(settings)
    else:
        audio_provider = HuggingFaceAudioEmotion(settings)
    return ProviderBundle(HuggingFaceSpeechToText(settings), audio_provider, HuggingFaceTextEmotion(settings))


def emotion_model_status(settings: Settings) -> dict[str, Any]:
    metadata = load_promoted_metadata(Path(settings.emotion_artifact_dir))
    if metadata and passes_promotion_gate(metadata.get("test_metrics", {}), settings.emotion_target_accuracy):
        return {
            "model": metadata.get("encoder_model", settings.hf_embedding_model),
            "configured": True,
            "promoted": True,
            "model_version": metadata.get("model_version"),
            "validation_accuracy": metadata.get("validation_accuracy"),
            "confidence_threshold": metadata.get("confidence_threshold"),
            "prediction_coverage": metadata.get("prediction_coverage"),
        }
    return {
        "model": settings.hf_audio_emotion_model,
        "configured": bool(settings.hf_audio_emotion_model),
        "promoted": False,
        "model_version": None,
        "validation_accuracy": None,
        "confidence_threshold": None,
        "prediction_coverage": None,
    }


def json_default(value: Any):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(f"Unsupported value: {type(value)}")


def serialize_raw(value: Any) -> str:
    return json.dumps(value, default=json_default)
