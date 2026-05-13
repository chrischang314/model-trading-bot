from __future__ import annotations

import numpy as np
import pandas as pd


STRATEGY_METADATA = {
    "name": "multi_factor_daily_long_cash_v1",
    "position_rule": "Long when signal_score >= 4, close is above SMA 20, and RSI is below 78; otherwise cash.",
    "components": [
        {
            "key": "trend_score",
            "label": "Trend",
            "signals": ["close vs SMA 50", "SMA 20 vs SMA 50", "MACD histogram"],
            "range": [-3, 3],
        },
        {
            "key": "momentum_score",
            "label": "Momentum",
            "signals": ["RSI 14", "stochastic %K/%D", "20-day price momentum"],
            "range": [-3, 3],
        },
        {
            "key": "volatility_score",
            "label": "Volatility",
            "signals": ["Bollinger Bands", "ATR percentage vs recent baseline"],
            "range": [-2, 2],
        },
        {
            "key": "volume_score",
            "label": "Volume",
            "signals": ["20-day volume z-score", "OBV direction"],
            "range": [-2, 2],
        },
    ],
    "indicator_notes": [
        "SMA/EMA and MACD are trend-following indicators.",
        "RSI and stochastic oscillators measure momentum and overbought/oversold regimes.",
        "Bollinger Bands and ATR are volatility/risk context indicators.",
        "OBV and volume z-score are volume confirmation indicators.",
    ],
}

SIGNAL_COLUMNS = [
    "date",
    "sym",
    "close",
    "ema_12",
    "ema_26",
    "sma_20",
    "sma_50",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_mid",
    "bb_upper",
    "bb_lower",
    "bb_width",
    "atr_14",
    "atr_pct",
    "stoch_k",
    "stoch_d",
    "obv",
    "volume_z",
    "momentum_20d",
    "distance_52w_high",
    "trend_score",
    "momentum_score",
    "volatility_score",
    "volume_score",
    "signal_score",
    "signal_reason",
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
        high = ordered["high"].astype(float)
        low = ordered["low"].astype(float)
        volume = ordered["volume"].astype(float)

        ordered["ema_12"] = close.ewm(span=12, adjust=False).mean()
        ordered["ema_26"] = close.ewm(span=26, adjust=False).mean()
        ordered["sma_20"] = close.rolling(window=20, min_periods=5).mean()
        ordered["sma_50"] = close.rolling(window=50, min_periods=10).mean()
        ordered["rsi_14"] = _rsi(close, periods=14)
        ordered["macd"] = ordered["ema_12"] - ordered["ema_26"]
        ordered["macd_signal"] = ordered["macd"].ewm(span=9, adjust=False).mean()
        ordered["macd_hist"] = ordered["macd"] - ordered["macd_signal"]

        rolling_std_20 = close.rolling(window=20, min_periods=5).std()
        ordered["bb_mid"] = ordered["sma_20"]
        ordered["bb_upper"] = ordered["bb_mid"] + (2 * rolling_std_20)
        ordered["bb_lower"] = ordered["bb_mid"] - (2 * rolling_std_20)
        ordered["bb_width"] = (ordered["bb_upper"] - ordered["bb_lower"]) / ordered["bb_mid"]

        ordered["atr_14"] = _atr(high, low, close, periods=14)
        ordered["atr_pct"] = ordered["atr_14"] / close
        ordered["stoch_k"] = _stochastic_k(high, low, close)
        ordered["stoch_d"] = ordered["stoch_k"].rolling(window=3, min_periods=1).mean()
        ordered["obv"] = _obv(close, volume)
        ordered["volume_z"] = _volume_zscore(volume)
        ordered["momentum_20d"] = close.pct_change(20)
        rolling_high_252 = close.rolling(window=252, min_periods=30).max()
        ordered["distance_52w_high"] = close / rolling_high_252 - 1

        ordered["trend_score"] = _trend_score(ordered)
        ordered["momentum_score"] = _momentum_score(ordered)
        ordered["volatility_score"] = _volatility_score(ordered)
        ordered["volume_score"] = _volume_score(ordered)
        ordered["signal_score"] = (
            ordered["trend_score"] + ordered["momentum_score"] + ordered["volatility_score"] + ordered["volume_score"]
        )

        long_condition = (ordered["signal_score"] >= 4) & (close > ordered["sma_20"]) & (ordered["rsi_14"] < 78)
        ordered["position"] = np.where(long_condition, 1, 0).astype(int)
        change = ordered["position"].diff().fillna(ordered["position"])
        ordered["trade_signal"] = np.select(
            [change > 0, change < 0],
            ["BUY", "SELL"],
            default="HOLD",
        )
        ordered["signal_reason"] = ordered.apply(_signal_reason, axis=1)
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


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, periods: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / periods, min_periods=periods, adjust=False).mean()


