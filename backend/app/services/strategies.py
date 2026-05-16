from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_STRATEGY_ID = "multi_factor_scorecard"
CUSTOM_STRATEGY_ID = "custom_scorecard"

DEFAULT_CUSTOM_STRATEGY = {
    "name": "Custom scorecard",
    "min_signal_score": 5.0,
    "max_rsi": 78.0,
    "min_rsi": None,
    "require_above_sma20": True,
    "require_positive_macd": False,
    "min_adx": None,
    "min_momentum_score": None,
}

BASE_COMPONENTS = [
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
]

STRATEGY_CATALOG = [
    {
        "id": DEFAULT_STRATEGY_ID,
        "name": "multi_factor_daily_long_cash_v2",
        "label": "Scorecard",
        "kind": "built_in",
        "description": "Balanced long/cash scorecard across trend, momentum, volatility, and volume confirmation.",
        "position_rule": "Long when signal_score >= 5, close is above SMA 20, and RSI is below 78; otherwise cash.",
        "components": BASE_COMPONENTS,
        "indicator_notes": [
            "Moving averages, MACD, ADX, and Donchian channels are trend-following indicators.",
            "RSI, stochastic, Williams %R, rate-of-change, and 12-1 momentum measure momentum and overbought/oversold regimes.",
            "Bollinger Bands, ATR, and realized volatility provide volatility and risk context.",
            "OBV, rolling VWAP, and volume z-scores are volume confirmation indicators.",
        ],
    },
    {
        "id": "trend_breakout",
        "name": "trend_breakout_long_cash",
        "label": "Trend Breakout",
        "kind": "built_in",
        "description": "Trend-following rule that waits for bullish moving-average structure and directional strength.",
        "position_rule": "Long when price is above SMA 200, SMA 50 is above SMA 200, MACD is positive, and either ADX confirms trend strength or price breaks the Donchian channel.",
        "components": [BASE_COMPONENTS[0], BASE_COMPONENTS[3]],
        "indicator_notes": [
            "This is a classic long/cash trend-following template.",
            "It reacts later than the scorecard, but tries to avoid sideways markets.",
        ],
    },
    {
        "id": "mean_reversion",
        "name": "rsi_bollinger_mean_reversion",
        "label": "Mean Reversion",
        "kind": "built_in",
        "description": "Oversold bounce rule using RSI, Bollinger z-score, and a long-term trend filter.",
        "position_rule": "Long when RSI is oversold or price is below the lower Bollinger Band, while price remains above SMA 200; exit after RSI normalizes or price reaches SMA 20.",
        "components": [BASE_COMPONENTS[1], BASE_COMPONENTS[2]],
        "indicator_notes": [
            "Mean reversion expects short-term extremes to partially unwind.",
            "The SMA 200 filter avoids buying severe downtrends in this toy version.",
        ],
    },
    {
        "id": "momentum_rotation",
        "name": "time_series_momentum",
        "label": "Momentum",
        "kind": "built_in",
        "description": "Long/cash momentum rule inspired by 12-1 month momentum and short-term confirmation.",
        "position_rule": "Long when 12-1 month momentum is positive, 20-day momentum is positive, RSI is constructive but not overheated, and volume is non-negative.",
        "components": [BASE_COMPONENTS[0], BASE_COMPONENTS[1], BASE_COMPONENTS[3]],
        "indicator_notes": [
            "This mimics a simple time-series momentum filter.",
            "It skips the most recent month in the 12-1 measure to reduce short-term reversal noise.",
        ],
    },
    {
        "id": "low_volatility_trend",
        "name": "low_volatility_trend",
        "label": "Low Vol Trend",
        "kind": "built_in",
        "description": "Defensive trend rule that prefers uptrends with calmer realized volatility and moderate ATR.",
        "position_rule": "Long when price is above SMA 50 and SMA 200, realized volatility is below its 63-day baseline, and ATR is not elevated.",
        "components": [BASE_COMPONENTS[0], BASE_COMPONENTS[2]],
        "indicator_notes": [
            "This rule is intentionally conservative and may stay in cash more often.",
            "It is useful for comparing return, exposure, and drawdown against more aggressive strategies.",
        ],
    },
    {
        "id": CUSTOM_STRATEGY_ID,
        "name": "custom_scorecard",
        "label": "Custom",
        "kind": "custom",
        "description": "User-configurable long/cash scorecard assembled from the existing indicator columns.",
        "position_rule": "Long when the configured score and optional filters pass; otherwise cash.",
        "components": BASE_COMPONENTS,
        "indicator_notes": [
            "This toy builder mirrors a production config-driven rule strategy without executing arbitrary code.",
            "For richer custom algorithms, add a versioned strategy module or a validated expression DSL.",
        ],
    },
]


