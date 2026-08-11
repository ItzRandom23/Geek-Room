import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
from .audio import load_audio_samples
from .audio_candidates import build_audio_candidate, get_candidate_spec
from .labels import normalize_label, normalize_scores
from ..config import Settings
from ..ml.emotion import TRAINED_LABELS, WavLMFeatureExtractor, load_promoted_metadata, passes_promotion_gate, promoted_paths
from ..ml.promotion import load_signed_promotion_manifest, safe_calibration_path


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
        # Whisper supports both transcription and translation. Always select
        # transcription so the stored radio evidence remains in the language
        # spoken by the driver.
        configured_language = normalize_language(self.settings.stt_language)
        generate_kwargs = {"task": "transcribe"}
        if configured_language != "und":
            # Short, noisy radio clips are especially prone to Whisper choosing
            # a related but incorrect language. Supplying the known source
            # language prevents English speech from being decoded as Spanish.
            generate_kwargs["language"] = configured_language
        output = pipe(
            {"array": audio, "sampling_rate": sample_rate},
            return_timestamps=True,
            return_language=True,
            generate_kwargs=generate_kwargs,
        )
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
        language = configured_language or "und"
        if language == "und":
            language = normalize_language(output.get("language") if isinstance(output, dict) else None)
        if language == "und":
            for chunk in chunks:
                language = normalize_language(chunk.get("language"))
                if language != "und":
                    break
        return TranscriptionResult(transcript, segments, language, None, output if isinstance(output, dict) else {})


LANGUAGE_ALIASES = {
    "english": "en",
    "hindi": "hi",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "arabic": "ar",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh",
}

# Whisper's supported ISO-639-1 language codes.  Validate against this set so
# placeholders (for example, legacy "auto") and malformed strings are never
# presented as a detected driver language.
WHISPER_LANGUAGE_CODES = {
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh",
}


def normalize_language(value: Any) -> str:
    """Normalise Whisper's language token without inventing an unknown language."""
    if isinstance(value, (list, tuple)):
        value = next((item for item in value if item), None)
    if not value:
        return "und"
    text = str(value).strip().lower()
    token = re.fullmatch(r"<\|([a-z]{2,3})\|>", text)
    if token:
        text = token.group(1)
    text = LANGUAGE_ALIASES.get(text, text.split("-", 1)[0])
    return text if text in WHISPER_LANGUAGE_CODES else "und"


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


def benchmark_promotion(settings: Settings) -> dict[str, Any] | None:
    return load_signed_promotion_manifest(
        Path(settings.benchmark_promotion_manifest),
        settings.benchmark_signing_key,
        Path(settings.emotion_calibration_dir),
    )


