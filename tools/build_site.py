#!/usr/bin/env python3
"""GasDex static site generator.

Reads templates/index.template.html and data from data/*.json,
renders out/index.html with real feed data.

Data sources (in data/ directory):
- news.json: {"fetched_at", "sample", "items": [...]}
- club.json: {"fetched_at", "sample", "items": [...]}
- youtube.json: {"fetched_at", "sample", "items": [...]}
- results.json: {"fetched_at", "sample", "results": [...], "fixtures": [...]}

If any file is missing, fallback to hardcoded sample data.
All sample data (or fallback) keeps PROTOTYPE banner visible.
"""
import json
import sys
import html
from pathlib import Path
from datetime import datetime, timedelta, timezone
import re

# News relevance filter (shared with tools/feeds/fetch_news.py). Applied
# again at history-merge time as a second gate so a stale, unfiltered
# news.json can never (re)pollute the rolling archive.
sys.path.insert(0, str(Path(__file__).resolve().parent / "feeds"))
from news_filter import filter_items as filter_news_items

# Hardcoded fallback sample data (used when JSON files are missing)
FALLBACK_NEWS = {
    "fetched_at": datetime.now(tz=None).isoformat(),
    "sample": True,
    "items": [
        {
            "title": "Rovers boss praises \"unfair\" defeat response",
            "url": "https://example.com/news1",
            "source": "BristolLive",
            "published": (datetime.now() - timedelta(hours=2)).isoformat()
        },
        {
            "title": "League Two weekend preview: Grimsby test awaits",
            "url": "https://example.com/news2",
            "source": "BBC Sport",
            "published": (datetime.now() - timedelta(hours=5)).isoformat()
        },
        {
            "title": "Sotiriou attracting interest after hot streak",
            "url": "https://example.com/news3",
            "source": "FLW",
            "published": (datetime.now() - timedelta(days=1)).isoformat()
        },
        {
            "title": "Memorial Stadium redevelopment: latest",
            "url": "https://example.com/news4",
            "source": "BristolLive",
            "published": (datetime.now() - timedelta(days=2)).isoformat()
        },
        {
            "title": "Fan gallery: best photos from Barrow away",
            "url": "https://example.com/news5",
            "source": "Bristol Post",
            "published": (datetime.now() - timedelta(days=3)).isoformat()
        },
    ]
}

FALLBACK_CLUB = {
    "fetched_at": datetime.now(tz=None).isoformat(),
    "sample": True,
    "items": [
        {
            "title": "Ticket details: Grimsby (H)",
            "url": "https://example.com/club1",
            "source": "Official",
            "published": (datetime.now() - timedelta(hours=6)).isoformat()
        },
        {
            "title": "U18s friendly result and report",
            "url": "https://example.com/club2",
            "source": "Official",
            "published": (datetime.now() - timedelta(days=1)).isoformat()
        },
        {
            "title": "Community Trust summer camps open",
            "url": "https://example.com/club3",
            "source": "Official",
            "published": (datetime.now() - timedelta(days=2)).isoformat()
        },
        {
            "title": "Away travel: Salford coach bookings",
            "url": "https://example.com/club4",
            "source": "Official",
            "published": (datetime.now() - timedelta(days=3)).isoformat()
        },
    ]
}

FALLBACK_YOUTUBE = {
    "fetched_at": datetime.now(tz=None).isoformat(),
    "sample": True,
    "items": [
        {
            "title": "HIGHLIGHTS: Rovers 0–1 Gillingham",
            "url": "https://youtube.com/watch?v=example1",
            "channel": "Official",
            "published": (datetime.now() - timedelta(days=1)).isoformat()
        },
        {
            "title": "Gas Cast #142: transfer window special",
            "url": "https://youtube.com/watch?v=example2",
            "channel": "Gas Cast",
            "published": (datetime.now() - timedelta(days=2)).isoformat()
        },
        {
            "title": "Matchday vlog: Barrow away trip",
            "url": "https://youtube.com/watch?v=example3",
            "channel": "Rovers Vlogs",
            "published": (datetime.now() - timedelta(days=4)).isoformat()
        },
        {
            "title": "Every goal from June",
            "url": "https://youtube.com/watch?v=example4",
            "channel": "Official",
            "published": (datetime.now() - timedelta(days=6)).isoformat()
        },
    ]
}

