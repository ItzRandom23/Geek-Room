from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from ..config import get_settings
from ..services.analysis import urgency_score
from ..services.ai import HuggingFaceSpeechToText, HuggingFaceTextEmotion
from ..services.audio import load_audio_samples
from .emotion import (
    FEATURE_SCHEMA_VERSION,
    TRAINED_LABELS,
    WavLMFeatureExtractor,
    augment_samples,
    evaluate_predictions,
    passes_promotion_gate,
    read_manifest,
    select_confidence_threshold,
    speaker_group_split,
)


def _cache_key(path: Path, model_id: str, transcript: str) -> str:
    stat = path.stat()
    raw = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{model_id}:{FEATURE_SCHEMA_VERSION}:{transcript}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _extract_dataset(items, extractor, cache_dir: Path, transcribe_missing: bool, seed: int):
    settings = get_settings()
    stt = HuggingFaceSpeechToText(settings) if transcribe_missing else None
    text_provider = HuggingFaceTextEmotion(settings)
    audio_features, augmented_features, context_features = [], [], []
    cache_dir.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(items, start=1):
        cache_path = cache_dir / f"{_cache_key(item.audio_path, extractor.model_id, item.transcript)}.npz"
        if cache_path.exists():
            cached = np.load(cache_path)
            audio_vector = cached["audio"]
            augmented_vectors = cached["augmented"]
            context_vector = cached["context"]
        else:
            audio, sample_rate = load_audio_samples(item.audio_path, 16000)
            variants = augment_samples(audio, seed + index)
            vectors = [extractor.extract_sample_clip(variant, sample_rate) for variant in variants]
            audio_vector = vectors[0]
            augmented_vectors = np.stack(vectors[1:])
            transcript = item.transcript
            if not transcript and stt is not None:
                transcript = stt.transcribe(item.audio_path).transcript
            text_scores = text_provider.analyse(transcript) if transcript else {}
            context_vector = np.asarray([text_scores.get(label, 0.0) for label in TRAINED_LABELS] + [urgency_score(transcript)], dtype=np.float32)
            np.savez_compressed(cache_path, audio=audio_vector, augmented=augmented_vectors, context=context_vector)
        audio_features.append(audio_vector)
        augmented_features.append(augmented_vectors)
        context_features.append(context_vector)
        print(f"[{index}/{len(items)}] features: {item.audio_path.name}")
    return np.stack(audio_features), np.stack(augmented_features), np.stack(context_features)


def _candidate_models(seed: int):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    return {
        "logistic": Pipeline([("scale", StandardScaler()), ("classifier", LogisticRegression(max_iter=4000, class_weight="balanced", C=2.0, random_state=seed))]),
        "rbf_svm": Pipeline([("scale", StandardScaler()), ("classifier", SVC(C=5.0, gamma="scale", probability=True, class_weight="balanced", random_state=seed))]),
    }


