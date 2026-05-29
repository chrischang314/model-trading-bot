from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd
import requests

from app.utils import normalize_symbols


BAR_COLUMNS = ["date", "sym", "open", "high", "low", "close", "adj_close", "volume", "source"]


class MarketDataProviderError(RuntimeError):
    pass


class NoMarketDataError(MarketDataProviderError):
    pass


class MarketDataProvider(Protocol):
    def fetch_daily_bars(
        self,
        symbols: list[str],
        start: date | None = None,
        end: date | None = None,
        period: str = "2y",
    ) -> pd.DataFrame:
        ...


class YFinanceProvider:
    source = "yfinance"

    def fetch_daily_bars(
        self,
        symbols: list[str],
        start: date | None = None,
        end: date | None = None,
        period: str = "2y",
    ) -> pd.DataFrame:
        import yfinance as yf

        tickers = normalize_symbols(symbols)
        kwargs: dict = {
            "tickers": tickers,
            "interval": "1d",
            "group_by": "ticker",
            "auto_adjust": False,
            "progress": False,
            "threads": True,
        }
        if start:
            kwargs["start"] = start.isoformat()
            if end:
                kwargs["end"] = end.isoformat()
        else:
            kwargs["period"] = period

        raw = yf.download(**kwargs)
        if raw.empty:
            raise NoMarketDataError("yfinance returned no rows")
        frames = [self._normalize_symbol_frame(raw, symbol) for symbol in tickers]
        bars = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
        if bars.empty:
            raise NoMarketDataError("yfinance response did not contain requested symbols")
        return bars[BAR_COLUMNS].sort_values(["sym", "date"]).reset_index(drop=True)

    def _normalize_symbol_frame(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if isinstance(raw.columns, pd.MultiIndex):
            first_level = set(raw.columns.get_level_values(0))
            second_level = set(raw.columns.get_level_values(1))
            if symbol in first_level:
                frame = raw[symbol].copy()
            elif symbol in second_level:
                frame = raw.xs(symbol, level=1, axis=1).copy()
            else:
                return pd.DataFrame(columns=BAR_COLUMNS)
        else:
            frame = raw.copy()

        frame = frame.reset_index()
        date_column = "Date" if "Date" in frame.columns else frame.columns[0]
        rename = {
            date_column: "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
        frame = frame.rename(columns=rename)
        if "adj_close" not in frame.columns:
            frame["adj_close"] = frame["close"]
        frame["sym"] = symbol
        frame["source"] = self.source
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame["volume"] = frame["volume"].fillna(0).astype("int64")
        return frame.dropna(subset=["close"])[BAR_COLUMNS]


class StooqProvider:
    source = "stooq"

    def fetch_daily_bars(
        self,
        symbols: list[str],
        start: date | None = None,
        end: date | None = None,
        period: str = "2y",
    ) -> pd.DataFrame:
        frames = [self._fetch_symbol(symbol, start, end) for symbol in normalize_symbols(symbols)]
        bars = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
        if bars.empty:
            raise NoMarketDataError("Stooq returned no rows")
        return bars[BAR_COLUMNS].sort_values(["sym", "date"]).reset_index(drop=True)

    def _fetch_symbol(self, symbol: str, start: date | None, end: date | None) -> pd.DataFrame:
        stooq_symbol = symbol.lower()
        if "." not in stooq_symbol:
            stooq_symbol = f"{stooq_symbol}.us"
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        from io import StringIO

        frame = pd.read_csv(StringIO(response.text))
        if frame.empty or "Date" not in frame.columns:
            return pd.DataFrame(columns=BAR_COLUMNS)
        frame = frame.rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        if start:
            frame = frame[frame["date"] >= pd.Timestamp(start)]
        if end:
            frame = frame[frame["date"] <= pd.Timestamp(end)]
        if not start and period.endswith("y"):
            years = int(period[:-1])
            frame = frame[frame["date"] >= pd.Timestamp.today().normalize() - pd.DateOffset(years=years)]
        frame["sym"] = symbol.upper()
        frame["adj_close"] = frame["close"]
        frame["source"] = self.source
        frame["volume"] = frame["volume"].fillna(0).astype("int64")
        return frame.dropna(subset=["close"])[BAR_COLUMNS]


class FallbackProvider:
    def __init__(self) -> None:
        self.providers = [YFinanceProvider(), StooqProvider()]

    def fetch_daily_bars(
        self,
        symbols: list[str],
        start: date | None = None,
        end: date | None = None,
        period: str = "2y",
    ) -> pd.DataFrame:
        errors = []
        no_data_errors = []
        for provider in self.providers:
            try:
                return provider.fetch_daily_bars(symbols, start=start, end=end, period=period)
            except NoMarketDataError as exc:
                errors.append(f"{provider.source}: {exc}")
                no_data_errors.append(exc)
            except Exception as exc:  # pragma: no cover - depends on external providers
                errors.append(f"{provider.source}: {exc}")
        detail = "; ".join(errors)
        if len(no_data_errors) == len(self.providers):
            raise NoMarketDataError(detail)
        raise MarketDataProviderError(detail)


def create_provider(name: str) -> MarketDataProvider:
    if name == "stooq":
        return StooqProvider()
    if name == "yfinance":
        return FallbackProvider()
    if name == "fallback":
        return FallbackProvider()
    raise ValueError(f"Unknown data provider: {name}")