FALLBACK_RESULTS = {
    "fetched_at": datetime.now(tz=None).isoformat(),
    "sample": True,
    "results": [
        {"date": "19 Jul", "opponent": "Gillingham", "venue": "H", "score_for": 0, "score_against": 1, "outcome": "L", "competition": "League Two"},
        {"date": "16 Jul", "opponent": "Barrow", "venue": "A", "score_for": 2, "score_against": 1, "outcome": "W", "competition": "League Two"},
        {"date": "13 Jul", "opponent": "Notts County", "venue": "H", "score_for": 1, "score_against": 1, "outcome": "D", "competition": "League Two"},
        {"date": "10 Jul", "opponent": "Tranmere", "venue": "H", "score_for": 2, "score_against": 0, "outcome": "W", "competition": "League Two"},
        {"date": "6 Jul", "opponent": "Crewe", "venue": "A", "score_for": 2, "score_against": 2, "outcome": "D", "competition": "League Two"},
    ],
    "fixtures": [
        {"date": "25 Jul", "kickoff": "15:00", "opponent": "Grimsby", "venue": "H", "competition": "League Two"},
        {"date": "28 Jul", "kickoff": "19:45", "opponent": "Salford", "venue": "A", "competition": "League Two"},
        {"date": "1 Aug", "kickoff": "15:00", "opponent": "Colchester", "venue": "H", "competition": "League Two"},
        {"date": "8 Aug", "kickoff": "15:00", "opponent": "Newport", "venue": "A", "competition": "League Two"},
    ]
}


def format_relative_time(iso_string):
    """Convert ISO datetime to relative format like '2h ago', 'Fri', etc."""
    try:
        # Parse ISO string (handle both with/without microseconds/timezone)
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        now = datetime.now(tz=None)
        # Localize for comparison
        if dt.tzinfo:
            now = now.replace(tzinfo=dt.tzinfo)

        delta = now - dt
        minutes = delta.total_seconds() / 60
        hours = minutes / 60
        days = hours / 24

        if minutes < 60:
            return f"{int(minutes)}m ago" if int(minutes) >= 1 else "now"
        elif hours < 24:
            h = int(hours)
            return f"{h}h ago"
        elif days < 7:
            d = int(days)
            return f"{d}d" if d > 1 else "1d"
        else:
            # Return day of week abbreviation
            return dt.strftime("%a")
    except Exception:
        return "recently"


