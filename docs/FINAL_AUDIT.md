# PitSense AI Final Repository Audit

Audit date: 2026-08-15. Scope: full repository inventory, automated checks, live local services, bounded local concurrency smoke, browser route sweep, three judge-demo runs, responsive inspection, and targeted fixes.

## Source inventory

The inventory below covers every application, test, configuration, migration, deployment, script, asset, and judge-facing documentation file in the checkout. Generated Next guidance files were inspected, identified as generated, removed, and added to `.gitignore`; no source file was skipped. Backend routes were enumerated directly from `app.routes`, not inferred from the README.

| File | Purpose / consumers | Status | Action |
|---|---|---|---|
| `frontend/app/page.tsx` | Landing page; links to dashboard/demo | Working | Keep |
| `frontend/app/layout.tsx` | App shell, navigation, metadata | Working; removed scroll warning | Fix/keep |
| `frontend/app/globals.css` | Shared visual system and responsive styles | Working | Keep |
| `frontend/app/login/page.tsx` | Register/login UI; calls auth API | Working; remember-me now uses session storage correctly | Fix/keep |
| `frontend/app/onboarding/page.tsx` | Three-step post-registration setup | Working; fixed literal JSX text | Fix/keep |
| `frontend/app/sessions/page.tsx` | Dashboard, create/delete sessions, demo entry | Working; fixed hook ordering | Fix/keep |
| `frontend/app/sessions/[id]/page.tsx` | Upload, laps, analysis lifecycle, exports | Working for demo and tested API paths; media-play interruption handled | Fix/keep |
| `frontend/app/analytics/page.tsx` | Historical metrics, filtering, CSV export | Working; fixed hook ordering and enabled export | Fix/keep |
| `frontend/app/methodology/page.tsx` | Judge-facing pipeline explanation | Working | Keep |
| `frontend/app/settings/page.tsx` | Profile, password, preferences, sign-out | Working; replaced fake local-only actions | Fix/keep |
| `frontend/components/ui.tsx` | Buttons, badges, errors, status primitives | Working | Keep |
| `frontend/components/processing-panel.tsx` | Job progress/error/cancel UI | Working and unit-tested | Keep |
| `frontend/components/results-dashboard.tsx` | Transcript, events, chart, recommendations, exports | Working and unit-tested | Keep |
| `frontend/components/interactive-background.tsx` | Decorative background only | Working | Keep |
| `frontend/lib/api.ts` | Typed client, auth token, polling, error mapping | Working; added profile/password calls and session storage | Fix/keep |
| `frontend/lib/validation.ts` | Audio/lap client validation | Working and unit-tested | Keep |
| `frontend/test/validation.test.ts` | Validation tests | Passing | Keep |
| `frontend/test/processing-panel.test.tsx` | Processing states | Passing | Keep |
| `frontend/test/results-dashboard.test.tsx` | Report rendering | Passing | Keep |
| `frontend/package.json` | Next/Vitest scripts and dependencies | Working | Keep |
| `frontend/package-lock.json` | Reproducible frontend dependency graph | Installed and used | Keep |
| `frontend/next.config.mjs` | Next configuration | Working; disables generated guidance files and allows localhost/127.0.0.1 dev assets | Fix/keep |
| `frontend/tailwind.config.ts` | Tailwind theme | Working | Keep |
| `frontend/postcss.config.mjs` | CSS build | Working | Keep |
| `frontend/tsconfig.json` | TypeScript configuration | Working | Keep |
| `frontend/next-env.d.ts` | Next types | Working | Keep |
| `frontend/Dockerfile` | Production-shaped frontend image | Not run; Docker unavailable | Keep/verify later |
| `frontend/public/demo-laps.csv` | User-facing real-lap example download | Working | Keep |
| `frontend/public/og.png` | Social preview asset | Present | Keep |
| `backend/app/main.py` | FastAPI routes, auth/session access, exports, error middleware | Working; added report summaries and account endpoints | Fix/keep |
| `backend/app/auth.py` | JWT, scrypt password hashing, org access | Working and tested | Keep |
| `backend/app/config.py` | Environment settings and safety defaults | Working | Keep |
| `backend/app/database.py` | SQLAlchemy engine/session and Alembic entry | Working | Keep |
| `backend/app/models.py` | Relational schema models/constraints | Working and migrated | Keep |
| `backend/app/schemas.py` | Pydantic request contracts | Working; added settings schemas | Fix/keep |
| `backend/app/jobs.py` | Analysis worker lifecycle, retry/failure mapping | Working and tested | Keep |
| `backend/app/worker.py` | Redis/RQ worker entry point | Production path; not run without Redis | Keep |
| `backend/app/storage.py` | Local/S3-compatible storage abstraction | Working by inspection/tests | Keep |
| `backend/app/retention.py` | Retention cleanup command | Documented operational path | Keep |
| `backend/app/seed_demo.py` | Explicit offline fixture creation/reset | Working; fixed idempotency, language metadata, and scoped `--reset` | Fix/keep |
| `backend/app/services/ai.py` | STT/text/audio provider adapters and provenance | Real inference path; external weights required | Keep |
| `backend/app/services/analysis.py` | Fusion, correlation, recommendation domain logic | Working and unit-tested | Keep |
| `backend/app/services/audio.py` | Decode, validate, store, duration | Working and API-tested | Keep |
| `backend/app/services/audio_candidates.py` | Candidate analyzer adapters | Promotion path; not judge-critical | Keep |
| `backend/app/services/csv_import.py` | Lap CSV parse/validation | Working and API-tested | Keep |
| `backend/app/services/labels.py` | Model-label normalization | Working and ML-tested | Keep |
| `backend/app/services/pdf_report.py` | Styled PDF + dependency-free fallback | Fixed and tested | Fix/keep |
| `backend/app/services/rate_limit.py` | In-process rate limiter | Working and tested | Keep |
| `backend/app/ml/emotion.py` | Feature extraction, calibration, emotion model path | Real ML path; external model dependency | Keep |
| `backend/app/ml/train.py` | Speaker-held-out training/promotion workflow | Active documented capability | Keep |
| `backend/app/ml/benchmark.py` | Candidate benchmark/promotion workflow | Active documented capability | Keep |
| `backend/app/ml/promotion.py` | Signed promotion gates | Active documented capability | Keep |
| `backend/app/ml/prepare_cameo.py` | Dataset preparation utility | Active utility | Keep |
| `backend/migrations/env.py` | Alembic runtime | Working | Keep |
| `backend/migrations/versions/0001_production_foundation.py` | Base schema | Applied | Keep |
| `backend/migrations/versions/0002_active_clip.py` | Active clip migration | Applied | Keep |
| `backend/migrations/versions/0003_audit_events.py` | Audit events migration | Applied | Keep |
| `backend/migrations/versions/0004_job_processing_time.py` | Job timing migration | Applied | Keep |
| `backend/migrations/versions/c32d35590951_add_onboarding_completed_to_user.py` | Onboarding field migration | Applied | Keep |
| `backend/tests/test_api.py` | Health, upload, CSV, locking, persistence API tests | Passing | Keep |
| `backend/tests/test_e2e.py` | Upload → laps → analysis → results tests | Passing | Keep |
| `backend/tests/test_production.py` | Export/cancel/org isolation tests | Passing; PDF header assertion strengthened | Fix/keep |
| `backend/tests/test_settings.py` | New profile/password auth tests | Passing | Add/keep |
| `backend/tests/conftest.py` | Disposable database/upload isolation for pytest | Working; prevents test rows appearing in the local dashboard | Add/keep |
| `backend/tests/test_domain.py` | Correlation/recommendation domain tests | Passing | Keep |
| `backend/tests/test_ml_pipeline.py` | Label/fusion/provider tests | Passing | Keep |
| `backend/tests/test_benchmark.py` | Benchmark/promotion tests | Passing | Keep |
| `backend/tests/test_rate_limit.py` | Rate-limit tests | Passing | Keep |
| `backend/requirements.txt` | Backend runtime pins | Python 3.11 target; full install not compatible with current 3.14 environment | Keep/document |
| `backend/requirements-benchmark.txt` | Optional benchmark dependencies | Not needed for demo | Keep |
| `backend/Dockerfile` | Backend image | Not run; Docker unavailable | Keep/verify later |
| `backend/alembic.ini` | Migration config | Working | Keep |
| `backend/pytest.ini` | Test discovery | Working | Keep |
| `docker-compose.yml` | PostgreSQL/Redis/API/worker/frontend stack | Not run; Docker unavailable | Keep/verify later |
| `start-pitsense.bat` | Windows local launcher | Source-verified; not launched as a batch file | Keep |
| `README.md` | Setup, architecture, demo, claims | Updated with judge docs and Python target | Fix/keep |
| `sample-data/demo-laps.csv` | Sample timing input | Present | Keep |
| `docs/*.md` | Existing architecture/model/runbook references | Read and retained | Keep |
| `HACKATHON_FINAL_DEMO_PROMPT_ADDENDUM.md` | User-provided audit constraints | Read and followed | Keep |

