# Audio-emotion benchmark and promotion

PitSense keeps `superb/wav2vec2-base-superb-er` as its baseline until a candidate passes a signed, speaker-held-out race-radio benchmark. A Hugging Face model-card metric is not a production accuracy claim.

## CUDA benchmark environment

Create a CUDA-capable environment and install the optional candidate runtimes:

```powershell
cd backend
pip install -r requirements-benchmark.txt
$env:BENCHMARK_SIGNING_KEY = "store-this-in-your-secret-manager"
```

Pin every model to a Hub commit SHA. The benchmark refuses `main` or an unpinned candidate.

To produce reproducible, licensed CAMEO cross-domain evidence, materialize one configuration at a time. Keep the exported audio outside the application upload directory and retain the generated manifest with the run:

```powershell
python -m app.ml.prepare_cameo --config crema_d --split train --output-dir C:\secure-data\cameo-crema-d
```

The CAMEO dataset is licensed `CC BY-NC-SA 4.0`; each exported row also preserves the source-row license. Review its terms and each included corpus' terms before use.

```powershell
python -m app.ml.benchmark `
  --pilot-manifest C:\secure-data\race-radio-pilot.csv `
  --public-manifest C:\secure-data\cameo-mapped.csv `
  --candidate baseline-superb@<commit-sha> `
  --candidate meralion-ser-v1@<commit-sha> `
  --candidate emotion2vec-plus-large@<commit-sha> `
  --candidate sensevoice-small@<commit-sha> `
  --candidate speechbrain-iemocap@<commit-sha> `
  --output-dir .\artifacts\emotion\benchmark `
  --license-review-id LEGAL-123 `
  --security-review-id SEC-456 `
  --sign
```

The output contains JSON and Markdown scorecards, each calibrator artifact, urgent false-negative examples, confusion matrices, per-language results, latency/real-time factor, GPU information, and a promotion manifest only for candidates that clear every gate.

## Pilot manifest

Use UTF-8 CSV. Every entry must be a short, independently labeled radio interval. The source audio path must point to the extracted interval, not a shared long recording.

```csv
audio_path,label,speaker_id,recording_id,language,start_seconds,end_seconds,radio_condition,annotator_a,annotator_b,adjudicated_label
clips/run-001.wav,stressed,driver-01,run-001,en,42.0,46.0,engine+radio,annotator-a,annotator-b,stressed
```

PitSense requires at least 1,000 pilot clips from 10 speakers, with all five operational labels. A language is scored as qualified only after 100 adjudicated clips from 10 speakers. Public corpora must use the separate public-manifest format (`dataset`, `dataset_version`, and `license`); they are calibrated using the race-radio training split and reported only as cross-domain evidence. They never enter the pilot split, validation threshold, paired bootstrap, or promotion decision.

## Promotion

Copy the winning artifact and its signed `promotion-<candidate>.json` into `EMOTION_CALIBRATION_DIR`, then set `BENCHMARK_PROMOTION_MANIFEST` to that manifest and provide the same `BENCHMARK_SIGNING_KEY` at runtime. The backend verifies the HMAC, candidate ID/revision, and calibration SHA-256 before activation. An absent, modified, or unsigned manifest always leaves the baseline active.

The promotion gate requires a five-point macro-F1 improvement, a positive paired speaker-bootstrap lower bound, at least 70% coverage, no urgent-recall regression, and no qualified language regression above five points. License and security review remain required before deploying a signed result.
