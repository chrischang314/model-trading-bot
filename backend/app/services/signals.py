from __future__ import annotations

import numpy as np
import pandas as pd


STRATEGY_METADATA = {
    "name": "multi_factor_daily_long_cash_v2",
    "position_rule": "Long when signal_score >= 5, close is above SMA 20, and RSI is below 78; otherwise cash.",
    "components": [
        {
            "key": "trend_score",
            "label": "Trend",
            "signals": ["close vs SMA 50/200", "SMA 50 vs SMA 200", "MACD histogram", "ADX/+DI trend strength"],
            "range": [-5, 5],
        },
        {
            "key": "momentum_score",
            "label": "Momentum",
            "signals": ["RSI 14", "stochastic %K/%D", "20-day momentum", "12-1 month momentum", "Williams %R"],
            "range": [-6, 6],
        },
        {
            "key": "volatility_score",
            "label": "Volatility",
            "signals": ["Bollinger Bands", "ATR percentage", "20-day realized volatility", "Donchian breakouts"],
            "range": [-4, 4],
        },
        {
            "key": "volume_score",
            "label": "Volume",
            "signals": ["20-day volume z-score", "OBV direction", "rolling VWAP"],
            "range": [-3, 3],
        },
    ],
    "indicator_notes": [
        "Moving averages, MACD, ADX, and Donchian channels are trend-following indicators.",
        "RSI, stochastic, Williams %R, rate-of-change, and 12-1 momentum measure momentum and overbought/oversold regimes.",
        "Bollinger Bands, ATR, and realized volatility provide volatility and risk context.",
        "OBV, rolling VWAP, and volume z-scores are volume confirmation indicators.",
    ],
}