Additional files inspected and classified:

| File(s) | Purpose / consumers | Status | Action |
|---|---|---|---|
| `backend/app/__init__.py`, `backend/app/services/__init__.py`, `backend/app/ml/__init__.py` | Python package markers | Working | Keep |
| `backend/index.py` | Alternate ASGI import entry | Working | Keep |
| `backend/migrations/script.py.mako` | Alembic migration template | Working | Keep |
| `backend/requirements-benchmark.txt` | Optional benchmark/training dependencies | Documented optional path | Keep |
| `backend/.python-version` | Pinned local Python runtime hint | Aligned to the Dockerfile and README at Python 3.11 | Fix/keep |
| `frontend/next-env.d.ts`, `frontend/public/og.png` | Next type declarations and social-preview asset | Working/present | Keep |
| `frontend/postcss.config.mjs`, `frontend/tailwind.config.ts` | CSS processing and design tokens | Working | Keep |
| `docs/ai-pipeline.md`, `docs/architecture.md`, `docs/model-benchmark.md`, `docs/model-training.md`, `docs/production-runbook.md` | Architecture, model, and operations references consumed by the team | Consistent with code, with prototype boundaries stated | Keep |
| `docs/demo-script.md`, `docs/judging-pitch.md` | Earlier presentation references | Retained legacy references; not the canonical judge script | Keep/document |
| `docs/DEMO_SCRIPT.md`, `docs/DEMO_BACKUP.md`, `docs/JUDGES_QA.md`, `docs/PRESENTATION_PLAN.md`, `docs/QA_MATRIX.md` | Canonical judge-facing completion artifacts | Updated and verified | Keep |
| `sample-data/demo-laps.csv`, `frontend/public/demo-laps.csv` | Real timing-input examples | Working | Keep |
| `README.md`, `LICENSE`, `.env.example`, `backend/.env.example`, `frontend/.env.example`, `.gitignore`, `start-pitsense.bat`, `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` | Setup, environment, license, launcher, deployment, and ignore rules | Source-verified; local launcher verified, containers blocked by missing Docker | Keep/document |

