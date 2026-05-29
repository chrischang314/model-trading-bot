from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_username(username: str) -> tuple[str, str]:
    clean = " ".join(username.strip().split())
    if not clean:
        raise ValueError("Username cannot be empty")
    return clean[:80], clean.casefold()


class SharedAuthStore:
    """SQLite-backed local auth and model-trading-bot account store.

    The `users` table is intentionally app-neutral so other local apps can log
    into the same database and receive the same numeric user id.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    username_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_trading_bot_profiles (
                    user_id INTEGER PRIMARY KEY,
                    paper_cash REAL NOT NULL DEFAULT 100000,
                    selected_strategy_id TEXT NOT NULL DEFAULT 'multi_factor_scorecard',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_trading_bot_strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, name)
                );

                CREATE TABLE IF NOT EXISTS model_trading_bot_paper_portfolios (
                    user_id INTEGER PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    cash REAL NOT NULL,
                    strategy_id TEXT NOT NULL,
                    custom_strategy_json TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_trading_bot_paper_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    run_at TEXT NOT NULL,
                    symbols_json TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    custom_strategy_json TEXT,
                    requested_cash REAL NOT NULL,
                    resulting_cash REAL NOT NULL,
                    resulting_equity REAL NOT NULL,
                    positions_json TEXT NOT NULL,
                    orders_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    error_flags_json TEXT NOT NULL DEFAULT '{}',
                    snapshot_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_model_trading_bot_paper_runs_user_at
                ON model_trading_bot_paper_runs (user_id, run_at DESC, id DESC);
                """
            )

    def get_or_create_user(self, username: str) -> dict[str, Any]:
        clean, key = normalize_username(username)
        now = utcnow()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username_key = ?", (key,)).fetchone()
            if row is None:
                cursor = conn.execute(
                    "INSERT INTO users (username, username_key, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (clean, key, now, now),
                )
                row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            elif row["username"] != clean:
                conn.execute("UPDATE users SET username = ?, updated_at = ? WHERE id = ?", (clean, now, row["id"]))
                row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
        assert row is not None
        user = self._user(row)
        self.ensure_model_profile(user["id"])
        return user

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._user(row) if row else None

    def ensure_model_profile(self, user_id: int) -> dict[str, Any]:
        now = utcnow()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM model_trading_bot_profiles WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO model_trading_bot_profiles
                    (user_id, paper_cash, selected_strategy_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, 100000.0, "multi_factor_scorecard", now, now),
                )
                row = conn.execute("SELECT * FROM model_trading_bot_profiles WHERE user_id = ?", (user_id,)).fetchone()
        assert row is not None
        return dict(row)

    def list_user_strategies(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM model_trading_bot_strategies
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._strategy(row) for row in rows]

    def get_user_strategy(self, user_id: int, strategy_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM model_trading_bot_strategies WHERE user_id = ? AND id = ?",
                (user_id, strategy_id),
            ).fetchone()
        return self._strategy(row) if row else None

    def save_user_strategy(self, user_id: int, config: dict[str, Any]) -> dict[str, Any]:
        name = str(config.get("name") or "Custom scorecard").strip()[:80] or "Custom scorecard"
        payload = {**config, "name": name}
        raw = json.dumps(payload, sort_keys=True)
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO model_trading_bot_strategies (user_id, name, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, name) DO UPDATE SET
                    config_json = excluded.config_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, name, raw, now, now),
            )
            row = conn.execute(
                "SELECT * FROM model_trading_bot_strategies WHERE user_id = ? AND name = ?",
                (user_id, name),
            ).fetchone()
        assert row is not None
        return self._strategy(row)

    def delete_user_strategy(self, user_id: int, strategy_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM model_trading_bot_strategies WHERE user_id = ? AND id = ?",
                (user_id, strategy_id),
            )
        return cursor.rowcount > 0

    def save_paper_portfolio(
        self,
        user_id: int,
        snapshot: dict[str, Any],
        cash: float,
        strategy_id: str,
        custom_strategy: dict[str, Any] | None,
    ) -> dict[str, Any]:
        now = utcnow()
        raw_snapshot = json.dumps(snapshot, sort_keys=True)
        raw_custom = json.dumps(custom_strategy, sort_keys=True) if custom_strategy else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO model_trading_bot_paper_portfolios
                (user_id, snapshot_json, cash, strategy_id, custom_strategy_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    snapshot_json = excluded.snapshot_json,
                    cash = excluded.cash,
                    strategy_id = excluded.strategy_id,
                    custom_strategy_json = excluded.custom_strategy_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, raw_snapshot, cash, strategy_id, raw_custom, now),
            )
        return self.get_paper_portfolio(user_id) or {"snapshot": snapshot, "updated_at": now}

    def get_paper_portfolio(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM model_trading_bot_paper_portfolios WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "snapshot": json.loads(row["snapshot_json"]),
            "cash": row["cash"],
            "strategy_id": row["strategy_id"],
            "custom_strategy": json.loads(row["custom_strategy_json"]) if row["custom_strategy_json"] else None,
            "updated_at": row["updated_at"],
        }

    def save_paper_run(
        self,
        user_id: int,
        symbols: list[str],
        snapshot: dict[str, Any],
        requested_cash: float,
        strategy_id: str,
        custom_strategy: dict[str, Any] | None,
    ) -> dict[str, Any]:
        now = utcnow()
        positions = snapshot.get("positions") if isinstance(snapshot.get("positions"), list) else []
        orders = snapshot.get("orders") if isinstance(snapshot.get("orders"), list) else []
        warnings = snapshot.get("warnings") if isinstance(snapshot.get("warnings"), list) else []
        error_flags = snapshot.get("error_flags") if isinstance(snapshot.get("error_flags"), dict) else {}
        resulting_cash = float(snapshot.get("cash", requested_cash))
        resulting_equity = float(snapshot.get("equity", resulting_cash))
        raw_custom = json.dumps(custom_strategy, sort_keys=True) if custom_strategy else None
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO model_trading_bot_paper_runs
                (
                    user_id, run_at, symbols_json, strategy_id, custom_strategy_json,
                    requested_cash, resulting_cash, resulting_equity, positions_json,
                    orders_json, warnings_json, error_flags_json, snapshot_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    now,
                    json.dumps(symbols),
                    strategy_id,
                    raw_custom,
                    requested_cash,
                    resulting_cash,
                    resulting_equity,
                    json.dumps(positions, sort_keys=True),
                    json.dumps(orders, sort_keys=True),
                    json.dumps(warnings, sort_keys=True),
                    json.dumps(error_flags, sort_keys=True),
                    json.dumps(snapshot, sort_keys=True),
                ),
            )
            run_id = int(cursor.lastrowid)
        return self.get_paper_run(user_id, run_id) or {
            "id": run_id,
            "user_id": user_id,
            "run_at": now,
            "symbols": symbols,
            "strategy_id": strategy_id,
            "requested_cash": requested_cash,
            "cash": resulting_cash,
            "equity": resulting_equity,
            "position_count": len(positions),
            "order_count": len(orders),
            "custom_strategy": custom_strategy,
            "positions": positions,
            "orders": orders,
            "warnings": warnings,
            "error_flags": error_flags,
            "snapshot": snapshot,
        }

    def list_paper_runs(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 50))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM model_trading_bot_paper_runs
                WHERE user_id = ?
                ORDER BY run_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, safe_limit),
            ).fetchall()
        return [self._paper_run_summary(row) for row in rows]

    def get_paper_run(self, user_id: int, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM model_trading_bot_paper_runs WHERE user_id = ? AND id = ?",
                (user_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return {
            **self._paper_run_summary(row),
            "custom_strategy": json.loads(row["custom_strategy_json"]) if row["custom_strategy_json"] else None,
            "positions": json.loads(row["positions_json"]),
            "orders": json.loads(row["orders_json"]),
            "warnings": json.loads(row["warnings_json"]),
            "error_flags": json.loads(row["error_flags_json"]),
            "snapshot": json.loads(row["snapshot_json"]),
        }

    def reset_model_account(self, user_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("DELETE FROM model_trading_bot_profiles WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM model_trading_bot_strategies WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM model_trading_bot_paper_portfolios WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM model_trading_bot_paper_runs WHERE user_id = ?", (user_id,))
        self.ensure_model_profile(user_id)
        return self.user_state(user_id)

    def user_state(self, user_id: int) -> dict[str, Any]:
        return {
            "profile": self.ensure_model_profile(user_id),
            "strategies": self.list_user_strategies(user_id),
            "paper_portfolio": self.get_paper_portfolio(user_id),
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _user(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _strategy(row: sqlite3.Row) -> dict[str, Any]:
        config = json.loads(row["config_json"])
        return {
            "id": row["id"],
            "strategy_id": f"user_strategy_{row['id']}",
            "user_id": row["user_id"],
            "name": row["name"],
            "label": row["name"],
            "config": config,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _paper_run_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "run_at": row["run_at"],
            "symbols": json.loads(row["symbols_json"]),
            "strategy_id": row["strategy_id"],
            "requested_cash": row["requested_cash"],
            "cash": row["resulting_cash"],
            "equity": row["resulting_equity"],
            "position_count": len(json.loads(row["positions_json"])),
            "order_count": len(json.loads(row["orders_json"])),
            "warnings": json.loads(row["warnings_json"]),
            "error_flags": json.loads(row["error_flags_json"]),
        }
