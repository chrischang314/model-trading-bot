from __future__ import annotations

from datetime import UTC, datetime
import json

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.services.universe import SP500UniverseService


class FakeStorage:
    def health(self) -> dict:
        return {"backend": "local", "path": "/tmp/model-trading-bot", "ok": True}

    def list_symbols(self) -> list[str]:
        return ["MSFT"]

    def get_bars(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        return self._frame(symbols)

    def get_signals(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        return self._frame(symbols)

    def _frame(self, symbols: list[str] | None) -> pd.DataFrame:
        active_symbols = symbols or ["AAPL"]
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-05-19"] * len(active_symbols)),
                "sym": active_symbols,
            }
        )


class FakeAuthStore:
    def init(self) -> None:
        return None


class FakeUniverseService:
    def cache_status(self) -> dict:
        return {
            "ok": True,
            "path": "/tmp/sp500.json",
            "source": "test",
            "as_of": "2026-05-19T12:00:00+00:00",
            "count": 503,
            "stale": False,
        }


def test_diagnostics_endpoint_reports_operational_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "storage", FakeStorage())
    monkeypatch.setattr(main_module, "auth_store", FakeAuthStore())
    monkeypatch.setattr(main_module, "universe_service", FakeUniverseService())

    response = TestClient(main_module.app).get("/api/diagnostics")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["storage_ok"] is True
    assert data["auth_ok"] is True
    assert data["symbols"]["count"] == 6
    assert "MSFT" in data["symbols"]["items"]
    assert data["signals"]["latest_date"] == "2026-05-19"
    assert data["signals"]["missing_symbols"] == []
    assert data["universe"]["count"] == 503


def test_universe_cache_status_uses_existing_cache_without_refresh(tmp_path) -> None:
    cache_path = tmp_path / "sp500.json"
    cache_path.write_text(
        json.dumps(
            {
                "source": "test-source",
                "as_of": datetime.now(UTC).isoformat(),
                "count": 1,
                "members": [{"symbol": "AAPL", "name": "Apple", "sector": "Tech", "industry": "Devices"}],
            }
        ),
        encoding="utf-8",
    )
    service = SP500UniverseService(cache_path, refresh_hours=24)

    status = service.cache_status()

    assert status["ok"] is True
    assert status["source"] == "test-source"
    assert status["count"] == 1
    assert status["stale"] is False