def should_show_new_tag(iso_string):
    """Check if item was published within last 48 hours."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        now = datetime.now(tz=None)
        if dt.tzinfo:
            now = now.replace(tzinfo=dt.tzinfo)
        delta = now - dt
        return delta.total_seconds() < (48 * 3600)
    except Exception:
        return False


def render_news_items(items):
    """Render news list items with markup."""
    html_items = []
    for item in items:
        title = html.escape(item.get("title", ""))
        url = html.escape(item.get("url", "#"))
        source = html.escape(item.get("source", ""))
        published = item.get("published", "")

        when_text = f"{source} &middot; {format_relative_time(published)}"
        new_tag = '<span class="tag-new">NEW</span>' if should_show_new_tag(published) else ""

        html_items.append(
            f'      <li><span class="ico">&#128240;</span><div><a href="{url}" class="ext" target="_blank" rel="noopener">{title}</a>{new_tag}<span class="when">{when_text}</span></div></li>'
        )
    return "\n".join(html_items)


def render_archive_news_items(items):
    """Render archive news items (site/archive-news.html markup)."""
    html_items = []
    for item in items:
        title = html.escape(item.get("title", ""))
        url = html.escape(item.get("url", "#"))
        source = html.escape(item.get("source", ""))
        published = item.get("published", "")

        when_text = f"{source} &middot; {format_relative_time(published)}"
        new_tag = '\n          <span class="tag-new">NEW</span>' if should_show_new_tag(published) else ""

        html_items.append(
            '      <li class="news-item">\n'
            '        <span class="ico">&#128240;</span>\n'
            '        <div class="content">\n'
            f'          <a href="{url}" class="ext" target="_blank" rel="noopener">{title}</a>{new_tag}\n'
            f'          <span class="when">{when_text}</span>\n'
            '        </div>\n'
            '      </li>'
        )
    return "\n".join(html_items)


def update_news_history(data_dir, news_data, cap=200):
    """Merge current news items into the rolling data/news-history.json cache.

    Mirrors the results-history.json pattern: dedupe by URL, newest first,
    capped. The history file must NOT be deleted and should persist between
    CI builds. Sample/fallback data is never written into the cache.
    Returns the merged item list (history items, newest first).
    """
    history_path = Path(data_dir) / "news-history.json"
    history = load_json_data(history_path) or {"items": []}
    # Second-gate relevance filter: scrub existing cache AND incoming items
    # (see tools/feeds/news_filter.py for the policy).
    history_items = filter_news_items(history.get("items", []))
    existing = {item.get("url"): item for item in history_items if item.get("url")}

    if not news_data.get("sample"):
        for item in filter_news_items(news_data.get("items", [])):
            url = item.get("url")
            if url:
                existing[url] = item  # newest fetch wins (title fixes etc.)

    merged = sorted(existing.values(), key=lambda i: i.get("published", ""), reverse=True)[:cap]

    if not news_data.get("sample"):
        history_out = {
            "updated_at": datetime.now(tz=None).isoformat(),
            "items": merged,
        }
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history_out, f, ensure_ascii=False, indent=1)

    return merged


def build_archive_news(template_path, data_dir, output_path, news_data):
    """Render out/archive-news.html from its template + rolling news history."""
    if not template_path.exists():
        print(f"  NOTE: archive-news template missing ({template_path}); skipped")
        return None

    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    merged = update_news_history(data_dir, news_data)
    # Fall back to whatever the current feed has (incl. samples) if history empty
    items = merged if merged else news_data.get("items", [])

    archive_html = render_archive_news_items(items)
    output = re.sub(
        r'<!--BLOCK:archive-news-->.*?<!--/BLOCK:archive-news-->',
        lambda m: f'<!--BLOCK:archive-news-->\n{archive_html}\n    <!--/BLOCK:archive-news-->',
        template,
        flags=re.DOTALL
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)
    print(f"✓ Rendered to {output_path} ({len(items)} news items"
          f"{', from rolling history' if merged else ', sample fallback'})")
    return output_path


SITE_URL = "https://gasdex.co.uk"


def _rfc822(iso_string):
    """ISO datetime -> RFC 822 date for RSS pubDate (falls back to now)."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    except Exception:
        dt = datetime.now(tz=None)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _xml(text):
    """Escape text for XML element content."""
    return html.escape(str(text), quote=True)


def build_feed(output_path, news_items, club_items, youtube_items, cap=50):
    """Write out/feed.xml — RSS 2.0 combining news, club and YouTube items.

    Item links point at the original articles/videos (same as the index).
    The channel self-URL uses SITE_URL; until the custom domain is attached
    the feed still works fine on the github.io URL (readers follow the
    relative autodiscovery link on the index).
    """
    entries = []
    for item in news_items:
        entries.append((item.get("published", ""), item, f"News · {item.get('source', '')}"))
    for item in club_items:
        entries.append((item.get("published", ""), item, "Club announcement"))
    for item in youtube_items:
        entries.append((item.get("published", ""), item, f"Video · {item.get('channel', '')}"))
    entries.sort(key=lambda e: e[0], reverse=True)
    entries = entries[:cap]

    items_xml = []
    for published, item, label in entries:
        url = item.get("url", "")
        title = item.get("title", "")
        items_xml.append(
            "    <item>\n"
            f"      <title>{_xml(title)}</title>\n"
            f"      <link>{_xml(url)}</link>\n"
            f"      <guid isPermaLink=\"false\">{_xml(url)}</guid>\n"
            f"      <category>{_xml(label)}</category>\n"
            f"      <pubDate>{_rfc822(published)}</pubDate>\n"
            "    </item>"
        )

    now_822 = _rfc822(datetime.now(tz=None).isoformat())
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>GasDex — Everything Bristol Rovers</title>\n"
        f"    <link>{SITE_URL}/</link>\n"
        "    <description>Bristol Rovers news, club announcements and videos, "
        "aggregated by GasDex (unofficial).</description>\n"
        "    <language>en-gb</language>\n"
        f"    <lastBuildDate>{now_822}</lastBuildDate>\n"
        f'    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items_xml) + "\n"
        "  </channel>\n"
        "</rss>\n"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(feed)
    print(f"✓ Rendered to {output_path} ({len(entries)} feed entries)")
    return output_path


