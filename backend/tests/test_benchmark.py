import csv
import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.benchmark import (
    BenchmarkItem,
    _candidate_from_argument,
    benchmark_candidates,
    expected_calibration_error,
    language_coverage,
    promotion_decision,
    read_benchmark_manifest,
    select_operational_threshold,
    validate_pilot,
)
from app.ml.prepare_cameo import language_code
from app.ml.promotion import (
    PROMOTION_SCHEMA_VERSION,
    artifact_sha256,
    load_signed_promotion_manifest,
    sign_manifest,
)
from app.services.audio_candidates import FunASRCandidate, get_candidate_spec


def item(index: int, language: str = "en", label: str = "calm") -> BenchmarkItem:
    return BenchmarkItem(Path(f"clip-{index}.wav"), label, f"driver-{index % 10}", f"recording-{index}", language, "pilot", "v1", "operator")


def test_funasr_parser_preserves_native_scores_and_unknown_fallback():
    scores, label, confidence, raw = FunASRCandidate.parse_output(
        [{"emotion_scores": {"happy": 0.2, "angry": 0.8}, "emotion": "angry"}],
        get_candidate_spec("emotion2vec-plus-large").native_labels,
    )
    assert scores == {"happy": 0.2, "angry": 0.8}
    assert label == "angry"
    assert confidence == 0.8
    assert raw["emotion"] == "angry"
    _, unknown_label, unknown_confidence, _ = FunASRCandidate.parse_output({}, ("happy",))
    assert unknown_label == "unknown"
    assert unknown_confidence == 0


def test_sensevoice_emotion_tokens_are_normalized_to_native_labels():
    scores, label, confidence, _ = FunASRCandidate.parse_output(
        [{"text": "<|zh|><|EMO_ANGRY|><|Speech|>"}],
        get_candidate_spec("sensevoice-small").native_labels,
    )
    assert label == "angry"
    assert confidence == 1.0
    assert scores["angry"] == 1.0


def test_candidate_cli_requires_and_retains_an_immutable_model_revision():
    revision = "a" * 40
    candidate = _candidate_from_argument(f"baseline-superb@{revision}")
    assert candidate.revision == revision
    with pytest.raises(ValueError, match="40-character immutable"):
        _candidate_from_argument("baseline-superb@main")


def test_manifest_requires_independent_adjudication_and_normalizes_public_labels(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF")
    pilot = tmp_path / "pilot.csv"
    fields = ["audio_path", "label", "speaker_id", "recording_id", "language", "start_seconds", "end_seconds", "radio_condition", "annotator_a", "annotator_b", "adjudicated_label"]
    with pilot.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"audio_path": "clip.wav", "label": "calm", "speaker_id": "driver", "recording_id": "r1", "language": "en", "start_seconds": 0, "end_seconds": 1, "radio_condition": "engine", "annotator_a": "a", "annotator_b": "b", "adjudicated_label": "urgent"})
    assert read_benchmark_manifest(pilot)[0].label == "urgent"
    public = tmp_path / "public.csv"
    with public.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["audio_path", "label", "speaker_id", "recording_id", "language", "dataset", "dataset_version", "license"])
        writer.writeheader()
        writer.writerow({"audio_path": "clip.wav", "label": "fearful", "speaker_id": "public", "recording_id": "p1", "language": "fr", "dataset": "CAMEO", "dataset_version": "1", "license": "research"})
    assert read_benchmark_manifest(public, public=True)[0].label == "stressed"


def test_pilot_validation_and_language_qualification_thresholds():
    items = [item(index, "en" if index < 100 else "hi", ("calm", "stressed", "tired", "frustrated", "urgent")[index % 5]) for index in range(1000)]
    summary = validate_pilot(items)
    assert summary["clips"] == 1000
    assert summary["languages"]["en"]["qualified"] is True
    assert summary["languages"]["hi"]["qualified"] is True
    with pytest.raises(ValueError, match="at least 1000"):
        validate_pilot(items[:99])


def test_threshold_and_calibration_metrics_are_deterministic():
    truth = np.asarray(["calm", "stressed", "tired", "frustrated", "urgent"])
    classes = ["calm", "stressed", "tired", "frustrated", "urgent"]
    probabilities = np.eye(5, dtype=float)
    threshold = select_operational_threshold(truth, probabilities, classes)
    assert threshold == 1.0
    assert expected_calibration_error(probabilities, truth, classes) == 0.0


