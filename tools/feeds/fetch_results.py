#!/usr/bin/env python3
"""
Fetch Bristol Rovers results and fixtures.
Pluggable provider design with fallback to sample data.

Source policy (settled 22 Jul 2026 after the fixtures accuracy audit — see
DECISIONS.md "fixtures engine" entries for the full rationale):

  1. TheSportsDBProvider — the automated baseline. Free community API,
     explicitly intended for hobby projects, no key needed. Its times are
     served in UTC and are now converted to Europe/London properly (that
     conversion bug was the main cause of wrong kickoff times on the site).
  2. data/fixtures-overrides.json — a SMALL, MAINTAINER-CURATED corrections
     file applied on top of whatever the source returns. It removes phantom
     fixtures, adds competitions the free tier misses (League Cup / Vertu
     Trophy), and corrects club-moved kickoffs (e.g. Newport H 12:30).
     These are plain fixture facts, verified against the official club
     fixture list BY HAND — no automated scraping of any licensed feed.
  3. SampleProvider — offline fallback, always works.

  RESULTS: TheSportsDB → Sample, accumulated through the rolling cache
  data/results-history.json as before.

  AUDIT: every run writes data/fixtures-audit.json (source used, override
  counts, fetch errors). The daily digest reads that file, so a silent
  source outage or a stale overrides file is never invisible.

  Paid upgrade path: APIFootballProvider below (API-Football, api-sports.io)
  is kept dormant — a properly licensed per-user API covering League Two.
  Enable with USE_API_FOOTBALL=1 + FOOTBALL_API_KEY once on a paid plan.

Usage:
  python3 tools/feeds/fetch_results.py                 # normal run
  FOOTBALL_API_KEY=... USE_API_FOOTBALL=1 python3 ...  # paid path

Output: data/results.json with schema:
  {"fetched_at": "...Z", "sample": bool, "fixtures_source": str,
   "results_source": str, "results": [...], "fixtures": [...]}
  Fixture dicts also carry: competition, match_id (ballot slug, e.g.
  "york-city-a-20260815"), tbc. build_site.py ignores the extras.

NOTE: data/results-history.json is a persistent cache — do NOT delete it casually
(unlike the other data/*.json files it cannot be fully regenerated on demand).
"""

import os
import re
import sys
import json
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, List, Tuple
from abc import ABC, abstractmethod
import urllib.request
import urllib.error

LONDON = ZoneInfo("Europe/London")


def get_project_root():
    """Resolve project root from this script's location."""
    current = os.path.dirname(os.path.abspath(__file__))
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "templates", "index.template.html")):
            return current
        current = os.path.dirname(current)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_url(url: str, headers: Optional[Dict] = None, timeout: int = 20) -> Optional[str]:
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
    def __init__(self, date, kickoff, opponent, venue, competition, tbc=False):
        self.date = date              # YYYY-MM-DD (Europe/London)
        self.kickoff = kickoff        # HH:MM (Europe/London)
        self.opponent = opponent
        self.venue = venue            # "H" or "A"
        self.competition = competition
        self.tbc = tbc                # kickoff time still to be confirmed

    @property
    def match_id(self):
        """Ballot slug, e.g. york-city-a-20260815 (see ratings backend)."""
        slug = re.sub(r"[^a-z0-9]+", "-", self.opponent.lower()).strip("-")
        return f"{slug}-{self.venue.lower()}-{self.date.replace('-', '')}"

    def to_dict(self):
        return {"date": self.date, "kickoff": self.kickoff, "opponent": self.opponent,
                "venue": self.venue, "competition": self.competition,
                "match_id": self.match_id, "tbc": self.tbc}


class Provider(ABC):
    @abstractmethod
    def get_results(self, limit: int = 5) -> List[Result]:
        ...

    @abstractmethod
    def get_fixtures(self, limit: int = 5) -> List[Fixture]:
        ...


