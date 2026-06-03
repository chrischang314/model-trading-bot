from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.services.data_provider import MarketDataProviderError, NoMarketDataError
from app.services.ingest_runs import IngestRunStore


def bars_for(symbol: str, source: str = "test") -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=280, freq="D")
    close = [100 + i * 0.2 for i in range(280)]
    return pd.DataFrame(
        {
            "date": dates,
            "sym": symbol,
            "open": close,
            "high": [price + 1 for price in close],
            "low": [price - 1 for price in close],
            "close": close,
            "adj_close": close,
            "volume": 1_000_000,
            "source": source,
        }
    )


class RecordingStorage:
    def __init__(self) -> None:
        self.bars = pd.DataFrame()
        self.signals = pd.DataFrame()

    def save_bars(self, bars: pd.DataFrame) -> int:
        self.bars = bars.copy()
        return len(self.bars)

    def save_signals(self, signals: pd.DataFrame) -> int:
        self.signals = signals.copy()
        return len(self.signals)

    def get_bars(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        if self.bars.empty or not symbols:
            return self.bars
        return self.bars[self.bars["sym"].isin(symbols)].reset_index(drop=True)

    def get_signals(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        if self.signals.empty or not symbols:
            return self.signals
        return self.signals[self.signals["sym"].isin(symbols)].reset_index(drop=True)

    def list_symbols(self) -> list[str]:
        if self.bars.empty:
            return []
        return sorted(self.bars["sym"].dropna().astype(str).unique())

    def health(self) -> dict:
        return {"backend": "test", "ok": True}


class PartialProvider:
    def fetch_daily_bars(self, symbols, start=None, end=None, period="2y"):
        return bars_for("AAPL", source="partial-provider")


class NoDataProvider:
    def fetch_daily_bars(self, symbols, start=None, end=None, period="2y"):
        raise NoMarketDataError("provider returned no rows")


class FailingProvider:
    def fetch_daily_bars(self, symbols, start=None, end=None, period="2y"):
        raise MarketDataProviderError("provider timeout")


def test_ingest_run_store_keeps_newest_first_and_bounded(tmp_path) -> None:
    store = IngestRunStore(tmp_path / "ingest_runs.json", max_runs=2)

    store.record({"id": "old", "status": "success"})
    store.record({"id": "middle", "status": "partial"})
    store.record({"id": "new", "status": "failure"})

    assert [run["id"] for run in store.list_runs(limit=10)] == ["new", "middle"]
    assert store.latest()["id"] == "new"


def test_ingest_endpoint_records_partial_provider_outcome(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main_module, "storage", RecordingStorage())
    monkeypatch.setattr(main_module, "provider", PartialProvider())
    monkeypatch.setattr(main_module, "ingest_run_store", IngestRunStore(tmp_path / "ingest_runs.json"))

    response = TestClient(main_module.app).post(
        "/api/ingest",
        json={"symbols": ["AAPL", "MSFT"], "period": "1y"},
    )

    assert response.status_code == 200
    runs = TestClient(main_module.app).get("/api/ingest/runs").json()["data"]
    assert runs[0]["status"] == "partial"
    assert runs[0]["trigger"] == "manual"
    assert runs[0]["requested_symbols"] == ["AAPL", "MSFT"]
    assert runs[0]["no_data_symbols"] == ["MSFT"]
    assert runs[0]["sources"] == ["partial-provider"]
    assert runs[0]["source_counts"]["partial-provider"] == 280
    assert runs[0]["bars_written"] == 280
    assert runs[0]["signals_written"] > 0
    assert runs[0]["duration_ms"] >= 0


def test_symbol_auto_ingest_records_no_data_without_changing_404(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main_module, "storage", RecordingStorage())
    monkeypatch.setattr(main_module, "provider", NoDataProvider())
    monkeypatch.setattr(main_module, "ingest_run_store", IngestRunStore(tmp_path / "ingest_runs.json"))

    response = TestClient(main_module.app).get("/api/timeseries/NO_SUCH_SYMBOL_123")

    assert response.status_code == 404
    runs = TestClient(main_module.app).get("/api/ingest/runs").json()["data"]
    assert runs[0]["status"] == "failure"
    assert runs[0]["trigger"] == "auto_symbol"
    assert runs[0]["no_data_symbols"] == ["NO_SUCH_SYMBOL_123"]
    assert runs[0]["error_type"] == "NoMarketDataError"


def test_ingest_endpoint_records_provider_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main_module, "storage", RecordingStorage())
    monkeypatch.setattr(main_module, "provider", FailingProvider())
    monkeypatch.setattr(main_module, "ingest_run_store", IngestRunStore(tmp_path / "ingest_runs.json"))

    response = TestClient(main_module.app).post("/api/ingest", json={"symbols": ["AAPL"], "period": "1y"})

    assert response.status_code == 502
    runs = TestClient(main_module.app).get("/api/ingest/runs").json()["data"]
    assert runs[0]["status"] == "failure"
    assert runs[0]["trigger"] == "manual"
    assert runs[0]["error_type"] == "MarketDataProviderError"
    assert runs[0]["error_summary"] == "provider timeout"
