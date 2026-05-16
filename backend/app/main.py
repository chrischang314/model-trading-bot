from __future__ import annotations

import asyncio
from datetime import date

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import ApiEnvelope, BacktestRequest, IngestRequest, IngestResponse, PaperRequest, SymbolRequest
from app.services.backtest import run_long_cash_backtest
from app.services.data_provider import create_provider
from app.services.paper import run_paper_snapshot
from app.services.signals import SIGNAL_CATALOG, STRATEGY_METADATA, calculate_signals
from app.services.universe import SP500UniverseService
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
universe_service = SP500UniverseService(settings.local_data_dir / "universe" / "sp500.json", settings.sp500_refresh_hours)


@app.on_event("startup")
async def bootstrap() -> None:
    if settings.universe_refresh_on_startup:
        asyncio.create_task(_refresh_universe_periodically())
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
    return ApiEnvelope(data=_available_symbols())


@app.post("/api/symbols", response_model=IngestResponse)
def add_symbols(request: SymbolRequest) -> IngestResponse:
    try:
        return run_ingestion(IngestRequest(symbols=request.symbols, period=request.period))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/strategy", response_model=ApiEnvelope)
def strategy() -> ApiEnvelope:
    return ApiEnvelope(data=STRATEGY_METADATA)


@app.get("/api/signals/catalog", response_model=ApiEnvelope)
def signal_catalog() -> ApiEnvelope:
    return ApiEnvelope(data=SIGNAL_CATALOG)


@app.get("/api/signals/latest", response_model=ApiEnvelope)
def latest_signals(
    symbols: str | None = Query(default=None, description="Comma-separated symbol list. Defaults to ingested/default symbols."),
    limit: int = Query(default=500, ge=1, le=1000),
) -> ApiEnvelope:
    symbol_list = normalize_symbols(symbols.split(",")) if symbols else _available_symbols()
    signals = _signals_or_bootstrap(symbol_list)
    if signals.empty:
        return ApiEnvelope(data=[])
    latest = signals.sort_values("date").groupby("sym", as_index=False).tail(1)
    latest = latest.sort_values(["signal_score", "sym"], ascending=[False, True]).head(limit)
    return ApiEnvelope(data=clean_records(latest))


@app.get("/api/explain/{symbol}", response_model=ApiEnvelope)
def explain(symbol: str) -> ApiEnvelope:
    clean_symbol = normalize_symbols([symbol])[0]
    signals = storage.get_signals(symbols=[clean_symbol])
    if signals.empty and settings.auto_ingest_on_empty:
        run_ingestion(IngestRequest(symbols=[clean_symbol], period="2y"))
        signals = storage.get_signals(symbols=[clean_symbol])
    if signals.empty:
        raise HTTPException(status_code=404, detail=f"No signals available for {clean_symbol}")
    latest = clean_records(signals.sort_values("date").tail(1))[0]
    components = []
    for component in STRATEGY_METADATA["components"]:
        components.append(
            {
                **component,
                "value": latest.get(component["key"]),
            }
        )
    return ApiEnvelope(data={"symbol": clean_symbol, "latest": latest, "components": components, "strategy": STRATEGY_METADATA})


@app.get("/api/universe/sp500", response_model=ApiEnvelope)
def sp500_universe(refresh: bool = False) -> ApiEnvelope:
    try:
        return ApiEnvelope(data=universe_service.get_members(force_refresh=refresh))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/universe/sp500/refresh", response_model=ApiEnvelope)
def refresh_sp500_universe() -> ApiEnvelope:
    try:
        return ApiEnvelope(data=universe_service.refresh())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    try:
        return run_ingestion(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/overview", response_model=ApiEnvelope)
def overview() -> ApiEnvelope:
    symbols = _available_symbols()
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


def _available_symbols() -> list[str]:
    stored_symbols = []
    try:
        stored_symbols = storage.list_symbols()
    except Exception:
        stored_symbols = []
    return normalize_symbols([*settings.default_symbols, *stored_symbols])


async def _refresh_universe_periodically() -> None:
    while True:
        try:
            await asyncio.to_thread(universe_service.get_members, False)
        except Exception:
            pass
        await asyncio.sleep(max(settings.sp500_refresh_hours, 1) * 3600)
