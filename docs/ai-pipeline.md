# AI pipeline

1. The API validates extension, MIME, file signatures, size, duration, and server-generated storage names. Production audio is stored in S3-compatible object storage and served through short-lived signed URLs.
2. The speech adapter calls multilingual Whisper through `automatic-speech-recognition` with `return_timestamps=true`; Whisper detects the spoken language automatically. The optional text-emotion model is treated as an English-focused secondary signal.
3. The audio-emotion adapter loads audio at 16 kHz and evaluates overlapping windows. Raw labels and scores are stored.
4. Labels are mapped to `calm`, `stressed`, `tired`, `frustrated`, `urgent`, or `uncertain`.
5. Optional text emotion contributes a small score; urgency keywords contribute a small bounded signal. The audio model remains primary.
6. If the user selected audio-only, no lap comparison is performed. If the user supplied real lap timing, high-stress events are matched only to a lap whose timestamp window contains the event; unmatched events remain unmatched. That lap and the next lap are compared with the session median.
7. Rules generate recommendations, with an explicit “association, not proof of causation” explanation.

The model IDs are environment variables so the adapters can be changed without rewriting business logic. Analysis runs in a Redis/RQ worker and the API reports queued/running/failed/completed states. A model download failure becomes a retryable job error; it is not replaced by a fabricated normal-user result. Raw outputs, labels, confidence, language, model IDs, processing version, and timestamps are retained for provenance.