def list_strategies() -> list[dict[str, Any]]:
    return deepcopy(STRATEGY_CATALOG)


def get_strategy_metadata(strategy_id: str = DEFAULT_STRATEGY_ID, custom_strategy: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = deepcopy(_find_strategy(strategy_id))
    if metadata["id"] == CUSTOM_STRATEGY_ID:
        custom = _normalize_custom_strategy(custom_strategy)
        metadata["label"] = custom["name"] or metadata["label"]
        metadata["name"] = custom["name"] or metadata["name"]
        metadata["position_rule"] = _custom_rule_text(custom)
        metadata["custom"] = custom
    return metadata


def apply_strategy(
    signals: pd.DataFrame,
    strategy_id: str = DEFAULT_STRATEGY_ID,
    custom_strategy: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if signals.empty:
        return signals.copy()

    _find_strategy(strategy_id)
    frames = []
    for _, frame in signals.groupby("sym", sort=True):
        ordered = frame.sort_values("date").copy()
        frames.append(_apply_strategy_to_symbol(ordered, strategy_id, custom_strategy))
    return pd.concat(frames, ignore_index=True).sort_values(["sym", "date"]).reset_index(drop=True)


def _apply_strategy_to_symbol(frame: pd.DataFrame, strategy_id: str, custom_strategy: dict[str, Any] | None) -> pd.DataFrame:
    base_score = _base_score(frame)
    if strategy_id == DEFAULT_STRATEGY_ID:
        score = base_score
        position = (score >= 5) & (frame["close"] > frame["sma_20"]) & (frame["rsi_14"] < 78)
        reason = [_scorecard_reason(row, "Scorecard") for _, row in frame.assign(signal_score=score, position=position.astype(int)).iterrows()]
    elif strategy_id == "trend_breakout":
        score = frame["trend_score"].fillna(0) + frame["volume_score"].fillna(0) + frame["donchian_breakout"].fillna(0)
        position = (
            (frame["close"] > frame["sma_200"])
            & (frame["sma_50"] > frame["sma_200"])
            & (frame["macd_hist"] > 0)
            & ((frame["adx_14"] > 22) | (frame["donchian_breakout"] > 0))
        )
        reason = [_simple_reason(row, "Trend breakout", ["SMA trend", "MACD", "ADX/Donchian"]) for _, row in frame.assign(signal_score=score, position=position.astype(int)).iterrows()]
    elif strategy_id == "mean_reversion":
        oversold = (frame["rsi_14"] < 35) | (frame["close"] < frame["bb_lower"]) | (frame["zscore_20"] < -1.5)
        exit_zone = (frame["rsi_14"] > 58) | (frame["close"] > frame["sma_20"])
        raw_position = oversold & (frame["close"] > frame["sma_200"])
        position = raw_position.where(~exit_zone, False)
        score = (50 - frame["rsi_14"].fillna(50)) / 5 - frame["zscore_20"].fillna(0) + frame["volatility_score"].fillna(0)
        reason = [_simple_reason(row, "Mean reversion", ["RSI", "Bollinger/z-score", "SMA 200 filter"]) for _, row in frame.assign(signal_score=score, position=position.astype(int)).iterrows()]
    elif strategy_id == "momentum_rotation":
        score = frame["trend_score"].fillna(0) + frame["momentum_score"].fillna(0) + frame["volume_score"].fillna(0)
        position = (
            (frame["momentum_252_skip_21"] > 0)
            & (frame["momentum_20d"] > 0)
            & (frame["rsi_14"].between(45, 76))
            & (frame["volume_score"] >= 0)
        )
        reason = [_simple_reason(row, "Momentum", ["12-1 momentum", "20D momentum", "RSI/volume"]) for _, row in frame.assign(signal_score=score, position=position.astype(int)).iterrows()]
    elif strategy_id == "low_volatility_trend":
        score = frame["trend_score"].fillna(0) + frame["volatility_score"].fillna(0)
        position = (
            (frame["close"] > frame["sma_50"])
            & (frame["close"] > frame["sma_200"])
            & (frame["realized_vol_20"] <= frame["realized_vol_63"])
            & (frame["atr_pct"] < 0.04)
        )
        reason = [_simple_reason(row, "Low-vol trend", ["SMA trend", "realized vol", "ATR"]) for _, row in frame.assign(signal_score=score, position=position.astype(int)).iterrows()]
    elif strategy_id == CUSTOM_STRATEGY_ID:
        custom = _normalize_custom_strategy(custom_strategy)
        score = base_score
        position = _custom_position(frame, score, custom)
        reason = [_custom_reason(row, custom) for _, row in frame.assign(signal_score=score, position=position.astype(int)).iterrows()]
    else:
        raise ValueError(f"Unknown strategy_id: {strategy_id}")

    frame["signal_score"] = pd.Series(score, index=frame.index).fillna(0).astype(float)
    frame["position"] = pd.Series(position, index=frame.index).fillna(False).astype(int)
    change = frame["position"].diff().fillna(frame["position"])
    frame["trade_signal"] = np.select([change > 0, change < 0], ["BUY", "SELL"], default="HOLD")
    frame["signal_reason"] = reason
    return frame


def _find_strategy(strategy_id: str) -> dict[str, Any]:
    for strategy in STRATEGY_CATALOG:
        if strategy["id"] == strategy_id:
            return strategy
    raise ValueError(f"Unknown strategy_id: {strategy_id}")


def _base_score(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["trend_score"].fillna(0)
        + frame["momentum_score"].fillna(0)
        + frame["volatility_score"].fillna(0)
        + frame["volume_score"].fillna(0)
    )


def _normalize_custom_strategy(custom_strategy: dict[str, Any] | None) -> dict[str, Any]:
    custom = {**DEFAULT_CUSTOM_STRATEGY, **(custom_strategy or {})}
    custom["name"] = str(custom.get("name") or DEFAULT_CUSTOM_STRATEGY["name"])[:80]
    for key in ["min_signal_score", "max_rsi", "min_rsi", "min_adx", "min_momentum_score"]:
        if custom.get(key) in ("", None):
            custom[key] = None if key not in ["min_signal_score", "max_rsi"] else DEFAULT_CUSTOM_STRATEGY[key]
        else:
            custom[key] = float(custom[key])
    for key in ["require_above_sma20", "require_positive_macd"]:
        custom[key] = bool(custom.get(key))
    return custom


def _custom_position(frame: pd.DataFrame, score: pd.Series, custom: dict[str, Any]) -> pd.Series:
    position = score >= custom["min_signal_score"]
    if custom["max_rsi"] is not None:
        position &= frame["rsi_14"] <= custom["max_rsi"]
    if custom["min_rsi"] is not None:
        position &= frame["rsi_14"] >= custom["min_rsi"]
    if custom["require_above_sma20"]:
        position &= frame["close"] > frame["sma_20"]
    if custom["require_positive_macd"]:
        position &= frame["macd_hist"] > 0
    if custom["min_adx"] is not None:
        position &= frame["adx_14"] >= custom["min_adx"]
    if custom["min_momentum_score"] is not None:
        position &= frame["momentum_score"] >= custom["min_momentum_score"]
    return position


def _custom_rule_text(custom: dict[str, Any]) -> str:
    clauses = [f"signal_score >= {custom['min_signal_score']:g}", f"RSI <= {custom['max_rsi']:g}"]
    if custom["min_rsi"] is not None:
        clauses.append(f"RSI >= {custom['min_rsi']:g}")
    if custom["require_above_sma20"]:
        clauses.append("close above SMA 20")
    if custom["require_positive_macd"]:
        clauses.append("MACD histogram positive")
    if custom["min_adx"] is not None:
        clauses.append(f"ADX >= {custom['min_adx']:g}")
    if custom["min_momentum_score"] is not None:
        clauses.append(f"momentum_score >= {custom['min_momentum_score']:g}")
    return "Long when " + ", ".join(clauses) + "; otherwise cash."


def _scorecard_reason(row: pd.Series, label: str) -> str:
    stance = "Long" if int(row["position"]) == 1 else "Cash"
    macd_state = "MACD bullish" if row["macd_hist"] > 0 else "MACD bearish"
    rsi_state = _rsi_state(row["rsi_14"])
    return (
        f"{stance}: {label} score {row['signal_score']:.0f} "
        f"(trend {row['trend_score']:+.0f}, momentum {row['momentum_score']:+.0f}, "
        f"volatility {row['volatility_score']:+.0f}, volume {row['volume_score']:+.0f}); "
        f"{macd_state}; {rsi_state}"
    )


def _simple_reason(row: pd.Series, label: str, checks: list[str]) -> str:
    stance = "Long" if int(row["position"]) == 1 else "Cash"
    return f"{stance}: {label} score {row['signal_score']:.0f}; checks: {', '.join(checks)}; {_rsi_state(row['rsi_14'])}"


def _custom_reason(row: pd.Series, custom: dict[str, Any]) -> str:
    stance = "Long" if int(row["position"]) == 1 else "Cash"
    return f"{stance}: {custom['name']} score {row['signal_score']:.0f}; {_custom_rule_text(custom)}"


def _rsi_state(rsi: float) -> str:
    if rsi > 70:
        return "RSI overbought"
    if rsi < 30:
        return "RSI oversold"
    return "RSI neutral"
