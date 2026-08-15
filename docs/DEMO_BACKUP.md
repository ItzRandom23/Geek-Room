# Demo Backup and Recovery

## Internet unavailable

Use the locally seeded fixture. It contains the transcript, vocal-state events, timing, recommendations, and generated audio file. No external inference is needed for the judge path.

## Backend unavailable

Start it from `backend`:

```powershell
python -m app.seed_demo
python -m uvicorn app.main:app --reload --port 8000
```

Confirm `http://localhost:8000/api/health` returns `status: ok`.

## Database unavailable

The default local database is SQLite at `backend/pitsense.db`. From `backend`, rerun `python -m app.seed_demo`; migrations run automatically. Do not delete a shared production database as a reset step.

For a deliberate local demo reset, use the scoped command below. It deletes only the session marked `is_demo=true`, removes its fixture audio, and recreates it:

```powershell
python -m app.seed_demo --reset
```

## Authentication unavailable

Use `http://localhost:3000/sessions?demo=1`. Demo mode defaults to `AUTH_REQUIRED=false`; the fixture is intentionally available without registration.

## External model/API unavailable

Do not start a normal live analysis during judging. Use the explicit fixture and say: “The live inference path is real, but this run is using labelled local fixture evidence so the demo is deterministic.”

## Deployment unavailable

Run the two local services using the documented commands. Docker Compose is the production-shaped path, but Docker was not available in the verification environment.

## Live demo completely unavailable

Use the screenshots and the 2:30 script to narrate: problem → source-language radio → urgent timestamp → supplied lap context → deterministic recommendation → analytics. Do not present fixture metrics as production evidence.
