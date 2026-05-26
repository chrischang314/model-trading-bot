from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    symbols: list[str] | None = None
    start: date | None = None
    end: date | None = None
    period: str = Field(default="2y", description="Provider period when start is omitted.")


class IngestResponse(BaseModel):
    symbols: list[str]
    bars: int
    signals: int
    storage_backend: str


class SymbolRequest(BaseModel):
    symbols: list[str]
    period: str = Field(default="2y", description="Provider period used when adding the symbol.")


class LoginRequest(BaseModel):
    username: str


class CustomStrategyRequest(BaseModel):
    name: str = "Custom scorecard"
    min_signal_score: float = 5.0
    max_rsi: float = 78.0
    min_rsi: float | None = None
    require_above_sma20: bool = True
    require_positive_macd: bool = False
    min_adx: float | None = None
    min_momentum_score: float | None = None


class BacktestRequest(BaseModel):
    symbol: str
    start: date | None = None
    end: date | None = None
    initial_capital: float = 100_000
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    strategy_id: str = "multi_factor_scorecard"
    custom_strategy: CustomStrategyRequest | None = None


class BacktestComparisonRequest(BaseModel):
    symbol: str
    strategy_ids: list[str] | None = Field(default=None, max_length=8)
    start: date | None = None
    end: date | None = None
    initial_capital: float = 100_000
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    custom_strategy: CustomStrategyRequest | None = None


class PaperRequest(BaseModel):
    symbols: list[str] | None = None
    cash: float = 100_000
    strategy_id: str = "multi_factor_scorecard"
    custom_strategy: CustomStrategyRequest | None = None


class SaveStrategyRequest(BaseModel):
    strategy: CustomStrategyRequest


class ResetAccountResponse(BaseModel):
    ok: bool
    data: Any


class ApiEnvelope(BaseModel):
    data: Any