# ============================================================================
# Shared helpers
# ============================================================================

TEAM_NAME = "Bristol Rovers"

COMPETITION_NAMES = {
    # Normalise for the tight index boxes (tabs must stay one line)
    "English League 2": "League Two",
    "League Two": "League Two",
    "League Cup": "League Cup",
    "EFL Cup": "League Cup",
    "EFL Trophy": "Vertu Trophy",
    "Club Friendlies": "Friendly",
    "Friendly": "Friendly",
    "FA Cup": "FA Cup",
}


def normalise_competition(name: str) -> str:
    return COMPETITION_NAMES.get(name, name or "Unknown")


def clean_team_name(name: str) -> str:
    """'Newport County AFC' -> 'Newport County'; 'Chelsea FC Under 21' -> 'Chelsea U21'."""
    t = (name or "").strip()
    t = t.replace(" FC Under 21", " U21").replace(" Under 21", " U21")
    for suf in (" AFC", " FC"):
        if t.endswith(suf):
            t = t[: -len(suf)]
    return t.strip()


# ============================================================================
# TheSportsDB Provider (baseline source — with proper UK-time conversion)
# ============================================================================

class TheSportsDBProvider(Provider):
    """
    thesportsdb.com v1 API with the public free key. Free-tier caps volume
    (1 last result / 1 next event / partial season list). KNOWN ISSUES found
    22 Jul 2026: serves times in UTC (converted below), can list phantom
    fixtures the club doesn't recognise, misses cup/Trophy games. Those gaps
    are corrected by data/fixtures-overrides.json (see module docstring).
    """

    BASE = "https://www.thesportsdb.com/api/v1/json/123"
    TEAM_ID = 134358        # Bristol Rovers (verified)
    LEAGUE_TWO_ID = 4397    # English League 2 (verified; 4396 is League 1)

    @staticmethod
    def _season_str(today: Optional[date] = None) -> str:
        """English season string, e.g. 2026-2027 (rolls over in June)."""
        d = today or date.today()
        start = d.year if d.month >= 6 else d.year - 1
        return f"{start}-{start + 1}"

    @staticmethod
    def _to_london(date_str: str, time_str: str) -> Tuple[str, str]:
        """TheSportsDB serves UTC; convert to Europe/London for display."""
        try:
            dt = datetime.fromisoformat(f"{date_str}T{(time_str or '15:00:00')[:8]}")
            dt = dt.replace(tzinfo=timezone.utc).astimezone(LONDON)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except Exception:
            return date_str, (time_str or "15:00")[:5]

    def _event_common(self, e):
        home = e.get("strHomeTeam") or ""
        away = e.get("strAwayTeam") or ""
        is_home = TEAM_NAME in home
        opponent = clean_team_name(away if is_home else home)
        comp = normalise_competition(e.get("strLeague") or "Unknown")
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
            if not d or e.get("intHomeScore") is not None:
                return
            is_home, opponent, comp = self._event_common(e)
            ldate, ltime = self._to_london(d, e.get("strTime") or "")
            if ldate < date.today().isoformat():
                return
            fixtures[(ldate, opponent)] = Fixture(ldate, ltime, opponent,
                                                  "H" if is_home else "A", comp)

        # 1. Next event(s) for the team (free tier: usually 1)
        data = fetch_json(f"{self.BASE}/eventsnext.php?id={self.TEAM_ID}")
        for e in (data or {}).get("events") or []:
            add(e)

        # 2. League Two season schedule, filtered to the team (partial on free tier)
        season = self._season_str()
        data = fetch_json(f"{self.BASE}/eventsseason.php?id={self.LEAGUE_TWO_ID}&s={season}")
        for e in (data or {}).get("events") or []:
            if TEAM_NAME in (e.get("strHomeTeam") or "") + (e.get("strAwayTeam") or ""):
                add(e)

        return sorted(fixtures.values(), key=lambda f: (f.date, f.kickoff))[:limit]

    def is_alive(self) -> bool:
        data = fetch_json(f"{self.BASE}/lookupteam.php?id={self.TEAM_ID}")
        teams = (data or {}).get("teams") or []
        return bool(teams and TEAM_NAME in (teams[0].get("strTeam") or ""))


