from __future__ import annotations

from app.services.auth import SharedAuthStore


def test_shared_auth_store_reuses_user_and_resets_model_account(tmp_path) -> None:
    store = SharedAuthStore(tmp_path / "auth.db")
    store.init()

    first = store.get_or_create_user("Chris")
    second = store.get_or_create_user(" chris ")

    assert second["id"] == first["id"]
    assert second["username"] == "chris"

    saved = store.save_user_strategy(
        first["id"],
        {
            "name": "RSI guard",
            "min_signal_score": 4,
            "max_rsi": 70,
            "min_rsi": None,
            "require_above_sma20": True,
            "require_positive_macd": False,
            "min_adx": None,
            "min_momentum_score": None,
        },
    )
    store.save_paper_portfolio(
        first["id"],
        {"cash": 1, "equity": 1, "positions": [], "orders": []},
        1,
        "custom_scorecard",
        saved["config"],
    )

    assert store.list_user_strategies(first["id"])[0]["name"] == "RSI guard"
    assert store.get_paper_portfolio(first["id"]) is not None

    reset = store.reset_model_account(first["id"])

    assert reset["strategies"] == []
    assert reset["paper_portfolio"] is None
    assert reset["profile"]["paper_cash"] == 100000


def test_shared_auth_store_keeps_user_scoped_paper_run_history(tmp_path) -> None:
    store = SharedAuthStore(tmp_path / "auth.db")
    store.init()

    chris = store.get_or_create_user("Chris")
    alex = store.get_or_create_user("Alex")
    first_snapshot = {
        "cash": 25000,
        "equity": 100000,
        "positions": [{"sym": "AAPL", "quantity": 10, "last_price": 150, "market_value": 1500}],
        "orders": [{"sym": "AAPL", "side": "BUY", "notional": 1500, "reason": "BUY"}],
    }
    second_snapshot = {
        "cash": 50000,
        "equity": 101500,
        "positions": [],
        "orders": [{"sym": "MSFT", "side": "HOLD_CASH", "notional": 0, "reason": "HOLD"}],
    }

    first = store.save_paper_run(chris["id"], ["AAPL"], first_snapshot, 100000, "multi_factor_scorecard", None)
    second = store.save_paper_run(chris["id"], ["MSFT"], second_snapshot, 100000, "trend_breakout", None)
    store.save_paper_portfolio(chris["id"], second_snapshot, 100000, "trend_breakout", None)

    runs = store.list_paper_runs(chris["id"])

    assert [run["id"] for run in runs] == [second["id"], first["id"]]
    assert runs[0]["requested_symbols"] == ["MSFT"]
    assert runs[0]["resulting_equity"] == 101500
    assert runs[0]["order_count"] == 1
    assert store.get_paper_run(chris["id"], first["id"])["snapshot"] == first_snapshot
    assert store.get_paper_run(alex["id"], first["id"]) is None
    assert store.get_paper_portfolio(chris["id"])["snapshot"] == second_snapshot

    reset = store.reset_model_account(chris["id"])

    assert reset["paper_portfolio"] is None
    assert store.list_paper_runs(chris["id"]) == []