Generated `frontend/AGENTS.md` and `frontend/CLAUDE.md` were created by Next.js during development, verified as generated guidance, removed from the working tree, and added to `.gitignore`.

## Feature audit

Feature: Landing page  
Status: WORKING  
Frontend: `frontend/app/page.tsx`  
Backend: Not required for landing  
Database: Not required  
External dependency: Google Fonts may be unavailable; layout remains usable  
Tested: Browser DOM, screenshot, route sweep  
Demo safe: Yes  
Notes: Impact numbers are explicitly labelled demo data.

Feature: Demo access and seeded session  
Status: DEMO  
Frontend: `/sessions?demo=1` redirects to the seeded `is_demo` session  
Backend: `seed_demo.py`, session/report endpoints  
Database: SQLite by default; migrations applied  
External dependency: None for fixture path  
Tested: Seeded twice; three complete browser runs  
Demo safe: Yes  
Notes: Fixture data is visibly labelled and normal uploads do not substitute it.

Feature: Authentication, onboarding, profile, password  
Status: WORKING  
Frontend: login/onboarding/settings routes  
Backend: JWT, scrypt, `/api/me`, `/api/me/password`, onboarding endpoint  
Database: users, organizations, memberships, audit events  
External dependency: None  
Tested: Register, onboarding, invalid login, profile save, logout, re-login; password endpoint automated  
Demo safe: Yes  
Notes: Demo mode does not require auth; production should set `AUTH_REQUIRED=true` and a real JWT secret.

