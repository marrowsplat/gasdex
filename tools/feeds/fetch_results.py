#!/usr/bin/env python3
"""
Fetch Bristol Rovers results and fixtures.
Pluggable provider design with fallback to sample data.

Provider order (see docs/data-sources.md for the 2026-07-19 findings):
  1. TheSportsDBProvider — PRIMARY. Free, no key, live current-season data.
     Free tier caps volume (1 last result / 1 next event / partial season list),
     so a rolling history cache (data/results-history.json) accumulates results
     across the ~3-hourly builds until we always have the last 5.
  2. APIFootballProvider — kept for a possible PAID upgrade ($19/mo). The FREE
     tier is useless here: no last/next params and seasons capped at 2022-2024
     (verified 19 Jul 2026 with a real key). Team ID 1334 (verified).
  3. SampleProvider — offline fallback, always works.

Usage:
  python3 tools/feeds/fetch_results.py                 # TheSportsDB, no key needed
  FOOTBALL_API_KEY=... USE_API_FOOTBALL=1 python3 ...  # only useful on a paid plan

Output: data/results.json with schema:
  {"fetched_at": "...Z", "sample": bool, "results": [...], "fixtures": [...]}

NOTE: data/results-history.json is a persistent cache — do NOT delete it casually
(unlike the other data/*.json files it cannot be fully regenerated on demand).
"""

import os
import sys
import json
from datetime import datetime, date
from typing import Optional, Dict, List
from abc import ABC, abstractmethod
import urllib.request
import urllib.error


def get_project_root():
    """Resolve project root from this script's location."""
    current = os.path.dirname(os.path.abspath(__file__))
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "templates", "index.template.html")):
            return current
        current = os.path.dirname(current)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_url(url: str, headers: Optional[Dict] = None, timeout: int = 15) -> Optional[str]:
    """Fetch URL and return decoded text, or None on error."""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_json(url: str, headers: Optional[Dict] = None) -> Optional[Dict]:
    text = fetch_url(url, headers=headers)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ============================================================================
# Data Model
# ============================================================================

class Result:
    """A match result (past game)."""
    def __init__(self, date, opponent, venue, score_for, score_against, outcome, competition):
        self.date = date              # YYYY-MM-DD
        self.opponent = opponent
        self.venue = venue            # "H" or "A"
        self.score_for = score_for
        self.score_against = score_against
        self.outcome = outcome        # "W", "D", "L"
        self.competition = competition

    def to_dict(self):
        return {"date": self.date, "opponent": self.opponent, "venue": self.venue,
                "score_for": self.score_for, "score_against": self.score_against,
                "outcome": self.outcome, "competition": self.competition}


class Fixture:
    """An upcoming fixture (future game)."""
    def __init__(self, date, kickoff, opponent, venue, competition):
        self.date = date              # YYYY-MM-DD
        self.kickoff = kickoff        # HH:MM
        self.opponent = opponent
        self.venue = venue            # "H" or "A"
        self.competition = competition

    def to_dict(self):
        return {"date": self.date, "kickoff": self.kickoff, "opponent": self.opponent,
                "venue": self.venue, "competition": self.competition}


class Provider(ABC):
    @abstractmethod
    def get_results(self, limit: int = 5) -> List[Result]:
        ...

    @abstractmethod
    def get_fixtures(self, limit: int = 5) -> List[Fixture]:
        ...


# ============================================================================
# TheSportsDB Provider (PRIMARY — free, keyless, current data)
# ============================================================================

