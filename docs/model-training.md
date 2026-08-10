# Race-radio emotion training

PitSense only activates a custom emotion model after it reaches the configured release gate on a speaker-held-out test set. The default target is 99% balanced accuracy and 99% macro-F1. A rejected candidate is retained for review but never replaces the active model.

## Manifest

Use UTF-8 CSV with one row per independently labeled clip:

```csv
audio_path,label,speaker_id,recording_id,transcript
clips/driver-01-001.wav,calm,driver-01,run-001,"Balance feels good"
clips/driver-02-014.wav,stressed,driver-02,run-014,"Rear is moving under braking"
```

Required columns are `audio_path`, `label`, `speaker_id`, and `recording_id`. `transcript` is optional; missing transcripts are generated during feature extraction. Supported training labels are `calm`, `stressed`, `tired`, `frustrated`, and `urgent`. `uncertain` is reserved for predictions below the promoted confidence threshold.

Every source recording and speaker must have a unique stable ID. The validator rejects duplicate recordings, missing audio, unsupported labels, fewer than 1,000 clips, or fewer than 10 speakers. It warns about substantial class imbalance.

## Train and promote

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.ml.train --manifest C:\path\to\manifest.csv
```

Feature extraction is cached under `artifacts/emotion/cache`. Candidate reports are written to `artifacts/emotion/candidates/<version>`. Only a candidate that passes both release metrics is atomically copied to `artifacts/emotion/promoted`.

The report includes candidate cross-validation scores, speaker counts, split sizes, confusion matrix, per-class recall, selective accuracy, prediction coverage, and a speaker-bootstrap 95% accuracy interval. A rejected command exits with code `2` so automated training jobs can stop deployment.

Training and uploaded-audio inference are CPU compatible, but initial WavLM and transcript feature extraction can take a long time. Keep the generated artifact directory out of source control and back up promoted artifacts separately.

