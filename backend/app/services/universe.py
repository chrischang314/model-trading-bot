from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup


SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    name: str
    sector: str
    industry: str


class SP500UniverseService:
    def __init__(self, cache_path: Path, refresh_hours: int = 24) -> None:
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.refresh_hours = refresh_hours

    def get_members(self, force_refresh: bool = False) -> dict:
        cached = self._read_cache()
        if force_refresh or not cached or self._is_stale(cached):
            try:
                return self.refresh()
            except Exception:
                if cached:
                    return cached
                raise
        return cached

    def refresh(self) -> dict:
        members = self._fetch_from_wikipedia()
        payload = {
            "source": SP500_WIKI_URL,
            "as_of": datetime.now(UTC).isoformat(),
            "count": len(members),
            "members": [asdict(member) for member in members],
        }
        self.cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _fetch_from_wikipedia(self) -> list[UniverseMember]:
        response = requests.get(
            SP500_WIKI_URL,
            headers={"User-Agent": "model-trading-bot/0.1 educational universe refresh"},
            timeout=30,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="constituents")
        if table is None:
            raise RuntimeError("Unable to find S&P 500 constituents table")

        members: list[UniverseMember] = []
        for row in table.find_all("tr")[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
            if len(cells) < 5:
                continue
            symbol = cells[0].replace(".", "-").upper()
            members.append(
                UniverseMember(
                    symbol=symbol,
                    name=cells[1],
                    sector=cells[2],
                    industry=cells[3],
                )
            )
        if len(members) < 400:
            raise RuntimeError(f"Unexpected S&P 500 constituent count: {len(members)}")
        return sorted(members, key=lambda member: member.symbol)

    def _read_cache(self) -> dict | None:
        if not self.cache_path.exists():
            return None
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _is_stale(self, payload: dict) -> bool:
        raw_as_of = payload.get("as_of")
        if not raw_as_of:
            return True
        try:
            as_of = datetime.fromisoformat(raw_as_of)
        except ValueError:
            return True
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)
        return datetime.now(UTC) - as_of > timedelta(hours=self.refresh_hours)
