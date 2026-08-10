from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from ..services.audio import load_audio_samples

TRAINED_LABELS = ("calm", "stressed", "tired", "frustrated", "urgent")
FEATURE_SCHEMA_VERSION = "wavlm-prosody-v1"


class ManifestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ManifestItem:
    audio_path: Path
    label: str
    speaker_id: str
    recording_id: str
    transcript: str = ""


@dataclass(frozen=True)
class ManifestDataset:
    items: list[ManifestItem]
    warnings: list[str]


def read_manifest(path: Path, min_clips: int = 1000, min_speakers: int = 10) -> ManifestDataset:
    manifest_path = path.resolve()
    if not manifest_path.is_file():
        raise ManifestValidationError(f"Manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"audio_path", "label", "speaker_id", "recording_id"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ManifestValidationError(f"Manifest is missing required columns: {', '.join(missing)}")
        items: list[ManifestItem] = []
        for line_number, row in enumerate(reader, start=2):
            label = (row.get("label") or "").strip().lower()
            if label not in TRAINED_LABELS:
                raise ManifestValidationError(f"Line {line_number} has unsupported label '{label}'.")
            speaker_id = (row.get("speaker_id") or "").strip()
            recording_id = (row.get("recording_id") or "").strip()
            if not speaker_id or not recording_id:
                raise ManifestValidationError(f"Line {line_number} requires speaker_id and recording_id.")
            audio_path = Path((row.get("audio_path") or "").strip())
            if not audio_path.is_absolute():
                audio_path = manifest_path.parent / audio_path
            audio_path = audio_path.resolve()
            if not audio_path.is_file():
                raise ManifestValidationError(f"Line {line_number} audio file does not exist: {audio_path}")
            items.append(ManifestItem(audio_path, label, speaker_id, recording_id, (row.get("transcript") or "").strip()))

    if len(items) < min_clips:
        raise ManifestValidationError(f"At least {min_clips} labeled clips are required; found {len(items)}.")
    speaker_count = len({item.speaker_id for item in items})
    if speaker_count < min_speakers:
        raise ManifestValidationError(f"At least {min_speakers} speakers are required; found {speaker_count}.")
    duplicate_recordings = [key for key, count in Counter(item.recording_id for item in items).items() if count > 1]
    if duplicate_recordings:
        preview = ", ".join(duplicate_recordings[:5])
        raise ManifestValidationError(f"recording_id values must be unique; duplicates include: {preview}")
    duplicate_paths = [str(key) for key, count in Counter(item.audio_path for item in items).items() if count > 1]
    if duplicate_paths:
        raise ManifestValidationError(f"Audio files must be unique; duplicate includes: {duplicate_paths[0]}")

    counts = Counter(item.label for item in items)
    missing_labels = [label for label in TRAINED_LABELS if not counts[label]]
    if missing_labels:
        raise ManifestValidationError(f"Every state requires examples; missing: {', '.join(missing_labels)}")
    warnings = []
    largest = max(counts.values())
    for label in TRAINED_LABELS:
        if counts[label] < largest * 0.4:
            warnings.append(f"Class '{label}' has {counts[label]} clips versus {largest} in the largest class.")
    return ManifestDataset(items, warnings)


def speaker_group_split(items: list[ManifestItem], seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from sklearn.model_selection import StratifiedGroupKFold

    labels = np.asarray([item.label for item in items])
    groups = np.asarray([item.speaker_id for item in items])
    indices = np.arange(len(items))
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    train_val_idx, test_idx = next(outer.split(indices, labels, groups))
    inner_labels = labels[train_val_idx]
    inner_groups = groups[train_val_idx]
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed + 1)
    train_rel, val_rel = next(inner.split(train_val_idx, inner_labels, inner_groups))
    train_idx = train_val_idx[train_rel]
    val_idx = train_val_idx[val_rel]

    split_groups = [set(groups[part]) for part in (train_idx, val_idx, test_idx)]
    if split_groups[0] & split_groups[1] or split_groups[0] & split_groups[2] or split_groups[1] & split_groups[2]:
        raise RuntimeError("Speaker leakage detected while constructing train/validation/test splits.")
    for name, part in (("training", train_idx), ("validation", val_idx), ("test", test_idx)):
        missing = set(TRAINED_LABELS) - set(labels[part])
        if missing:
            raise ManifestValidationError(f"The {name} split is missing labels: {', '.join(sorted(missing))}")
    return train_idx, val_idx, test_idx


def preprocess_samples(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    import librosa

    samples = np.asarray(audio, dtype=np.float32)
    if not samples.size:
        return samples
    trimmed, _ = librosa.effects.trim(samples, top_db=35)
    samples = trimmed if trimmed.size else samples
    samples = samples - float(np.mean(samples))
    peak = float(np.max(np.abs(samples)))
    if peak > 0:
        samples = samples / peak * 0.95
    return np.asarray(samples, dtype=np.float32)


def split_windows(audio: np.ndarray, sample_rate: int = 16000, window_seconds: float = 4.0, step_seconds: float = 2.0) -> list[tuple[float, float, np.ndarray]]:
    if not audio.size:
        return []
    window_size = max(1, int(window_seconds * sample_rate))
    step_size = max(1, int(step_seconds * sample_rate))
    if len(audio) <= window_size:
        return [(0.0, len(audio) / sample_rate, audio)]
    starts = list(range(0, max(1, len(audio) - window_size + 1), step_size))
    final_start = len(audio) - window_size
    if starts[-1] != final_start:
        starts.append(final_start)
    return [(start / sample_rate, min(len(audio), start + window_size) / sample_rate, audio[start:start + window_size]) for start in starts]


def augment_samples(audio: np.ndarray, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    gain = float(rng.uniform(0.82, 1.18))
    noise_level = float(rng.uniform(0.001, 0.008))
    noise = rng.normal(0, noise_level, size=len(audio)).astype(np.float32)
    return [audio, np.clip(audio * gain, -1, 1).astype(np.float32), np.clip(audio + noise, -1, 1).astype(np.float32)]


def prosodic_features(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    import librosa

    if not audio.size:
        return np.zeros(10, dtype=np.float32)
    rms = librosa.feature.rms(y=audio)[0]
    zcr = librosa.feature.zero_crossing_rate(audio)[0]
    centroid = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sample_rate)[0]
    return np.asarray([
        np.mean(rms), np.std(rms), np.mean(zcr), np.std(zcr),
        np.mean(centroid), np.std(centroid), np.mean(bandwidth), np.std(bandwidth),
        np.percentile(rms, 90), len(audio) / sample_rate,
    ], dtype=np.float32)


class WavLMFeatureExtractor:
    def __init__(self, model_id: str = "microsoft/wavlm-base-plus"):
        self.model_id = model_id
        self._processor = None
        self._model = None

    def _load(self):
        if self._model is None:
            import torch
            from transformers import AutoFeatureExtractor, WavLMModel

            self._processor = AutoFeatureExtractor.from_pretrained(self.model_id)
            self._model = WavLMModel.from_pretrained(self.model_id)
            self._model.eval()
            self._torch = torch
        return self._processor, self._model

    def extract_samples(self, audio: np.ndarray, sample_rate: int = 16000) -> list[tuple[float, float, np.ndarray]]:
        processor, model = self._load()
        audio = preprocess_samples(audio, sample_rate)
        results = []
        for start, end, window in split_windows(audio, sample_rate):
            encoded = processor(window, sampling_rate=sample_rate, return_tensors="pt", padding=True)
            with self._torch.inference_mode():
                hidden = model(**encoded).last_hidden_state.mean(dim=1).cpu().numpy()[0]
            results.append((start, end, np.concatenate([hidden.astype(np.float32), prosodic_features(window, sample_rate)])))
        return results

    def extract_windows(self, audio_path: Path) -> list[tuple[float, float, np.ndarray]]:
        audio, sample_rate = load_audio_samples(audio_path, 16000)
        return self.extract_samples(audio, sample_rate)

    def extract_clip(self, audio_path: Path) -> np.ndarray:
        windows = self.extract_windows(audio_path)
        if not windows:
            raise ValueError(f"No usable audio samples in {audio_path}")
        return np.mean(np.stack([item[2] for item in windows]), axis=0).astype(np.float32)

    def extract_sample_clip(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        windows = self.extract_samples(audio, sample_rate)
        if not windows:
            raise ValueError("No usable audio samples.")
        return np.mean(np.stack([item[2] for item in windows]), axis=0).astype(np.float32)


def select_confidence_threshold(y_true: Iterable[str], probabilities: np.ndarray, classes: Iterable[str], target_accuracy: float = 0.99) -> tuple[float, float]:
    truth = np.asarray(list(y_true))
    class_names = np.asarray(list(classes))
    probabilities = np.asarray(probabilities, dtype=float)
    confidence = probabilities.max(axis=1)
    predictions = class_names[probabilities.argmax(axis=1)]
    candidates = sorted({0.0, 1.0, *confidence.tolist()})
    best_threshold, best_coverage = 1.0, 0.0
    for threshold in candidates:
        accepted = confidence >= threshold
        if not accepted.any():
            continue
        accuracy = float(np.mean(predictions[accepted] == truth[accepted]))
        coverage = float(np.mean(accepted))
        if accuracy >= target_accuracy and coverage > best_coverage:
            best_threshold, best_coverage = float(threshold), coverage
    return round(best_threshold, 6), round(best_coverage, 6)


def evaluate_predictions(y_true: Iterable[str], probabilities: np.ndarray, classes: Iterable[str], threshold: float, groups: Iterable[str] | None = None, seed: int = 42) -> dict:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, recall_score

    truth = np.asarray(list(y_true))
    class_names = np.asarray(list(classes))
    probabilities = np.asarray(probabilities, dtype=float)
    confidence = probabilities.max(axis=1)
    predictions = class_names[probabilities.argmax(axis=1)]
    accepted = confidence >= threshold
    selective_accuracy = float(accuracy_score(truth[accepted], predictions[accepted])) if accepted.any() else 0.0
    recalls = recall_score(truth, predictions, labels=list(TRAINED_LABELS), average=None, zero_division=0)
    low, high = bootstrap_accuracy_interval(truth, predictions, groups, seed=seed)
    return {
        "accuracy": round(float(accuracy_score(truth, predictions)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(truth, predictions)), 6),
        "macro_f1": round(float(f1_score(truth, predictions, labels=list(TRAINED_LABELS), average="macro", zero_division=0)), 6),
        "per_class_recall": {label: round(float(value), 6) for label, value in zip(TRAINED_LABELS, recalls)},
        "confusion_matrix": confusion_matrix(truth, predictions, labels=list(TRAINED_LABELS)).tolist(),
        "selective_accuracy": round(selective_accuracy, 6),
        "prediction_coverage": round(float(np.mean(accepted)), 6),
        "confidence_interval_95": [round(low, 6), round(high, 6)],
    }


def bootstrap_accuracy_interval(y_true: np.ndarray, y_pred: np.ndarray, groups: Iterable[str] | None = None, iterations: int = 1000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    truth = np.asarray(y_true)
    predictions = np.asarray(y_pred)
    group_values = np.asarray(list(groups)) if groups is not None else np.arange(len(truth)).astype(str)
    unique_groups = np.unique(group_values)
    scores = []
    for _ in range(iterations):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        sampled_indices = np.concatenate([np.flatnonzero(group_values == group) for group in sampled_groups])
        scores.append(float(np.mean(truth[sampled_indices] == predictions[sampled_indices])))
    return float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))


def passes_promotion_gate(metrics: dict, target_accuracy: float = 0.99) -> bool:
    return bool(metrics.get("balanced_accuracy", 0) >= target_accuracy and metrics.get("macro_f1", 0) >= target_accuracy)


def promoted_paths(root: Path) -> tuple[Path, Path]:
    promoted = root / "promoted"
    return promoted / "model.joblib", promoted / "metadata.json"


def load_promoted_metadata(root: Path) -> dict | None:
    _, metadata_path = promoted_paths(root)
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return data if data.get("promoted") is True else None