# ============================================================================
# API-Football Provider (paid upgrade path — dormant)
# ============================================================================

class APIFootballProvider(Provider):
    """
    API-Football (api-sports.io). Requires a PAID plan for current-season data:
    free tier rejects last/next params and caps seasons at 2022-2024 (verified
    19 Jul 2026). This is the properly licensed upgrade path if the site takes
    off. Enable with USE_API_FOOTBALL=1 + FOOTBALL_API_KEY.
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
            Result("2026-07-21", "Forest Green Rovers", "A", 0, 0, "D", "Friendly"),
            Result("2026-07-18", "Portsmouth", "H", 1, 1, "D", "Friendly"),
            Result("2026-07-10", "Tiverton Town", "H", 3, 0, "W", "Friendly"),
            Result("2026-07-04", "Yate Town", "A", 2, 0, "W", "Friendly"),
            Result("2026-06-28", "Almondsbury Town", "H", 4, 1, "W", "Friendly"),
        ]
        return sample[:limit]

    def get_fixtures(self, limit: int = 5) -> List[Fixture]:
        sample = [
            Fixture("2026-08-08", "15:00", "Peterborough United", "H", "League Cup"),
            Fixture("2026-08-15", "15:00", "York City", "A", "League Two"),
            Fixture("2026-08-22", "12:30", "Newport County", "H", "League Two"),
        ]
        return sample[:limit]


# ============================================================================
# Overrides — maintainer-curated corrections applied on top of any source.
# data/fixtures-overrides.json schema:
#   {"remove": [{"opponent": "...", "date": "..."}],   # all given fields must match
#    "add":    [{date, kickoff, opponent, venue, competition, tbc?}],
#    "amend":  {"<match_id>": {"kickoff": "12:30", ...}}}
# ============================================================================

def load_overrides(path: str) -> Dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def apply_overrides(fixtures: List[Fixture], overrides: Dict,
                    today: Optional[str] = None) -> Tuple[List[Fixture], Dict]:
    """Apply remove/amend/add corrections. Returns (fixtures, applied-counts)."""
    today = today or date.today().isoformat()
    applied = {"removed": [], "amended": [], "added": []}

    def matches(fx: Fixture, rule: Dict) -> bool:
        checks = []
        if "match_id" in rule:
            checks.append(fx.match_id == rule["match_id"])
        if "opponent" in rule:
            checks.append(rule["opponent"].lower() in fx.opponent.lower())
        if "date" in rule:
            checks.append(fx.date == rule["date"])
        return bool(checks) and all(checks)

    # 1. removes (phantom fixtures the club doesn't recognise)
    for rule in overrides.get("remove") or []:
        keep = []
        for fx in fixtures:
            if matches(fx, rule):
                applied["removed"].append(fx.match_id)
            else:
                keep.append(fx)
        fixtures = keep

    # 2. amends (club-moved kickoffs etc.), keyed by ballot slug
    amends = overrides.get("amend") or {}
    for fx in fixtures:
        rule = amends.get(fx.match_id)
        if rule:
            for field in ("date", "kickoff", "venue", "competition", "tbc"):
                if field in rule:
                    setattr(fx, field, rule[field])
            applied["amended"].append(fx.match_id)

    # 3. adds (competitions the source misses) — replace same-slug duplicates
    existing = {fx.match_id: fx for fx in fixtures}
    for entry in overrides.get("add") or []:
        fx = Fixture(entry["date"], entry.get("kickoff", "15:00"),
                     entry["opponent"], entry["venue"],
                     entry.get("competition", "Unknown"),
                     tbc=entry.get("tbc", False))
        if fx.date < today:
            continue
        if fx.match_id in existing:
            fixtures = [f for f in fixtures if f.match_id != fx.match_id]
        fixtures.append(fx)
        applied["added"].append(fx.match_id)

    fixtures.sort(key=lambda f: (f.date, f.kickoff))
    return fixtures, applied


# ============================================================================
# Rolling history cache — accumulates results across builds so a sparse
# source's "1 last result" becomes "last 5" over time.
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

FIXTURES_KEEP = 5   # how many upcoming fixtures results.json carries


def main():
    project_root = get_project_root()
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    output_file = os.path.join(data_dir, "results.json")
    history_file = os.path.join(data_dir, "results-history.json")
    overrides_file = os.path.join(data_dir, "fixtures-overrides.json")
    audit_file = os.path.join(data_dir, "fixtures-audit.json")

    audit = {"generated_at": datetime.now(timezone.utc).isoformat(),
             "fixtures_source": None, "results_source": None,
             "overrides_applied": {}, "errors": [], "notes": []}

    # Optional paid path (properly licensed per-user API)
    api_key = os.environ.get("FOOTBALL_API_KEY", "")
    use_api_football = os.environ.get("USE_API_FOOTBALL", "") == "1" and api_key
    primary: Provider = APIFootballProvider(api_key) if use_api_football \
        else TheSportsDBProvider()
    primary_name = "api-football" if use_api_football else "thesportsdb"

    # ---- Fixtures (primary source -> overrides -> sample) ----
    sample = False
    src_fx = primary.get_fixtures(limit=50)
    if not src_fx:
        audit["errors"].append(f"{primary_name}: no fixtures returned")
    overrides = load_overrides(overrides_file)
    if not overrides:
        audit["notes"].append("no fixtures-overrides.json found (or unreadable)")
    fixtures, applied = apply_overrides(src_fx, overrides)
    audit["overrides_applied"] = applied

    if fixtures:
        audit["fixtures_source"] = primary_name + ("+overrides" if overrides else "")
    else:
        fixtures = SampleProvider().get_fixtures()
        audit["fixtures_source"] = "sample"
        sample = True

    # ---- Results (primary source -> sample) ----
    fresh_results = primary.get_results(limit=10)
    if fresh_results:
        audit["results_source"] = primary_name
    else:
        fresh_results = SampleProvider().get_results()
        audit["results_source"] = "sample"
        audit["errors"].append(f"{primary_name}: no results returned")

    if audit["results_source"] == "sample":
        results_out = [r.to_dict() for r in fresh_results][:5]
    else:
        history = load_history(history_file)
        results_out = merge_history(history, fresh_results)[:5]
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sample": sample,
        "fixtures_source": audit["fixtures_source"],
        "results_source": audit["results_source"],
        "results": results_out,
        "fixtures": [f.to_dict() for f in fixtures[:FIXTURES_KEEP]],
        # Full upcoming list (uncapped) for the season archive page
        # (out/archive-season.html) — same source + overrides as above.
        "fixtures_all": [f.to_dict() for f in fixtures],
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    with open(audit_file, "w") as f:
        json.dump(audit, f, indent=2)

    status = "SAMPLE" if sample else f"LIVE fixtures:{audit['fixtures_source']} results:{audit['results_source']}"
    ov = audit["overrides_applied"]
    ov_note = (f", overrides -{len(ov.get('removed', []))} "
               f"~{len(ov.get('amended', []))} +{len(ov.get('added', []))}") if ov else ""
    errs = f", errors: {'; '.join(audit['errors'])}" if audit["errors"] else ""
    print(f"✓ [{status}] {len(results_out)} results, {min(len(fixtures), FIXTURES_KEEP)} fixtures → {output_file}{ov_note}{errs}")


if __name__ == "__main__":
    main()
