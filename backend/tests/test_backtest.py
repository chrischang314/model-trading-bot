from __future__ import annotations

import pandas as pd

from app.services.backtest import run_long_cash_backtest
from app.services.signals import calculate_signals


def test_backtest_returns_metrics_equity_and_trades() -> None:
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    close = [100 + i * 0.4 for i in range(120)]
    bars = pd.DataFrame(
        {
            "date": dates,
            "sym": "META",
            "open": close,
            "high": [price + 1 for price in close],
            "low": [price - 1 for price in close],
            "close": close,
            "adj_close": close,
            "volume": 1_000_000,
            "source": "test",
        }
    )
    signals = calculate_signals(bars)

    result = run_long_cash_backtest(signals, initial_capital=10_000)

    assert result.symbol == "META"
    assert "total_return" in result.metrics
    assert "max_drawdown" in result.metrics
    assert not result.equity_curve.empty
    assert result.equity_curve["equity"].iloc[-1] > 0

