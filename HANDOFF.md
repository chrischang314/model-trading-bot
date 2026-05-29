# Handoff

## Current Candidate

- Branch: `model-trading-bot-implementer-a-2026-05-29-paper-run-journal`.
- Feature: Paper Trading Run Journal And Replay for the `model-trading-bot` Projects LAN ranked brief.
- Backend: `POST /api/paper/run` still updates the latest user paper portfolio and now appends a user-scoped row to `model_trading_bot_paper_runs`.
- Backend: `GET /api/paper/runs` returns the signed-in user's newest-first compact run list; `GET /api/paper/runs/{id}` returns that user's full saved snapshot/detail or `404`.
- Backend: account reset clears saved scorecards, latest paper portfolio, and the user's paper run history.
- Frontend: Backtesting now has a Paper Run Journal panel with explicit Run Paper, recent runs, open detail, and Load Run replay into the visible Paper Equity state.
- Frontend: app load now reads the latest saved paper portfolio instead of creating hidden paper runs during initial load, symbol changes, or strategy refreshes.
- Docs: `README.md` and `PROJECT_HANDBOOK.md` describe the journal/replay behavior and read-only paper replay boundary.
- Deployment: not deployed from this implementer branch; leave container image/cluster rollout to the judge-selected implementation.

## Verification

- Backend: from `backend/`, `..\.venv\Scripts\python.exe -m pytest` -> `17 passed, 2 warnings`.
- Frontend: from `frontend/`, use the local Codex Node binary because `pnpm` is not on PATH:

```powershell
& 'C:\Users\chris\AppData\Local\OpenAI\Codex\bin\node.exe' .\node_modules\typescript\bin\tsc -b
& 'C:\Users\chris\AppData\Local\OpenAI\Codex\bin\node.exe' .\node_modules\vite\bin\vite.js build
```

- Frontend build passes with the existing Vite chunk-size warning.

## Notes

- Paper replay is intentionally read-only: loading an older run only displays the saved simulation snapshot and does not fetch market data, re-simulate, or route broker orders.
- Run records persist requested symbols, requested cash, requested strategy id, resolved custom/saved strategy JSON when present, resulting cash/equity, positions, orders, warnings, and error flags.
- Existing `GET /api/paper/portfolio` remains the compatibility/latest snapshot endpoint.
