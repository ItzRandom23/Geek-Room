# Judges’ Technical Q&A

## 1. What problem are you solving?

Race engineers hear driver radio and inspect telemetry in separate tools. PitSense preserves the radio as timestamped evidence, surfaces vocal-state signals, and associates those signals with supplied lap timing so the team can review the next action faster.

## 2. Why this problem?

Driver radio is a high-value real-time signal, but a short, noisy session creates too much material for manual review. The prototype focuses on a concrete engineering workflow with safety and performance review value.

## 3. Who is the target user?

Race engineers and performance engineers are the primary users. A technical director or team principal is the likely buyer and consumer of aggregate reporting.

## 4. What is technically difficult?

The difficult part is the evidence chain: multilingual transcription, overlapping audio windows, confidence calibration, normalized labels, maximum-overlap lap matching, deterministic recommendations, and keeping raw provenance inspectable.

## 5. Explain the architecture.

Next.js calls FastAPI REST endpoints. FastAPI validates input, enforces organization access, persists sessions/audio/laps/jobs in SQLAlchemy, and enqueues analysis locally or through Redis/RQ. The worker runs STT/audio/text providers, fusion, lap correlation, and deterministic rules, then stores a schema-versioned report.

## 6. Why this stack?

Next.js/TypeScript gives a fast judge-facing UI with typed API helpers. FastAPI/Python matches the ML/audio ecosystem. SQLAlchemy/Alembic keeps persistence explicit, and Redis/RQ is an optional production queue without making the local demo depend on Redis.

## 7. What happens with 10,000 users?

The intended path is PostgreSQL for transactional data, S3-compatible storage for audio, Redis/RQ workers for inference, and horizontally scaled frontend/API processes. That scale path is represented in Docker Compose and the architecture docs but has not been load-tested in this hackathon checkout.

## 8. How is data stored?

Local development defaults to SQLite and local uploads. Production configuration points to PostgreSQL and S3-compatible storage. Sessions, clips, transcript segments, emotion results, laps, insights, jobs, organizations, memberships, and audit events have relational models and migrations.

## 9. How is authentication handled?

Registration creates a user, organization, and membership. Passwords use `hashlib.scrypt` with a random salt; sessions use JWT bearer tokens. Organization membership is checked server-side when authentication is enabled. Demo access intentionally works without registration when `AUTH_REQUIRED=false`.

## 10. Which APIs/services are used?

The normal analysis path uses Hugging Face model adapters for Whisper/STT, audio emotion, and optional English text emotion. No external LLM is called. The demo fixture uses local seeded evidence and does not claim live model inference.

## 11. What happens when an external service fails?

Jobs store a user-safe error code/message and retryability. The UI shows a processing failure with retry/cancel behavior. The judge path can continue with the explicit fixture if model downloads or network inference are unavailable.

## 12. What security measures exist?

Secrets are environment-configured, auth uses scrypt/JWT, organization access is enforced server-side, uploads use extension/MIME/magic-byte and size/duration validation, paths are resolved safely, rate limiting protects login, and request IDs/errors are sanitized. This is a security baseline, not an enterprise certification.

## 13. How is this different from alternatives?

Typical workflows search radio manually or view telemetry separately. PitSense connects the original-language evidence, vocal-state signal, lap overlap, and rule-generated action in one review surface.

## 14. What is the competitive advantage?

Inspectable provenance and conservative claims: ambiguous predictions become `uncertain`, timing comes from real supplied laps, and recommendations state association rather than causation.

## 15. What social impact can this create?

It can reduce repetitive review time, help teams notice safety-relevant radio sooner, and make driver feedback more accessible across languages. The landing-page metrics are visibly labelled demo data, not verified impact evidence.

## 16. How will impact be measured?

Measure review minutes per session, time-to-flag a safety event, percentage of flagged events confirmed by a human engineer, false-alert rate, and model quality on speaker-held-out adjudicated data.

## 17. What is the business model?

Free individual usage, paid Pro seats for serious teams, Team organization plans, and Enterprise/on-prem or air-gapped deployments are the documented direction. No payment processing is implemented.

## 18. Who pays?

The likely buyer is a technical director or team principal; the champion is the race/performance engineer who benefits from faster review.

## 19. How would the architecture scale?

Separate the API, queue, worker, database, and object storage; add indexed organization/session queries, bounded pagination, signed audio URLs, worker concurrency limits, observability, and model artifact caching.

## 20. What would you build with another month?

Speaker-held-out evaluation with team-adjudicated data, load testing, job observability, pagination, stronger account lifecycle controls, and a deployment rehearsal with managed PostgreSQL/Redis/S3.

## 21. Which parts are prototype-only?

The seeded demo fixture, local SQLite/local audio defaults, browser-local preference storage, and the optional PDF fallback are prototype-friendly paths. The live ML path is real code but depends on external model weights and has not been exercised in this environment.

## 22. What functionality is mocked?

Only the explicit demo session’s transcript, emotion windows, laps, and report are fixture data. Normal uploads do not silently substitute fixture output.

## 23. What did the team implement?

The repository contains the frontend workflow, FastAPI API, relational models/migrations, auth, upload validation, async analysis job lifecycle, ML adapters, evidence fusion/correlation/rules, exports, demo seed, tests, and judge documentation.

## 24. What was technically hardest?

Preserving an auditable link from sliding-window model output to a source-language transcript and real lap interval, while handling uncertainty and external-model failure without misleading the engineer.

## 25. What trade-offs were made?

The demo prioritizes a deterministic, instant fixture over waiting for multi-gigabyte model downloads. Production infrastructure is represented and configurable, but Docker/load testing/live model execution were not claimed as verified on this machine.