Feature: Normal audio analysis  
Status: PARTIAL  
Frontend: upload, mode selection, progress, cancellation, retry UI  
Backend: real provider adapters and worker lifecycle  
Database: clips, transcripts, emotion results, jobs, reports  
External dependency: Hugging Face model weights/token/network; optional Redis  
Tested: API path with deterministic fake providers; live model inference not run here  
Demo safe: Only with fixture fallback  
Notes: Do not claim a live model result unless weights are available and the job completes.

Feature: Lap correlation and recommendations  
Status: WORKING  
Frontend: manual/CSV timing UI, chart, event selection, recommendations  
Backend: maximum-overlap matching and deterministic rules  
Database: constrained lap rows and schema-versioned report  
External dependency: None after timing input  
Tested: Demo browser flow and domain/API tests  
Demo safe: Yes for supplied fixture timing  
Notes: Associations are not proof of causation.

Feature: History and analytics  
Status: WORKING  
Frontend: dashboard, analytics filters, summary KPIs, client CSV export  
Backend: session list includes report summaries for analytics  
Database: persisted sessions/jobs/results  
External dependency: None  
Tested: Browser route and KPI checks; build/tests  
Demo safe: Yes  
Notes: Empty states are present; automated tests now use a disposable database, so the local judge database remains limited to the explicit fixture after verification.

Feature: Report exports  
Status: WORKING  
Frontend: JSON/CSV/PDF actions  
Backend: JSON/CSV endpoints and WeasyPrint/fallback PDF  
Database: report rebuilt from persisted evidence when needed  
External dependency: WeasyPrint optional; fallback removes this demo dependency  
Tested: Backend endpoint tests and `%PDF-` assertion; browser click had no console error, but the in-app browser did not expose a download event  
Demo safe: Yes  
Notes: Show the on-screen report if browser download UX is unavailable.

Feature: Settings preferences/session  
Status: WORKING  
Frontend: profile/security/preferences/session tabs  
Backend: profile/password endpoints  
Database: user fields/password; preferences are browser-local by design  
External dependency: None  
Tested: Authenticated profile save and sign-out browser flow  
Demo safe: Yes  
Notes: No fake delete-account control remains.

## Production functionality

- Real FastAPI routes, validation, relational models, migrations, organization access checks, password hashing, JWT auth, job lifecycle, upload handling, report generation, and exports exist.
- The frontend production build succeeds and the core demo pages render without console errors.
- Postgres/Redis/S3-shaped configuration exists but was not exercised in this environment.
- Local Next development is reliable from both `localhost` and `127.0.0.1`; the Next 16 `allowedDevOrigins` setting prevents a blank dashboard caused by blocked dev assets.
- Evidence selection and clipboard actions no longer create unhandled promise errors when media or clipboard access is interrupted.
- Automated tests are isolated from the judge fixture through `backend/tests/conftest.py`.

