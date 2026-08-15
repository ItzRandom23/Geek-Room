# Seven-Minute Presentation Plan

## 0:00–0:45 — Problem

Tell a relatable pit-wall scenario: the driver’s voice changes before the data review catches up. Explain that radio, emotion cues, and lap timing are disconnected and manual review is slow.

## 0:45–1:15 — Solution

“PitSense turns driver radio into timestamped, inspectable race-engineering evidence: transcript, vocal state, real lap context, and the next human action.” Clarify that the product supports review; it does not diagnose the driver or claim causation.

## 1:15–3:30 — Live demo

Use [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md): landing → explicit fixture → playable source-language radio → urgent evidence → lap context → recommendation → analytics. Keep the demo under 2:30 and use the final 60 seconds for technical context.

## 3:30–4:20 — Technical architecture

Show the real architecture: Next.js/TypeScript UI, FastAPI validation/auth, SQLAlchemy/Alembic persistence, local or Redis/RQ job queue, backend-only model adapters, fusion, maximum-overlap lap correlation, deterministic recommendations, and schema-versioned exports. Emphasize provenance and uncertainty gating.

## 4:20–5:05 — Social impact

Discuss review time, faster safety-event review, multilingual evidence access, and human confirmation rate. Label all current landing metrics as demo data; propose verified measures for a pilot.

## 5:05–5:45 — Business model

Target race/performance engineering teams. The buyer is a technical director/team principal; monetization is seats, organization collaboration, governed model updates, private deployment, and enterprise/on-prem support. Payment is not implemented in the prototype.

## 5:45–6:25 — Scale and future

Describe PostgreSQL + S3-compatible audio + Redis/RQ worker scaling, signed URLs, model artifact caching, load tests, speaker-held-out validation, pagination, and observability. State clearly what was not load-tested.

## 6:25–6:50 — Close

Return to the original problem: PitSense helps an engineer move from “something sounded wrong” to “here is the timestamp, the evidence, the real lap context, and the next review action.” Leave about 10 seconds of buffer.