def _stochastic_k(high: pd.Series, low: pd.Series, close: pd.Series, periods: int = 14) -> pd.Series:
    lowest_low = low.rolling(window=periods, min_periods=periods).min()
    highest_high = high.rolling(window=periods, min_periods=periods).max()
    denominator = (highest_high - lowest_low).replace(0, np.nan)
    return (100 * (close - lowest_low) / denominator).fillna(50)


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def _volume_zscore(volume: pd.Series) -> pd.Series:
    average = volume.rolling(window=20, min_periods=5).mean()
    deviation = volume.rolling(window=20, min_periods=5).std().replace(0, np.nan)
    return ((volume - average) / deviation).fillna(0)


def _trend_score(frame: pd.DataFrame) -> pd.Series:
    score = pd.Series(0, index=frame.index, dtype=float)
    score += np.where(frame["close"] > frame["sma_50"], 1, -1)
    score += np.where(frame["sma_20"] > frame["sma_50"], 1, -1)
    score += np.where(frame["macd_hist"] > 0, 1, -1)
    return score


def _momentum_score(frame: pd.DataFrame) -> pd.Series:
    score = pd.Series(0, index=frame.index, dtype=float)
    score += np.where((frame["rsi_14"] >= 45) & (frame["rsi_14"] <= 70), 1, 0)
    score += np.where((frame["rsi_14"] > 75) | (frame["rsi_14"] < 30), -1, 0)
    score += np.where((frame["stoch_k"] > frame["stoch_d"]) & (frame["stoch_k"] < 80), 1, 0)
    score += np.where((frame["stoch_k"] < frame["stoch_d"]) & (frame["stoch_k"] > 20), -1, 0)
    score += np.where(frame["momentum_20d"] > 0, 1, -1)
    return score


def _volatility_score(frame: pd.DataFrame) -> pd.Series:
    score = pd.Series(0, index=frame.index, dtype=float)
    score += np.where((frame["close"] > frame["bb_mid"]) & (frame["close"] < frame["bb_upper"]), 1, 0)
    score += np.where((frame["close"] < frame["bb_lower"]) | (frame["close"] > frame["bb_upper"]), -1, 0)
    atr_median = frame["atr_pct"].rolling(window=60, min_periods=20).median()
    atr_upper = frame["atr_pct"].rolling(window=60, min_periods=20).quantile(0.75)
    score += np.where(frame["atr_pct"] <= atr_median, 1, 0)
    score += np.where(frame["atr_pct"] > atr_upper, -1, 0)
    return score


def _volume_score(frame: pd.DataFrame) -> pd.Series:
    obv_slope = frame["obv"].diff(5)
    score = pd.Series(0, index=frame.index, dtype=float)
    score += np.where(frame["volume_z"] > 0.5, 1, 0)
    score += np.where(frame["volume_z"] < -0.75, -1, 0)
    score += np.where(obv_slope > 0, 1, -1)
    return score


def _signal_reason(row: pd.Series) -> str:
    stance = "Long" if int(row["position"]) == 1 else "Cash"
    macd_state = "MACD bullish" if row["macd_hist"] > 0 else "MACD bearish"
    rsi = row["rsi_14"]
    if rsi > 70:
        rsi_state = "RSI overbought"
    elif rsi < 30:
        rsi_state = "RSI oversold"
    else:
        rsi_state = "RSI neutral"
    return (
        f"{stance}: score {row['signal_score']:.0f} "
        f"(trend {row['trend_score']:+.0f}, momentum {row['momentum_score']:+.0f}, "
        f"volatility {row['volatility_score']:+.0f}, volume {row['volume_score']:+.0f}); "
        f"{macd_state}; {rsi_state}"
    )
