from __future__ import annotations

import pandas as pd


def run_paper_snapshot(signals: pd.DataFrame, cash: float) -> dict:
    if signals.empty:
        return {"cash": cash, "equity": cash, "positions": [], "orders": []}

    latest = signals.sort_values("date").groupby("sym", as_index=False).tail(1)
    target_symbols = latest[latest["position"] > 0]["sym"].tolist()
    allocation = cash / len(target_symbols) if target_symbols else 0

    positions = []
    orders = []
    remaining_cash = cash
    for row in latest.itertuples(index=False):
        if row.position > 0:
            quantity = allocation / row.close if row.close else 0
            notional = quantity * row.close
            remaining_cash -= notional
            positions.append(
                {
                    "sym": row.sym,
                    "quantity": quantity,
                    "last_price": row.close,
                    "market_value": notional,
                }
            )
            orders.append({"sym": row.sym, "side": "BUY", "notional": notional, "reason": row.trade_signal})
        else:
            orders.append({"sym": row.sym, "side": "HOLD_CASH", "notional": 0, "reason": row.trade_signal})

    equity = remaining_cash + sum(position["market_value"] for position in positions)
    return {"cash": remaining_cash, "equity": equity, "positions": positions, "orders": orders}

