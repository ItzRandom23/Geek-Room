"""Version-pinned audio-emotion candidate adapters used by the benchmark.

The production application does not instantiate these adapters unless a signed
benchmark promotion manifest selects one.  Imports for optional research
runtimes therefore remain lazy and do not make the normal fallback fragile.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .audio import load_audio_samples


@dataclass(frozen=True)
class CandidateSpec:
    identifier: str
    model_id: str
    runtime: str
    license_name: str
    native_labels: tuple[str, ...]
    language_scope: tuple[str, ...]
    dimensions: tuple[str, ...] = ()
    requires_gpu: bool = False
    backbone: str = ""


CANDIDATES: dict[str, CandidateSpec] = {
    "baseline-superb": CandidateSpec(
        "baseline-superb", "superb/wav2vec2-base-superb-er", "transformers", "apache-2.0",
        ("neu", "hap", "ang", "sad"), ("en",), backbone="wav2vec2-base",
    ),
    "meralion-ser-v1": CandidateSpec(
        "meralion-ser-v1", "MERaLiON/MERaLiON-SER-v1", "meralion", "meralion-public-license",
        ("neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised"),
        ("en", "zh", "ms", "ta", "th", "id", "vi"), ("valence", "arousal", "dominance"), True, "Whisper-Medium encoder + ECAPA-TDNN",
    ),
    "emotion2vec-plus-large": CandidateSpec(
        "emotion2vec-plus-large", "emotion2vec/emotion2vec_plus_large", "funasr", "model-license",
        ("angry", "disgusted", "fearful", "happy", "neutral", "other", "sad", "surprised", "unknown"),
        ("multilingual",), (), True, "emotion2vec+ large",
    ),
    "sensevoice-small": CandidateSpec(
        "sensevoice-small", "FunAudioLLM/SenseVoiceSmall", "funasr", "model-license",
        ("angry", "happy", "neutral", "sad", "unknown"), ("zh", "en", "yue", "ja", "ko"), (), False, "SenseVoice Small",
    ),
    "speechbrain-iemocap": CandidateSpec(
        "speechbrain-iemocap", "speechbrain/emotion-recognition-wav2vec2-IEMOCAP", "speechbrain", "apache-2.0",
        ("ang", "hap", "neu", "sad"), ("en",), (), False, "wav2vec2-base",
    ),
}


@dataclass
class CandidateWindow:
    start: float
    end: float
    native_scores: dict[str, float]
    raw_label: str
    confidence: float
    dimensions: dict[str, float] = field(default_factory=dict)
    revision: str | None = None
    latency_ms: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class AudioEmotionCandidate:
    """Common benchmark interface for native model outputs and features."""

    def __init__(self, spec: CandidateSpec, revision: str | None = None):
        self.spec = spec
        self.revision = revision

    @property
    def feature_names(self) -> list[str]:
        return [f"score:{label}" for label in self.spec.native_labels] + [f"dimension:{name}" for name in self.spec.dimensions]

    def feature_vector(self, window: CandidateWindow) -> np.ndarray:
        return np.asarray(
            [float(window.native_scores.get(label, 0.0)) for label in self.spec.native_labels]
            + [float(window.dimensions.get(name, 0.0)) for name in self.spec.dimensions],
            dtype=np.float32,
        )

    def analyse(self, audio_path: Path) -> list[CandidateWindow]:
        raise NotImplementedError

    @staticmethod
    def _windows(audio: np.ndarray, sample_rate: int, window_seconds: float = 4.0, step_seconds: float = 2.0):
        if not len(audio):
            return []
        size = max(1, int(window_seconds * sample_rate))
        step = max(1, int(step_seconds * sample_rate))
        if len(audio) <= size:
            return [(0.0, len(audio) / sample_rate, audio)]
        starts = list(range(0, len(audio) - size + 1, step))
        final_start = len(audio) - size
        if starts[-1] != final_start:
            starts.append(final_start)
        return [(start / sample_rate, min(len(audio), start + size) / sample_rate, audio[start:start + size]) for start in starts]


class TransformersCandidate(AudioEmotionCandidate):
    def __init__(self, spec: CandidateSpec, revision: str | None = None):
        super().__init__(spec, revision)
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from transformers import pipeline

            kwargs: dict[str, Any] = {"model": self.spec.model_id, "task": "audio-classification"}
            if self.revision:
                kwargs["revision"] = self.revision
            try:
                import torch
                if torch.cuda.is_available():
                    kwargs["device"] = 0
            except ImportError:
                pass
            self._pipeline = pipeline(**kwargs)
        return self._pipeline

    @staticmethod
    def _score_map(output: Any) -> dict[str, float]:
        rows = output[0] if output and isinstance(output[0], list) else output
        return {str(item["label"]).lower(): float(item["score"]) for item in rows or []}

    def analyse(self, audio_path: Path) -> list[CandidateWindow]:
        audio, sample_rate = load_audio_samples(audio_path, 16000)
        pipe = self._load()
        windows = []
        for start, end, samples in self._windows(audio, sample_rate):
            started = time.perf_counter()
            scores = self._score_map(pipe({"array": samples, "sampling_rate": sample_rate}, top_k=None))
            label, confidence = max(scores.items(), key=lambda item: item[1]) if scores else ("unknown", 0.0)
            windows.append(CandidateWindow(start, end, scores, label, confidence, revision=self.revision, latency_ms=round((time.perf_counter() - started) * 1000, 3)))
        return windows


class MeralionCandidate(AudioEmotionCandidate):
    """Adapter for MERaLiON's custom Transformers output (logits + VAD)."""

    def __init__(self, spec: CandidateSpec, revision: str | None = None):
        super().__init__(spec, revision)
        self._processor = None
        self._model = None
        self._torch = None

    def _load(self):
        if self._model is None:
            import torch
            from transformers import AutoModelForAudioClassification, AutoProcessor

            kwargs: dict[str, Any] = {"trust_remote_code": True}
            if self.revision:
                kwargs["revision"] = self.revision
            self._processor = AutoProcessor.from_pretrained(self.spec.model_id, **kwargs)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = AutoModelForAudioClassification.from_pretrained(self.spec.model_id, **kwargs).to(device).eval()
            self._torch = torch
        return self._processor, self._model, self._torch

    def analyse(self, audio_path: Path) -> list[CandidateWindow]:
        audio, sample_rate = load_audio_samples(audio_path, 16000)
        processor, model, torch = self._load()
        windows = []
        for start, end, samples in self._windows(audio, sample_rate):
            started = time.perf_counter()
            inputs = processor(samples, sampling_rate=sample_rate, return_tensors="pt", return_attention_mask=True)
            inputs = {key: value.to(next(model.parameters()).device) for key, value in inputs.items() if key in ("input_features", "attention_mask")}
            with torch.inference_mode():
                output = model(**inputs)
            logits = output["logits"] if isinstance(output, dict) else output.logits
            probabilities = torch.softmax(logits, dim=-1)[0].detach().cpu().numpy()
            scores = {label: float(score) for label, score in zip(self.spec.native_labels, probabilities)}
            dimensions_raw = output.get("dims") if isinstance(output, dict) else getattr(output, "dims", None)
            values = dimensions_raw[0].detach().cpu().numpy() if dimensions_raw is not None else []
            dimensions = {name: float(value) for name, value in zip(self.spec.dimensions, values)}
            label, confidence = max(scores.items(), key=lambda item: item[1])
            windows.append(CandidateWindow(start, end, scores, label, confidence, dimensions, self.revision, round((time.perf_counter() - started) * 1000, 3)))
        return windows


