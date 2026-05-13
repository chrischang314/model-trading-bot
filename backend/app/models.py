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


class BacktestRequest(BaseModel):
    symbol: str
    start: date | None = None
    end: date | None = None
    initial_capital: float = 100_000
    fee_bps: float = 1.0
    slippage_bps: float = 2.0


class PaperRequest(BaseModel):
    symbols: list[str] | None = None
    cash: float = 100_000


class ApiEnvelope(BaseModel):
    data: Any
