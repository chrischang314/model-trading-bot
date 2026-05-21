# Handoff

## Current Candidate

- Branch/worktree: `projects-lan-implementer-b-2026-05-21-strategy-compare` at `C:\Users\chris\Projects\model-trading-bot-implementer-b-2026-05-21-strategy-compare`
- Feature: Backtesting strategy comparison.
- Backend: `POST /api/backtests/compare` compares up to 8 strategy IDs on one symbol and returns compact sorted metric summaries.
- Frontend: Backtesting page has a Strategy Comparison panel that compares built-ins and includes the active custom or saved strategy when selected.
- Tooling: `frontend/pnpm-workspace.yaml` approves the `esbuild` build script needed by Vite under pnpm 11.

## Verification

Run from this worktree:

```powershell
cd C:\Users\chris\Projects\model-trading-bot-implementer-b-2026-05-21-strategy-compare\backend
$env:STORAGE_BACKEND="local"
C:\Users\chris\Projects\model-trading-bot\.venv\Scripts\python.exe -m pytest tests
```

For frontend checks, use a real Node executable rather than the WindowsApps shim. Install frontend dependencies in this worktree with the repo lockfile before running the build.

## Notes

- The original `C:\Users\chris\Projects\model-trading-bot` working directory currently has separate implementer-C data-freshness edits; do not overwrite them when judging.
- No deployment has been performed from this candidate branch yet.
