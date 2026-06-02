from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_symbols(raw: str | None) -> tuple[str, ...]:
    value = raw or "AAPL,AMZN,META,NFLX,GOOGL"
    return tuple(symbol.strip().upper() for symbol in value.split(",") if symbol.strip())


def _split_csv(raw: str | None, default: str) -> tuple[str, ...]:
    value = raw or default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "model-trading-bot"
    default_symbols: tuple[str, ...] = _split_symbols(os.getenv("DEFAULT_SYMBOLS"))
    data_provider: str = os.getenv("DATA_PROVIDER", "yfinance").lower()
    storage_backend: str = os.getenv("STORAGE_BACKEND", "local").lower()
    kdb_host: str = os.getenv("KDB_HOST", "localhost")
    kdb_port: int = int(os.getenv("KDB_PORT", "5000"))
    kdb_username: str | None = os.getenv("KDB_USERNAME")
    kdb_password: str | None = os.getenv("KDB_PASSWORD")
    local_data_dir: Path = Path(os.getenv("LOCAL_DATA_DIR", "data")).resolve()
    shared_auth_db: Path = Path(os.getenv("SHARED_AUTH_DB", str(Path.home() / ".local-webapps" / "auth.db"))).expanduser().resolve()
    auth_cookie_domain: str | None = os.getenv("AUTH_COOKIE_DOMAIN") or None
    auth_cookie_secure: bool = _bool_env("AUTH_COOKIE_SECURE", False)
    auth_session_ttl_days: int = int(os.getenv("AUTH_SESSION_TTL_DAYS", "30"))
    auth_allow_legacy_password_claim: bool = _bool_env("AUTH_ALLOW_LEGACY_PASSWORD_CLAIM", False)
    cors_origins: tuple[str, ...] = _split_csv(
        os.getenv("CORS_ORIGINS"),
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080,http://modeltradingbot.lan",
    )
    bootstrap_on_startup: bool = _bool_env("BOOTSTRAP_ON_STARTUP", False)
    auto_ingest_on_empty: bool = _bool_env("AUTO_INGEST_ON_EMPTY", True)
    sp500_refresh_hours: int = int(os.getenv("SP500_REFRESH_HOURS", "24"))
    universe_refresh_on_startup: bool = _bool_env("UNIVERSE_REFRESH_ON_STARTUP", True)


settings = Settings()