def render_club_items(items):
    """Render club announcements list items."""
    html_items = []
    for item in items:
        title = html.escape(item.get("title", ""))
        url = html.escape(item.get("url", "#"))
        published = item.get("published", "")

        when_text = format_relative_time(published)
        new_tag = '<span class="tag-new">NEW</span>' if should_show_new_tag(published) else ""

        html_items.append(
            f'      <li><span class="ico">&#128309;</span><div><a href="{url}" class="ext" target="_blank" rel="noopener">{title}</a>{new_tag}<span class="when">{when_text}</span></div></li>'
        )
    return "\n".join(html_items)


def render_youtube_items(items):
    """Render YouTube list items."""
    html_items = []
    for item in items:
        title = html.escape(item.get("title", ""))
        url = html.escape(item.get("url", "#"))
        channel = html.escape(item.get("channel", ""))
        published = item.get("published", "")

        when_text = f"{channel} &middot; {format_relative_time(published)}"
        new_tag = '<span class="tag-new">NEW</span>' if should_show_new_tag(published) else ""

        html_items.append(
            f'      <li><span class="ico">&#9654;&#65039;</span><div><a href="{url}" class="ext" target="_blank" rel="noopener">{title}</a>{new_tag}<span class="when">{when_text}</span></div></li>'
        )
    return "\n".join(html_items)


def render_results(results):
    """Render latest results score rows."""
    html_rows = []
    for result in results:
        opp = html.escape(result.get("opponent", ""))
        venue = result.get("venue", "")
        score_for = result.get("score_for", 0)
        score_against = result.get("score_against", 0)
        outcome = result.get("outcome", "")

        venue_str = " (H)" if venue == "H" else " (A)"
        score_str = f"{score_for}&ndash;{score_against}"

        # Outcome class: w, d, or l
        outcome_class = outcome.lower() if outcome in "WDL" else "d"

        comp = html.escape(result.get("competition", ""))
        comp_span = f'<span class="comp">{comp}</span>' if comp else ""

        html_rows.append(
            f'    <div class="score-row"><span class="opp">{opp}{venue_str}</span><span class="sc {outcome_class}">{outcome} {score_str}</span>{comp_span}</div>'
        )
    return "\n".join(html_rows)