SIGNAL_CATALOG = [
    {"key": "sma_20", "label": "SMA 20", "group": "trend", "description": "Short moving average trend baseline.", "formula": "20-session average close.", "interpretation": "Price above SMA 20 usually signals short-term upside drift."},
    {"key": "sma_50", "label": "SMA 50", "group": "trend", "description": "Intermediate moving average trend baseline.", "formula": "50-session average close.", "interpretation": "Often used as a medium-term trend filter."},
    {"key": "sma_200", "label": "SMA 200", "group": "trend", "description": "Long-term trend baseline and golden-cross reference.", "formula": "200-session average close.", "interpretation": "Price above SMA 200 is a common long-term risk-on filter."},
    {"key": "ema_12", "label": "EMA 12", "group": "trend", "description": "Fast EMA used in MACD.", "formula": "Exponentially weighted 12-session close.", "interpretation": "Responds quickly to recent price changes."},
    {"key": "ema_26", "label": "EMA 26", "group": "trend", "description": "Slow EMA used in MACD.", "formula": "Exponentially weighted 26-session close.", "interpretation": "Acts as the slower trend anchor in MACD."},
    {"key": "ema_50", "label": "EMA 50", "group": "trend", "description": "Intermediate exponential trend estimate.", "formula": "Exponentially weighted 50-session close.", "interpretation": "A smoother trend gauge that still reacts faster than SMA 50."},
    {"key": "macd_hist", "label": "MACD Histogram", "group": "trend", "description": "Fast/slow EMA spread minus signal line.", "formula": "(EMA 12 - EMA 26) - EMA 9 of that spread.", "interpretation": "Positive values suggest bullish trend acceleration."},
    {"key": "adx_14", "label": "ADX 14", "group": "trend", "description": "Trend-strength indicator based on directional movement.", "formula": "14-session smoothed directional movement index.", "interpretation": "Higher values mean stronger trend, independent of direction."},
    {"key": "plus_di_14", "label": "+DI 14", "group": "trend", "description": "Positive directional movement component.", "formula": "14-session positive directional movement divided by ATR.", "interpretation": "+DI above -DI favors upward directional pressure."},
    {"key": "minus_di_14", "label": "-DI 14", "group": "trend", "description": "Negative directional movement component.", "formula": "14-session negative directional movement divided by ATR.", "interpretation": "-DI above +DI favors downward directional pressure."},
    {"key": "donchian_breakout", "label": "Donchian Breakout", "group": "trend", "description": "Close crossing prior 20-day channel high or low.", "formula": "1 if close exceeds prior channel high, -1 if below prior channel low.", "interpretation": "Breakouts are classic trend-following entry or exit signals."},
    {"key": "rsi_14", "label": "RSI 14", "group": "momentum", "description": "Smoothed relative strength oscillator.", "formula": "100 - 100 / (1 + smoothed gains / smoothed losses).", "interpretation": "Low values flag oversold conditions; high values flag overbought conditions."},
    {"key": "stoch_k", "label": "Stochastic %K", "group": "momentum", "description": "Close location within recent high-low range.", "formula": "100 * (close - 14-day low) / (14-day high - 14-day low).", "interpretation": "Readings near 100 mean price is closing near recent highs."},
    {"key": "williams_r_14", "label": "Williams %R", "group": "momentum", "description": "Overbought/oversold oscillator similar to stochastic.", "formula": "-100 * (14-day high - close) / (14-day high - 14-day low).", "interpretation": "Values near 0 are overbought; values near -100 are oversold."},
    {"key": "cci_20", "label": "CCI 20", "group": "momentum", "description": "Typical-price deviation from its moving average.", "formula": "(typical price - 20-day average typical price) / mean deviation.", "interpretation": "Large positive or negative readings flag unusually strong moves."},
    {"key": "momentum_20d", "label": "20D Momentum", "group": "momentum", "description": "One-month rate of change.", "formula": "close / close 20 sessions ago - 1.", "interpretation": "Positive values show short-term price persistence."},
    {"key": "momentum_252_skip_21", "label": "12-1 Momentum", "group": "momentum", "description": "Academic-style 12-month momentum skipping the most recent month.", "formula": "close 21 sessions ago / close 252 sessions ago - 1.", "interpretation": "Positive values approximate longer-horizon trend persistence."},
    {"key": "bb_width", "label": "Bollinger Width", "group": "volatility", "description": "Normalized width of two-standard-deviation Bollinger Bands.", "formula": "(upper band - lower band) / middle band.", "interpretation": "Wider bands indicate higher recent price dispersion."},
    {"key": "atr_pct", "label": "ATR %", "group": "volatility", "description": "Average true range normalized by close.", "formula": "14-session ATR / close.", "interpretation": "Higher values imply larger typical daily ranges relative to price."},
    {"key": "realized_vol_20", "label": "20D Realized Vol", "group": "volatility", "description": "Annualized standard deviation of daily returns.", "formula": "20-session return standard deviation * sqrt(252).", "interpretation": "Useful for comparing recent risk across symbols."},
    {"key": "keltner_upper", "label": "Keltner Upper", "group": "volatility", "description": "EMA 20 plus two ATRs.", "formula": "EMA 20 + 2 * ATR 14.", "interpretation": "Upper volatility envelope around trend."},
    {"key": "keltner_lower", "label": "Keltner Lower", "group": "volatility", "description": "EMA 20 minus two ATRs.", "formula": "EMA 20 - 2 * ATR 14.", "interpretation": "Lower volatility envelope around trend."},
    {"key": "obv", "label": "OBV", "group": "volume", "description": "Cumulative signed volume.", "formula": "Add volume on up days; subtract volume on down days.", "interpretation": "Rising OBV can confirm buying pressure behind price moves."},
    {"key": "volume_z", "label": "Volume Z", "group": "volume", "description": "Volume surprise relative to the last 20 sessions.", "formula": "(volume - 20-day average volume) / 20-day volume standard deviation.", "interpretation": "Positive values flag above-normal participation."},
    {"key": "rolling_vwap_20", "label": "20D VWAP", "group": "volume", "description": "Volume-weighted rolling average of close.", "formula": "sum(close * volume) / sum(volume) over 20 sessions.", "interpretation": "Price above VWAP suggests buyers are paying above the recent volume-weighted basis."},
]