class CalibratedCandidateEmotion(AudioEmotionProvider):
    """Runtime adapter activated only by a signed benchmark promotion manifest."""

    def __init__(self, settings: Settings, promotion: dict[str, Any]):
        self.settings = settings
        self.promotion = promotion
        self._candidate = None
        self._artifact = None

    def _load(self):
        if self._artifact is None:
            import joblib

            candidate_id = str(self.promotion["candidate_id"])
            spec = get_candidate_spec(candidate_id)
            if spec.model_id != self.promotion["model_id"]:
                raise RuntimeError("The promoted candidate model ID does not match the registered adapter.")
            artifact_path = safe_calibration_path(Path(self.settings.emotion_calibration_dir), str(self.promotion["calibration_artifact"]))
            artifact = joblib.load(artifact_path)
            expected = {"candidate_id": candidate_id, "model_id": spec.model_id, "model_revision": self.promotion["model_revision"]}
            if any(artifact.get(key) != value for key, value in expected.items()):
                raise RuntimeError("The promoted calibration artifact does not match its signed manifest.")
            self._candidate = build_audio_candidate(candidate_id, str(self.promotion["model_revision"]))
            self._artifact = artifact
        return self._candidate, self._artifact

    def analyse(self, audio_path: Path) -> list[EmotionWindowResult]:
        candidate, artifact = self._load()
        classifier = artifact["classifier"]
        classes = [str(label) for label in artifact["classes"]]
        threshold = float((self.promotion.get("benchmark") or {}).get("metrics", {}).get("confidence_threshold", 1.0))
        windows = []
        for window in candidate.analyse(audio_path):
            probabilities = classifier.predict_proba(candidate.feature_vector(window).reshape(1, -1))[0]
            calibrated = {label: float(score) for label, score in zip(classes, probabilities)}
            label = max(TRAINED_LABELS, key=lambda item: calibrated.get(item, 0.0))
            confidence = calibrated.get(label, 0.0)
            if confidence < threshold:
                label = "uncertain"
            scores = {item: calibrated.get(item, 0.0) for item in TRAINED_LABELS}
            scores["uncertain"] = max(0.0, 1.0 - confidence) if label == "uncertain" else 0.0
            windows.append(EmotionWindowResult(
                window.start,
                window.end,
                label,
                window.raw_label,
                confidence,
                scores,
                {
                    "candidate_id": candidate.spec.identifier,
                    "model_id": candidate.spec.model_id,
                    "model_revision": candidate.revision,
                    "native_scores": window.native_scores,
                    "dimensions": window.dimensions,
                    "calibration_version": artifact.get("calibration_version"),
                    "latency_ms": window.latency_ms,
                },
            ))
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
    promotion = benchmark_promotion(settings)
    metadata = load_promoted_metadata(Path(settings.emotion_artifact_dir))
    audio_provider: AudioEmotionProvider
    if promotion:
        audio_provider = CalibratedCandidateEmotion(settings, promotion)
    elif metadata and passes_promotion_gate(metadata.get("test_metrics", {}), settings.emotion_target_accuracy):
        audio_provider = PromotedRaceRadioEmotion(settings)
    else:
        audio_provider = HuggingFaceAudioEmotion(settings)
    return ProviderBundle(HuggingFaceSpeechToText(settings), audio_provider, HuggingFaceTextEmotion(settings))


def emotion_model_status(settings: Settings) -> dict[str, Any]:
    promotion = benchmark_promotion(settings)
    if promotion:
        benchmark = promotion.get("benchmark") or {}
        metrics = benchmark.get("metrics") or {}
        spec = get_candidate_spec(str(promotion["candidate_id"]))
        return {
            "model": spec.model_id,
            "configured": True,
            "promoted": True,
            "model_version": promotion.get("model_revision"),
            "validation_accuracy": metrics.get("balanced_accuracy"),
            "confidence_threshold": metrics.get("confidence_threshold"),
            "prediction_coverage": metrics.get("prediction_coverage"),
            "analyzer_provenance": {
                "candidate_id": spec.identifier,
                "model_id": spec.model_id,
                "backbone": spec.backbone,
                "model_revision": promotion.get("model_revision"),
                "calibration_version": (promotion.get("benchmark") or {}).get("calibration_version"),
                "language_scope": list(spec.language_scope),
                "benchmark": benchmark,
                "promotion_state": "signed_promoted",
            },
        }
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
            "analyzer_provenance": {"candidate_id": "custom-race-radio", "promotion_state": "legacy_promoted"},
        }
    return {
        "model": settings.hf_audio_emotion_model,
        "configured": bool(settings.hf_audio_emotion_model),
        "promoted": False,
        "model_version": None,
        "validation_accuracy": None,
        "confidence_threshold": None,
        "prediction_coverage": None,
        "analyzer_provenance": {
            "candidate_id": "baseline-superb",
            "model_id": settings.hf_audio_emotion_model,
            "backbone": get_candidate_spec("baseline-superb").backbone,
            "model_revision": None,
            "language_scope": ["en"],
            "promotion_state": "baseline",
            "benchmark": None,
        },
    }


def json_default(value: Any):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(f"Unsupported value: {type(value)}")


def serialize_raw(value: Any) -> str:
    return json.dumps(value, default=json_default)
