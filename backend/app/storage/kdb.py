from __future__ import annotations

from datetime import date
import re

import pandas as pd

from app.services.data_provider import BAR_COLUMNS
from app.services.signals import SIGNAL_COLUMNS


_SYMBOL_RE = re.compile(r"^[A-Z0-9._-]+$")


class KdbStorage:
    def __init__(self, host: str, port: int, username: str | None = None, password: str | None = None) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def save_bars(self, bars: pd.DataFrame) -> int:
        frame = bars[BAR_COLUMNS].copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        with self._connection() as q:
            return int(q(".bot.upsertBars", frame).py())

    def save_signals(self, signals: pd.DataFrame) -> int:
        frame = signals[SIGNAL_COLUMNS].copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        with self._connection() as q:
            return int(q(".bot.upsertSignals", frame).py())

    def get_bars(self, symbols: list[str] | None = None, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        return self._query_table("bars", BAR_COLUMNS, symbols, start, end)

    def get_signals(
        self, symbols: list[str] | None = None, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        return self._query_table("signals", SIGNAL_COLUMNS, symbols, start, end)

    def health(self) -> dict:
        with self._connection() as q:
            rows = q("(count bars;count signals)").py()
        return {"backend": "kdb", "host": self.host, "port": self.port, "ok": True, "rows": {"bars": rows[0], "signals": rows[1]}}

    def _connection(self):
        import pykx as kx

        kwargs = {}
        if self.username:
            kwargs["username"] = self.username
        if self.password:
            kwargs["password"] = self.password
        return kx.SyncQConnection(self.host, self.port, **kwargs)

    def _query_table(
        self,
        table: str,
        columns: list[str],
        symbols: list[str] | None,
        start: date | None,
        end: date | None,
    ) -> pd.DataFrame:
        clauses = []
        if symbols:
            safe_symbols = [self._safe_symbol(symbol) for symbol in symbols]
            symbol_list = "`" + "`".join(safe_symbols)
            clauses.append(f"sym in {symbol_list}")
        if start:
            clauses.append(f"date>={self._q_date(start)}")
        if end:
            clauses.append(f"date<={self._q_date(end)}")
        where = "" if not clauses else " where " + ",".join(clauses)
        query = f"select from {table}{where}"
        with self._connection() as q:
            result = q(query).pd()
        if result.empty:
            return pd.DataFrame(columns=columns)
        result["date"] = pd.to_datetime(result["date"])
        return result[columns].sort_values(["sym", "date"]).reset_index(drop=True)

    def _safe_symbol(self, symbol: str) -> str:
        clean = symbol.strip().upper()
        if not _SYMBOL_RE.match(clean):
            raise ValueError(f"Invalid symbol for q query: {symbol}")
        return clean

    def _q_date(self, value: date) -> str:
        return value.isoformat().replace("-", ".")
