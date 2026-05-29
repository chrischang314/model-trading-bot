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
            close = [100 + index * 10 + day * 0.25 for day in range(280)]
            frames.append(
                pd.DataFrame(
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
            )
        return calculate_signals(pd.concat(frames, ignore_index=True))


def test_paper_run_journal_api_appends_scopes_and_resets(monkeypatch, tmp_path) -> None:
    store = SharedAuthStore(tmp_path / "auth.db")
    store.init()
    chris = store.get_or_create_user("Chris")
    other = store.get_or_create_user("Dana")
    monkeypatch.setattr(main_module, "auth_store", store)
    monkeypatch.setattr(main_module, "storage", PaperFakeStorage())

    client = TestClient(main_module.app)
    headers = {"X-User-Id": str(chris["id"])}

    first = client.post(
        "/api/paper/run",
        headers=headers,
        json={"symbols": ["AAPL", "META"], "cash": 50000, "strategy_id": "trend_breakout"},
    )
    second = client.post(
        "/api/paper/run",
        headers=headers,
        json={"symbols": ["MSFT"], "cash": 75000, "strategy_id": "multi_factor_scorecard"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    latest = client.get("/api/paper/portfolio", headers=headers).json()["data"]
    assert latest["snapshot"]["equity"] == second.json()["data"]["equity"]

    runs_response = client.get("/api/paper/runs", headers=headers)
    assert runs_response.status_code == 200
    runs = runs_response.json()["data"]
    assert [run["symbols"] for run in runs] == [["MSFT"], ["AAPL", "META"]]
    assert runs[0]["requested_cash"] == 75000
    assert runs[0]["order_count"] == 1
    assert "snapshot" not in runs[0]

    detail_response = client.get(f"/api/paper/runs/{runs[1]['id']}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["symbols"] == ["AAPL", "META"]
    assert detail["snapshot"]["orders"]
    assert detail["strategy_id"] == "trend_breakout"

    cross_user_response = client.get(f"/api/paper/runs/{runs[1]['id']}", headers={"X-User-Id": str(other["id"])})
    assert cross_user_response.status_code == 404

    reset_response = client.post("/api/user/account/reset", headers=headers)
    assert reset_response.status_code == 200
    assert reset_response.json()["data"]["paper_portfolio"] is None
    assert client.get("/api/paper/runs", headers=headers).json()["data"] == []
