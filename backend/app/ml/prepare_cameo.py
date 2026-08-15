"""Materialize an auditable CAMEO cross-domain manifest for PitSense.

This intentionally produces *public evidence* only. The benchmark runner
never permits this output to decide a production promotion.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .emotion import TRAINED_LABELS
from ..services.labels import normalize_label


LANGUAGE_CODES = {
    "arabic": "ar", "bengali": "bn", "chinese": "zh", "english": "en",
    "french": "fr", "german": "de", "italian": "it", "polish": "pl",
    "portuguese": "pt", "russian": "ru", "spanish": "es", "urdu": "ur",
}
FIELDNAMES = ["audio_path", "label", "speaker_id", "recording_id", "language", "dataset", "dataset_version", "license"]


def language_code(value: str) -> str:
    value = value.strip().lower()
    return LANGUAGE_CODES.get(value, value.split("-", 1)[0] or "und")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one licensed CAMEO configuration to a PitSense public benchmark manifest.")
    parser.add_argument("--config", required=True, help="CAMEO configuration/split name, for example crema_d.")
    parser.add_argument("--split", default="train")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, help="Optional bounded fixture export.")
    args = parser.parse_args()

    try:
        from datasets import load_dataset
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Install backend/requirements-benchmark.txt before preparing CAMEO.") from exc

    dataset = load_dataset("amu-cai/CAMEO", args.config, split=args.split)
    audio_dir = args.output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.output_dir / f"cameo-{args.config}-{args.split}.csv"
    rows = 0
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for index, row in enumerate(dataset):
            label = normalize_label(str(row.get("emotion", "")))
            if label not in TRAINED_LABELS:
                continue
            audio = row.get("audio") or {}
            samples, sample_rate = audio.get("array"), audio.get("sampling_rate")
            if samples is None or not sample_rate:
                continue
            recording_id = str(row.get("file_id") or f"{args.config}-{index}")
            filename = f"{recording_id}.flac"
            destination = audio_dir / filename
            sf.write(destination, samples, int(sample_rate))
            writer.writerow({
                "audio_path": str(destination.relative_to(manifest.parent)),
                "label": label,
                "speaker_id": str(row.get("speaker_id") or recording_id),
                "recording_id": recording_id,
                "language": language_code(str(row.get("language") or "und")),
                "dataset": str(row.get("dataset") or "CAMEO"),
                "dataset_version": f"CAMEO/{args.config}/{args.split}",
                "license": str(row.get("license") or "cc-by-nc-sa-4.0"),
            })
            rows += 1
            if args.limit and rows >= args.limit:
                break
    print(f"Wrote {rows} CAMEO rows to {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