SIGNAL_COLUMNS = [
    "date",
    "sym",
    "close",
    "return_1d",
    "return_5d",
    "return_21d",
    "return_63d",
    "ema_12",
    "ema_26",
    "ema_50",
    "sma_20",
    "sma_50",
    "sma_200",
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
    "realized_vol_20",
    "realized_vol_63",
    "stoch_k",
    "stoch_d",
    "williams_r_14",
    "cci_20",
    "adx_14",
    "plus_di_14",
    "minus_di_14",
    "obv",
    "volume_z",
    "rolling_vwap_20",
    "momentum_20d",
    "momentum_252_skip_21",
    "zscore_20",
    "donchian_high_20",
    "donchian_low_20",
    "donchian_breakout",
    "keltner_mid",
    "keltner_upper",
    "keltner_lower",
    "gap_return",
    "intraday_return",
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
        open_ = ordered["open"].astype(float)
        close = ordered["close"].astype(float)
        high = ordered["high"].astype(float)
        low = ordered["low"].astype(float)
        volume = ordered["volume"].astype(float)

        ordered["return_1d"] = close.pct_change()
        ordered["return_5d"] = close.pct_change(5)
        ordered["return_21d"] = close.pct_change(21)
        ordered["return_63d"] = close.pct_change(63)
        ordered["ema_12"] = close.ewm(span=12, adjust=False).mean()
        ordered["ema_26"] = close.ewm(span=26, adjust=False).mean()
        ordered["ema_50"] = close.ewm(span=50, adjust=False).mean()
        ordered["sma_20"] = close.rolling(window=20, min_periods=5).mean()
        ordered["sma_50"] = close.rolling(window=50, min_periods=10).mean()
        ordered["sma_200"] = close.rolling(window=200, min_periods=50).mean()
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
        ordered["realized_vol_20"] = ordered["return_1d"].rolling(window=20, min_periods=10).std() * np.sqrt(252)
        ordered["realized_vol_63"] = ordered["return_1d"].rolling(window=63, min_periods=20).std() * np.sqrt(252)
        ordered["stoch_k"] = _stochastic_k(high, low, close)
        ordered["stoch_d"] = ordered["stoch_k"].rolling(window=3, min_periods=1).mean()
        ordered["williams_r_14"] = _williams_r(high, low, close)
        ordered["cci_20"] = _cci(high, low, close)
        directional = _adx(high, low, close)
        ordered["adx_14"] = directional["adx_14"]
        ordered["plus_di_14"] = directional["plus_di_14"]
        ordered["minus_di_14"] = directional["minus_di_14"]
        ordered["obv"] = _obv(close, volume)
        ordered["volume_z"] = _volume_zscore(volume)
        ordered["rolling_vwap_20"] = (close * volume).rolling(window=20, min_periods=5).sum() / volume.rolling(
            window=20, min_periods=5
        ).sum()
        ordered["momentum_20d"] = close.pct_change(20)
        ordered["momentum_252_skip_21"] = close.shift(21) / close.shift(252) - 1
        ordered["zscore_20"] = (close - ordered["sma_20"]) / rolling_std_20.replace(0, np.nan)
        ordered["donchian_high_20"] = high.rolling(window=20, min_periods=10).max()
        ordered["donchian_low_20"] = low.rolling(window=20, min_periods=10).min()
        ordered["donchian_breakout"] = np.select(
            [close > ordered["donchian_high_20"].shift(1), close < ordered["donchian_low_20"].shift(1)],
            [1, -1],
            default=0,
        )
        ordered["keltner_mid"] = close.ewm(span=20, adjust=False).mean()
        ordered["keltner_upper"] = ordered["keltner_mid"] + (2 * ordered["atr_14"])
        ordered["keltner_lower"] = ordered["keltner_mid"] - (2 * ordered["atr_14"])
        ordered["gap_return"] = open_ / close.shift(1) - 1
        ordered["intraday_return"] = close / open_ - 1
        rolling_high_252 = close.rolling(window=252, min_periods=30).max()
        ordered["distance_52w_high"] = close / rolling_high_252 - 1

        ordered["trend_score"] = _trend_score(ordered)
        ordered["momentum_score"] = _momentum_score(ordered)
        ordered["volatility_score"] = _volatility_score(ordered)
        ordered["volume_score"] = _volume_score(ordered)
        ordered["signal_score"] = (
            ordered["trend_score"] + ordered["momentum_score"] + ordered["volatility_score"] + ordered["volume_score"]
        )

        long_condition = (ordered["signal_score"] >= 5) & (close > ordered["sma_20"]) & (ordered["rsi_14"] < 78)
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


def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series, periods: int = 14) -> pd.Series:
    lowest_low = low.rolling(window=periods, min_periods=periods).min()
    highest_high = high.rolling(window=periods, min_periods=periods).max()
    denominator = (highest_high - lowest_low).replace(0, np.nan)
    return (-100 * (highest_high - close) / denominator).fillna(-50)


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, periods: int = 20) -> pd.Series:
    typical = (high + low + close) / 3
    average = typical.rolling(window=periods, min_periods=periods).mean()
    mean_deviation = (typical - average).abs().rolling(window=periods, min_periods=periods).mean()
    return ((typical - average) / (0.015 * mean_deviation.replace(0, np.nan))).fillna(0)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, periods: int = 14) -> pd.DataFrame:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=high.index)
    atr = _atr(high, low, close, periods=periods).replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / periods, min_periods=periods, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / periods, min_periods=periods, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / periods, min_periods=periods, adjust=False).mean()
    return pd.DataFrame(
        {
            "adx_14": adx.fillna(0),
            "plus_di_14": plus_di.fillna(0),
            "minus_di_14": minus_di.fillna(0),
        }
    )


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
    score += np.where(frame["close"] > frame["sma_200"], 1, -1)
    score += np.where((frame["plus_di_14"] > frame["minus_di_14"]) & (frame["adx_14"] > 20), 1, 0)
    score += np.where((frame["minus_di_14"] > frame["plus_di_14"]) & (frame["adx_14"] > 20), -1, 0)
    return score


