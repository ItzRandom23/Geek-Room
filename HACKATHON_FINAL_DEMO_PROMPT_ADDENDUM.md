# Mandatory Code Audit, Refactoring, Testing & Production-Readiness Addendum

Apply this addendum to the hackathon completion prompt. These requirements are mandatory and take priority over visual polish or new feature work.

## A. Inspect the Entire Codebase Before Editing

Before changing code, inspect every relevant file in the repository, not only the obvious frontend pages. Include:

- every frontend route, layout, component, hook, utility, style, asset, and test
- every backend route, schema, model, service, worker, migration, configuration file, and test
- package manifests, lockfiles, Docker/deployment files, scripts, environment-variable usage, and documentation
- imports and exports, route registration, API calls, database queries, authentication/authorization, error handling, and external-service integrations

Create a source inventory with the file path, purpose, callers/consumers, status, and action: **keep**, **fix**, **refactor**, **replace**, or **remove**.

Do not claim that the codebase was inspected if files were skipped. If a file cannot be inspected or executed, record the exact reason in `docs/FINAL_AUDIT.md`.

## B. Self-Critique Every Important Implementation

For every important route, feature, component, API endpoint, and service, ask and answer these questions before marking it complete:

1. Is this code actually reachable from the user journey?
2. Who calls it, what data does it receive, and what does it return?
3. What happens with empty, malformed, duplicate, slow, unauthorized, or failed input?
4. Can it produce a blank screen, crash, stale data, race condition, security issue, or misleading result?
5. Is the loading, success, empty, failure, retry, and cancellation behavior correct?
6. Does it work after refresh, logout/login, navigation away and back, and a second attempt?
7. Is the implementation consistent with the rest of the architecture and data model?
8. Is this the simplest reliable implementation, or is there unnecessary complexity?
9. Is it covered by an appropriate automated or manual test?
10. Would a judge understand what happened and what to do next?

Record meaningful findings and decisions in `docs/FINAL_AUDIT.md`. Do not perform a superficial search-and-replace refactor.

## C. Remove Dead, Useless, and Non-Working Code

Search the entire repository and the rendered UI for unused or suspicious code, including:

- unreachable routes and components
- unused imports, variables, functions, types, schemas, models, services, hooks, styles, and assets
- duplicate implementations and obsolete compatibility code
- abandoned experiments, debug code, temporary logs, test panels, commented-out blocks, and development-only banners
- fake buttons, placeholder handlers, empty callbacks, dead links, orphaned API endpoints, and unused dependencies
- TODO/FIXME markers, lorem ipsum, dummy/test data in the judging path, broken images, `undefined`, `null`, `NaN`, and unhandled promises

Before removing anything, verify that it is not used through dynamic imports, route conventions, configuration, migrations, scripts, tests, or deployment files. Remove only code proven unnecessary, and run the full test suite after cleanup. Do not remove a feature merely because it is not on the main demo path if it is an active, documented product capability.

## D. Mandatory Runtime Verification — Do It Yourself

Static inspection is not sufficient. Start the actual application and test it yourself using the available local runtime/browser tools. Do not rely only on screenshots, source review, or generated tests.

First determine the exact start commands, ports, required environment variables, seed/reset commands, and service dependencies. Then:

1. Start all required services from a clean or documented state.
2. Open the real running website.
3. Enumerate every registered and linked route from the router and navigation.
4. Visit every route directly and through normal navigation.
5. Click every visible navigation item and every important visible button.
6. Submit every important form with valid, invalid, empty, duplicate, and boundary inputs.
7. Verify every API call's loading, success, empty, timeout, unauthorized, and failure states.
8. Test protected routes while logged out and after logout.
9. Test demo access, refresh, repeated submissions, retry, and a second complete session.
10. Check browser console errors, failed network requests, server logs, hydration errors, unhandled exceptions, and warnings that affect behavior.
11. Test desktop, smaller laptop/tablet width, and mobile width; confirm no horizontal overflow, clipped dialogs, overlap, or unusable controls.
12. Perform the complete judge demo from landing page to logout **three consecutive times**.

For each route and critical flow, record evidence: URL/path, actions, expected result, observed result, pass/fail, and any fix made. If browser automation is unavailable, use the strongest available runtime test and explicitly disclose the limitation; never mark an untested flow as working.

### Repository-specific baseline

