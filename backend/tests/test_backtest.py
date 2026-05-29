from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.services.backtest import run_long_cash_backtest
from app.services.data_provider import MarketDataProviderError, NoMarketDataError
from app.services.signals import calculate_signals


def test_backtest_returns_metrics_equity_and_trades() -> None:
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    close = [100 + i * 0.4 for i in range(120)]
    bars = pd.DataFrame(
        {
            "date": dates,
            "sym": "META",
            "open": close,
            "high": [price + 1 for price in close],
            "low": [price - 1 for price in close],
            "close": close,
            "adj_close": close,
            "volume": 1_000_000,
            "source": "test",
        }
    )
    signals = calculate_signals(bars)

    result = run_long_cash_backtest(signals, initial_capital=10_000)

    assert result.symbol == "META"
    assert "total_return" in result.metrics
    assert "max_drawdown" in result.metrics
    assert not result.equity_curve.empty
    assert result.equity_curve["equity"].iloc[-1] > 0


class CompareFakeStorage:
    def get_signals(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", periods=280, freq="D")
        close = [100 + i * 0.25 for i in range(280)]
        bars = pd.DataFrame(
            {
                "date": dates,
                "sym": symbols[0] if symbols else "AAPL",
                "open": close,
                "high": [price + 1 for price in close],
                "low": [price - 1 for price in close],
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "test",
            }
        )
        return calculate_signals(bars)


class EmptySignalStorage:
    def get_signals(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        return pd.DataFrame()


class CompareFakeAuthStore:
    def get_or_create_user(self, username: str) -> dict:
        return {
            "id": 1,
            "username": username,
            "created_at": "2026-05-21T00:00:00+00:00",
            "updated_at": "2026-05-21T00:00:00+00:00",
        }


def fail_ingestion(request) -> None:
    raise NoMarketDataError("provider returned no rows")


def provider_error(request) -> None:
    raise MarketDataProviderError("upstream timeout")


def test_backtest_compare_endpoint_returns_sorted_strategy_summaries(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "storage", CompareFakeStorage())
    monkeypatch.setattr(main_module, "auth_store", CompareFakeAuthStore())

    response = TestClient(main_module.app).post(
        "/api/backtests/compare",
        json={"symbol": "AAPL", "strategy_ids": ["multi_factor_scorecard", "trend_breakout"], "initial_capital": 10_000},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["symbol"] == "AAPL"
    assert [item["strategy"]["id"] for item in data["comparisons"]] == ["multi_factor_scorecard", "trend_breakout"]
    assert data["comparisons"][0]["final_equity"] > 0
    assert "total_return" in data["comparisons"][0]["metrics"]
    assert "equity_curve" not in data["comparisons"][0]


def test_explain_unknown_symbol_returns_not_found_when_auto_ingest_fails(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "storage", EmptySignalStorage())
    monkeypatch.setattr(main_module, "auth_store", CompareFakeAuthStore())
    monkeypatch.setattr(main_module, "run_ingestion", fail_ingestion)

    response = TestClient(main_module.app).get("/api/explain/NO_SUCH_SYMBOL_123")

    assert response.status_code == 404
    assert "No market data available for NO_SUCH_SYMBOL_123" in response.json()["detail"]


def test_timeseries_unknown_symbol_returns_not_found_when_auto_ingest_fails(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "storage", EmptySignalStorage())
    monkeypatch.setattr(main_module, "auth_store", CompareFakeAuthStore())
    monkeypatch.setattr(main_module, "run_ingestion", fail_ingestion)

    response = TestClient(main_module.app).get("/api/timeseries/NO_SUCH_SYMBOL_123")

    assert response.status_code == 404
    assert "No market data available for NO_SUCH_SYMBOL_123" in response.json()["detail"]


def test_backtest_unknown_symbol_returns_not_found_when_auto_ingest_fails(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "storage", EmptySignalStorage())
    monkeypatch.setattr(main_module, "auth_store", CompareFakeAuthStore())
    monkeypatch.setattr(main_module, "run_ingestion", fail_ingestion)

    response = TestClient(main_module.app).post("/api/backtests", json={"symbol": "NO_SUCH_SYMBOL_123"})

    assert response.status_code == 404
    assert "No market data available for NO_SUCH_SYMBOL_123" in response.json()["detail"]


def test_explain_provider_error_returns_bad_gateway(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "storage", EmptySignalStorage())
    monkeypatch.setattr(main_module, "auth_store", CompareFakeAuthStore())
    monkeypatch.setattr(main_module, "run_ingestion", provider_error)

    response = TestClient(main_module.app).get("/api/explain/AAPL")

    assert response.status_code == 502
    assert "Market data provider failed" in response.json()["detail"]
