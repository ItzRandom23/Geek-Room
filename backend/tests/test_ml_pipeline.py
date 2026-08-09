import csv
from pathlib import Path

import numpy as np
import pytest

from app.jobs import ANALYSIS_PHASE_PROGRESS
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

