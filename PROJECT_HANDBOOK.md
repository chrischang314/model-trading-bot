# Project Handbook

## Plain-Language Model

Model Trading Bot is an educational market-data stack. It does not place real trades. The app fetches daily equity prices, stores price and signal rows, applies simple strategy rules, and shows the result in a React dashboard.

## Main Concepts

- Bars are daily open/high/low/close/volume records from the configured data provider.
- Signals are calculated indicator rows such as moving averages, RSI, volatility, momentum, and a combined score.
- Strategies turn signal rows into a long-or-cash position rule.
- Backtests replay those positions with simple costs and compare them with buy-and-hold.
- Strategy comparisons run several long/cash rules on the same symbol and assumptions so return, drawdown, Sharpe, exposure, and trade count can be compared without changing pages.
- Paper snapshots turn the latest strategy result into a simulated portfolio without sending orders.
- Paper run records preserve successful simulation inputs and outputs by local user, making the paper account reviewable over time while keeping it separate from real brokerage execution.

## Operational Checks

Use `GET /api/diagnostics` or the Home page Operations panel for a quick health read:

- Storage shows whether the configured storage backend is reachable.
- Shared Login shows whether the shared local auth database can initialize.
- Market Data shows the latest stored bar date, row age, stale status, and whether watched symbols are missing rows.
- Signals shows the latest calculated signal date, row age, stale status, and whether watched symbols are missing rows.
- S&P Cache shows whether the cached S&P 500 universe exists and whether it is stale.

Bars and signals are marked stale after more than three calendar days without a latest row. This keeps weekday outages visible while avoiding weekend-only false alarms.

The diagnostics endpoint must not trigger an S&P 500 internet refresh. Manual refresh still belongs to `POST /api/universe/sp500/refresh` or the S&P 500 button in the dashboard.

Symbol-specific read endpoints may auto-ingest when local signals are missing. If the provider cannot return data for a ticker, explain, timeseries, and backtest requests should return HTTP 404 with a clear no-market-data message. Pure provider outages should return HTTP 502, and storage or unexpected application failures should not be hidden as invalid-symbol responses. A mixed fallback result where one provider reports no rows and another provider fails to parse or authenticate should stay on the no-market-data path for symbol-specific reads.

## Safety Boundaries

- Keep the app clearly educational; do not imply investment advice.
- Do not add live brokerage execution without explicit risk controls, authentication, audit logs, and user confirmation flows.
- Loading an old paper run should only replay the stored snapshot in the UI; it must not fetch fresh market data, place orders, or mutate the user's latest saved portfolio.
- Keep credentials, KDB license files, local data, and generated frontend/backend artifacts out of git.
