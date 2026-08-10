"""Signed benchmark promotion manifests for external audio-emotion candidates."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any


PROMOTION_SCHEMA_VERSION = 1
REQUIRED_PROMOTION_CHECKS = {
    "macro_f1_uplift_at_least_5pp",
    "paired_bootstrap_lower_bound_positive",
    "coverage_at_least_70pct",
    "urgent_recall_non_regression",
    "qualified_languages_no_more_than_5pp_regression",
    "license_review_approved",
    "security_review_approved",
}


def canonical_manifest(manifest: dict[str, Any]) -> bytes:
    payload = {key: value for key, value in manifest.items() if key != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_manifest(manifest: dict[str, Any], signing_key: str) -> dict[str, Any]:
    if not signing_key:
        raise ValueError("A non-empty BENCHMARK_SIGNING_KEY is required to sign a promotion manifest.")
    signed = dict(manifest)
    signed["signature"] = hmac.new(signing_key.encode("utf-8"), canonical_manifest(signed), hashlib.sha256).hexdigest()
    return signed


def verify_manifest(manifest: dict[str, Any], signing_key: str | None) -> bool:
    if not signing_key or manifest.get("schema_version") != PROMOTION_SCHEMA_VERSION:
        return False
    signature = manifest.get("signature")
    if not isinstance(signature, str):
        return False
    expected = hmac.new(signing_key.encode("utf-8"), canonical_manifest(manifest), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_calibration_path(calibration_root: Path, relative_path: str) -> Path:
    root = calibration_root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Promotion manifest calibration artifact is outside EMOTION_CALIBRATION_DIR.")
    return candidate


def load_signed_promotion_manifest(path: Path, signing_key: str | None, calibration_root: Path) -> dict[str, Any] | None:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict) or not verify_manifest(manifest, signing_key):
        return None
    required = {"candidate_id", "model_id", "model_revision", "calibration_artifact", "calibration_sha256", "benchmark", "gates", "reviews"}
    reviews = manifest.get("reviews") or {}
    gates = manifest.get("gates") or {}
    checks = gates.get("checks") or {}
    if (
        required - set(manifest)
        or not gates.get("passed")
        or not all(checks.get(name) is True for name in REQUIRED_PROMOTION_CHECKS)
        or not reviews.get("license_approved")
        or not reviews.get("security_approved")
        or not reviews.get("license_review_id")
        or not reviews.get("security_review_id")
    ):
        return None
    try:
        artifact = safe_calibration_path(calibration_root, str(manifest["calibration_artifact"]))
        if not artifact.is_file() or artifact_sha256(artifact) != manifest["calibration_sha256"]:
            return None
    except (OSError, ValueError):
        return None
    return manifest
