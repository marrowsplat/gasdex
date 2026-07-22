# GasDex Build System

## Overview

The GasDex static site generator renders `out/index.html` from a template and JSON data feeds, with intelligent fallbacks to sample data when feeds are unavailable.

**Core files:**
- `tools/build_site.py` — main build script (Python 3, stdlib only)
- `templates/index.template.html` — HTML template with block placeholders
- `out/index.html` — generated site (output only, do not commit)
- `docs/build-notes.md` — this file

## Running the build

```bash
cd /path/to/gasdex
python3 tools/build_site.py
```

Output:
- Renders `out/index.html`
- Logs warnings if any data sources are missing or marked as sample data
- Prints last updated timestamp (Europe/London time, format: "Dow DD Mon, HH:MM")

## Data feeds

The builder looks for JSON files in `data/`:

### news.json
```json
{
  "fetched_at": "2026-07-19T...",
  "sample": false,
  "items": [
    {
      "title": "...",
      "url": "https://...",
      "source": "BristolLive",
      "published": "2026-07-19T14:39:46Z"
    }
  ]
}
```

### club.json
Same structure as `news.json` (title, url, source, published).

### youtube.json
```json
{
  "fetched_at": "...",
  "sample": false,
  "items": [
    {
      "title": "...",
      "url": "https://youtube.com/...",
      "channel": "Official",
      "published": "2026-07-19T..."
    }
  ]
}
```

### results.json
```json
{
  "fetched_at": "...",
  "sample": false,
  "results": [
    {
      "date": "19 Jul",
      "opponent": "Gillingham",
      "venue": "H|A",
      "score_for": 0,
      "score_against": 1,
      "outcome": "W|D|L",
      "competition": "League Two"
    }
  ],
  "fixtures": [
    {
      "date": "25 Jul",
      "kickoff": "15:00",
      "opponent": "Grimsby",
      "venue": "H|A",
      "competition": "League Two"
    }
  ]
}
```

## Fallback data

If any JSON file is missing or cannot be read, the builder uses hardcoded sample data (defined in `tools/build_site.py`). Sample data includes realistic examples for all feed types.

When fallback data is used (or any feed has `"sample": true`):
- The PROTOTYPE banner in the footer remains visible
- Build output shows a WARNING
- No real feeds message is logged

Only when **all** data sources are loaded as real data (no file missing, all have `"sample": false`) will the banner potentially be updated in future deployments.

## Template structure

The template (`templates/index.template.html`) is a byte-for-byte copy of `site/index.html` with these changes:

1. **Last updated timestamp**: Replaced with placeholder `<!--UPDATED-->`
2. **Data blocks** wrapped in comment delimiters (examples below)

### Block delimiters

All data-driven content is wrapped as:
```html
<!--BLOCK:blockname-->
...content...
<!--/BLOCK:blockname-->
```

Blocks:
- `<!--BLOCK:results-->` — Latest Results rows (5 rows of `.score-row` divs)
- `<!--BLOCK:fixtures-->` — Next Fixtures rows (`.fix-row` divs)
- `<!--BLOCK:news-->` — News list items (`.ico`-prefixed `<li>` elements)
- `<!--BLOCK:club-->` — Club Announcements list items (same markup as news)
- `<!--BLOCK:youtube-->` — YouTube list items (same markup, different icons/channels)

**Hand-curated sections** (not templated):
- Fan Player Ratings (static sample data, awaits backend)
- Fan Match Reports (static links, awaits report submissions backend)
- Rovers Sites, Social, and the strip (permanent reference links)

## Markup patterns

The builder strictly follows the approved design markup from `site/index.html`:

### External links
- Class: `class="ext"`
- Attributes: `target="_blank" rel="noopener"`
- Marker: `↗` (rendered by CSS `::after` pseudo-element)

### Internal links
- NO `class="ext"`, no `target="_blank"` attribute
- No marker

### Timestamps & freshness

**"When" timestamps** (relative):
- Format: e.g., "2h ago", "5h", "1d", "2d", "Fri"
- Inferred from ISO `published` date
- Logic: < 60m = "Xm ago"; < 24h = "Xh ago"; < 7d = "Xd"; >= 7d = day abbreviation
- CSS class: `.when` (news/YouTube) or `.when2` (fixtures)

**NEW tag**:
- Shown if item published within last 48 hours
- Markup: `<span class="tag-new">NEW</span>`
- Appears after link, before timestamp

**"Last updated" line** in masthead:
- Format: "Sun 19 Jul, 08:00" (day, date, time in Europe/London zone)
- Rendered fresh on every build

### Score rows (results)
```html
<div class="score-row">
  <span class="opp">OPPONENT (H|A)</span>
  <span class="sc w|d|l">OUTCOME SCORE</span>
</div>
```
Classes: `.sc` (score), outcome class `.w` (win), `.d` (draw), `.l` (loss)

### Fixture rows
```html
<div class="fix-row">
  <span class="opp">OPPONENT (H|A)</span>
  <span class="when2">DAY DATE, TIME</span>
</div>
```
E.g., "Sat 25 Jul, 15:00"

### List items (news, club, YouTube)
```html
<li>
  <span class="ico">EMOJI</span>
  <div>
    <a href="URL" class="ext" target="_blank" rel="noopener">TITLE</a>
    <span class="tag-new">NEW</span>
    <span class="when">SOURCE · WHEN</span>
  </div>
</li>
```

## Date formatting

The builder handles two date formats:

1. **"DD Mon" style** (e.g., "25 Jul"): Day of week is inferred; output "Sat 25 Jul"
2. **ISO format** (e.g., "2026-07-25"): Parsed and formatted to "Sat 25 Jul"

If parsing fails, the date is used as-is.

## Text escaping

All text from feeds (titles, sources, etc.) is HTML-escaped using `html.escape()` to prevent injection of unescaped & < > characters.

## Timestamp calculation

The build timestamp is calculated as:
```python
datetime.now().strftime("%a %d %b, %H:%M")
```
with `TZ=Europe/London` environment variable set (if possible).

## Output validation

After build, validate the output:
```bash
python3 tools/validate.py out/index.html
```

This checks:
- HTML tag balance
- External links have `class="ext"` + `target="_blank"`
- Internal links do NOT have external markers

## Workflow notes

- **Template preservation**: All approved markup, CSS, JS, and structure remain intact. Only the data blocks and timestamp are replaced.
- **No breaking changes to design**: The builder respects the settled design decisions and the visual design in `site/index.html`.
- **Idempotent**: Running the build multiple times with the same input produces identical output (except timestamp).
- **Future automation**: This script is designed to run on a schedule (e.g., GitHub Actions cron ~every 3h).

## Provisional notes (PROVISIONAL)

- **Fixture day-of-week inference**: The builder infers the day of week from "DD Mon" date strings. If data sources eventually include both formats, validation may be needed to ensure consistency.
- **Sample data banner**: Currently always shown when any fallback is used. Once real data is live, the mechanism to hide the banner will be implemented.
- **Timezone handling**: Currently attempts to set `TZ=Europe/London` before generating timestamp. If timezone support is unreliable in CI/CD, consider using `pytz` library (stdlib-only constraint would need review).
- **48-hour NEW tag window**: Hardcoded. If this needs to be configurable, pass as a parameter or read from config.