## Demo functionality

- The judge path uses a local explicit fixture: synthetic audio, hand-crafted transcript, labelled emotion windows, real fixture lap timing, and a complete report.
- Analytics and landing-page impact metrics are demo/sample content and are labelled in the UI.
- The PDF fallback is used only when the optional HTML-to-PDF runtime is absent.

## Final acceptance evidence

- Frontend route sweep: `/`, `/login`, `/onboarding`, `/sessions`, `/sessions/14`, `/analytics`, `/methodology`, and protected `/settings` were visited; `/settings` redirected to `/login` while logged out.
- Browser navigation: Dashboard, Analytics, Methodology, Settings, and Team access links were clicked from the primary navigation and resolved without page errors.
- Auth flow: registration, three-step onboarding, invalid credentials, authenticated settings profile/preferences, logout, re-login, and authenticated refresh passed.
- Responsive checks: default desktop, 768x900 tablet, and 390x844 mobile passed with no horizontal overflow.
- Three fresh demo runs completed in 10.51s, 10.47s, and 10.50s. Each reached the seeded report, selected urgent evidence, opened Analytics, opened Methodology, and recorded zero error-level browser logs.
- Bounded local concurrency smoke passed on backend port 8001: 50 concurrent health requests and 20 concurrent demo-report requests all returned HTTP 200 in 0.208 seconds, with request IDs and expected report/export content types observed. This is a responsiveness smoke check, not production-scale load validation.

## Known limitations

- Live Hugging Face inference was not run because model weights/network are external and the reliable judge path is fixture-backed.
- Docker Compose was not run because `docker --version` returned “The term 'docker' is not recognized”.
- The pinned `backend/requirements.txt` full install was not possible under the available Python 3.14: pandas 2.2.3 fell back to a source build and failed because Visual Studio `vswhere.exe` was unavailable. Python 3.11 is the documented target; compatible missing packages were installed to the existing environment for verification.
- `npm audit --omit=dev` is clean after the non-force audit fix. The full audit still reports 5 development-tool vulnerabilities (3 moderate, 1 high, 1 critical) in the Vitest/Vite/esbuild chain; `npm audit fix --force` would move Vitest outside the stated dependency range, so it was not applied blindly.
- The in-process rate limiter and local thread queue are suitable for development, not multi-instance production.
- Preferences are browser-local and there is no self-service account deletion endpoint.
- The analytics CSV download was validated by code/build and by clicking the enabled browser action; the in-app browser did not surface a download event for the client-side action.
- The old `npm run lint` alias was repaired for Next 16 and now runs the strict TypeScript check (`tsc --noEmit`); a separate ESLint configuration is not present in this prototype.

## Technical debt

- Add pagination and server-side analytics aggregation for large organizations.
- Add managed Postgres/Redis/S3 deployment rehearsal, observability, load tests, and signed URL expiry tests.
- Add adjudicated speaker-held-out model evaluation and model artifact release automation.
- Add account deletion/organization administration only when product requirements justify it.

## Recommended presentation claims

- “PitSense preserves source-language radio as timestamped evidence and links high-risk events to real supplied timing.”
- “The analysis pipeline runs behind the API; the frontend never calls the models directly.”
- “Uncertain predictions remain uncertain, and recommendations are deterministic and human-reviewable.”
- “The demo is deterministic and offline-safe because the fixture is explicit and visibly labelled.”
- “The architecture has a clear path to Postgres, Redis/RQ, and S3-compatible storage.”

## Claims to avoid

- Do not claim live model inference was demonstrated in this verification run.
- Do not call demo metrics verified field evidence.
- Do not claim causation, diagnosis, medical/psychological assessment, or formal safety certification.
- Do not claim enterprise-grade security, 10,000-user load validation, Docker deployment validation, or production SLA.
- Do not claim payment processing, real-time streaming, or account deletion are implemented.
