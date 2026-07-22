# Data sources — results & fixtures

> **CORRECTION (19 Jul 2026, tested with a real key):** the recommendation below
> is SUPERSEDED. API-Football's FREE tier cannot serve current-season data:
> the `last`/`next` parameters are paid-only and seasons are capped at 2022-2024.
> **Adopted solution: TheSportsDB** (free public key, no signup) — verified live
> for Bristol Rovers (team 134358) incl. 2026-27 League Two (league 4397).
> Free-tier volume caps are worked around with a rolling cache
> (`data/results-history.json`) that accumulates results across builds.
> API-Football remains the upgrade path if paid ($19/mo, team ID 1334 verified);
> enable with `USE_API_FOOTBALL=1` + `FOOTBALL_API_KEY`.
> Original research retained below for reference.

Research date: July 2026. Target: Bristol Rovers EFL League Two results and fixtures.
Use case: Static site rebuild every ~3 hours, needs last 5 results + next 5 fixtures.

## Executive Summary

**RECOMMENDATION (Primary): API-Football** (api-sports.io)
- Free tier: 100 req/day, covers League Two, all endpoints
- Paid: $19/month, no practical limits
- Reliable, well-maintained, includes League Two out of the box
- Best cost/benefit for low-volume fan site

**RECOMMENDATION (Fallback): football-data.org**
- Free: 12 major leagues only (no League Two)
- Paid: €49/month gets 25 leagues with live data (confirms League Two coverage)
- High reliability, but costs more; use only if API-Football fails repeatedly

---

## API Comparison Table

| Provider | Free Tier | Req/Day | League Two? | Cost (Paid) | Data Quality | Maintenance |
|---|---|---|---|---|---|---|
| **API-Football** | ✓ 100/day | 100 | ✓ Yes | $19/mo | Excellent | Active |
| **football-data.org** | ✓ 12 leagues | 600/hour | ✗ Free only | €49/mo | Excellent | Active |
| **SportMonks** | ✗ (2 leagues only) | Varies | ✓ (Pro+) | €99/mo (30 lg) | Professional | Active |
| **TheSportsDB** | ✓ Free | 30/min | ✓ Likely | Free | Fair* | Community |
| **openfootball** | ✓ Public domain | N/A | ✓ Yes | Free | Historical only | Limited |
| **FotMob** | None (unofficial) | ? | ? | Free (scrape) | Good | Fragile** |

*TheSportsDB data is community-edited; crowd-sourced; not professionally maintained.
**FotMob has no official API; all access is via reverse-engineering. ToS violation risk.

---

## Detailed Analysis

### 1. API-Football (api-sports.io) — RECOMMENDED PRIMARY

**Coverage:** 1,200+ leagues including EFL League Two. All endpoints (fixtures, results, standings) on free tier.

**Pricing:**
- Free: 100 requests/day (no credit card required)
- Paid: $19/month (or higher plans with greater limits)

**Rate Limits:**
- Free: 100 requests/day (shared across all endpoints)
- Paid: Limits increase but still practical for 3-hour rebuild cycles

**Pros:**
- Free tier is genuinely useful: 100 req/day can support 3-4 rebuilds/day
- All competitions included on all tiers (no league gate-locking)
- Very reliable; actively maintained
- Simple REST API, easy integration
- Live score updates every 15 seconds during matches (when needed)

**Cons:**
- Free tier is a daily hard cap; must plan rebuilds carefully
- For higher usage (hourly rebuilds), costs escalate

**Verdict:** Best for low-volume fan site. Start here.

**Setup:** Sign up at api-sports.io, grab API key, set `FOOTBALL_API_KEY` env var.

**Key Info:**
- Base URL: https://api.api-football.com/v3
- Bristol Rovers Team ID: 234 (needs verification)
- Authentication: x-apisports-key header
- Endpoints: /fixtures (with team filter, last/next params)

---

### 2. football-data.org — RECOMMENDED FALLBACK

**Coverage:** Free tier is 12 major leagues only (no League Two). Paid tiers expand coverage.

**Pricing:**
- Free: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Primeira Liga, Championship, Champions League, Carabao Cup, World Cup, European Championship
- €29/month (Free+): 15 leagues (live data instead of 15-min delay)
- €49/month (Standard): 25 leagues
- €99/month (Advanced): 50 leagues

**Rate Limits:**
- All tiers: 10 requests/minute (600/hour), very generous