class FunASRCandidate(AudioEmotionCandidate):
    """Adapter for emotion2vec+ and SenseVoice.  Output variants are normalized."""

    def __init__(self, spec: CandidateSpec, revision: str | None = None):
        super().__init__(spec, revision)
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from funasr import AutoModel
            except ImportError as exc:
                raise RuntimeError("Install backend/requirements-benchmark.txt to use FunASR candidates.") from exc
            model_location = self.spec.model_id
            if self.revision:
                try:
                    from huggingface_hub import snapshot_download
                except ImportError as exc:
                    raise RuntimeError("Install huggingface-hub to load a version-pinned FunASR candidate.") from exc
                model_location = snapshot_download(repo_id=self.spec.model_id, revision=self.revision)
            kwargs: dict[str, Any] = {"model": model_location, "trust_remote_code": True, "disable_update": True}
            try:
                import torch
                if torch.cuda.is_available():
                    kwargs["device"] = "cuda"
            except ImportError:
                pass
            self._model = AutoModel(**kwargs)
        return self._model

    @staticmethod
    def parse_output(value: Any, labels: tuple[str, ...]) -> tuple[dict[str, float], str, float, dict[str, Any]]:
        row = value[0] if isinstance(value, list) and value else value
        row = row if isinstance(row, dict) else {"raw": row}
        raw_scores = row.get("scores") or row.get("score") or row.get("emotion_scores") or {}
        if isinstance(raw_scores, list):
            raw_scores = {label: float(score) for label, score in zip(labels, raw_scores)}
        scores = {str(key).lower(): float(item) for key, item in raw_scores.items()} if isinstance(raw_scores, dict) else {}
        label = str(row.get("label") or row.get("emotion") or "").lower()
        if not label:
            tokens = re.findall(r"<\|([a-z_]+)\|>", str(row.get("text") or "").lower())
            label = next((token.removeprefix("emo_") for token in tokens if token.removeprefix("emo_") in labels), "unknown")
        label = label.removeprefix("emo_")
        if not scores and label in labels:
            scores = {item: 1.0 if item == label else 0.0 for item in labels}
        best_label, confidence = max(scores.items(), key=lambda item: item[1]) if scores else (label, float(row.get("confidence", 0)))
        return scores, best_label, float(confidence), row

    def analyse(self, audio_path: Path) -> list[CandidateWindow]:
        model = self._load()
        started = time.perf_counter()
        try:
            output = model.generate(input=str(audio_path), granularity="utterance", extract_embedding=False)
        except TypeError:
            output = model.generate(input=str(audio_path))
        scores, label, confidence, raw = self.parse_output(output, self.spec.native_labels)
        audio, sample_rate = load_audio_samples(audio_path, 16000)
        return [CandidateWindow(0.0, len(audio) / sample_rate if len(audio) else 0.0, scores, label, confidence, revision=self.revision, latency_ms=round((time.perf_counter() - started) * 1000, 3), raw=raw)]


