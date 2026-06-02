from __future__ import annotations

import json
import base64
import hashlib
import hmac
import sqlite3
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PASSWORD_ITERATIONS = 200_000
SESSION_COOKIE_NAME = "projects_lan_session"
SESSION_TTL_DAYS = 30


class UserAlreadyExistsError(ValueError):
    """Raised when registering a username that already has a password."""


class InvalidCredentialsError(ValueError):
    """Raised when username/password authentication fails."""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_username(username: str) -> tuple[str, str]:
    clean = " ".join(username.strip().split())
    if not clean:
        raise ValueError("Username cannot be empty")
    return clean[:80], clean.casefold()


def normalize_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(password) > 1024:
        raise ValueError("Password is too long")
    return password


def _new_salt() -> str:
    return base64.b64encode(secrets.token_bytes(16)).decode("ascii")


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return base64.b64encode(digest).decode("ascii")


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
                    password_hash TEXT,
                    password_salt TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
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
                    requested_symbols_json TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    cash REAL NOT NULL,
                    strategy_id TEXT NOT NULL,
                    custom_strategy_json TEXT,
                    resulting_cash REAL NOT NULL,
                    resulting_equity REAL NOT NULL,
                    positions_json TEXT NOT NULL,
                    orders_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    error_flags_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_model_trading_bot_paper_runs_user_created
                    ON model_trading_bot_paper_runs(user_id, created_at DESC, id DESC);
                """
            )
            self._ensure_user_columns(conn)

    def register_user(self, username: str, password: str, *, allow_legacy_claim: bool = False) -> dict[str, Any]:
        clean, key = normalize_username(username)
        password = normalize_password(password)
        now = utcnow()
        salt = _new_salt()
        password_hash = _hash_password(password, base64.b64decode(salt.encode("ascii")))
        self.init()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username_key = ?", (key,)).fetchone()
            if row is None:
                cursor = conn.execute(
                    """
                    INSERT INTO users (
                        username, username_key, password_hash, password_salt, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (clean, key, password_hash, salt, now, now),
                )
                row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            elif row["password_hash"] is None or row["password_salt"] is None:
                if not allow_legacy_claim:
                    raise UserAlreadyExistsError(
                        "That username already exists. Ask an admin to migrate the legacy account before registering."
                    )
                conn.execute(
                    """
                    UPDATE users
                    SET username = ?, password_hash = ?, password_salt = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean, password_hash, salt, now, row["id"]),
                )
                row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            else:
                raise UserAlreadyExistsError("That username is already registered")
        assert row is not None
        user = self._user(row)
        self.ensure_model_profile(user["id"])
        return user

    def authenticate_user(self, username: str, password: str) -> dict[str, Any]:
        _, key = normalize_username(username)
        password = normalize_password(password)
        self.init()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username_key = ?", (key,)).fetchone()
        if row is None or row["password_hash"] is None or row["password_salt"] is None:
            raise InvalidCredentialsError("Invalid username or password")
        salt = base64.b64decode(str(row["password_salt"]).encode("ascii"))
        candidate = _hash_password(password, salt)
        if not hmac.compare_digest(candidate, str(row["password_hash"])):
            raise InvalidCredentialsError("Invalid username or password")
        user = self._user(row)
        self.ensure_model_profile(user["id"])
        return user

    def create_session(self, user_id: int, ttl_days: int = SESSION_TTL_DAYS) -> str:
        if self.get_user(user_id) is None:
            raise InvalidCredentialsError("User not found")
        self.init()
        token = secrets.token_urlsafe(32)
        created = _utcnow()
        expires = created + timedelta(days=ttl_days)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auth_sessions (user_id, token_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, _token_hash(token), created.isoformat(), expires.isoformat()),
            )
        return token

    def get_user_by_session_token(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        self.init()
        now = utcnow()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT users.*
                FROM auth_sessions
                JOIN users ON users.id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = ?
                  AND auth_sessions.revoked_at IS NULL
                  AND auth_sessions.expires_at > ?
                """,
                (_token_hash(token), now),
            ).fetchone()
        if row is None:
            return None
        user = self._user(row)
        self.ensure_model_profile(user["id"])
        return user

    def revoke_session(self, token: str | None) -> None:
        if not token:
            return
        self.init()
        with self._connect() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ?",
                (utcnow(), _token_hash(token)),
            )

    def get_or_create_user(self, username: str) -> dict[str, Any]:
        clean, key = normalize_username(username)
        now = utcnow()
        self.init()
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
        self.init()
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

    def save_paper_run(
        self,
        user_id: int,
        requested_symbols: list[str],
        snapshot: dict[str, Any],
        cash: float,
        strategy_id: str,
        custom_strategy: dict[str, Any] | None,
    ) -> dict[str, Any]:
        now = utcnow()
        positions = snapshot.get("positions") if isinstance(snapshot.get("positions"), list) else []
        orders = snapshot.get("orders") if isinstance(snapshot.get("orders"), list) else []
        warnings = snapshot.get("warnings") if isinstance(snapshot.get("warnings"), list) else []
        error_flags = snapshot.get("error_flags") if isinstance(snapshot.get("error_flags"), dict) else {}
        raw_custom = json.dumps(custom_strategy, sort_keys=True) if custom_strategy else None
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO model_trading_bot_paper_runs
                (
                    user_id,
                    requested_symbols_json,
                    snapshot_json,
                    cash,
                    strategy_id,
                    custom_strategy_json,
                    resulting_cash,
                    resulting_equity,
                    positions_json,
                    orders_json,
                    warnings_json,
                    error_flags_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    json.dumps(requested_symbols, sort_keys=True),
                    json.dumps(snapshot, sort_keys=True),
                    cash,
                    strategy_id,
                    raw_custom,
                    float(snapshot.get("cash", cash)),
                    float(snapshot.get("equity", cash)),
                    json.dumps(positions, sort_keys=True),
                    json.dumps(orders, sort_keys=True),
                    json.dumps(warnings, sort_keys=True),
                    json.dumps(error_flags, sort_keys=True),
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM model_trading_bot_paper_runs WHERE id = ? AND user_id = ?",
                (cursor.lastrowid, user_id),
            ).fetchone()
        assert row is not None
        return self._paper_run(row, include_detail=True)

    def list_paper_runs(self, user_id: int, limit: int = 25) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM model_trading_bot_paper_runs
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._paper_run(row, include_detail=False) for row in rows]

    def get_paper_run(self, user_id: int, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM model_trading_bot_paper_runs WHERE user_id = ? AND id = ?",
                (user_id, run_id),
            ).fetchone()
        return self._paper_run(row, include_detail=True) if row else None

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
    def _ensure_user_columns(conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        if "password_salt" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")

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
    def _paper_run(row: sqlite3.Row, include_detail: bool) -> dict[str, Any]:
        positions = json.loads(row["positions_json"])
        orders = json.loads(row["orders_json"])
        payload = {
            "id": row["id"],
            "user_id": row["user_id"],
            "created_at": row["created_at"],
            "requested_symbols": json.loads(row["requested_symbols_json"]),
            "cash": row["cash"],
            "strategy_id": row["strategy_id"],
            "custom_strategy": json.loads(row["custom_strategy_json"]) if row["custom_strategy_json"] else None,
            "resulting_cash": row["resulting_cash"],
            "resulting_equity": row["resulting_equity"],
            "order_count": len(orders),
            "position_count": len(positions),
            "warnings": json.loads(row["warnings_json"]),
            "error_flags": json.loads(row["error_flags_json"]),
        }
        if include_detail:
            payload["snapshot"] = json.loads(row["snapshot_json"])
            payload["positions"] = positions
            payload["orders"] = orders
        return payload
