from __future__ import annotations

import numpy as np
import pandas as pd


SIGNAL_COLUMNS = [
    "date",
    "sym",
    "close",
    "sma_20",
    "sma_50",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "trade_signal",
    "position",
]


def calculate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame(columns=SIGNAL_COLUMNS)

    frames = []
    for symbol, frame in bars.groupby("sym", sort=True):
        ordered = frame.sort_values("date").copy()
        close = ordered["close"].astype(float)
        ordered["sma_20"] = close.rolling(window=20, min_periods=5).mean()
        ordered["sma_50"] = close.rolling(window=50, min_periods=10).mean()
        ordered["rsi_14"] = _rsi(close, periods=14)
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        ordered["macd"] = ema_fast - ema_slow
        ordered["macd_signal"] = ordered["macd"].ewm(span=9, adjust=False).mean()
        ordered["macd_hist"] = ordered["macd"] - ordered["macd_signal"]
        long_condition = (
            (ordered["macd"] > ordered["macd_signal"])
            & (ordered["rsi_14"] < 70)
            & (ordered["close"] > ordered["sma_20"])
        )
        ordered["position"] = np.where(long_condition, 1, 0).astype(int)
        change = ordered["position"].diff().fillna(ordered["position"])
        ordered["trade_signal"] = np.select(
            [change > 0, change < 0],
            ["BUY", "SELL"],
            default="HOLD",
        )
        ordered["sym"] = symbol
        frames.append(ordered[SIGNAL_COLUMNS])

    signals = pd.concat(frames, ignore_index=True)
    return signals.sort_values(["sym", "date"]).reset_index(drop=True)


def _rsi(close: pd.Series, periods: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / periods, min_periods=periods, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / periods, min_periods=periods, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

