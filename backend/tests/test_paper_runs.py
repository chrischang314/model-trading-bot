from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.services.auth import SharedAuthStore
from app.services.signals import calculate_signals


class PaperRunStorage:
    def get_signals(self, symbols: list[str] | None = None, start=None, end=None) -> pd.DataFrame:
        symbols = symbols or ["AAPL"]
        frames = []
        for index, symbol in enumerate(symbols):
            dates = pd.date_range("2024-01-01", periods=280, freq="D")
            close = [100 + index * 10 + i * 0.25 for i in range(280)]
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


def test_paper_run_endpoints_are_user_scoped_and_reset(monkeypatch, tmp_path) -> None:
    store = SharedAuthStore(tmp_path / "auth.db")
    store.init()
    first_user = store.get_or_create_user("Chris")
    second_user = store.get_or_create_user("Alex")
    monkeypatch.setattr(main_module, "auth_store", store)
    monkeypatch.setattr(main_module, "storage", PaperRunStorage())
    client = TestClient(main_module.app)

    first_headers = {"X-User-Id": str(first_user["id"])}
    second_headers = {"X-User-Id": str(second_user["id"])}
    first_run = client.post(
        "/api/paper/run",
        headers=first_headers,
        json={"symbols": ["AAPL"], "cash": 100000, "strategy_id": "multi_factor_scorecard"},
    )
    second_run = client.post(
        "/api/paper/run",
        headers=first_headers,
        json={"symbols": ["MSFT"], "cash": 50000, "strategy_id": "trend_breakout"},
    )
    other_run = client.post(
        "/api/paper/run",
        headers=second_headers,
        json={"symbols": ["AAPL"], "cash": 25000, "strategy_id": "multi_factor_scorecard"},
    )

    assert first_run.status_code == 200
    assert second_run.status_code == 200
    assert other_run.status_code == 200

    first_id = first_run.json()["data"]["run_id"]
    second_id = second_run.json()["data"]["run_id"]
    other_id = other_run.json()["data"]["run_id"]
    runs = client.get("/api/paper/runs", headers=first_headers)

    assert runs.status_code == 200
    assert [item["id"] for item in runs.json()["data"]] == [second_id, first_id]
    assert "snapshot" not in runs.json()["data"][0]
    assert runs.json()["data"][0]["symbols"] == ["MSFT"]
    assert runs.json()["data"][0]["order_count"] >= 1

    detail = client.get(f"/api/paper/runs/{first_id}", headers=first_headers)

    assert detail.status_code == 200
    assert detail.json()["data"]["user_id"] == first_user["id"]
    assert detail.json()["data"]["symbols"] == ["AAPL"]
    assert detail.json()["data"]["requested_cash"] == 100000
    assert "positions" in detail.json()["data"]["snapshot"]
    assert client.get(f"/api/paper/runs/{other_id}", headers=first_headers).status_code == 404
    assert client.get("/api/paper/runs/999999", headers=first_headers).status_code == 404

    portfolio = client.get("/api/paper/portfolio", headers=first_headers)

    assert portfolio.status_code == 200
    assert portfolio.json()["data"]["strategy_id"] == "trend_breakout"

    reset = client.post("/api/user/account/reset", headers=first_headers)

    assert reset.status_code == 200
    assert client.get("/api/paper/runs", headers=first_headers).json()["data"] == []
    assert client.get("/api/paper/portfolio", headers=first_headers).json()["data"] is None
