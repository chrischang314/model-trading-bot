from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.main as main_module
from app.services.auth import (
    SESSION_COOKIE_NAME,
    InvalidCredentialsError,
    SharedAuthStore,
    UserAlreadyExistsError,
)


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


def test_register_rejects_legacy_username_only_user_by_default(tmp_path) -> None:
    db_path = tmp_path / "auth.db"
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                username_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO users (username, username_key, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("Chris Chang", "chris chang", now, now),
        )

    store = SharedAuthStore(db_path)
    try:
        store.register_user("Chris Chang", "correct-horse")
    except UserAlreadyExistsError:
        pass
    else:
        raise AssertionError("expected legacy username-only registration to require admin migration")


def test_register_can_claim_legacy_username_only_user_when_enabled(tmp_path) -> None:
    db_path = tmp_path / "auth.db"
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                username_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO users (username, username_key, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("Chris Chang", "chris chang", now, now),
        )

    store = SharedAuthStore(db_path)
    registered = store.register_user("Chris Chang", "correct-horse", allow_legacy_claim=True)
    authenticated = store.authenticate_user("chris chang", "correct-horse")

    assert registered["id"] == 1
    assert authenticated["id"] == 1
    try:
        store.register_user("Chris Chang", "another-password")
    except UserAlreadyExistsError:
        pass
    else:
        raise AssertionError("expected duplicate registration to fail")


def test_shared_auth_store_sessions_resolve_and_revoke(tmp_path) -> None:
    store = SharedAuthStore(tmp_path / "auth.db")
    user = store.register_user("Chris", "correct-horse")

    token = store.create_session(user["id"])

    assert store.get_user_by_session_token(token)["username"] == "Chris"
    store.revoke_session(token)
    assert store.get_user_by_session_token(token) is None
    try:
        store.authenticate_user("Chris", "wrong-password")
    except InvalidCredentialsError:
        pass
    else:
        raise AssertionError("expected bad password to fail")


def test_auth_api_sets_projects_lan_session_cookie_and_logout_revokes(monkeypatch, tmp_path) -> None:
    store = SharedAuthStore(tmp_path / "auth.db")
    monkeypatch.setattr(main_module, "auth_store", store)
    client = TestClient(main_module.app)

    registered = client.post("/api/auth/register", json={"username": "Chris", "password": "correct-horse"})

    assert registered.status_code == 200
    assert registered.json()["data"]["user"]["username"] == "Chris"
    assert SESSION_COOKIE_NAME in client.cookies
    cookie = registered.headers["set-cookie"]
    assert SESSION_COOKIE_NAME in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert client.get("/api/auth/me").json()["data"]["user"]["username"] == "Chris"

    assert client.post("/api/auth/login", json={"username": "Chris", "password": "wrong-password"}).status_code == 401

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    logged_in = client.post("/api/auth/login", json={"username": "Chris", "password": "correct-horse"})

    assert logged_in.status_code == 200
    assert client.get("/api/auth/me").json()["data"]["user"]["username"] == "Chris"
