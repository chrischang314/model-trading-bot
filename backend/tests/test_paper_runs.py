from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.services.auth import SharedAuthStore
from app.services.signals import calculate_signals


class PaperFakeStorage:
    def get_signals(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        frames = []
        for index, symbol in enumerate(symbols or ["AAPL"]):
            dates = pd.date_range("2024-01-01", periods=280, freq="D")
            close = [100 + index * 10 + step * 0.25 for step in range(280)]
            bars = pd.DataFrame(
                {
                    "date": dates,
                    "sym": symbol,
                    "open": close,
                    "high": [price + 1 for price in close],
                    "low": [price - 1 for price in close],
                    "close": close,
                    "adj_close": close,
                    "volume": 1_000_000,
                    "source": "test",
                }
            )
            frames.append(calculate_signals(bars))
        return pd.concat(frames, ignore_index=True)


def test_paper_run_api_lists_details_and_scopes_users(monkeypatch, tmp_path) -> None:
    store = SharedAuthStore(tmp_path / "auth.db")
    store.init()
    chris = store.get_or_create_user("Chris")
    alex = store.get_or_create_user("Alex")
    monkeypatch.setattr(main_module, "auth_store", store)
    monkeypatch.setattr(main_module, "storage", PaperFakeStorage())
    client = TestClient(main_module.app)
    chris_headers = {"X-User-Id": str(chris["id"])}
    alex_headers = {"X-User-Id": str(alex["id"])}

    first = client.post(
        "/api/paper/run",
        headers=chris_headers,
        json={"symbols": ["AAPL"], "cash": 50_000, "strategy_id": "multi_factor_scorecard"},
    )
    second = client.post(
        "/api/paper/run",
        headers=chris_headers,
        json={"symbols": ["AAPL", "MSFT"], "cash": 75_000, "strategy_id": "trend_breakout"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    portfolio = client.get("/api/paper/portfolio", headers=chris_headers)
    assert portfolio.status_code == 200
    assert portfolio.json()["data"]["snapshot"] == second.json()["data"]

    runs = client.get("/api/paper/runs", headers=chris_headers)
    assert runs.status_code == 200
    run_rows = runs.json()["data"]
    assert len(run_rows) == 2
    assert run_rows[0]["requested_symbols"] == ["AAPL", "MSFT"]
    assert run_rows[0]["strategy_id"] == "trend_breakout"
    assert run_rows[0]["resulting_equity"] > 0
    assert run_rows[0]["order_count"] == 2

    detail = client.get(f"/api/paper/runs/{run_rows[0]['id']}", headers=chris_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["snapshot"] == second.json()["data"]
    assert detail.json()["data"]["orders"] == second.json()["data"]["orders"]

    assert client.get(f"/api/paper/runs/{run_rows[0]['id']}", headers=alex_headers).status_code == 404
    assert client.get("/api/paper/runs/999999", headers=chris_headers).status_code == 404

    reset = client.post("/api/user/account/reset", headers=chris_headers)

    assert reset.status_code == 200
    assert reset.json()["data"]["paper_portfolio"] is None
    assert client.get("/api/paper/runs", headers=chris_headers).json()["data"] == []