def train(args: argparse.Namespace) -> dict:
    from sklearn.base import clone
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    dataset = read_manifest(args.manifest, args.min_clips, args.min_speakers)
    for warning in dataset.warnings:
        print(f"warning: {warning}")
    train_idx, val_idx, test_idx = speaker_group_split(dataset.items, args.seed)
    extractor = WavLMFeatureExtractor(args.encoder_model)
    audio_x, augmented_x, context_x = _extract_dataset(dataset.items, extractor, args.cache_dir, args.transcribe_missing, args.seed)
    labels = np.asarray([item.label for item in dataset.items])
    speakers = np.asarray([item.speaker_id for item in dataset.items])

    train_audio = np.concatenate([audio_x[train_idx], augmented_x[train_idx].reshape(-1, audio_x.shape[1])], axis=0)
    train_context = np.concatenate([context_x[train_idx], np.repeat(context_x[train_idx], augmented_x.shape[1], axis=0)], axis=0)
    train_labels = np.concatenate([labels[train_idx], np.repeat(labels[train_idx], augmented_x.shape[1])])
    train_speakers = np.concatenate([speakers[train_idx], np.repeat(speakers[train_idx], augmented_x.shape[1])])

    candidate_scores = {}
    folds = min(5, len(np.unique(train_speakers)))
    grouped_cv = GroupKFold(n_splits=folds)
    candidates = _candidate_models(args.seed)
    for name, model in candidates.items():
        scores = cross_val_score(model, train_audio, train_labels, groups=train_speakers, cv=grouped_cv, scoring="f1_macro", n_jobs=1)
        candidate_scores[name] = {"mean_macro_f1": round(float(np.mean(scores)), 6), "folds": [round(float(score), 6) for score in scores]}
    selected_name = max(candidate_scores, key=lambda name: candidate_scores[name]["mean_macro_f1"])
    audio_model = clone(candidates[selected_name])
    oof_probabilities = cross_val_predict(audio_model, train_audio, train_labels, groups=train_speakers, cv=grouped_cv, method="predict_proba", n_jobs=1)
    oof_classes = np.asarray(candidates[selected_name].fit(train_audio, train_labels).classes_)
    audio_model.fit(train_audio, train_labels)

    fusion_model = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=4000, class_weight="balanced", C=1.0, random_state=args.seed)),
    ])
    fusion_model.fit(np.concatenate([oof_probabilities, train_context], axis=1), train_labels)

    val_audio = audio_model.predict_proba(audio_x[val_idx])
    val_probabilities = fusion_model.predict_proba(np.concatenate([val_audio, context_x[val_idx]], axis=1))
    classes = np.asarray(fusion_model.classes_)
    threshold, validation_coverage = select_confidence_threshold(labels[val_idx], val_probabilities, classes, args.target_accuracy)
    validation_metrics = evaluate_predictions(labels[val_idx], val_probabilities, classes, threshold, speakers[val_idx], args.seed)

    test_audio = audio_model.predict_proba(audio_x[test_idx])
    test_probabilities = fusion_model.predict_proba(np.concatenate([test_audio, context_x[test_idx]], axis=1))
    test_metrics = evaluate_predictions(labels[test_idx], test_probabilities, classes, threshold, speakers[test_idx], args.seed + 2)
    promoted = passes_promotion_gate(test_metrics, args.target_accuracy)
    now = datetime.now(timezone.utc)
    version = f"race-radio-{now.strftime('%Y%m%dT%H%M%SZ')}"
    metadata = {
        "model_version": version,
        "promoted": promoted,
        "target_accuracy": args.target_accuracy,
        "validation_accuracy": validation_metrics["balanced_accuracy"],
        "confidence_threshold": threshold,
        "prediction_coverage": test_metrics["prediction_coverage"],
        "encoder_model": args.encoder_model,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "labels": list(TRAINED_LABELS),
        "selected_classifier": selected_name,
        "candidate_scores": candidate_scores,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "split_sizes": {"train": len(train_idx), "validation": len(val_idx), "test": len(test_idx)},
        "speaker_counts": {"train": len(set(speakers[train_idx])), "validation": len(set(speakers[val_idx])), "test": len(set(speakers[test_idx]))},
        "created_at": now.isoformat(),
        "warnings": dataset.warnings,
        "audio_class_order": oof_classes.tolist(),
        "fusion_class_order": classes.tolist(),
    }

    candidate_dir = args.output_dir / "candidates" / version
    candidate_dir.mkdir(parents=True, exist_ok=False)
    artifact = {"audio_classifier": audio_model, "fusion_classifier": fusion_model, "metadata": metadata}
    joblib.dump(artifact, candidate_dir / "model.joblib")
    (candidate_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    if promoted:
        promoted_dir = args.output_dir / "promoted"
        promoted_dir.mkdir(parents=True, exist_ok=True)
        model_tmp = promoted_dir / "model.joblib.tmp"
        metadata_tmp = promoted_dir / "metadata.json.tmp"
        shutil.copyfile(candidate_dir / "model.joblib", model_tmp)
        shutil.copyfile(candidate_dir / "metadata.json", metadata_tmp)
        os.replace(model_tmp, promoted_dir / "model.joblib")
        os.replace(metadata_tmp, promoted_dir / "metadata.json")
        print(f"Promoted {version}: test balanced accuracy {test_metrics['balanced_accuracy']:.2%}")
    else:
        print(f"Candidate rejected: balanced accuracy {test_metrics['balanced_accuracy']:.2%}, macro-F1 {test_metrics['macro_f1']:.2%}")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train, evaluate, and conditionally promote the PitSense race-radio emotion classifier.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("./artifacts/emotion"))
    parser.add_argument("--cache-dir", type=Path, default=Path("./artifacts/emotion/cache"))
    parser.add_argument("--encoder-model", default="microsoft/wavlm-base-plus")
    parser.add_argument("--target-accuracy", type=float, default=0.99)
    parser.add_argument("--min-clips", type=int, default=1000)
    parser.add_argument("--min-speakers", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--transcribe-missing", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


if __name__ == "__main__":
    result = train(parse_args())
    raise SystemExit(0 if result["promoted"] else 2)