**League Two Status:**
- NOT in free tier
- Coverage table lists "England - League Two - LEAGUE" but tier not specified
- Likely available in Standard (€49) or Advanced (€99) plans

**Pros:**
- Extremely reliable; been operational for 10+ years
- Very generous rate limit (10 req/min)
- Professional data maintenance
- Detailed fixture/results coverage
- Simple REST API

**Cons:**
- Free tier does NOT include League Two
- Must pay to unlock it (minimum €49/month)
- Paid plans are expensive for hobby use
- League-gating model (must know which leagues to add)

**Verdict:** Use as fallback if API-Football is down or rate-limited. Verify League Two availability before subscribing.

**Setup:** Sign up at football-data.org, select League Two in your plan, set `FOOTBALL_DATA_KEY` env var.

**Key Info:**
- Base URL: https://api.football-data.org/v4
- Authentication: X-Auth-Token header
- Endpoints: /teams/{id}/matches, /competitions/{code}/matches

---

### 3. SportMonks Football API v3

**Coverage:** 2,500+ leagues, extremely comprehensive. EFL League Two is covered.

**Pricing:**
- Free: Only 2 leagues (Danish and Scottish) — unusable for this purpose
- €29/month (Starter): 5 leagues of your choice
- €99/month (Growth): 30 leagues of your choice
- €249/month (Pro): 120 leagues of your choice
- Enterprise: 2,200+ leagues (custom pricing)

**Plus:** Additional costs for odds data and historical data as add-ons.

**Pros:**
- Professional-grade data quality
- Extremely comprehensive coverage
- Flexible league selection (choose any league, not locked sets)

**Cons:**
- Free tier is practically useless (only 2 leagues)
- Minimum paid tier (€29) barely covers Bristol Rovers alone
- Growth tier (€99) needed for reasonable redundancy and history
- Most expensive option

**Verdict:** Overkill for a small fan site. Only consider if needing historical stats or if using as primary + backup.

**Setup:** Visit sportmonks.com/football-api/plans-pricing, select Growth (€99/mo minimum), set `SPORTMONKS_API_KEY` env var.

---

### 4. TheSportsDB

**Coverage:** 617 soccer leagues (crowd-sourced). League Two likely included.

**Pricing:** Completely free.

**Rate Limits:** 30 requests/minute (1,800/hour).

**Data Quality:** Community-edited; hobby-grade accuracy. Not professionally maintained.

**Pros:**
- Completely free
- Very generous rate limit
- Includes team logos, images, artwork

**Cons:**
- Data is crowd-sourced and can have gaps or errors
- Lower priority if professional accuracy matters
- Community-maintained; may become stale

**Verdict:** Good supplement (for logos/artwork) but risky as primary source for scores/fixtures.

**Setup:** Free; no API key needed. Visit thesportsdb.com.

---

### 5. OpenFootball (github.com/openfootball/england)

**Coverage:** Free, open-domain football data. League Two included.

**Format:** Football.txt (structured text) and JSON. Historical and current fixtures.

**Pricing:** Completely free (public domain, CC0).

**Pros:**
- No API, no auth, no rate limits
- Public domain data; zero licensing concerns
- Git-based updates (predictable, auditable)

**Cons:**
- Historical data only (not real-time)
- Manual update cycle (not live during matches)
- Data freshness depends on volunteer maintenance
- Requires parsing text files or generating JSON locally

**Verdict:** Good for season schedules and historical records. Not suitable for live results.

**Setup:** Clone repo, parse local files. No API key needed.

---

### 6. FotMob

**Coverage:** Extensive, includes League Two.

**Pricing:** Free (but unofficial/unsupported).

**Pros:**
- Good data quality
- No official API key needed

**Cons:**
- **NO OFFICIAL API** — all access is via reverse-engineering
- Multiple unofficial wrappers exist (fotmob-api on PyPI, pyfotmob, etc.)
- High risk of breakage if FotMob changes their site
- **Terms of Service violation**; ToS explicitly prohibits automated scraping
- Not suitable for production/maintenance

**Verdict:** **Avoid.** ToS violation risk; can disappear mid-season.

---

### 7. BBC Sport / Web Scraping

**Coverage:** League Two fixtures, results, standings available on BBC Sport pages.

**Pricing:** Free (but unsupported).

**Pros:**
- BBC is a trusted, stable data source
- League Two is well-covered