def _momentum_score(frame: pd.DataFrame) -> pd.Series:
    score = pd.Series(0, index=frame.index, dtype=float)
    score += np.where((frame["rsi_14"] >= 45) & (frame["rsi_14"] <= 70), 1, 0)
    score += np.where((frame["rsi_14"] > 75) | (frame["rsi_14"] < 30), -1, 0)
    score += np.where((frame["stoch_k"] > frame["stoch_d"]) & (frame["stoch_k"] < 80), 1, 0)
    score += np.where((frame["stoch_k"] < frame["stoch_d"]) & (frame["stoch_k"] > 20), -1, 0)
    score += np.where(frame["momentum_20d"] > 0, 1, -1)
    score += np.where(frame["momentum_252_skip_21"] > 0, 1, -1)
    score += np.where(frame["williams_r_14"] > -50, 1, -1)
    score += np.where(frame["cci_20"] > 100, 1, 0)
    score += np.where(frame["cci_20"] < -100, -1, 0)
    return score


def _volatility_score(frame: pd.DataFrame) -> pd.Series:
    score = pd.Series(0, index=frame.index, dtype=float)
    score += np.where((frame["close"] > frame["bb_mid"]) & (frame["close"] < frame["bb_upper"]), 1, 0)
    score += np.where((frame["close"] < frame["bb_lower"]) | (frame["close"] > frame["bb_upper"]), -1, 0)
    atr_median = frame["atr_pct"].rolling(window=60, min_periods=20).median()
    atr_upper = frame["atr_pct"].rolling(window=60, min_periods=20).quantile(0.75)
    score += np.where(frame["atr_pct"] <= atr_median, 1, 0)
    score += np.where(frame["atr_pct"] > atr_upper, -1, 0)
    vol_upper = frame["realized_vol_20"].rolling(window=120, min_periods=30).quantile(0.75)
    score += np.where(frame["realized_vol_20"] < vol_upper, 1, -1)
    score += np.where(frame["donchian_breakout"] > 0, 1, 0)
    score += np.where(frame["donchian_breakout"] < 0, -1, 0)
    return score


def _volume_score(frame: pd.DataFrame) -> pd.Series:
    obv_slope = frame["obv"].diff(5)
    score = pd.Series(0, index=frame.index, dtype=float)
    score += np.where(frame["volume_z"] > 0.5, 1, 0)
    score += np.where(frame["volume_z"] < -0.75, -1, 0)
    score += np.where(obv_slope > 0, 1, -1)
    score += np.where(frame["close"] > frame["rolling_vwap_20"], 1, -1)
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
