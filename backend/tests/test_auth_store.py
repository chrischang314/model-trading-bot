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
    first_run = store.save_paper_run(
        first["id"],
        ["AAPL"],
        {"cash": 99_000, "equity": 100_500, "positions": [{"sym": "AAPL"}], "orders": [{"sym": "AAPL"}]},
        100_000,
        "custom_scorecard",
        saved["config"],
    )
    second_run = store.save_paper_run(
        first["id"],
        ["MSFT"],
        {"cash": 100_000, "equity": 100_000, "positions": [], "orders": [{"sym": "MSFT"}], "warnings": ["cash only"]},
        100_000,
        "multi_factor_scorecard",
        None,
    )
    other_user = store.get_or_create_user("Alex")
    store.save_paper_run(
        other_user["id"],
        ["AAPL"],
        {"cash": 50_000, "equity": 50_000, "positions": [], "orders": []},
        50_000,
        "multi_factor_scorecard",
        None,
    )

    assert store.list_user_strategies(first["id"])[0]["name"] == "RSI guard"
    assert store.get_paper_portfolio(first["id"]) is not None
    assert store.get_paper_portfolio(first["id"])["cash"] == 1
    assert [run["id"] for run in store.list_paper_runs(first["id"])] == [second_run["id"], first_run["id"]]
    assert store.list_paper_runs(first["id"])[0]["warnings"] == ["cash only"]
    assert store.get_paper_run(first["id"], first_run["id"])["positions"] == [{"sym": "AAPL"}]
    assert store.get_paper_run(other_user["id"], first_run["id"]) is None

    reset = store.reset_model_account(first["id"])

    assert reset["strategies"] == []
    assert reset["paper_portfolio"] is None
    assert reset["profile"]["paper_cash"] == 100000
    assert store.list_paper_runs(first["id"]) == []
