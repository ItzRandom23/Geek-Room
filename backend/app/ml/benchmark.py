"""Reproducible evaluation of audio-emotion candidates on race-radio manifests.

The command intentionally needs a human-adjudicated manifest.  Public corpora
are useful cross-domain evidence, but cannot prove safety for radio traffic.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np

from ..services.audio_candidates import AudioEmotionCandidate, build_audio_candidate, get_candidate_spec
from ..services.labels import normalize_label
from .emotion import TRAINED_LABELS, speaker_group_split
from .promotion import PROMOTION_SCHEMA_VERSION, artifact_sha256, sign_manifest


PILOT_COLUMNS = {
    "audio_path", "label", "speaker_id", "recording_id", "language", "start_seconds", "end_seconds",
    "radio_condition", "annotator_a", "annotator_b", "adjudicated_label",
}
PUBLIC_COLUMNS = {"audio_path", "label", "speaker_id", "recording_id", "language", "dataset", "dataset_version", "license"}


@dataclass(frozen=True)
class BenchmarkItem:
    audio_path: Path
    label: str
    speaker_id: str
    recording_id: str
    language: str
    source: str
    dataset_version: str
    license_name: str
    start_seconds: float = 0.0
    end_seconds: float | None = None
    radio_condition: str = "unspecified"
    annotator_a: str = ""
    annotator_b: str = ""
    adjudicated_label: str = ""


def _required_columns(public: bool) -> set[str]:
    return PUBLIC_COLUMNS if public else PILOT_COLUMNS


def read_benchmark_manifest(path: Path, *, public: bool = False) -> list[BenchmarkItem]:
    path = path.resolve()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = _required_columns(public) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {', '.join(sorted(missing))}")
        items: list[BenchmarkItem] = []
        for line, row in enumerate(reader, start=2):
            raw_label = (row.get("adjudicated_label") or row.get("label") or "").strip().lower()
            label = normalize_label(raw_label) if public else raw_label
            if label not in TRAINED_LABELS:
                raise ValueError(f"{path.name}:{line} has unsupported operational label '{label}'.")
            audio_path = Path((row.get("audio_path") or "").strip())
            if not audio_path.is_absolute():
                audio_path = path.parent / audio_path
            audio_path = audio_path.resolve()
            if not audio_path.is_file():
                raise ValueError(f"{path.name}:{line} audio file does not exist: {audio_path}")
            speaker = (row.get("speaker_id") or "").strip()
            recording = (row.get("recording_id") or "").strip()
            language = (row.get("language") or "").strip().lower()
            if not speaker or not recording or not language:
                raise ValueError(f"{path.name}:{line} requires speaker_id, recording_id, and language.")
            if not public and (row.get("annotator_a") or "").strip() == (row.get("annotator_b") or "").strip():
                raise ValueError(f"{path.name}:{line} requires two independent annotator identifiers.")
            items.append(BenchmarkItem(
                audio_path=audio_path,
                label=label,
                speaker_id=speaker,
                recording_id=recording,
                language=language,
                source=(row.get("dataset") or "race-radio-pilot").strip(),
                dataset_version=(row.get("dataset_version") or "pilot-v1").strip(),
                license_name=(row.get("license") or "operator-controlled").strip(),
                start_seconds=float(row.get("start_seconds") or 0),
                end_seconds=float(row["end_seconds"]) if row.get("end_seconds") else None,
                radio_condition=(row.get("radio_condition") or "unspecified").strip(),
                annotator_a=(row.get("annotator_a") or "").strip(),
                annotator_b=(row.get("annotator_b") or "").strip(),
                adjudicated_label=(row.get("adjudicated_label") or "").strip().lower(),
            ))
    recordings = Counter(item.recording_id for item in items)
    if duplicates := [name for name, count in recordings.items() if count > 1]:
        raise ValueError(f"{path.name} repeats recording_id values; first duplicate is '{duplicates[0]}'.")
    return items


def language_coverage(items: Iterable[BenchmarkItem], minimum_clips: int = 100, minimum_speakers: int = 10) -> dict[str, dict[str, Any]]:
    by_language: dict[str, list[BenchmarkItem]] = {}
    for item in items:
        by_language.setdefault(item.language, []).append(item)
    return {
        language: {
            "clips": len(rows),
            "speakers": len({row.speaker_id for row in rows}),
            "qualified": len(rows) >= minimum_clips and len({row.speaker_id for row in rows}) >= minimum_speakers,
        }
        for language, rows in sorted(by_language.items())
    }


def dataset_coverage(items: Iterable[BenchmarkItem]) -> list[dict[str, Any]]:
    return [
        {"source": source, "version": version, "license": license_name, "clips": clips}
        for (source, version, license_name), clips in sorted(Counter((item.source, item.dataset_version, item.license_name) for item in items).items())
    ]


def validate_pilot(items: list[BenchmarkItem], minimum_clips: int = 1000, minimum_speakers: int = 10) -> dict[str, Any]:
    if len(items) < minimum_clips:
        raise ValueError(f"Pilot requires at least {minimum_clips} clips; found {len(items)}.")
    speakers = {item.speaker_id for item in items}
    if len(speakers) < minimum_speakers:
        raise ValueError(f"Pilot requires at least {minimum_speakers} speakers; found {len(speakers)}.")
    label_counts = Counter(item.label for item in items)
    missing = [label for label in TRAINED_LABELS if not label_counts[label]]
    if missing:
        raise ValueError(f"Pilot has no examples for: {', '.join(missing)}.")
    return {"clips": len(items), "speakers": len(speakers), "labels": dict(label_counts), "languages": language_coverage(items)}


def _calibrator(seed: int):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=4000, class_weight="balanced", C=1.0, random_state=seed)),
    ])


def _probabilities(candidate: AudioEmotionCandidate, items: list[BenchmarkItem]) -> tuple[np.ndarray, dict[str, Any]]:
    vectors, window_timing, clip_timing, durations = [], [], [], []
    for index, item in enumerate(items, start=1):
        windows = candidate.analyse(item.audio_path)
        if not windows:
            raise RuntimeError(f"{candidate.spec.identifier} returned no predictions for {item.audio_path.name}.")
        weighted = np.stack([candidate.feature_vector(window) for window in windows])
        durations_for_windows = np.asarray([max(0.05, window.end - window.start) for window in windows], dtype=np.float32)
        vectors.append(np.average(weighted, axis=0, weights=durations_for_windows))
        clip_latency = sum(window.latency_ms or 0.0 for window in windows)
        window_timing.extend(window.latency_ms or 0.0 for window in windows)
        clip_timing.append(clip_latency)
        durations.append(max(0.001, item.end_seconds - item.start_seconds if item.end_seconds is not None else sum(durations_for_windows)))
        print(f"[{candidate.spec.identifier}] {index}/{len(items)} {item.audio_path.name}")
    return np.stack(vectors), {
        "median_window_latency_ms": round(float(np.median(window_timing)), 3),
        "p95_window_latency_ms": round(float(np.percentile(window_timing, 95)), 3),
        "median_clip_latency_ms": round(float(np.median(clip_timing)), 3),
        "median_real_time_factor": round(float(np.median(np.asarray(clip_timing) / 1000 / np.asarray(durations))), 5),
        "precision": "fp32",
    }


def select_operational_threshold(y_true: np.ndarray, probabilities: np.ndarray, classes: list[str], minimum_coverage: float = 0.70) -> float:
    """Choose the validation threshold with highest macro F1 at usable coverage."""
    from sklearn.metrics import f1_score

    confidence = probabilities.max(axis=1)
    raw = np.asarray(classes)[probabilities.argmax(axis=1)]
    choices = []
    for threshold in sorted(set(float(value) for value in confidence)):
        accepted = confidence >= threshold
        coverage = float(np.mean(accepted))
        if coverage < minimum_coverage:
            continue
        score = f1_score(y_true[accepted], raw[accepted], labels=list(TRAINED_LABELS), average="macro", zero_division=0)
        choices.append((score, coverage, threshold))
    return round(max(choices, default=(0.0, 0.0, 1.0))[2], 6)


def expected_calibration_error(probabilities: np.ndarray, truth: np.ndarray, classes: list[str], bins: int = 10) -> float:
    confidence = probabilities.max(axis=1)
    predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
    correct = predicted == truth
    total = len(truth)
    value = 0.0
    for lower in np.linspace(0, 1, bins, endpoint=False):
        upper = lower + 1 / bins
        selected = (confidence >= lower) & (confidence < upper if upper < 1 else confidence <= upper)
        if selected.any():
            value += abs(float(correct[selected].mean()) - float(confidence[selected].mean())) * float(selected.sum()) / total
    return round(value, 6)


def grouped_metric_interval(truth: np.ndarray, predictions: np.ndarray, speakers: np.ndarray, *, metric: str = "macro_f1", iterations: int = 1000, seed: int = 42) -> list[float]:
    from sklearn.metrics import f1_score

    rng = np.random.default_rng(seed)
    groups = np.unique(speakers)
    values = []
    for _ in range(iterations):
        sample = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([np.flatnonzero(speakers == group) for group in sample])
        if metric == "macro_f1":
            values.append(float(f1_score(truth[indices], predictions[indices], labels=list(TRAINED_LABELS), average="macro", zero_division=0)))
        else:
            values.append(float(np.mean(truth[indices] == predictions[indices])))
    return [round(float(np.percentile(values, 2.5)), 6), round(float(np.percentile(values, 97.5)), 6)]


def paired_macro_f1_interval(truth: np.ndarray, baseline: np.ndarray, candidate: np.ndarray, speakers: np.ndarray, iterations: int = 1000, seed: int = 42) -> list[float]:
    from sklearn.metrics import f1_score

    rng = np.random.default_rng(seed)
    groups = np.unique(speakers)
    deltas = []
    for _ in range(iterations):
        sample = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([np.flatnonzero(speakers == group) for group in sample])
        candidate_score = f1_score(truth[indices], candidate[indices], labels=list(TRAINED_LABELS), average="macro", zero_division=0)
        baseline_score = f1_score(truth[indices], baseline[indices], labels=list(TRAINED_LABELS), average="macro", zero_division=0)
        deltas.append(float(candidate_score - baseline_score))
    return [round(float(np.percentile(deltas, 2.5)), 6), round(float(np.percentile(deltas, 97.5)), 6)]


def score_predictions(items: list[BenchmarkItem], probabilities: np.ndarray, classes: list[str], threshold: float, *, language_requirements: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score

    truth = np.asarray([item.label for item in items])
    speakers = np.asarray([item.speaker_id for item in items])
    confidence = probabilities.max(axis=1)
    raw = np.asarray(classes)[probabilities.argmax(axis=1)]
    accepted = confidence >= threshold
    predicted = np.where(accepted, raw, "uncertain")
    recall = recall_score(truth, predicted, labels=list(TRAINED_LABELS), average=None, zero_division=0)
    urgent_total = int(np.sum(truth == "urgent"))
    urgent_false_negatives = int(np.sum((truth == "urgent") & (predicted != "urgent")))
    report = {
        "accuracy": round(float(accuracy_score(truth, predicted)), 6),
        # Explicit labels keep the abstention token out of the class set while
        # still counting every abstained item as a false negative for its truth.
        "balanced_accuracy": round(float(np.mean(recall)), 6),
        "macro_f1": round(float(f1_score(truth, predicted, labels=list(TRAINED_LABELS), average="macro", zero_division=0)), 6),
        "macro_f1_ci_95": grouped_metric_interval(truth, predicted, speakers),
        "per_class_recall": {label: round(float(value), 6) for label, value in zip(TRAINED_LABELS, recall)},
        "urgent_false_negative_rate": round(urgent_false_negatives / urgent_total, 6) if urgent_total else None,
        "prediction_coverage": round(float(np.mean(accepted)), 6),
        "expected_calibration_error": expected_calibration_error(probabilities, truth, classes),
        "confidence_threshold": threshold,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=list(TRAINED_LABELS)).tolist(),
        "failure_clips": [
            {"recording_id": item.recording_id, "language": item.language, "label": item.label, "prediction": str(predicted[index]), "confidence": round(float(confidence[index]), 4), "radio_condition": item.radio_condition}
            for index, item in enumerate(items)
            if item.label == "urgent" and predicted[index] != "urgent"
        ][:20],
    }
    by_language: dict[str, dict[str, Any]] = {}
    for language in sorted({item.language for item in items}):
        indices = np.asarray([index for index, item in enumerate(items) if item.language == language])
        qualification = (language_requirements or {}).get(language, {})
        by_language[language] = {
            "qualified": bool(qualification.get("qualified")),
            "clips": len(indices),
            "speakers": len({items[index].speaker_id for index in indices}),
            "macro_f1": round(float(f1_score(truth[indices], predicted[indices], labels=list(TRAINED_LABELS), average="macro", zero_division=0)), 6),
            "urgent_recall": round(float(recall_score(truth[indices], predicted[indices], labels=["urgent"], average="macro", zero_division=0)), 6),
        }
    report["per_language"] = by_language
    return report


def promotion_decision(candidate: dict[str, Any], baseline: dict[str, Any], paired_ci: list[float], reviews: dict[str, str] | None = None) -> dict[str, Any]:
    candidate_languages = candidate.get("per_language", {})
    baseline_languages = baseline.get("per_language", {})
    language_regressions = [
        language for language, result in candidate_languages.items()
        if result.get("qualified") and result["macro_f1"] < baseline_languages.get(language, {}).get("macro_f1", 0) - 0.05
    ]
    delta = round(candidate["macro_f1"] - baseline["macro_f1"], 6)
    urgent_baseline = baseline["per_class_recall"].get("urgent", 0.0)
    reviews = reviews or {}
    checks = {
        "macro_f1_uplift_at_least_5pp": delta >= 0.05,
        "paired_bootstrap_lower_bound_positive": paired_ci[0] > 0,
        "coverage_at_least_70pct": candidate["prediction_coverage"] >= 0.70,
        "urgent_recall_non_regression": candidate["per_class_recall"].get("urgent", 0.0) >= urgent_baseline,
        "qualified_languages_no_more_than_5pp_regression": not language_regressions,
        "license_review_approved": bool(reviews.get("license_review_id")),
        "security_review_approved": bool(reviews.get("security_review_id")),
    }
    return {"passed": all(checks.values()), "checks": checks, "macro_f1_delta": delta, "paired_macro_f1_ci_95": paired_ci, "language_regressions": language_regressions, "reviews": {"license_review_id": reviews.get("license_review_id"), "security_review_id": reviews.get("security_review_id")}}


def runtime_environment() -> dict[str, Any]:
    result: dict[str, Any] = {"python": sys.version.split()[0], "platform": platform.platform(), "precision": "fp32"}
    try:
        import torch
        result.update({"torch": torch.__version__, "cuda_available": bool(torch.cuda.is_available())})
        if torch.cuda.is_available():
            result["gpu"] = torch.cuda.get_device_name(0)
            result["gpu_memory_bytes"] = int(torch.cuda.get_device_properties(0).total_memory)
    except ImportError:
        result["torch"] = None
        result["cuda_available"] = False
    return result


def _calibration_artifact(candidate: AudioEmotionCandidate, model, classes: list[str], feature_names: list[str], path: Path, training_hash: str) -> dict[str, Any]:
    artifact = {"candidate_id": candidate.spec.identifier, "model_id": candidate.spec.model_id, "model_revision": candidate.revision, "feature_names": feature_names, "classes": classes, "training_hash": training_hash, "calibration_version": f"cal-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "classifier": model}
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    return {key: value for key, value in artifact.items() if key != "classifier"}


def benchmark_candidates(pilot_items: list[BenchmarkItem], candidates: list[AudioEmotionCandidate], output_dir: Path, seed: int = 42, *, public_items: list[BenchmarkItem] | None = None, reviews: dict[str, str] | None = None, require_cuda: bool = True) -> dict[str, Any]:
    """Fit and gate on the speaker-held-out radio pilot only.

    Licensed public corpora are scored after calibration as cross-domain
    evidence. They never enter the split, threshold selection, paired
    bootstrap, or promotion decision because a backbone may have seen some
    public corpus material during pre-training.
    """
    if not candidates or candidates[0].spec.identifier != "baseline-superb":
        raise ValueError("The first benchmark candidate must be baseline-superb.")
    environment = runtime_environment()
    if require_cuda and not environment.get("cuda_available"):
        raise RuntimeError("A CUDA GPU is required for a production benchmark. Run this command in the approved GPU environment.")
    pilot = validate_pilot(pilot_items)
    public_items = public_items or []
    train_idx, validation_idx, test_idx = speaker_group_split(pilot_items, seed)
    labels = np.asarray([item.label for item in pilot_items])
    languages = language_coverage(pilot_items)
    output_dir.mkdir(parents=True, exist_ok=True)
    values: dict[str, Any] = {}
    test_predictions: dict[str, np.ndarray] = {}
    for candidate in candidates:
        torch = None
        if environment.get("cuda_available"):
            import torch as torch_module
            torch = torch_module
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        features, timing = _probabilities(candidate, pilot_items)
        calibrator = _calibrator(seed)
        calibrator.fit(features[train_idx], labels[train_idx])
        classes = [str(label) for label in calibrator.classes_]
        validation_probabilities = calibrator.predict_proba(features[validation_idx])
        threshold = select_operational_threshold(labels[validation_idx], validation_probabilities, classes)
        test_probabilities = calibrator.predict_proba(features[test_idx])
        metrics = score_predictions([pilot_items[index] for index in test_idx], test_probabilities, classes, threshold, language_requirements=languages)
        metrics["runtime"] = timing
        cross_domain: dict[str, Any] | None = None
        if public_items:
            public_features, public_timing = _probabilities(candidate, public_items)
            public_probabilities = calibrator.predict_proba(public_features)
            cross_domain = score_predictions(
                public_items,
                public_probabilities,
                classes,
                threshold,
                language_requirements=language_coverage(public_items),
            )
            cross_domain["runtime"] = public_timing
            cross_domain["datasets"] = dataset_coverage(public_items)
        if torch is not None:
            timing["peak_vram_bytes"] = int(torch.cuda.max_memory_allocated())
            timing["gpu"] = environment.get("gpu")
        artifact_path = output_dir / "calibrators" / f"{candidate.spec.identifier}.joblib"
        manifest_hash = hashlib.sha256("|".join(item.recording_id for item in [pilot_items[index] for index in train_idx]).encode("utf-8")).hexdigest()
        calibration = _calibration_artifact(candidate, calibrator, classes, candidate.feature_names, artifact_path, manifest_hash)
        values[candidate.spec.identifier] = {"candidate": asdict(candidate.spec), "revision": candidate.revision, "metrics": metrics, "cross_domain_public": cross_domain, "calibration": calibration, "calibration_artifact": str(artifact_path.relative_to(output_dir)), "calibration_sha256": artifact_sha256(artifact_path)}
        test_predictions[candidate.spec.identifier] = np.where(test_probabilities.max(axis=1) >= threshold, np.asarray(classes)[test_probabilities.argmax(axis=1)], "uncertain")
    baseline = values["baseline-superb"]
    decisions = {}
    truth = labels[test_idx]
    speakers = np.asarray([pilot_items[index].speaker_id for index in test_idx])
    for identifier, value in values.items():
        if identifier == "baseline-superb":
            continue
        paired_ci = paired_macro_f1_interval(truth, test_predictions["baseline-superb"], test_predictions[identifier], speakers, seed=seed)
        decisions[identifier] = promotion_decision(value["metrics"], baseline["metrics"], paired_ci, reviews)
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "environment": environment, "pilot": pilot, "pilot_datasets": dataset_coverage(pilot_items), "public_cross_domain_clips": len(public_items), "split_sizes": {"train": len(train_idx), "validation": len(validation_idx), "test": len(test_idx)}, "candidates": values, "promotion_decisions": decisions}


def write_scorecard(report: dict[str, Any], output_dir: Path, signing_key: str | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# PitSense audio-emotion benchmark", "", f"Generated: {report['generated_at']}", "", "| Candidate | Macro F1 | Balanced accuracy | Coverage | Promotion |", "| --- | ---: | ---: | ---: | --- |"]
    for identifier, value in report["candidates"].items():
        metrics = value["metrics"]
        decision = report["promotion_decisions"].get(identifier, {"passed": False})
        lines.append(f"| {identifier} | {metrics['macro_f1']:.3f} | {metrics['balanced_accuracy']:.3f} | {metrics['prediction_coverage']:.3f} | {'approved' if decision['passed'] else 'not promoted'} |")
    (output_dir / "benchmark-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not signing_key:
        return
    for identifier, decision in report["promotion_decisions"].items():
        if not decision["passed"]:
            continue
        candidate = report["candidates"][identifier]
        manifest = sign_manifest({
            "schema_version": PROMOTION_SCHEMA_VERSION,
            "candidate_id": identifier,
            "model_id": candidate["candidate"]["model_id"],
            "model_revision": candidate["revision"],
            "calibration_artifact": candidate["calibration_artifact"],
            "calibration_sha256": candidate["calibration_sha256"],
            "benchmark": {
                "report_sha256": hashlib.sha256((output_dir / "benchmark-report.json").read_bytes()).hexdigest(),
                "metrics": candidate["metrics"],
                "baseline_metrics": report["candidates"]["baseline-superb"]["metrics"],
                "datasets": report["pilot_datasets"],
                "language_coverage": report["pilot"]["languages"],
                "environment": report["environment"],
                "calibration_version": candidate["calibration"]["calibration_version"],
            },
            "gates": decision,
            "reviews": {"license_approved": True, "security_approved": True, **decision["reviews"]},
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }, signing_key)
        (output_dir / f"promotion-{identifier}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _candidate_from_argument(value: str) -> AudioEmotionCandidate:
    identifier, separator, revision = value.partition("@")
    if not separator or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise ValueError("Candidates must use a 40-character immutable commit SHA, e.g. meralion-ser-v1@<commit-sha>.")
    return build_audio_candidate(identifier, revision)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark version-pinned PitSense audio-emotion candidates.")
    parser.add_argument("--pilot-manifest", type=Path, required=True)
    parser.add_argument("--public-manifest", type=Path, action="append", default=[])
    parser.add_argument("--candidate", action="append", required=True, help="candidate@immutable-revision; include baseline-superb first")
    parser.add_argument("--output-dir", type=Path, default=Path("./artifacts/emotion/benchmark"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sign", action="store_true", help="Write a signed promotion manifest only if a candidate passes all gates.")
    parser.add_argument("--license-review-id", help="Approved license-review ticket/record; required with --sign.")
    parser.add_argument("--security-review-id", help="Approved security-review ticket/record; required with --sign.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pilot_items = read_benchmark_manifest(args.pilot_manifest)
    public_items: list[BenchmarkItem] = []
    for manifest in args.public_manifest:
        public_items.extend(read_benchmark_manifest(manifest, public=True))
    candidates = [_candidate_from_argument(value) for value in args.candidate]
    reviews = {"license_review_id": args.license_review_id or "", "security_review_id": args.security_review_id or ""}
    report = benchmark_candidates(pilot_items, candidates, args.output_dir, args.seed, public_items=public_items, reviews=reviews)
    signing_key = os.getenv("BENCHMARK_SIGNING_KEY") if args.sign else None
    if args.sign and not signing_key:
        raise ValueError("BENCHMARK_SIGNING_KEY is required with --sign.")
    if args.sign and (not args.license_review_id or not args.security_review_id):
        raise ValueError("--license-review-id and --security-review-id are required with --sign.")
    write_scorecard(report, args.output_dir, signing_key)
    print(json.dumps({"output_dir": str(args.output_dir), "promotion_decisions": report["promotion_decisions"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
