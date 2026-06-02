# Handoff

## Current Branch

- Worktree: `C:\Users\chris\Projects\model-trading-bot-sso-contract`
- Branch: `codex/projects-lan-sso-model-trading-bot`
- Task: Projects LAN shared SSO contract for `model-trading-bot`.

## What Changed

- Backend auth now uses `SHARED_AUTH_DB` for shared `users` and hashed `auth_sessions`.
- Register/login require username plus password and set the HttpOnly `projects_lan_session` cookie.
- Logout revokes the session token and clears the cookie.
- Account-scoped model-trading-bot endpoints resolve users from the session cookie, not `X-User-Id`, query params, or localStorage.
- Public market-data and built-in strategy views can still load without a session; saved strategies, account reset, paper portfolio, and paper run journal require a signed-in session.
- Frontend API calls include credentials and no longer send user ids. localStorage only keeps a display username hint.
- Paper run and portfolio user scoping remains keyed by shared numeric `user_id`.

## Configuration

- `SHARED_AUTH_DB`: shared SQLite auth DB path.
- `AUTH_COOKIE_DOMAIN`: optional cookie domain for LAN host sharing.
- `AUTH_COOKIE_SECURE`: set `true` only when serving over HTTPS.
- `AUTH_SESSION_TTL_DAYS`: session cookie/backend session lifetime, default `30`.
- `AUTH_ALLOW_LEGACY_PASSWORD_CLAIM`: default `false`; set `true` only for a trusted migration window if existing passwordless rows must be claimed by registration.
- `CORS_ORIGINS`: comma-separated frontend origins allowed to send credentialed requests during cross-origin dev.

## Verification

- Baseline before edits: from `backend/`, `..\.venv\Scripts\python.exe -m pytest` -> `17 passed, 3 warnings`.
- After changes: from `backend/`, `..\.venv\Scripts\python.exe -m pytest` -> `20 passed, 3 warnings`.
- After changes: from `frontend/`, with the portable CodexTools Node path prepended, `corepack pnpm run build` -> passes with the existing Vite chunk-size warning.

## Notes

- Do not reintroduce `X-User-Id` or `user_id` query auth. They were the localStorage authority path this refactor removes.
- If sibling apps need to share this exact SSO session, align them to the `projects_lan_session` cookie name and the same `auth_sessions` table.
