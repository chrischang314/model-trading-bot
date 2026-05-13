from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import ApiEnvelope, BacktestRequest, IngestRequest, IngestResponse, PaperRequest
from app.services.backtest import run_long_cash_backtest
from app.services.data_provider import create_provider
from app.services.paper import run_paper_snapshot
from app.services.signals import calculate_signals
from app.storage import create_storage
from app.utils import clean_records, normalize_symbols


app = FastAPI(title="Model Trading Bot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

provider = create_provider(settings.data_provider)
storage = create_storage(settings)


@app.on_event("startup")
def bootstrap() -> None:
    if settings.bootstrap_on_startup:
        try:
            run_ingestion(IngestRequest(symbols=list(settings.default_symbols), period="2y"))
        except Exception:
            pass


@app.get("/health")
def health() -> dict:
    status = {"app": settings.app_name, "storage_backend": settings.storage_backend}
    try:
        status["storage"] = storage.health()
    except Exception as exc:
        status["storage"] = {"ok": False, "error": str(exc)}
    return status


@app.get("/api/symbols", response_model=ApiEnvelope)
def symbols() -> ApiEnvelope:
    return ApiEnvelope(data=list(settings.default_symbols))


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    try:
        return run_ingestion(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/overview", response_model=ApiEnvelope)
def overview() -> ApiEnvelope:
    symbols = list(settings.default_symbols)
    signals = _signals_or_bootstrap(symbols)
    bars = storage.get_bars(symbols=symbols)
    if signals.empty or bars.empty:
        return ApiEnvelope(data=[])

    latest_signals = signals.sort_values("date").groupby("sym", as_index=False).tail(1)
    latest_bars = bars.sort_values("date").groupby("sym", as_index=False).tail(1)
    first_bars = bars.sort_values("date").groupby("sym", as_index=False).head(1)[["sym", "close"]].rename(
        columns={"close": "first_close"}
    )
    merged = latest_signals.merge(latest_bars[["sym", "volume", "source"]], on="sym", how="left").merge(
        first_bars, on="sym", how="left"
    )
    merged["period_return"] = merged["close"] / merged["first_close"] - 1
    return ApiEnvelope(data=clean_records(merged.drop(columns=["first_close"])))


@app.get("/api/timeseries/{symbol}", response_model=ApiEnvelope)
def timeseries(symbol: str, start: date | None = None, end: date | None = None) -> ApiEnvelope:
    clean_symbol = normalize_symbols([symbol])[0]
    signals = storage.get_signals(symbols=[clean_symbol], start=start, end=end)
    if signals.empty and settings.auto_ingest_on_empty:
        run_ingestion(IngestRequest(symbols=[clean_symbol], period="2y"))
        signals = storage.get_signals(symbols=[clean_symbol], start=start, end=end)
    return ApiEnvelope(data=clean_records(signals))


@app.post("/api/backtests", response_model=ApiEnvelope)
def backtest(request: BacktestRequest) -> ApiEnvelope:
    symbol = normalize_symbols([request.symbol])[0]
    signals = storage.get_signals(symbols=[symbol], start=request.start, end=request.end)
    if signals.empty and settings.auto_ingest_on_empty:
        run_ingestion(IngestRequest(symbols=[symbol], start=request.start, end=request.end))
        signals = storage.get_signals(symbols=[symbol], start=request.start, end=request.end)
    try:
        result = run_long_cash_backtest(
            signals,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiEnvelope(
        data={
            "symbol": result.symbol,
            "metrics": result.metrics,
            "equity_curve": clean_records(result.equity_curve),
            "trades": clean_records(result.trades),
        }
    )


@app.post("/api/paper/run", response_model=ApiEnvelope)
def paper(request: PaperRequest) -> ApiEnvelope:
    symbols = normalize_symbols(request.symbols or settings.default_symbols)
    signals = _signals_or_bootstrap(symbols)
    return ApiEnvelope(data=run_paper_snapshot(signals, request.cash))


def run_ingestion(request: IngestRequest) -> IngestResponse:
    symbols = normalize_symbols(request.symbols or settings.default_symbols)
    bars = provider.fetch_daily_bars(symbols, start=request.start, end=request.end, period=request.period)
    bars_count = storage.save_bars(bars)

    stored_bars = storage.get_bars(symbols=symbols)
    signals = calculate_signals(stored_bars)
    signals_count = storage.save_signals(signals)
    return IngestResponse(
        symbols=symbols,
        bars=bars_count,
        signals=signals_count,
        storage_backend=settings.storage_backend,
    )


def _signals_or_bootstrap(symbols: list[str]) -> pd.DataFrame:
    signals = storage.get_signals(symbols=symbols)
    if signals.empty and settings.auto_ingest_on_empty:
        run_ingestion(IngestRequest(symbols=symbols, period="2y"))
        signals = storage.get_signals(symbols=symbols)
    return signals

