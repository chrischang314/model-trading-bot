from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main_module
from app.services.auth import SESSION_COOKIE_NAME, SharedAuthStore
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
    chris = store.register_user("Chris", "correct-horse")
    alex = store.register_user("Alex", "correct-horse")
    monkeypatch.setattr(main_module, "auth_store", store)
    monkeypatch.setattr(main_module, "storage", PaperFakeStorage())
    chris_client = TestClient(main_module.app)
    chris_client.cookies.set(SESSION_COOKIE_NAME, store.create_session(chris["id"]))
    alex_client = TestClient(main_module.app)
    alex_client.cookies.set(SESSION_COOKIE_NAME, store.create_session(alex["id"]))
    anonymous_client = TestClient(main_module.app)

    assert anonymous_client.get("/api/paper/runs").status_code == 401

    first = chris_client.post(
        "/api/paper/run",
        json={"symbols": ["AAPL"], "cash": 50_000, "strategy_id": "multi_factor_scorecard"},
    )
    second = chris_client.post(
        "/api/paper/run",
        json={"symbols": ["AAPL", "MSFT"], "cash": 75_000, "strategy_id": "trend_breakout"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_id = first.json()["data"]["run_id"]
    second_id = second.json()["data"]["run_id"]
    portfolio = chris_client.get("/api/paper/portfolio")
    assert portfolio.status_code == 200
    assert portfolio.json()["data"]["snapshot"]["orders"] == second.json()["data"]["orders"]

    runs = chris_client.get("/api/paper/runs")
    assert runs.status_code == 200
    run_rows = runs.json()["data"]
    assert len(run_rows) == 2
    assert [item["id"] for item in run_rows] == [second_id, first_id]
    assert run_rows[0]["symbols"] == ["AAPL", "MSFT"]
    assert run_rows[0]["strategy_id"] == "trend_breakout"
    assert run_rows[0]["requested_cash"] == 75_000
    assert run_rows[0]["equity"] > 0
    assert run_rows[0]["order_count"] == 2
    assert "snapshot" not in run_rows[0]

    detail = chris_client.get(f"/api/paper/runs/{run_rows[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["snapshot"]["orders"] == second.json()["data"]["orders"]
    assert detail.json()["data"]["symbols"] == ["AAPL", "MSFT"]
    assert detail.json()["data"]["orders"] == second.json()["data"]["orders"]

    assert alex_client.get(f"/api/paper/runs/{run_rows[0]['id']}").status_code == 404
    assert chris_client.get("/api/paper/runs/999999").status_code == 404

    reset = chris_client.post("/api/user/account/reset")

    assert reset.status_code == 200
    assert reset.json()["data"]["paper_portfolio"] is None
    assert chris_client.get("/api/paper/runs").json()["data"] == []
