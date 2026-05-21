# Handoff

## Current Branch

- `projects-lan-implementer-c-2026-05-21-data-freshness`

## Change Summary

- `GET /api/diagnostics` now reports `age_days` and `stale` for bar and signal frames.
- The Home page Operations panel now separates Market Data from Signals and shows fresh/stale age text for both.
- Bars and signals become stale after more than three calendar days without a latest row.

## Verification

- Run backend tests from `backend/` with `..\.venv\Scripts\python.exe -m pytest`.
- Install browser-check tooling with `..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` and `..\.venv\Scripts\python.exe -m playwright install chromium`.
- Run the frontend build from `frontend/` with an available Node binary, for example:

```powershell
$node = 'C:\Users\chris\AppData\Local\OpenAI\Codex\bin\node.exe'
& $node .\node_modules\typescript\bin\tsc -b
& $node .\node_modules\vite\bin\vite.js build
```

## Notes For The Judge

- This implementer did not merge to `main`; compare this branch against any A/B candidates.
- No Kubernetes deployment should be done until the judge selects a winning implementation.
