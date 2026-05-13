from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    metrics: dict
    equity_curve: pd.DataFrame
    trades: pd.DataFrame


def run_long_cash_backtest(
    signals: pd.DataFrame,
    initial_capital: float = 100_000,
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
) -> BacktestResult:
    if signals.empty:
        raise ValueError("No signal data available for backtest")
    symbols = signals["sym"].dropna().unique()
    if len(symbols) != 1:
        raise ValueError("Backtest expects exactly one symbol")

    frame = signals.sort_values("date").copy()
    frame["asset_return"] = frame["close"].pct_change().fillna(0)
    frame["applied_position"] = frame["position"].shift(1).fillna(0)
    frame["turnover"] = frame["applied_position"].diff().abs().fillna(frame["applied_position"].abs())
    cost = frame["turnover"] * ((fee_bps + slippage_bps) / 10_000)
    frame["strategy_return"] = frame["applied_position"] * frame["asset_return"] - cost
    frame["equity"] = initial_capital * (1 + frame["strategy_return"]).cumprod()
    frame["benchmark_equity"] = initial_capital * (1 + frame["asset_return"]).cumprod()
    frame["drawdown"] = frame["equity"] / frame["equity"].cummax() - 1

    equity_curve = frame[
        [
            "date",
            "sym",
            "close",
            "position",
            "applied_position",
            "asset_return",
            "strategy_return",
            "equity",
            "benchmark_equity",
            "drawdown",
        ]
    ].copy()

    trades = _build_trades(frame)
    metrics = _metrics(frame, trades, initial_capital)
    return BacktestResult(str(symbols[0]), metrics, equity_curve, trades)


def _build_trades(frame: pd.DataFrame) -> pd.DataFrame:
    changes = frame[frame["position"].diff().fillna(frame["position"]) != 0].copy()
    if changes.empty:
        return pd.DataFrame(columns=["date", "sym", "side", "price", "position", "equity"])
    changes["side"] = np.where(changes["position"] > 0, "BUY", "SELL")
    return changes[["date", "sym", "side", "close", "position", "equity"]].rename(columns={"close": "price"})


def _metrics(frame: pd.DataFrame, trades: pd.DataFrame, initial_capital: float) -> dict:
    total_return = frame["equity"].iloc[-1] / initial_capital - 1
    benchmark_return = frame["benchmark_equity"].iloc[-1] / initial_capital - 1
    days = max((frame["date"].iloc[-1] - frame["date"].iloc[0]).days, 1)
    cagr = (1 + total_return) ** (365 / days) - 1
    volatility = frame["strategy_return"].std(ddof=0) * np.sqrt(252)
    sharpe = 0 if volatility == 0 or np.isnan(volatility) else frame["strategy_return"].mean() * 252 / volatility
    max_drawdown = frame["drawdown"].min()
    exposure = frame["applied_position"].mean()
    completed_trades = trades[trades["side"] == "SELL"]
    win_rate = None
    if not completed_trades.empty:
        buys = trades[trades["side"] == "BUY"].reset_index(drop=True)
        sells = completed_trades.reset_index(drop=True)
        pairs = min(len(buys), len(sells))
        if pairs:
            win_rate = float((sells.loc[: pairs - 1, "price"].to_numpy() > buys.loc[: pairs - 1, "price"].to_numpy()).mean())
    return {
        "total_return": float(total_return),
        "benchmark_return": float(benchmark_return),
        "cagr": float(cagr),
        "annualized_volatility": float(volatility) if not np.isnan(volatility) else 0.0,
        "sharpe": float(sharpe),
        "max_drawdown": float(max_drawdown),
        "exposure": float(exposure),
        "trade_count": int(len(trades)),
        "win_rate": win_rate,
    }