def render_fixtures(fixtures):
    """Render next fixtures."""
    html_rows = []
    for fixture in fixtures:
        opp = html.escape(fixture.get("opponent", ""))
        date_str = fixture.get("date", "")
        kickoff = html.escape(fixture.get("kickoff", ""))
        venue = fixture.get("venue", "")

        venue_str = " (H)" if venue == "H" else " (A)"

        # Try to infer day of week from date string if not provided
        # Handle both "25 Jul" and "2026-07-25" formats
        date_display = date_str
        try:
            # Try parsing as "DD Mon" or "D Mon" format
            from datetime import datetime
            if any(month in date_str for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                # Format: "25 Jul" - add current year for parsing
                parsed = datetime.strptime(f"{date_str} 2026", "%d %b %Y")
                date_display = parsed.strftime("%a %d %b")
            else:
                # Assume ISO format "2026-07-25"
                parsed = datetime.fromisoformat(date_str)
                date_display = parsed.strftime("%a %d %b")
        except Exception:
            # If parsing fails, use as-is
            pass

        datetime_str = f"{date_display}, {kickoff}"

        comp = html.escape(fixture.get("competition", ""))
        comp_span = f'<span class="comp">{comp}</span>' if comp else ""

        html_rows.append(
            f'    <div class="fix-row"><span class="opp">{opp}{venue_str}</span><span class="when2">{datetime_str}</span>{comp_span}</div>'
        )
    return "\n".join(html_rows)


def format_updated_timestamp():
    """Format the current timestamp as 'Dow DD Mon, HH:MM' in Europe/London time."""
    import os
    # Try to set timezone to Europe/London
    try:
        os.environ['TZ'] = 'Europe/London'
    except:
        pass

    now = datetime.now()
    # Format: "Sun 19 Jul, 08:00"
    return now.strftime("%a %d %b, %H:%M")


def load_json_data(filepath):
    """Load JSON data from file, return None if file doesn't exist."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def build_site(template_path, data_dir, output_path):
    """Build the site by rendering template with data."""
    print(f"Building GasDex site...")

    # Load template
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    # Load data files (or use fallback)
    data_dir = Path(data_dir)
    news_data = load_json_data(data_dir / "news.json") or FALLBACK_NEWS
    club_data = load_json_data(data_dir / "club.json") or FALLBACK_CLUB
    youtube_data = load_json_data(data_dir / "youtube.json") or FALLBACK_YOUTUBE
    results_data = load_json_data(data_dir / "results.json") or FALLBACK_RESULTS

    # Track if any data is sample/fallback
    using_sample = any([
        news_data.get("sample"),
        club_data.get("sample"),
        youtube_data.get("sample"),
        results_data.get("sample"),
    ])

    # Render content blocks
    news_html = render_news_items(news_data.get("items", []))
    club_html = render_club_items(club_data.get("items", []))
    youtube_html = render_youtube_items(youtube_data.get("items", []))
    results_html = render_results(results_data.get("results", []))
    fixtures_html = render_fixtures(results_data.get("fixtures", []))
    reports_html = render_report_items(load_published_reports(data_dir))
    updated_time = format_updated_timestamp()

    # Replace blocks in template
    output = template
    output = re.sub(
        r'<!--BLOCK:results-->.*?<!--/BLOCK:results-->',
        lambda m: f'<!--BLOCK:results-->\n{results_html}\n    <!--/BLOCK:results-->',
        output,
        flags=re.DOTALL
    )
    output = re.sub(
        r'<!--BLOCK:fixtures-->.*?<!--/BLOCK:fixtures-->',
        lambda m: f'<!--BLOCK:fixtures-->\n{fixtures_html}\n    <!--/BLOCK:fixtures-->',
        output,
        flags=re.DOTALL
    )
    output = re.sub(
        r'<!--BLOCK:news-->.*?<!--/BLOCK:news-->',
        lambda m: f'<!--BLOCK:news-->\n{news_html}\n    <!--/BLOCK:news-->',
        output,
        flags=re.DOTALL
    )
    output = re.sub(
        r'<!--BLOCK:club-->.*?<!--/BLOCK:club-->',
        lambda m: f'<!--BLOCK:club-->\n{club_html}\n    <!--/BLOCK:club-->',
        output,
        flags=re.DOTALL
    )
    output = re.sub(
        r'<!--BLOCK:youtube-->.*?<!--/BLOCK:youtube-->',
        lambda m: f'<!--BLOCK:youtube-->\n{youtube_html}\n    <!--/BLOCK:youtube-->',
        output,
        flags=re.DOTALL
    )
    output = re.sub(
        r'<!--BLOCK:reports-->.*?<!--/BLOCK:reports-->',
        lambda m: f'<!--BLOCK:reports-->\n{reports_html}\n    <!--/BLOCK:reports-->',
        output,
        flags=re.DOTALL
    )
    output = output.replace('<!--UPDATED-->', updated_time)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)

    # Log results
    print(f"✓ Rendered to {output_path}")
    sample_feeds = [name for name, d in [("news", news_data), ("club", club_data),
                    ("youtube", youtube_data), ("results", results_data)] if d.get("sample")]
    if sample_feeds:
        print(f"  NOTE: sample/fallback data used for: {', '.join(sample_feeds)} (rest are live)")
    else:
        print(f"  All feeds loaded live")
    print(f"  Last updated: {updated_time}")

    return output_path


def load_published_reports(data_dir):
    """Read approved fan reports (data/reports/*.json, "_"-prefixed skipped).

    Returns a list of dicts (newest submission first) used by the index box
    and the archive page. The per-report pages themselves are rendered by
    build_reports() from the same files — deleting a JSON un-publishes the
    report everywhere in one go.
    """
    reports_dir = Path(data_dir) / "reports"
    items = []
    if not reports_dir.exists():
        return items
    for jf in sorted(reports_dir.glob("*.json")):
        if jf.name.startswith("_"):
            continue
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                r = json.load(f)
        except Exception:
            continue
        slug = re.sub(r"[^a-z0-9-]", "", str(r.get("match_id") or jf.stem).lower())
        if not slug:
            continue
        home = str(r.get("match_team_home", "Bristol Rovers"))
        away = str(r.get("match_team_away", "Opponent"))
        if "Bristol Rovers" in home:
            opponent, venue = away, "H"
        else:
            opponent, venue = home, "A"
        # Season from the yyyymmdd tail of the match_id slug (fallback:
        # submission date). English seasons roll over in the summer: month
        # >= 7 belongs to the season that STARTS that year.
        year = month = None
        m = re.search(r"(\d{4})(\d{2})\d{2}$", slug)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
        else:
            try:
                dt = datetime.fromisoformat(str(r.get("date_submitted", "")).replace('Z', '+00:00'))
                year, month = dt.year, dt.month
            except Exception:
                pass
        if year:
            start = year if month >= 7 else year - 1
            season = f"{start}\u2013{str(start + 1)[2:]}"
        else:
            season = "Season unknown"
        items.append({
            "slug": slug,
            "title": str(r.get("title", "Untitled report")),
            "author": str(r.get("author", "Anonymous")),
            "opponent": opponent,
            "venue": venue,
            "season": season,
            "date_submitted": str(r.get("date_submitted", "")),
        })
    items.sort(key=lambda i: i["date_submitted"], reverse=True)
    return items


# The index box's zero-reports state (also the static markup in
# site/index.html — keep the two in lockstep).
REPORTS_EMPTY_LI = ('      <li><span class="ico">&#9997;&#65039;</span>'
                    '<div>No fan reports published yet &mdash; be the first!</div></li>')


def render_report_items(items, cap=5):
    """Render the index Fan Match Reports list (or its empty state)."""
    if not items:
        return REPORTS_EMPTY_LI
    rows = []
    for it in items[:cap]:
        title = html.escape(it["title"])
        author = html.escape(it["author"])
        opp = html.escape(it["opponent"])
        rows.append(
            f'      <li><span class="ico">&#9997;&#65039;</span><div>'
            f'<a href="report-{it["slug"]}.html">&quot;{title}&quot; &mdash; {opp} ({it["venue"]})</a>'
            f'<span class="when">by {author}</span></div></li>'
        )
    return "\n".join(rows)


def build_archive_reports(template_path, output_path, items):
    """Render out/archive-reports.html from its template + published reports.

    Reports are grouped by season, newest season first. With zero reports the
    page shows the same be-the-first invitation as the index box.
    """
    if not template_path.exists():
        print(f"  NOTE: archive-reports template missing ({template_path}); skipped")
        return None

    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    if not items:
        archive_html = (
            '    <p>No fan reports published yet &mdash; '
            '<a href="submit.html">be the first!</a></p>\n'
            '    <p style="margin-top:10px;font-size:11.5px;color:#6c6c72">'
            'Reports from fellow Gasheads appear here once they&rsquo;ve been reviewed.</p>'
        )
    else:
        seasons = {}
        order = []
        for it in items:
            if it["season"] not in seasons:
                seasons[it["season"]] = []
                order.append(it["season"])
            seasons[it["season"]].append(it)
        order.sort(reverse=True)
        groups = []
        for season in order:
            lis = []
            for it in seasons[season]:
                title = html.escape(it["title"])
                author = html.escape(it["author"])
                opp = html.escape(it["opponent"])
                lis.append(
                    '        <li class="report-item">\n'
                    '          <span class="ico">&#9997;&#65039;</span>\n'
                    '          <div class="content">\n'
                    f'            <a href="report-{it["slug"]}.html">&quot;{title}&quot; &mdash; {opp} ({it["venue"]})</a>\n'
                    f'            <span class="author">by {author}</span>\n'
                    '          </div>\n'
                    '        </li>'
                )
            groups.append(
                '    <div class="season-group">\n'
                f'      <div class="season-header">{html.escape(season)}</div>\n'
                '      <ul class="report-list">\n'
                + "\n".join(lis) + "\n"
                '      </ul>\n'
                '    </div>'
            )
        archive_html = "\n\n".join(groups)

    output = re.sub(
        r'<!--BLOCK:archive-reports-->.*?<!--/BLOCK:archive-reports-->',
        lambda m: f'<!--BLOCK:archive-reports-->\n{archive_html}\n    <!--/BLOCK:archive-reports-->',
        template,
        flags=re.DOTALL
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)
    print(f"✓ Rendered to {output_path} ({len(items)} published report(s))")
    return output_path


def _report_block(template, block, content):
    """Replace one <!--BLOCK:x-->...<!--/BLOCK:x--> region (markers kept)."""
    return re.sub(
        rf'<!--BLOCK:{block}-->.*?<!--/BLOCK:{block}-->',
        lambda m: f'<!--BLOCK:{block}-->{content}<!--/BLOCK:{block}-->',
        template,
        flags=re.DOTALL,
    )


def build_reports(template_path, data_dir, out_dir):
    """Render approved fan match reports to out/report-<match_id>.html.

    APPROVE-BY-FILE FLOW (docs/REPORT-PUBLISHING.md): the maintainer saves an
    approved submission as data/reports/<match_id>.json (schema =
    data/reports/_example.json), commits and pushes; CI renders + deploys the
    page automatically. Filenames starting with "_" are skipped (examples/
    templates). Output pages live flat in out/ so relative links and assets
    work on both the project-pages URL and the custom domain.
    """
    reports_dir = data_dir / "reports"
    if not template_path.exists() or not reports_dir.exists():
        return []

    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    written = []
    for jf in sorted(reports_dir.glob("*.json")):
        if jf.name.startswith("_"):
            continue
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                r = json.load(f)
        except Exception as e:
            print(f"  WARNING: skipping unreadable report {jf.name}: {e}")
            continue

        slug = re.sub(r"[^a-z0-9-]", "", str(r.get("match_id") or jf.stem).lower())
        if not slug:
            print(f"  WARNING: skipping report with unusable match_id: {jf.name}")
            continue

        title = html.escape(str(r.get("title", "Untitled report")))
        author = html.escape(str(r.get("author", "Anonymous")))
        home = html.escape(str(r.get("match_team_home", "Bristol Rovers")))
        away = html.escape(str(r.get("match_team_away", "Opponent")))
        score_h = html.escape(str(r.get("match_score_home", "?")))
        score_a = html.escape(str(r.get("match_score_away", "?")))
        comp = html.escape(str(r.get("competition", "League Two")))
        venue = html.escape(str(r.get("match_venue", "The Memorial Stadium")))
        match_date = html.escape(str(r.get("match_date", "")))

        try:
            dt = datetime.fromisoformat(str(r.get("date_submitted", "")).replace('Z', '+00:00'))
            submitted = dt.strftime('%a %d %b, %H:%M')
        except Exception:
            submitted = "after the match"

        meta_bits = [comp, venue]
        if match_date:
            meta_bits.append(match_date)
        att = r.get("match_attendance")
        if att:
            try:
                meta_bits.append(f"Att. {int(att):,}")
            except (TypeError, ValueError):
                pass

        paragraphs = [p.strip() for p in str(r.get("body", "")).split("\n\n") if p.strip()]
        body_html = "\n".join(f"      <p>{html.escape(p)}</p>" for p in paragraphs)

        ratings = r.get("ratings") or {}
        if ratings:
            rows = []
            ranked = sorted(ratings.items(), key=lambda kv: kv[1].get("avg", 0), reverse=True)
            for name, d in ranked:
                avg = float(d.get("avg", 0))
                width = max(0, min(100, round(avg * 10)))
                rows.append(
                    f'      <div class="rate-row"><span class="nm">{html.escape(name)}</span>'
                    f'<div class="bar"><i style="width:{width}%"></i></div>'
                    f'<span class="val">{avg:.1f}</span></div>'
                )
            motm_name, motm_d = max(ratings.items(), key=lambda kv: kv[1].get("motm_votes", 0))
            total_motm = sum(d.get("motm_votes", 0) for d in ratings.values())
            fan_count = r.get("ratings_count") or total_motm
            pct = round(100 * motm_d.get("motm_votes", 0) / total_motm) if total_motm else 0
            ratings_html = (
                '<div class="ratings">\n'
                '      <h3>Fan Player Ratings &mdash; this match</h3>\n'
                f'      <div class="rate-note">{fan_count} fans voted</div>\n'
                + "\n".join(rows) + "\n"
                f'      <div class="motm">Man of the Match: <b>{html.escape(motm_name)}</b> ({pct}% of votes)</div>\n'
                '    </div>'
            )
        else:
            ratings_html = ''

        page = template
        page = _report_block(page, 'doctitle',
                             f'<title>&ldquo;{title}&rdquo; &mdash; {away if "Bristol Rovers" in r.get("match_team_home", "Bristol Rovers") else home} | GasDex fan reports</title>')
        page = _report_block(page, 'description',
                             f'<meta name="description" content="A fan-written Bristol Rovers match report on GasDex: {title}, by {author}.">')
        page = _report_block(page, 'match',
                             '      <div class="score-line">\n'
                             f'        <span class="team">{home}</span>\n'
                             f'        <span class="score">{score_h} &ndash; {score_a}</span>\n'
                             f'        <span class="team">{away}</span>\n'
                             '      </div>\n'
                             f'      <div class="meta">{" &middot; ".join(meta_bits)}</div>')
        page = _report_block(page, 'heading',
                             f'    <h1 class="report-title">&ldquo;{title}&rdquo;</h1>\n'
                             f'    <div class="byline">by <b>{author}</b> &middot; submitted {submitted} &middot; published after review</div>')
        page = _report_block(page, 'body', body_html)
        page = _report_block(page, 'ratings', ratings_html)

        out_path = out_dir / f"report-{slug}.html"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(page)
        written.append(out_path)

    if written:
        print(f"✓ Rendered {len(written)} fan report page(s) to {out_dir}/report-*.html")
    return written


def build_fixtures_json(data_dir, output_path):
    """Publish the upcoming-fixtures list as out/fixtures.json.

    Consumed by the ratings worker's matchday cron (see
    backend/ratings-worker/worker.js getSiteFixtures) so ballot windows come
    from the same curated fixtures the site shows — TheSportsDB + the
    maintainer's overrides — at zero API cost. Kickoff times are London
    wall-clock, as everywhere else in the pipeline.
    """
    results_data = load_json_data(data_dir / "results.json") or {}
    fixtures = [
        f for f in results_data.get("fixtures", [])
        if f.get("match_id") and f.get("date")
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "Europe/London",
        "fixtures": fixtures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"✓ Rendered to {output_path} ({len(fixtures)} fixtures for the ballot cron)")


def main():
    root = Path(__file__).resolve().parent.parent
    template_path = root / "templates" / "index.template.html"
    data_dir = root / "data"
    output_path = root / "out" / "index.html"

    if not template_path.exists():
        print(f"ERROR: Template not found at {template_path}", file=sys.stderr)
        return 1

    try:
        build_site(template_path, data_dir, output_path)
        # Archive pages rendered from the same data
        news_data = load_json_data(data_dir / "news.json") or FALLBACK_NEWS
        build_archive_news(
            root / "templates" / "archive-news.template.html",
            data_dir,
            root / "out" / "archive-news.html",
            news_data,
        )
        # RSS feed from the same data (news uses the rolling history so the
        # feed doesn't drop items between fetches)
        club_data = load_json_data(data_dir / "club.json") or FALLBACK_CLUB
        youtube_data = load_json_data(data_dir / "youtube.json") or FALLBACK_YOUTUBE
        history = load_json_data(data_dir / "news-history.json") or {}
        feed_news = (history.get("items") or news_data.get("items", []))[:30]
        build_feed(
            root / "out" / "feed.xml",
            feed_news,
            club_data.get("items", []),
            youtube_data.get("items", []),
        )
        # Approved fan match reports (approve-by-file flow —
        # docs/REPORT-PUBLISHING.md)
        build_reports(
            root / "templates" / "report.template.html",
            data_dir,
            root / "out",
        )
        # Fan reports archive page, rendered from the same data/reports/
        # files (the index box is rendered inside build_site above).
        build_archive_reports(
            root / "templates" / "archive-reports.template.html",
            root / "out" / "archive-reports.html",
            load_published_reports(data_dir),
        )
        # Publish the fixtures list (out/fixtures.json) — the ratings worker's
        # matchday cron reads this to know when to open ballots (free, no API).
        build_fixtures_json(data_dir, root / "out" / "fixtures.json")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