class TheSportsDBProvider(Provider):
    """
    thesportsdb.com v1 API with the public free key.
    Verified 19 Jul 2026: returned the previous day's friendly and the next
    fixture, plus 2026-27 League Two fixtures via the season endpoint.
    Free-tier caps: eventslast/eventsnext return 1 event; eventsseason ~15 events.
    """

    BASE = "https://www.thesportsdb.com/api/v1/json/123"
    TEAM_ID = 134358        # Bristol Rovers (verified)
    TEAM_NAME = "Bristol Rovers"
    LEAGUE_TWO_ID = 4397    # English League 2 (verified; 4396 is League 1)

    @staticmethod
    def _season_str(today: Optional[date] = None) -> str:
        """English season string, e.g. 2026-2027 (rolls over in June)."""
        d = today or date.today()
        start = d.year if d.month >= 6 else d.year - 1
        return f"{start}-{start + 1}"

    def _event_common(self, e):
        home = e.get("strHomeTeam") or ""
        away = e.get("strAwayTeam") or ""
        is_home = self.TEAM_NAME in home
        opponent = away if is_home else home
        comp = e.get("strLeague") or "Unknown"
        # Normalise competition names for the tight index boxes
        comp = {"English League 2": "League Two",
                "Club Friendlies": "Friendly"}.get(comp, comp)
        return is_home, opponent, comp

    def get_results(self, limit: int = 5) -> List[Result]:
        data = fetch_json(f"{self.BASE}/eventslast.php?id={self.TEAM_ID}")
        events = (data or {}).get("results") or []
        results = []
        for e in events:
            hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
            if hs is None or as_ is None:
                continue
            hs, as_ = int(hs), int(as_)
            is_home, opponent, comp = self._event_common(e)
            score_for, score_against = (hs, as_) if is_home else (as_, hs)
            outcome = "W" if score_for > score_against else ("L" if score_for < score_against else "D")
            results.append(Result(e.get("dateEvent") or "", opponent,
                                  "H" if is_home else "A",
                                  score_for, score_against, outcome, comp))
        return results[:limit]

    def get_fixtures(self, limit: int = 5) -> List[Fixture]:
        fixtures = {}

        def add(e):
            d = e.get("dateEvent") or ""
            if not d or d < date.today().isoformat():
                return
            if e.get("intHomeScore") is not None:   # already played
                return
            is_home, opponent, comp = self._event_common(e)
            kickoff = (e.get("strTime") or "15:00")[:5]
            fixtures[(d, opponent)] = Fixture(d, kickoff, opponent,
                                              "H" if is_home else "A", comp)

        # 1. Next event(s) for the team (free tier: usually 1)
        data = fetch_json(f"{self.BASE}/eventsnext.php?id={self.TEAM_ID}")
        for e in (data or {}).get("events") or []:
            add(e)

        # 2. League Two season schedule, filtered to the team (partial on free tier)
        season = self._season_str()
        data = fetch_json(f"{self.BASE}/eventsseason.php?id={self.LEAGUE_TWO_ID}&s={season}")
        for e in (data or {}).get("events") or []:
            if self.TEAM_NAME in (e.get("strHomeTeam") or "") + (e.get("strAwayTeam") or ""):
                add(e)

        return sorted(fixtures.values(), key=lambda f: (f.date, f.kickoff))[:limit]

    def is_alive(self) -> bool:
        data = fetch_json(f"{self.BASE}/lookupteam.php?id={self.TEAM_ID}")
        teams = (data or {}).get("teams") or []
        return bool(teams and self.TEAM_NAME in (teams[0].get("strTeam") or ""))


# ============================================================================
# API-Football Provider (paid-plan path only — free tier verified unusable)
# ============================================================================

class APIFootballProvider(Provider):
    """
    API-Football (api-sports.io). Requires a PAID plan for current-season data:
    free tier rejects last/next params and caps seasons at 2022-2024 (verified
    19 Jul 2026). Kept as an upgrade path. Enable with USE_API_FOOTBALL=1.
    """

    BASE_URL = "https://v3.football.api-sports.io"
    TEAM_ID = 1334  # Bristol Rovers — VERIFIED via /teams?search= (19 Jul 2026)

    def __init__(self, api_key: str):
        self.headers = {"x-apisports-key": api_key}

    def _fetch(self, endpoint: str, params: Dict = None) -> Optional[List]:
        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        data = fetch_json(url, headers=self.headers)
        if not data:
            return None
        if data.get("errors"):
            print(f"API-Football error: {data['errors']}", file=sys.stderr)
            return None
        return data.get("response", [])

    def _parse(self, match):
        fixture = match.get("fixture", {})
        home = match.get("teams", {}).get("home", {})
        is_home = home.get("id") == self.TEAM_ID
        opp_side = "away" if is_home else "home"
        opponent = match.get("teams", {}).get(opp_side, {}).get("name", "?")
        comp = match.get("league", {}).get("name", "Unknown")
        dt = fixture.get("date", "")
        return fixture, is_home, opponent, comp, dt

    def get_results(self, limit: int = 5) -> List[Result]:
        response = self._fetch("/fixtures", {"team": self.TEAM_ID, "last": limit}) or []
        results = []
        for match in response:
            if match.get("fixture", {}).get("status", {}).get("short") not in ("FT", "AET", "PEN"):
                continue
            fixture, is_home, opponent, comp, dt = self._parse(match)
            goals = match.get("goals", {})
            hg, ag = goals.get("home", 0) or 0, goals.get("away", 0) or 0
            sf, sa = (hg, ag) if is_home else (ag, hg)
            outcome = "W" if sf > sa else ("L" if sf < sa else "D")
            results.append(Result(dt.split("T")[0], opponent, "H" if is_home else "A",
                                  sf, sa, outcome, comp))
        return results

    def get_fixtures(self, limit: int = 5) -> List[Fixture]:
        response = self._fetch("/fixtures", {"team": self.TEAM_ID, "next": limit}) or []
        fixtures = []
        for match in response:
            fixture, is_home, opponent, comp, dt = self._parse(match)
            if not dt:
                continue
            fixtures.append(Fixture(dt.split("T")[0], (dt.split("T")[1] if "T" in dt else "00:00")[:5],
                                    opponent, "H" if is_home else "A", comp))
        return fixtures


