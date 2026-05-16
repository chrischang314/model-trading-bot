from __future__ import annotations

import pandas as pd

from app.services.signals import SIGNAL_COLUMNS, calculate_signals
from app.services.strategies import apply_strategy, list_strategies


def test_calculate_signals_adds_expected_columns() -> None:
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    bars = pd.DataFrame(
        {
            "date": dates,
            "sym": "AAPL",
            "open": range(100, 180),
            "high": range(101, 181),
            "low": range(99, 179),
            "close": range(100, 180),
            "adj_close": range(100, 180),
            "volume": 1_000_000,
            "source": "test",
        }
    )

    signals = calculate_signals(bars)

    assert list(signals.columns) == SIGNAL_COLUMNS
    assert len(signals) == len(bars)
    assert set(signals["trade_signal"]).issubset({"BUY", "SELL", "HOLD"})
    assert set(signals["position"]).issubset({0, 1})


def test_strategy_registry_can_apply_all_builtin_strategies() -> None:
    dates = pd.date_range("2024-01-01", periods=260, freq="D")
    bars = pd.DataFrame(
        {
            "date": dates,
            "sym": "AAPL",
            "open": range(100, 360),
            "high": range(101, 361),
            "low": range(99, 359),
            "close": range(100, 360),
            "adj_close": range(100, 360),
            "volume": 1_000_000,
            "source": "test",
        }
    )
    signals = calculate_signals(bars)

    for strategy in list_strategies():
        custom = {"min_signal_score": 4, "max_rsi": 85} if strategy["kind"] == "custom" else None
        applied = apply_strategy(signals, strategy["id"], custom)

        assert len(applied) == len(signals)
        assert set(applied["trade_signal"]).issubset({"BUY", "SELL", "HOLD"})
        assert set(applied["position"]).issubset({0, 1})
