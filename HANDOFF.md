# Handoff

## Current Candidate

- Branch/worktree: `projects-lan-repair-invalid-symbol` for the Projects LAN invalid-symbol repair.
- Repair: symbol-specific explain, timeseries, and backtest reads return HTTP 404 with a clear "No market data available" detail when auto-ingest finds no provider rows; provider outages return HTTP 502.
- Feature: Backtesting strategy comparison plus diagnostics freshness status.
- Backend: `POST /api/backtests/compare` compares up to 8 strategy IDs on one symbol and returns compact sorted metric summaries.
- Backend: `GET /api/diagnostics` reports `age_days` and `stale` for bar and signal frames.
- Frontend: Backtesting page has a Strategy Comparison panel that compares built-ins and includes the active custom or saved strategy when selected.
- Frontend: The Home page Operations panel separates Market Data from Signals and shows fresh/stale age text for both.
- Tooling: `frontend/pnpm-workspace.yaml` approves the `esbuild` build script needed by Vite under pnpm 11.

## Verification

- Run backend tests from `backend/` with `..\.venv\Scripts\python.exe -m pytest`.
- Install browser-check tooling with `..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` and `..\.venv\Scripts\python.exe -m playwright install chromium`.
- Run the frontend build from `frontend/` with an available Node binary, for example:

```powershell
$node = 'C:\Users\chris\AppData\Local\OpenAI\Codex\bin\node.exe'
& $node .\node_modules\typescript\bin\tsc -b
& $node .\node_modules\vite\bin\vite.js build
```

## Notes

- Bars and signals become stale after more than three calendar days without a latest row.
- Reproduced before the repair: `GET /api/explain/NO_SUCH_SYMBOL_123`, `GET /api/timeseries/NO_SUCH_SYMBOL_123`, and `POST /api/backtests` for `NO_SUCH_SYMBOL_123` returned HTTP 500 on the LAN deployment.
- `POST /api/symbols` already returned a handled provider error and was left unchanged.
- The repair intentionally does not convert storage or unexpected application exceptions into invalid-symbol responses.