**Cons:**
- **All major sports sites prohibit automated scraping in their ToS**
- Fragile; site structure changes break scrapers
- Can disappear overnight
- Not suitable for maintenance

**Verdict:** **Avoid.** Use licensed APIs instead.

---

## Recommendation Rationale

### For GasDex specifically:

**Primary: API-Football**
- Free tier (100 req/day) is enough for 3-4 rebuilds/day
- Reliable, actively maintained, includes League Two
- Lowest friction to get started
- If you rebuild 4 times/day (every 6 hours), you'd hit 100 req/day only if each rebuild needs 25+ requests (unlikely)
- Cost: FREE or $19/month if you exceed free tier

**Fallback: football-data.org (if API-Football is down)**
- Must verify League Two is in your selected leagues first
- Cost: €49/month minimum to unlock League Two
- Only activate if API-Football is unreliable

**Do NOT use:**
- SportMonks (too expensive for hobby use)
- FotMob (ToS risk, no official API)
- BBC scraping (ToS risk, fragile)
- TheSportsDB alone (quality concerns)

---

## Implementation Plan

### Setup Steps (for user/developer)

1. **Get API-Football key:**
   - Sign up (free) at https://www.api-football.com/
   - Copy API key from dashboard
   - Set environment variable: `export FOOTBALL_API_KEY=<your-key>`

2. **Test fetch script:**
   - Run: `python3 tools/feeds/fetch_results.py`
   - Should output `data/results.json` with sample or live data

3. **(Optional) Get football-data.org key for fallback:**
   - Sign up at https://www.football-data.org/ (free tier first to explore)
   - If you want live League Two data, upgrade to Standard (€49/month)
   - Set env var: `export FOOTBALL_DATA_KEY=<your-key>`

### GitHub Actions Setup

In `.github/workflows/rebuild.yml` (or similar):
```yaml
- name: Fetch results
  env:
    FOOTBALL_API_KEY: ${{ secrets.FOOTBALL_API_KEY }}
  run: python3 tools/feeds/fetch_results.py
```

Store the API key in GitHub Secrets (Settings → Secrets and variables → Actions).

---

## Open Questions & Caveats

1. **League Two exact tier for football-data.org:** Documentation lists League Two but doesn't specify which paid plan(s) include it. **ACTION:** Contact football-data.org or test with a trial before subscribing.

2. **API-Football free tier sustained load:** With 100 req/day hard cap, if rebuild cycle ever needs >20 requests, you'd hit limits on 5+ rebuilds/day. **ACTION:** Monitor actual request usage; upgrade to $19/month if needed.

3. **Stale data in free API-Football:** Free tier may have slight delays vs. paid (research suggests live data, but verify). **ACTION:** Check timestamps in responses.

4. **Bristol Rovers team ID:** Both APIs need Bristol Rovers' team ID as a query param. Currently set to 234 in fetch_results.py but this needs verification before production. **ACTION:** Test with API-Football's /teams endpoint or /leagues endpoint to find correct ID.

5. **Seasonal transitions:** What happens in close-season (July-Aug)? Fixture list updates, but results may be empty (pre-season friendlies only). **ACTION:** Script should handle null/empty gracefully; template shows NO items if list is empty.

---

## Summary Table: Start Here

| Scenario | Provider | Cost | Action |
|---|---|---|---|
| **Just getting started** | API-Football free | $0 | Sign up, grab key, run script |
| **Free tier exhausted** | API-Football paid | $19/mo | Upgrade account |
| **API-Football down** | football-data.org | €49/mo | Add as fallback (after testing) |
| **Need redundancy** | Both (primary + fallback) | $19/mo + €49/mo | Implement dual-fetch with retry logic |
| **Budget very tight** | football-data.org free + openfootball | $0 | Accept 12-league limit or historical-only data; upgrade later |

---

## Sources Consulted

- API-Football Coverage & Pricing: https://www.api-football.com/ and https://www.api-football.com/coverage
- football-data.org: https://www.football-data.org/coverage and https://www.football-data.org/pricing
- SportMonks Football API: https://www.sportmonks.com/football-api/plans-pricing/
- TheSportsDB: https://www.thesportsdb.com/
- OpenFootball: https://github.com/openfootball/england
- Free Football API Comparisons: https://www.thestatsapi.com/blog/free-football-api-alternatives

---

**Last updated:** July 19, 2026
**Researcher:** Claude
**Status:** PROVISIONAL — Verify League Two coverage and Bristol Rovers team ID with API providers before full production rollout.
