from __future__ import annotations

import pandas as pd

from app.services.signals import SIGNAL_COLUMNS, calculate_signals


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

