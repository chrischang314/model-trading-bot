from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from app.services.data_provider import BAR_COLUMNS
from app.services.signals import SIGNAL_COLUMNS


class LocalCsvStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.bars_path = self.root / "bars.csv"
        self.signals_path = self.root / "signals.csv"

    def save_bars(self, bars: pd.DataFrame) -> int:
        merged = self._merge(self.bars_path, bars, BAR_COLUMNS, ["date", "sym"])
        return len(merged)

    def save_signals(self, signals: pd.DataFrame) -> int:
        merged = self._merge(self.signals_path, signals, SIGNAL_COLUMNS, ["date", "sym"])
        return len(merged)

    def get_bars(self, symbols: list[str] | None = None, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        return self._read_filtered(self.bars_path, BAR_COLUMNS, symbols, start, end)

    def get_signals(
        self, symbols: list[str] | None = None, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        return self._read_filtered(self.signals_path, SIGNAL_COLUMNS, symbols, start, end)

    def health(self) -> dict:
        return {"backend": "local", "path": str(self.root), "ok": True}

    def _merge(self, path: Path, incoming: pd.DataFrame, columns: list[str], keys: list[str]) -> pd.DataFrame:
        incoming = incoming.copy()
        incoming["date"] = pd.to_datetime(incoming["date"]).dt.strftime("%Y-%m-%d")
        if path.exists():
            existing = pd.read_csv(path)
            merged = pd.concat([existing, incoming[columns]], ignore_index=True)
        else:
            merged = incoming[columns]
        merged = merged.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)
        merged.to_csv(path, index=False)
        return merged

    def _read_filtered(
        self,
        path: Path,
        columns: list[str],
        symbols: list[str] | None,
        start: date | None,
        end: date | None,
    ) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame(columns=columns)
        frame = pd.read_csv(path, parse_dates=["date"])
        if symbols:
            frame = frame[frame["sym"].isin(symbols)]
        if start:
            frame = frame[frame["date"] >= pd.Timestamp(start)]
        if end:
            frame = frame[frame["date"] <= pd.Timestamp(end)]
        return frame.sort_values(["sym", "date"]).reset_index(drop=True)

