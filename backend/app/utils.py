from __future__ import annotations

from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd


def normalize_symbols(symbols: Iterable[str]) -> list[str]:
    normalized = []
    for symbol in symbols:
        clean = symbol.strip().upper()
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized


def clean_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    clean = df.copy()
    for column in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[column]):
            clean[column] = clean[column].dt.strftime("%Y-%m-%d")
        elif clean[column].map(lambda value: isinstance(value, date)).any():
            clean[column] = clean[column].map(lambda value: value.isoformat() if isinstance(value, date) else value)
    clean = clean.replace([np.inf, -np.inf], np.nan)
    clean = clean.astype(object).where(pd.notnull(clean), None)
    return clean.to_dict(orient="records")


def parse_date_column(df: pd.DataFrame) -> pd.DataFrame:
    if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
    return df

