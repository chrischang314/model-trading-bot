# Project Handbook

## Plain-Language Model

Model Trading Bot is an educational market-data stack. It does not place real trades. The app fetches daily equity prices, stores price and signal rows, applies simple strategy rules, and shows the result in a React dashboard.

## Main Concepts

- Bars are daily open/high/low/close/volume records from the configured data provider.
- Signals are calculated indicator rows such as moving averages, RSI, volatility, momentum, and a combined score.
- Strategies turn signal rows into a long-or-cash position rule.
- Backtests replay those positions with simple costs and compare them with buy-and-hold.
- Paper snapshots turn the latest strategy result into a simulated portfolio without sending orders.

## Operational Checks

Use `GET /api/diagnostics` or the Home page Operations panel for a quick health read:

- Storage shows whether the configured storage backend is reachable.
- Shared Login shows whether the shared local auth database can initialize.
- Signals shows the latest stored signal date and whether watched symbols are missing rows.
- S&P Cache shows whether the cached S&P 500 universe exists and whether it is stale.

The diagnostics endpoint must not trigger an S&P 500 internet refresh. Manual refresh still belongs to `POST /api/universe/sp500/refresh` or the S&P 500 button in the dashboard.

## Safety Boundaries

- Keep the app clearly educational; do not imply investment advice.
- Do not add live brokerage execution without explicit risk controls, authentication, audit logs, and user confirmation flows.
- Keep credentials, KDB license files, local data, and generated frontend/backend artifacts out of git.
