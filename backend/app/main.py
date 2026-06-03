from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import (
    ApiEnvelope,
    BacktestComparisonRequest,
    BacktestRequest,
    IngestRequest,
    IngestResponse,
    LoginRequest,
    PaperRequest,
    SaveStrategyRequest,
    SymbolRequest,
)
from app.services.auth import (
    SESSION_COOKIE_NAME,
    InvalidCredentialsError,
    SharedAuthStore,
    UserAlreadyExistsError,
)
from app.services.backtest import run_long_cash_backtest
from app.services.data_provider import MarketDataProviderError, NoMarketDataError, create_provider
from app.services.paper import run_paper_snapshot
from app.services.signals import SIGNAL_CATALOG, calculate_signals
from app.services.strategies import CUSTOM_STRATEGY_ID, DEFAULT_STRATEGY_ID, apply_strategy, get_strategy_metadata, list_strategies
from app.services.universe import SP500UniverseService
from app.storage import create_storage
from app.utils import clean_records, normalize_symbols


DATA_STALE_AFTER_DAYS = 3

app = FastAPI(title="Model Trading Bot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

provider = create_provider(settings.data_provider)
storage = create_storage(settings)
auth_store = SharedAuthStore(settings.shared_auth_db)
universe_service = SP500UniverseService(settings.local_data_dir / "universe" / "sp500.json", settings.sp500_refresh_hours)


def _current_user_optional(request: Request) -> dict | None:
    return auth_store.get_user_by_session_token(request.cookies.get(SESSION_COOKIE_NAME))


def _current_user_required(request: Request) -> dict:
    user = _current_user_optional(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in before using this account-scoped endpoint.")
    return user


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=60 * 60 * 24 * settings.auth_session_ttl_days,
        httponly=True,
        samesite="lax",
        path="/",
        domain=settings.auth_cookie_domain,
        secure=settings.auth_cookie_secure,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        domain=settings.auth_cookie_domain,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _strategy_context(
    strategy_id: str = Query(default=DEFAULT_STRATEGY_ID),
    custom_name: str = Query(default="Custom scorecard"),
    min_signal_score: float = Query(default=5.0),
    max_rsi: float = Query(default=78.0),
    min_rsi: float | None = Query(default=None),
    require_above_sma20: bool = Query(default=True),
    require_positive_macd: bool = Query(default=False),
    min_adx: float | None = Query(default=None),
    min_momentum_score: float | None = Query(default=None),
    current_user: dict | None = Depends(_current_user_optional),
) -> tuple[str, dict | None]:
    custom_strategy = None
    if strategy_id.startswith("user_strategy_"):
        if current_user is None:
            raise HTTPException(status_code=401, detail="Sign in before using a saved strategy.")
        try:
            saved_strategy_id = int(strategy_id.removeprefix("user_strategy_"))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown saved strategy: {strategy_id}") from exc
        saved = auth_store.get_user_strategy(current_user["id"], saved_strategy_id)
        if not saved:
            raise HTTPException(status_code=404, detail=f"Unknown saved strategy: {strategy_id}")
        return CUSTOM_STRATEGY_ID, saved["config"]
    if strategy_id == "custom_scorecard":
        custom_strategy = {
            "name": custom_name,
            "min_signal_score": min_signal_score,
            "max_rsi": max_rsi,
            "min_rsi": min_rsi,
            "require_above_sma20": require_above_sma20,
            "require_positive_macd": require_positive_macd,
            "min_adx": min_adx,
            "min_momentum_score": min_momentum_score,
        }
    return strategy_id, custom_strategy


@app.on_event("startup")
async def bootstrap() -> None:
    auth_store.init()
    if settings.universe_refresh_on_startup:
        asyncio.create_task(_refresh_universe_periodically())
    if settings.bootstrap_on_startup:
        try:
            run_ingestion(IngestRequest(symbols=list(settings.default_symbols), period="2y"))
        except Exception:
            pass


@app.get("/health")
def health() -> dict:
    return _health_snapshot()


@app.get("/api/diagnostics", response_model=ApiEnvelope)
def diagnostics() -> ApiEnvelope:
    return ApiEnvelope(data=_diagnostics_snapshot())


def _health_snapshot() -> dict:
    status = {"app": settings.app_name, "storage_backend": settings.storage_backend}
    try:
        status["storage"] = storage.health()
    except Exception as exc:
        status["storage"] = {"ok": False, "error": str(exc)}
    try:
        auth_store.init()
        status["auth"] = {"ok": True, "db": str(settings.shared_auth_db)}
    except Exception as exc:
        status["auth"] = {"ok": False, "error": str(exc)}
    return status


def _diagnostics_snapshot() -> dict:
    health_status = _health_snapshot()
    symbols = _available_symbols()
    generated_at = datetime.now(UTC)
    return {
        "app": settings.app_name,
        "generated_at": generated_at.isoformat(),
        "storage_ok": bool(health_status.get("storage", {}).get("ok")),
        "auth_ok": bool(health_status.get("auth", {}).get("ok")),
        "health": health_status,
        "symbols": {"count": len(symbols), "items": symbols},
        "bars": _storage_frame_diagnostics(lambda: storage.get_bars(symbols=symbols), symbols, generated_at.date()),
        "signals": _storage_frame_diagnostics(lambda: storage.get_signals(symbols=symbols), symbols, generated_at.date()),
        "universe": universe_service.cache_status(),
    }


def _auth_payload(user: dict) -> dict:
    return {"user": user, **auth_store.user_state(user["id"])}


@app.post("/api/auth/login", response_model=ApiEnvelope)
def auth_login(request: LoginRequest, response: Response) -> ApiEnvelope:
    try:
        user = auth_store.authenticate_user(request.username, request.password)
        _set_session_cookie(response, auth_store.create_session(user["id"], settings.auth_session_ttl_days))
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiEnvelope(data=_auth_payload(user))


@app.post("/api/auth/register", response_model=ApiEnvelope)
def auth_register(request: LoginRequest, response: Response) -> ApiEnvelope:
    try:
        user = auth_store.register_user(
            request.username,
            request.password,
            allow_legacy_claim=settings.auth_allow_legacy_password_claim,
        )
        _set_session_cookie(response, auth_store.create_session(user["id"], settings.auth_session_ttl_days))
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiEnvelope(data=_auth_payload(user))


@app.post("/api/auth/logout", response_model=ApiEnvelope)
def auth_logout(request: Request, response: Response) -> ApiEnvelope:
    auth_store.revoke_session(request.cookies.get(SESSION_COOKIE_NAME))
    _clear_session_cookie(response)
    return ApiEnvelope(data={"ok": True})


@app.get("/api/auth/me", response_model=ApiEnvelope)
def auth_me(current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    return ApiEnvelope(data=_auth_payload(current_user))


@app.get("/api/user/state", response_model=ApiEnvelope)
def user_state(current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    return ApiEnvelope(data=_auth_payload(current_user))


@app.get("/api/user/strategies", response_model=ApiEnvelope)
def user_strategies(current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    return ApiEnvelope(data=[_saved_strategy_metadata(item) for item in auth_store.list_user_strategies(current_user["id"])])


@app.post("/api/user/strategies", response_model=ApiEnvelope)
def save_user_strategy(request: SaveStrategyRequest, current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    saved = auth_store.save_user_strategy(current_user["id"], request.strategy.model_dump())
    return ApiEnvelope(data=_saved_strategy_metadata(saved))


@app.delete("/api/user/strategies/{strategy_id}", response_model=ApiEnvelope)
def delete_user_strategy(strategy_id: int, current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    deleted = auth_store.delete_user_strategy(current_user["id"], strategy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved strategy not found")
    return ApiEnvelope(data={"ok": True, "strategies": auth_store.list_user_strategies(current_user["id"])})


@app.post("/api/user/account/reset", response_model=ApiEnvelope)
def reset_user_account(current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    return ApiEnvelope(data={"user": current_user, **auth_store.reset_model_account(current_user["id"])})


@app.get("/api/symbols", response_model=ApiEnvelope)
def symbols() -> ApiEnvelope:
    return ApiEnvelope(data=_available_symbols())


@app.post("/api/symbols", response_model=IngestResponse)
def add_symbols(request: SymbolRequest) -> IngestResponse:
    try:
        return run_ingestion(IngestRequest(symbols=request.symbols, period=request.period))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/strategies", response_model=ApiEnvelope)
def strategies(current_user: dict | None = Depends(_current_user_optional)) -> ApiEnvelope:
    saved = [_saved_strategy_metadata(item) for item in auth_store.list_user_strategies(current_user["id"])] if current_user else []
    return ApiEnvelope(data=[*list_strategies(), *saved])


@app.get("/api/strategy", response_model=ApiEnvelope)
def strategy(strategy_context: tuple[str, dict | None] = Depends(_strategy_context)) -> ApiEnvelope:
    strategy_id, custom_strategy = strategy_context
    try:
        return ApiEnvelope(data=get_strategy_metadata(strategy_id, custom_strategy))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/signals/catalog", response_model=ApiEnvelope)
def signal_catalog() -> ApiEnvelope:
    return ApiEnvelope(data=SIGNAL_CATALOG)


@app.get("/api/signals/latest", response_model=ApiEnvelope)
def latest_signals(
    symbols: str | None = Query(default=None, description="Comma-separated symbol list. Defaults to ingested/default symbols."),
    limit: int = Query(default=500, ge=1, le=1000),
    strategy_context: tuple[str, dict | None] = Depends(_strategy_context),
) -> ApiEnvelope:
    strategy_id, custom_strategy = strategy_context
    symbol_list = normalize_symbols(symbols.split(",")) if symbols else _available_symbols()
    signals = _signals_or_bootstrap(symbol_list, strategy_id, custom_strategy)
    if signals.empty:
        return ApiEnvelope(data=[])
    latest = signals.sort_values("date").groupby("sym", as_index=False).tail(1)
    latest = latest.sort_values(["signal_score", "sym"], ascending=[False, True]).head(limit)
    return ApiEnvelope(data=clean_records(latest))


@app.get("/api/explain/{symbol}", response_model=ApiEnvelope)
def explain(symbol: str, strategy_context: tuple[str, dict | None] = Depends(_strategy_context)) -> ApiEnvelope:
    strategy_id, custom_strategy = strategy_context
    clean_symbol = normalize_symbols([symbol])[0]
    signals = storage.get_signals(symbols=[clean_symbol])
    if signals.empty and settings.auto_ingest_on_empty:
        _run_auto_ingestion_or_404([clean_symbol], IngestRequest(symbols=[clean_symbol], period="2y"))
        signals = storage.get_signals(symbols=[clean_symbol])
    if signals.empty:
        _raise_no_market_data([clean_symbol])
    signals = apply_strategy(signals, strategy_id, custom_strategy)
    latest = clean_records(signals.sort_values("date").tail(1))[0]
    components = []
    strategy_metadata = get_strategy_metadata(strategy_id, custom_strategy)
    for component in strategy_metadata["components"]:
        components.append(
            {
                **component,
                "value": latest.get(component["key"]),
            }
        )
    return ApiEnvelope(data={"symbol": clean_symbol, "latest": latest, "components": components, "strategy": strategy_metadata})


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
def overview(strategy_context: tuple[str, dict | None] = Depends(_strategy_context)) -> ApiEnvelope:
    strategy_id, custom_strategy = strategy_context
    symbols = _available_symbols()
    signals = _signals_or_bootstrap(symbols, strategy_id, custom_strategy)
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
def timeseries(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    strategy_context: tuple[str, dict | None] = Depends(_strategy_context),
) -> ApiEnvelope:
    strategy_id, custom_strategy = strategy_context
    clean_symbol = normalize_symbols([symbol])[0]
    signals = storage.get_signals(symbols=[clean_symbol], start=start, end=end)
    if signals.empty and settings.auto_ingest_on_empty:
        _run_auto_ingestion_or_404([clean_symbol], IngestRequest(symbols=[clean_symbol], period="2y"))
        signals = storage.get_signals(symbols=[clean_symbol], start=start, end=end)
    if signals.empty:
        _raise_no_market_data([clean_symbol])
    signals = apply_strategy(signals, strategy_id, custom_strategy)
    return ApiEnvelope(data=clean_records(signals))


@app.post("/api/backtests", response_model=ApiEnvelope)
def backtest(request: BacktestRequest, current_user: dict | None = Depends(_current_user_optional)) -> ApiEnvelope:
    _, signals = _load_backtest_signals(request.symbol, request.start, request.end)
    custom_strategy = request.custom_strategy.model_dump() if request.custom_strategy else None
    try:
        return ApiEnvelope(
            data=_backtest_payload(
                signals,
                request.strategy_id,
                custom_strategy,
                current_user,
                request.initial_capital,
                request.fee_bps,
                request.slippage_bps,
                include_details=True,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/backtests/compare", response_model=ApiEnvelope)
def compare_backtests(request: BacktestComparisonRequest, current_user: dict | None = Depends(_current_user_optional)) -> ApiEnvelope:
    symbol, signals = _load_backtest_signals(request.symbol, request.start, request.end)
    requested_ids = request.strategy_ids or [item["id"] for item in list_strategies() if item["kind"] == "built_in"]
    strategy_ids = list(dict.fromkeys(strategy_id.strip() for strategy_id in requested_ids if strategy_id.strip()))
    if not strategy_ids:
        raise HTTPException(status_code=400, detail="Choose at least one strategy to compare.")
    if len(strategy_ids) > 8:
        raise HTTPException(status_code=400, detail="Compare up to 8 strategies at a time.")

    custom_strategy = request.custom_strategy.model_dump() if request.custom_strategy else None
    comparisons = []
    try:
        for strategy_id in strategy_ids:
            comparisons.append(
                _backtest_payload(
                    signals,
                    strategy_id,
                    custom_strategy if strategy_id == CUSTOM_STRATEGY_ID else None,
                    current_user,
                    request.initial_capital,
                    request.fee_bps,
                    request.slippage_bps,
                    include_details=False,
                )
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ApiEnvelope(
        data={
            "symbol": symbol,
            "comparisons": sorted(comparisons, key=lambda item: item["metrics"].get("total_return") or 0, reverse=True),
        }
    )


def _load_backtest_signals(symbol: str, start: date | None, end: date | None) -> tuple[str, pd.DataFrame]:
    clean_symbol = normalize_symbols([symbol])[0]
    signals = storage.get_signals(symbols=[clean_symbol], start=start, end=end)
    if signals.empty and settings.auto_ingest_on_empty:
        _run_auto_ingestion_or_404([clean_symbol], IngestRequest(symbols=[clean_symbol], start=start, end=end))
        signals = storage.get_signals(symbols=[clean_symbol], start=start, end=end)
    if signals.empty:
        _raise_no_market_data([clean_symbol])
    return clean_symbol, signals


def _backtest_payload(
    signals: pd.DataFrame,
    strategy_id: str,
    custom_strategy: dict | None,
    current_user: dict | None,
    initial_capital: float,
    fee_bps: float,
    slippage_bps: float,
    include_details: bool,
) -> dict:
    resolved_strategy_id, resolved_custom_strategy, metadata = _resolve_requested_strategy(strategy_id, custom_strategy, current_user)
    result = run_long_cash_backtest(
        apply_strategy(signals, resolved_strategy_id, resolved_custom_strategy),
        initial_capital=initial_capital,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )
    payload = {
        "symbol": result.symbol,
        "metrics": result.metrics,
        "strategy": metadata,
    }
    if include_details:
        payload["equity_curve"] = clean_records(result.equity_curve)
        payload["trades"] = clean_records(result.trades)
    else:
        payload["final_equity"] = float(result.equity_curve["equity"].iloc[-1])
        payload["trade_count"] = int(len(result.trades))
    return payload


@app.post("/api/paper/run", response_model=ApiEnvelope)
def paper(request: PaperRequest, current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    symbols = normalize_symbols(request.symbols or settings.default_symbols)
    custom_strategy = request.custom_strategy.model_dump() if request.custom_strategy else None
    strategy_id, custom_strategy, _ = _resolve_requested_strategy(request.strategy_id, custom_strategy, current_user)
    signals = _signals_or_bootstrap(symbols, strategy_id, custom_strategy)
    snapshot = run_paper_snapshot(signals, request.cash)
    auth_store.save_paper_portfolio(current_user["id"], snapshot, request.cash, request.strategy_id, custom_strategy)
    run = auth_store.save_paper_run(current_user["id"], symbols, snapshot, request.cash, request.strategy_id, custom_strategy)
    return ApiEnvelope(data={**snapshot, "run_id": run["id"], "run_at": run["run_at"]})


@app.get("/api/paper/portfolio", response_model=ApiEnvelope)
def paper_portfolio(current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    return ApiEnvelope(data=auth_store.get_paper_portfolio(current_user["id"]))


@app.get("/api/paper/runs", response_model=ApiEnvelope)
def paper_runs(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: dict = Depends(_current_user_required),
) -> ApiEnvelope:
    return ApiEnvelope(data=auth_store.list_paper_runs(current_user["id"], limit=limit))


@app.get("/api/paper/runs/{run_id}", response_model=ApiEnvelope)
def paper_run_detail(run_id: int, current_user: dict = Depends(_current_user_required)) -> ApiEnvelope:
    run = auth_store.get_paper_run(current_user["id"], run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Paper run not found")
    return ApiEnvelope(data=run)


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


def _signals_or_bootstrap(
    symbols: list[str],
    strategy_id: str = DEFAULT_STRATEGY_ID,
    custom_strategy: dict | None = None,
) -> pd.DataFrame:
    signals = storage.get_signals(symbols=symbols)
    if signals.empty and settings.auto_ingest_on_empty:
        run_ingestion(IngestRequest(symbols=symbols, period="2y"))
        signals = storage.get_signals(symbols=symbols)
    return apply_strategy(signals, strategy_id, custom_strategy)


def _run_auto_ingestion_or_404(symbols: list[str], request: IngestRequest) -> None:
    try:
        run_ingestion(request)
    except NoMarketDataError as exc:
        _raise_no_market_data(symbols, exc)
    except MarketDataProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Market data provider failed: {exc}") from exc


def _raise_no_market_data(symbols: list[str], exc: Exception | None = None) -> None:
    symbol_text = ", ".join(symbols)
    detail = f"No market data available for {symbol_text}."
    if exc is not None:
        detail = f"{detail} Provider detail: {exc}"
    raise HTTPException(status_code=404, detail=detail)


def _available_symbols() -> list[str]:
    stored_symbols = []
    try:
        stored_symbols = storage.list_symbols()
    except Exception:
        stored_symbols = []
    return normalize_symbols([*settings.default_symbols, *stored_symbols])


def _freshness_fields(latest_date: str | None, reference_date: date) -> dict:
    if not latest_date:
        return {"age_days": None, "stale": True}
    latest = date.fromisoformat(latest_date)
    age_days = max((reference_date - latest).days, 0)
    return {"age_days": age_days, "stale": age_days > DATA_STALE_AFTER_DAYS}


def _storage_frame_diagnostics(load_frame, symbols: list[str], reference_date: date | None = None) -> dict:
    reference = reference_date or datetime.now(UTC).date()
    try:
        frame = load_frame()
    except Exception as exc:
        return {
            "ok": False,
            "rows": 0,
            "symbols": 0,
            "latest_date": None,
            "missing_symbols": symbols,
            "age_days": None,
            "stale": True,
            "error": str(exc),
        }
    if frame.empty:
        return {
            "ok": True,
            "rows": 0,
            "symbols": 0,
            "latest_date": None,
            "missing_symbols": symbols,
            "age_days": None,
            "stale": True,
        }

    present_symbols = sorted(frame["sym"].dropna().astype(str).str.upper().unique()) if "sym" in frame.columns else []
    latest_date = None
    if "date" in frame.columns:
        latest_raw = pd.to_datetime(frame["date"], errors="coerce").max()
        if not pd.isna(latest_raw):
            latest_date = latest_raw.date().isoformat()
    return {
        "ok": True,
        "rows": int(len(frame)),
        "symbols": len(present_symbols),
        "latest_date": latest_date,
        "missing_symbols": sorted(set(symbols) - set(present_symbols)),
        **_freshness_fields(latest_date, reference),
    }


def _saved_strategy_metadata(saved: dict) -> dict:
    metadata = get_strategy_metadata(CUSTOM_STRATEGY_ID, saved["config"])
    metadata["id"] = saved["strategy_id"]
    metadata["name"] = saved["name"]
    metadata["label"] = saved["label"]
    metadata["kind"] = "custom"
    metadata["saved_strategy_id"] = saved["id"]
    metadata["updated_at"] = saved["updated_at"]
    return metadata


def _resolve_requested_strategy(
    strategy_id: str,
    custom_strategy: dict | None,
    current_user: dict | None,
) -> tuple[str, dict | None, dict]:
    if strategy_id.startswith("user_strategy_"):
        if current_user is None:
            raise HTTPException(status_code=401, detail="Sign in before using a saved strategy.")
        try:
            saved_strategy_id = int(strategy_id.removeprefix("user_strategy_"))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown saved strategy: {strategy_id}") from exc
        saved = auth_store.get_user_strategy(current_user["id"], saved_strategy_id)
        if not saved:
            raise HTTPException(status_code=404, detail=f"Unknown saved strategy: {strategy_id}")
        return CUSTOM_STRATEGY_ID, saved["config"], _saved_strategy_metadata(saved)
    try:
        return strategy_id, custom_strategy, get_strategy_metadata(strategy_id, custom_strategy)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _refresh_universe_periodically() -> None:
    while True:
        try:
            await asyncio.to_thread(universe_service.get_members, False)
        except Exception:
            pass
        await asyncio.sleep(max(settings.sp500_refresh_hours, 1) * 3600)
