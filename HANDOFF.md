# Handoff

## Outage Repair - 2026-06-05

- Fixed backend startup against legacy shared auth databases where
  `model_trading_bot_paper_runs` existed without the newer `run_at` column.
- `SharedAuthStore.init()` now adds missing paper-run columns before creating
  the `run_at` index and copies legacy `created_at` values into `run_at`.
- Do not repair this class of crash by deleting `/shared-auth/auth.db`; the
  migration preserves saved users, strategies, and paper runs.

## Current Candidate

- Branch/worktree: cleanup branch from `origin/main` with the paper-run journal and ingest provenance C variants merged.
- Auth: Projects LAN shared SSO contract for `model-trading-bot`.
- Feature: Data Ingestion Provenance Center for the `model-trading-bot` Projects LAN ranked brief dated 2026-06-01.
- Backend auth uses `SHARED_AUTH_DB` for shared `users` and hashed `auth_sessions`.
- Register/login require username plus password and set the HttpOnly `projects_lan_session` cookie.
- Logout revokes the session token and clears the cookie.
- Account-scoped model-trading-bot endpoints resolve users from the session cookie, not `X-User-Id`, query params, or localStorage.
- Public market-data and built-in strategy views can still load without a session; saved strategies, account reset, paper portfolio, and paper run journal require a signed-in session.
- Frontend API calls include credentials and no longer send user ids. localStorage only keeps a display username hint.
- Backend: ingestion now records a bounded local JSON journal at `LOCAL_DATA_DIR\ingest_runs.json`.
- Backend: recorded attempts include trigger, requested symbols, period/start/end, provider mode, storage backend, source labels/counts, bars/signals written, returned bar count, date range, no-data symbols, duration, status, and short error summary.
- Backend: `POST /api/ingest`, `POST /api/symbols`, startup bootstrap, broad auto-bootstrap, and symbol-specific auto-ingest attempts all record success, partial, or failure outcomes.
- Backend: `GET /api/ingest/runs` returns recent newest-first ingest runs, and `GET /api/diagnostics` includes latest plus recent ingest summaries without forcing an internet refresh.
- Frontend: the Home Operations panel shows ingest status and recent runs, with a retry button for failed or partial symbols through the existing ingest endpoint.
- Docs: `README.md` and `PROJECT_HANDBOOK.md` describe the local non-sensitive ingest journal and retry behavior.

## Verification

- Baseline before edits: backend pytest passed with `17 passed, 2 warnings`; frontend TypeScript/Vite build passed with the existing chunk-size warning.
- Backend after edits: from `backend/`, `C:\Users\chris\Projects\model-trading-bot\.venv\Scripts\python.exe -m pytest` passed with `21 passed, 2 warnings`.
- Frontend after edits: from `frontend/`, local Codex Node ran TypeScript build and Vite production build successfully; Vite still reports the existing chunk-size warning.
- Diff check: `git diff --check` passed.
- API smoke: local FastAPI on `127.0.0.1:18300` returned ingest summaries through `/api/diagnostics` and `/api/ingest/runs`.
- Browser smoke: local Vite on `127.0.0.1:18380` verified login, Operations ingest provenance, retry affordance, Stock, Signals, Backtesting, Paper Run Journal visibility, and no console errors. Smoke servers were stopped.

## Deployment Status

- Not deployed from this implementer branch.
- No Kubernetes values, image tags, or container-orchestrator files were changed.
- Judge should compare A/B/C candidates, choose one implementation, then build/push/deploy through `container-orchestrator` and verify `http://modeltradingbot.lan/`, `/api/diagnostics`, and `/api/ingest/runs`.

## Notes

- Do not reintroduce `X-User-Id` or `user_id` query auth. They were the localStorage authority path this refactor removes.
- If sibling apps need to share this exact SSO session, align them to the `projects_lan_session` cookie name and the same `auth_sessions` table.
- Do not store API keys, raw provider responses, stack traces, browser state, or credentials in ingest-run records.
- Partial status means the provider returned rows for at least one requested symbol but not all requested symbols.
- Symbol-specific no-market-data behavior is preserved: no-data reads still return `404`; provider outages still return `502`.
