from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd


class MarketDataStorage(Protocol):
    def save_bars(self, bars: pd.DataFrame) -> int:
        ...

    def save_signals(self, signals: pd.DataFrame) -> int:
        ...

    def get_bars(self, symbols: list[str] | None = None, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        ...

    def get_signals(
        self, symbols: list[str] | None = None, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        ...

    def list_symbols(self) -> list[str]:
        ...

    def health(self) -> dict:
        ...
