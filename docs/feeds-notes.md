# GasDex Feed Fetchers — Implementation Notes

Date: 2026-07-19
Status: All scripts functional; news + club feeds live; YouTube sample data

## Overview

Three Python 3 fetcher scripts built to gather content for GasDex:
- `tools/feeds/fetch_news.py` — General Bristol Rovers news
- `tools/feeds/fetch_club.py` — Official club announcements
- `tools/feeds/fetch_youtube.py` — YouTube channel videos

All scripts:
- Use stdlib only (urllib, xml.etree, json, datetime)
- Degrade gracefully to sample data when feeds fail
- Output JSON with schema matching downstream contract
- Run via: `python3 tools/feeds/fetch_<name>.py`
- Write to: `data/<name>.json` (relative to project root)
- Handle timeouts (10s per feed), malformed XML, missing fields

## Feeds Status

### News Feed (fetch_news.py)

**Live feeds (all working from sandbox):**
1. **Google News** — `https://news.google.com/rss/search?q=%22Bristol+Rovers%22&hl=en-GB&gl=GB&ceid=GB:en`
   - Reliable, high volume (~92 items per run)
   - Includes official, fan, and sports news sources
   - Date format: RFC 2822

2. **BBC Sport** — `https://feeds.bbci.co.uk/sport/football/teams/bristol-rovers/rss.xml`
   - Working, lower volume (~4 items)
   - High-quality official source
   - Date format: RFC 2822

3. **Bristol Post** — `https://www.bristolpost.co.uk/all-about/bristol-rovers-fc?service=rss`
   - Working, good volume (~20 items)
   - Local journalism, consistent updates
   - Date format: ISO 8601 with timezone

**Deduplication:** By normalized title (lowercase, whitespace-compressed, punctuation-removed)

**Output:** Top 12 items, sorted newest-first, `sample: false`

**Real-world expect:** All three feeds should remain available on GitHub Actions (standard news RSS are allowlisted). No authentication required.

### Club Announcements Feed (fetch_club.py)

**Live feed:**
1. **Google News (site:bristolrovers.co.uk)** — `https://news.google.com/rss/search?q=site:bristolrovers.co.uk&hl=en-GB&gl=GB&ceid=GB:en`
   - Working, high volume (~100 items)
   - Filters results to official Bristol Rovers domain only
   - Includes press releases, fixture reports, announcements
   - Date format: RFC 2822

**Fallback feed (only used if primary <4 items):**
- Google News query: `"Bristol Rovers" official` — for safety if site filter breaks

**Output:** Top 8 items, sorted newest-first, `sample: false`

**Real-world expect:** Primary feed should remain stable. Fallback only triggers on edge cases.

### YouTube Feed (fetch_youtube.py)

**Channel Configuration (NEEDS VERIFICATION):**

Currently configured channels (placeholder IDs):
```python
CHANNELS = {
    "UCKQGnQHwYBCc6Z4xEz8iVvA": "Bristol Rovers FC",      # Official
    "UC6nSFpj9XWARhtsDMoCMtaQ": "Rovers Daily",           # Fan channel
    "UCLXnZvpFJqhIHj7lbX7gIhA": "Gas Nation",            # Fan channel
}
```

**Status from sandbox:** All three channels returned 404 (YouTube RSS endpoints may require specific IDs or may be blocked). Script gracefully degrades to realistic sample data.

**Next steps to fix:**
1. Visit YouTube.com
2. Search "Bristol Rovers FC" and "Rovers Daily" and "Gas Nation"
3. Click each channel → copy channel ID from URL: `youtube.com/channel/[24-char-ID]`
4. Update `CHANNELS` dict in `fetch_youtube.py`
5. Re-run script to verify live feeds

**Sample data generated:** Realistic July 2026 pre-season highlights (8 items)
- Topics: pre-season friendlies, manager interviews, stadium updates, signings, fan reactions
- Mix of official + fan channel content
- Marked `sample: true` in output

**Real-world expect:** Once channel IDs verified, YouTube feeds should work reliably from GitHub Actions.

## Data Output Schema

