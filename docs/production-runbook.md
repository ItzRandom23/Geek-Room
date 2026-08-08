# Production runbook

## Required services

- Next.js frontend deployed separately (for example Vercel).
- FastAPI API and one or more `python -m app.worker` processes.
- Managed PostgreSQL.
- Redis for RQ jobs.
- S3-compatible object storage for audio.

Set `ENVIRONMENT=production`, `AUTH_REQUIRED=true`, a rotated `JWT_SECRET`, a PostgreSQL `DATABASE_URL`, `REDIS_URL`, `STORAGE_BACKEND=s3`, `S3_BUCKET`, and the allowed frontend in `CORS_ORIGINS`. Keep `HF_TOKEN` in the platform secret store.

## Release checklist

1. Apply the image in staging and run `alembic upgrade head` through the API startup migration.
2. Check `/api/health` and `/api/readiness`.
3. Register two test teams and verify neither can open the other team’s session.
4. Upload WAV, MP3, M4A, and OGG samples; confirm duration and secure playback.
5. Run audio-only analysis, then a second run with real lap CSV data.
6. Verify job retry/cancel behavior and JSON/CSV/PDF exports.
7. Take a PostgreSQL backup and perform a restore test before production promotion.
8. Schedule `python -m app.retention` daily. The default retention is 30 days.

## Operations

Use structured platform logs and monitor failed jobs, queue depth, inference duration, empty transcripts, low-confidence events, database errors, and storage usage. Never log bearer tokens, full transcripts, or audio bytes. Rotate JWT and Hugging Face credentials through the platform secret manager.

## Deployment commands

```powershell
docker compose up --build
docker compose exec backend python -m app.retention
```

For split hosting, deploy `frontend` with `NEXT_PUBLIC_API_URL` pointing to the HTTPS API and deploy the backend image plus the worker image from the same commit. Do not expose the worker, PostgreSQL, Redis, or the object-storage credentials to the browser.