class SpeechBrainCandidate(AudioEmotionCandidate):
    def __init__(self, spec: CandidateSpec, revision: str | None = None):
        super().__init__(spec, revision)
        self._classifier = None

    def _load(self):
        if self._classifier is None:
            try:
                from speechbrain.inference.interfaces import foreign_class
            except ImportError as exc:
                raise RuntimeError("Install backend/requirements-benchmark.txt to use SpeechBrain candidates.") from exc
            source = self.spec.model_id
            if self.revision:
                try:
                    from huggingface_hub import snapshot_download
                except ImportError as exc:
                    raise RuntimeError("Install huggingface-hub to load a version-pinned SpeechBrain candidate.") from exc
                source = snapshot_download(repo_id=self.spec.model_id, revision=self.revision)
            run_opts: dict[str, Any] = {}
            try:
                import torch
                if torch.cuda.is_available():
                    run_opts["device"] = "cuda"
            except ImportError:
                pass
            self._classifier = foreign_class(source=source, pymodule_file="custom_interface.py", classname="CustomEncoderWav2vec2Classifier", run_opts=run_opts)
        return self._classifier

    def analyse(self, audio_path: Path) -> list[CandidateWindow]:
        classifier = self._load()
        started = time.perf_counter()
        probabilities, score, index, label = classifier.classify_file(str(audio_path))
        values = probabilities.squeeze().detach().cpu().numpy().tolist() if hasattr(probabilities, "detach") else list(probabilities)
        scores = {name: float(value) for name, value in zip(self.spec.native_labels, values)}
        raw_label = str(label[0] if isinstance(label, (list, tuple)) else label).lower()
        confidence = float(max(values)) if values else 0.0
        audio, sample_rate = load_audio_samples(audio_path, 16000)
        return [CandidateWindow(0.0, len(audio) / sample_rate if len(audio) else 0.0, scores, raw_label, confidence, revision=self.revision, latency_ms=round((time.perf_counter() - started) * 1000, 3))]


def get_candidate_spec(identifier: str) -> CandidateSpec:
    try:
        return CANDIDATES[identifier]
    except KeyError as exc:
        raise ValueError(f"Unknown audio-emotion candidate '{identifier}'.") from exc


def build_audio_candidate(identifier: str, revision: str | None) -> AudioEmotionCandidate:
    spec = get_candidate_spec(identifier)
    if spec.runtime == "transformers":
        return TransformersCandidate(spec, revision)
    if spec.runtime == "meralion":
        return MeralionCandidate(spec, revision)
    if spec.runtime == "funasr":
        return FunASRCandidate(spec, revision)
    if spec.runtime == "speechbrain":
        return SpeechBrainCandidate(spec, revision)
    raise ValueError(f"No runtime adapter is available for '{identifier}'.")