# ============================================================================
# Sample Provider (Offline fallback)
# ============================================================================

class SampleProvider(Provider):
    """Realistic July-2026 sample data; used when everything else fails."""

    def get_results(self, limit: int = 5) -> List[Result]:
        sample = [
            Result("2026-07-18", "Portsmouth", "H", 1, 1, "D", "Friendly"),
            Result("2026-07-14", "Oxford City", "A", 1, 1, "D", "Friendly"),
            Result("2026-07-10", "Tiverton Town", "H", 3, 0, "W", "Friendly"),
            Result("2026-07-04", "Yate Town", "A", 2, 0, "W", "Friendly"),
            Result("2026-06-28", "Almondsbury Town", "H", 4, 1, "W", "Friendly"),
        ]
        return sample[:limit]

    def get_fixtures(self, limit: int = 5) -> List[Fixture]:
        sample = [
            Fixture("2026-07-21", "18:00", "Forest Green Rovers", "A", "Friendly"),
            Fixture("2026-08-15", "14:00", "York City", "A", "League Two"),
            Fixture("2026-08-22", "14:00", "Newport County", "H", "League Two"),
        ]
        return sample[:limit]


# ============================================================================
# Rolling history cache — accumulates results across builds so the free tier's
# "1 last result" becomes "last 5" over time.
# ============================================================================

def load_history(path: str) -> Dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"results": {}}


def merge_history(history: Dict, results: List[Result], keep: int = 15) -> List[Dict]:
    """Merge fresh results into history; return newest `keep` as dicts."""
    store = history.setdefault("results", {})
    for r in results:
        store[f"{r.date}|{r.opponent}"] = r.to_dict()
    newest = sorted(store.values(), key=lambda d: d["date"], reverse=True)[:keep]
    history["results"] = {f"{d['date']}|{d['opponent']}": d for d in newest}
    return newest


# ============================================================================
# Main
# ============================================================================

def main():
    project_root = get_project_root()
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    output_file = os.path.join(data_dir, "results.json")
    history_file = os.path.join(data_dir, "results-history.json")

    provider, provider_name, sample = None, "", False

    # Optional paid API-Football path
    api_key = os.environ.get("FOOTBALL_API_KEY")
    if api_key and os.environ.get("USE_API_FOOTBALL") == "1":
        p = APIFootballProvider(api_key)
        if p.get_fixtures(1):
            provider, provider_name = p, "API-Football"
        else:
            print("⚠ API-Football unusable (free tier?); trying TheSportsDB.", file=sys.stderr)

    if not provider:
        p = TheSportsDBProvider()
        if p.is_alive():
            provider, provider_name = p, "TheSportsDB"
        else:
            print("⚠ TheSportsDB unreachable; using sample data.", file=sys.stderr)
            provider, provider_name, sample = SampleProvider(), "sample", True

    fresh_results = provider.get_results(limit=5)
    fixtures = provider.get_fixtures(limit=5)

    if sample:
        results_out = [r.to_dict() for r in fresh_results]
    else:
        # Accumulate through the rolling cache
        history = load_history(history_file)
        results_out = merge_history(history, fresh_results)[:5]
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

    output = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "sample": sample,
        "results": results_out,
        "fixtures": [f.to_dict() for f in fixtures],
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    status = "SAMPLE" if sample else f"LIVE via {provider_name}"
    print(f"✓ [{status}] {len(results_out)} results, {len(fixtures)} fixtures → {output_file}")


if __name__ == "__main__":
    main()