This repository currently contains a Next.js/React/TypeScript frontend and a Python/FastAPI backend. At minimum, inspect and exercise these frontend routes before declaring completion:

`/`, `/login`, `/onboarding`, `/sessions`, `/sessions/[id]`, `/analytics`, `/methodology`, and `/settings`.

Also enumerate backend routes from the FastAPI application rather than assuming the README is complete. Run the repository's actual checks, including the available equivalents of:

```text
cd frontend && npm run test
cd frontend && npm run build
cd backend && pytest
```

Run lint/type checks if configured. If any command is unavailable, broken because of repository configuration, or skipped due to an external dependency, capture the command and the exact output in the audit and fix the configuration when it is in scope.

## E. Test Matrix That Must Pass

Create `docs/QA_MATRIX.md` containing at least:

| Area | Test | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|
| Startup | Fresh documented start | Services start without avoidable errors |  |  |  |
| Routes | Every registered/linked route | Correct page loads; no dead route |  |  |  |
| Auth | Demo access, sign up, login, logout | Correct session behavior and messages |  |  |  |
| Security | Protected route while logged out | Access is denied safely |  |  |  |
| Core flow | Valid input | Processing and meaningful result |  |  |  |
| Core flow | Invalid/boundary input | Validation prevents bad submission |  |  |  |
| Recovery | Service/API failure | Useful fallback or error and retry |  |  |  |
| Persistence | Refresh and second session | Data/session behavior is correct |  |  |  |
| UI | Desktop/mobile checks | Responsive and usable |  |  |  |
| Quality | Console/network/server logs | No unexplained blocking errors |  |  |  |
| Demo | Complete run, repeated three times | Finishes under three minutes |  |  |  |

Every failure must be fixed and re-tested. If a failure cannot be fixed safely, mark the feature `PARTIAL`, `DEMO`, or `BROKEN`, explain why, provide a backup path, and remove it from unsupported claims.

## F. Production-Readiness Review

Make the project production-ready to the extent appropriate for this repository and hackathon. This means reliable behavior and honest boundaries, not pretending a prototype is enterprise production.

Review and improve:

- type safety and input validation at every client/server boundary
- authentication, authorization, session expiry, password handling, and protected routes
- secrets and environment variables; no credentials or private data in client bundles, logs, commits, or sample output
- database constraints, migrations, indexes, transaction/error behavior, seed isolation, and safe retry behavior
- API status codes, consistent response schemas, timeouts, rate limits where needed, and graceful dependency failure
- user-visible error, loading, empty, retry, and offline/disconnected states
- logging that is useful without leaking secrets or personal data
- CORS, security headers, file/upload handling, dangerous-content sanitization, and authorization server-side
- accessibility, keyboard navigation, focus management, labels, contrast, and semantic HTML
- performance, request duplication, unbounded lists, memory leaks, image sizes, and unnecessary re-renders
- deployment reproducibility, health checks, startup order, environment validation, and safe defaults
- test determinism, cleanup, isolation, and coverage of the highest-risk paths

Do not add dependencies or rewrite working architecture without a demonstrated benefit. Do not weaken security or validation to make a demo pass.

## G. Completion Gate

Do not stop after generating code. The task is complete only when:

- every existing and newly added route has been visited and classified
- every visible navigation item and important button has been exercised
- all meaningful source files have been inspected and classified
- dead code and useless dependencies have been removed or justified
- automated tests pass, plus the application has been tested in a real running browser/runtime
- the complete judge journey passes three times consecutively
- no unexplained console-breaking error, failed critical request, blank page, dead button, or placeholder UI remains
- `docs/QA_MATRIX.md`, `docs/FINAL_AUDIT.md`, `docs/DEMO_SCRIPT.md`, `docs/DEMO_BACKUP.md`, and the README match the actual implementation
- the final report clearly separates **WORKING**, **PARTIAL**, **DEMO/MOCKED**, **BLOCKED**, and **REMOVED** functionality

The final response must include:

1. files changed and why
2. files/code removed and why
3. commands used to run and test the project
4. route-by-route test results
5. automated test results
6. three full-demo run results and durations
7. production-readiness checks completed
8. known limitations and honest claims to make to judges
9. any test or environment that could not be executed, with the exact blocker

Never say “everything works,” “production-ready,” or “fully tested” without evidence in the audit and QA matrix.