def test_public_corpus_is_scored_but_cannot_change_the_pilot_promotion_split(monkeypatch, tmp_path):
    class Candidate:
        def __init__(self, identifier):
            self.spec = get_candidate_spec(identifier)
            self.revision = "a" * 40
            self.feature_names = [f"f-{index}" for index in range(len(self.spec.native_labels) + len(self.spec.dimensions))]

    labels = ("calm", "stressed", "tired", "frustrated", "urgent")
    pilot = [
        BenchmarkItem(Path(f"clip-{speaker}-{offset}.wav"), labels[offset % len(labels)], f"driver-{speaker}", f"recording-{speaker}-{offset}", "en", "race-radio-pilot", "v1", "operator")
        for speaker in range(10) for offset in range(100)
    ]
    public = [
        BenchmarkItem(Path(f"public-{index}.wav"), label, f"public-speaker-{index}", f"public-recording-{index}", "fr", "CAMEO", "v1", "cc-by-nc-sa-4.0")
        for index, label in enumerate(labels)
    ]

    def fake_probabilities(candidate, rows):
        width = len(candidate.feature_names)
        matrix = np.zeros((len(rows), width), dtype=np.float32)
        for row_index, row in enumerate(rows):
            matrix[row_index, labels.index(row.label) % width] = 1.0
        return matrix, {"median_window_latency_ms": 1.0, "p95_window_latency_ms": 1.0, "median_clip_latency_ms": 1.0, "median_real_time_factor": 0.01, "precision": "fp32"}

    monkeypatch.setattr("app.ml.benchmark._probabilities", fake_probabilities)
    monkeypatch.setattr("app.ml.benchmark.grouped_metric_interval", lambda *_args, **_kwargs: [0.0, 1.0])
    monkeypatch.setattr("app.ml.benchmark.paired_macro_f1_interval", lambda *_args, **_kwargs: [0.01, 0.02])
    report = benchmark_candidates(pilot, [Candidate("baseline-superb"), Candidate("meralion-ser-v1")], tmp_path, public_items=public, require_cuda=False)
    assert sum(report["split_sizes"].values()) == len(pilot)
    assert report["public_cross_domain_clips"] == len(public)
    assert report["candidates"]["baseline-superb"]["cross_domain_public"]["datasets"][0]["source"] == "CAMEO"


def test_cameo_language_names_are_converted_to_standard_codes():
    assert language_code("English") == "en"
    assert language_code("Bengali") == "bn"


def test_promotion_gate_requires_all_safety_conditions():
    baseline = {"macro_f1": 0.60, "prediction_coverage": 0.8, "per_class_recall": {"urgent": 0.80}, "per_language": {"en": {"macro_f1": 0.6}}}
    candidate = {"macro_f1": 0.66, "prediction_coverage": 0.75, "per_class_recall": {"urgent": 0.82}, "per_language": {"en": {"qualified": True, "macro_f1": 0.61}}}
    reviews = {"license_review_id": "LIC-1", "security_review_id": "SEC-1"}
    assert promotion_decision(candidate, baseline, [0.01, 0.12], reviews)["passed"] is True
    assert promotion_decision(candidate, baseline, [-0.01, 0.12], reviews)["passed"] is False


def test_signed_promotion_manifest_rejects_tampering_and_artifact_escape(tmp_path):
    artifact = tmp_path / "calibrators" / "candidate.joblib"
    artifact.parent.mkdir()
    artifact.write_bytes(b"calibration")
    manifest = sign_manifest({
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "candidate_id": "meralion-ser-v1",
        "model_id": "MERaLiON/MERaLiON-SER-v1",
        "model_revision": "abc123",
        "calibration_artifact": "calibrators/candidate.joblib",
        "calibration_sha256": artifact_sha256(artifact),
        "benchmark": {"metrics": {"macro_f1": 0.8}},
        "gates": {"passed": True, "checks": {
            "macro_f1_uplift_at_least_5pp": True,
            "paired_bootstrap_lower_bound_positive": True,
            "coverage_at_least_70pct": True,
            "urgent_recall_non_regression": True,
            "qualified_languages_no_more_than_5pp_regression": True,
            "license_review_approved": True,
            "security_review_approved": True,
        }},
        "reviews": {"license_approved": True, "security_approved": True, "license_review_id": "LIC-1", "security_review_id": "SEC-1"},
    }, "secret")
    path = tmp_path / "promotion.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert load_signed_promotion_manifest(path, "secret", tmp_path)["candidate_id"] == "meralion-ser-v1"
    manifest["model_revision"] = "tampered"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert load_signed_promotion_manifest(path, "secret", tmp_path) is None