### news.json & club.json
```json
{
  "fetched_at": "<ISO8601 UTC, e.g., 2026-07-19T16:31:34.884520Z>",
  "sample": false,
  "items": [
    {
      "title": "String (may contain HTML entities)",
      "url": "String (fully qualified HTTP/HTTPS)",
      "source": "String (e.g., 'Google News', 'BBC Sport', 'Bristol Post')",
      "published": "<ISO8601, e.g., 2026-07-19T14:39:46Z>"
    }
  ]
}
```

### youtube.json
```json
{
  "fetched_at": "<ISO8601 UTC>",
  "sample": true|false,
  "items": [
    {
      "title": "String (YouTube video title)",
      "url": "String (youtube.com/watch?v=... format)",
      "channel": "String (e.g., 'Bristol Rovers FC')",
      "published": "<ISO8601>"
    }
  ]
}
```

## Helper Library (common.py)

Shared utilities:
- `get_project_root()` — Robust root detection (walks up from the script location looking for templates/index.template.html)
- `fetch_url(url, timeout=10)` — Safe HTTP GET with timeout, returns text or None
- `parse_rss(xml_data)` — Parse RSS 2.0, handles missing namespaces
- `normalize_title(title)` — For deduplication (lowercase, strip punctuation)
- `dedupe_by_title(items)` — Remove duplicates by normalized title
- `ensure_iso8601(date_str)` — Convert RFC 2822 / ISO 8601 to consistent format
- `sort_by_date_desc(items)` — Sort by published date, newest first
- `save_json(data, filepath)` — Save with mkdir, UTF-8, 2-space indent
- `get_source_from_url(url)` — Infer source name from domain

## Testing Results (2026-07-19)

Run each script individually to verify:

```bash
cd <project root>
python3 tools/feeds/fetch_news.py
python3 tools/feeds/fetch_club.py
python3 tools/feeds/fetch_youtube.py
```

### news.json
- ✓ Valid JSON
- ✓ Schema correct (title, url, source, published)
- ✓ 12 items (top 12 kept)
- ✓ Newest first (2026-07-19 → 2026-07-18)
- ✓ sample: false (all 3 feeds live)
- Live items: Portsmouth vs Rovers fixture, signing news, BBC/Bristol Post reports

### club.json
- ✓ Valid JSON
- ✓ Schema correct
- ✓ 8 items (top 8 kept)
- ✓ Newest first (2026-07-18 → 2026-06-17)
- ✓ sample: false (primary feed live)
- Live items: Match reports, partnerships, EFL Trophy draws, loan deals

### youtube.json
- ✓ Valid JSON
- ✓ Schema correct (title, url, channel, published)
- ✓ 8 items (sample data)
- ✓ sample: true (no live channels)
- Content: Realistic July 2026 pre-season announcements

## Integration Notes for Downstream

1. **Site Generator**: These JSON files are the input to the static site builder. Fields must match exactly as specified above.

2. **"Last Updated" Line**: Use `fetched_at` timestamp from each JSON file.

3. **Sample Data Badges**: If `"sample": true`, pages should display a "PROTOTYPE" banner or similar.

4. **Freshness Signals**: "NEW" tags should be applied to items from today or yesterday (based on `published`).

5. **Deduplication Confidence**: Title deduplication is aggressive (normalized), so rare duplicates by URL are possible — downstream should check if needed.

## Maintenance & Future Improvements

- **YouTube channels**: Requires one-time manual research to find & verify channel IDs
- **Feed resilience**: All scripts emit `sample: true` if live feeds fail — site remains functional
- **Caching**: Currently no caching; every run re-fetches. For GitHub Actions cron, this is fine (~3 feeds × 10s timeout = 30s max)
- **Date parsing**: Handles RFC 2822, ISO 8601, and minimal GMT format; edge cases may fall through to `published` as-is
- **HTML entities**: RSS feeds sometimes contain HTML entities in titles (e.g., `&quot;`, `&amp;`) — downstream HTML rendering should handle (common browsers do automatically)

## File Locations

- Scripts: `tools/feeds/`
- Data: `data/`
- This doc: `docs/feeds-notes.md`
