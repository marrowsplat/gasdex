#!/usr/bin/env python3
"""
fetch_news.py — Fetch Bristol Rovers news from multiple sources.

Sources:
  1. Google News RSS (search "Bristol Rovers")
  2. BBC Sport RSS (Bristol Rovers team feed)
  3. Bristol Post RSS (Bristol Rovers tag)

Output: data/news.json with schema:
  {
    "fetched_at": "<ISO8601 UTC>",
    "sample": <bool>,
    "items": [
      {"title": str, "url": str, "source": str, "published": "<ISO8601>"},
      ...
    ]
  }
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for common.py
sys.path.insert(0, os.path.dirname(__file__))
from common import (
    get_project_root, fetch_url, parse_rss, normalize_title,
    dedupe_by_title, ensure_iso8601, sort_by_date_desc, save_json,
    get_source_from_url
)
from news_filter import filter_items

# Configuration
FEEDS = {
    "Google News": "https://news.google.com/rss/search?q=%22Bristol+Rovers%22&hl=en-GB&gl=GB&ceid=GB:en",
    "BBC Sport": "https://feeds.bbci.co.uk/sport/football/teams/bristol-rovers/rss.xml",
    "Bristol Post": "https://www.bristolpost.co.uk/all-about/bristol-rovers-fc?service=rss",
}

MAX_ITEMS = 12
TIMEOUT = 10


def fetch_news():
    """Fetch news from all configured feeds."""
    items = []
    sources_worked = []
    sources_failed = []

    for source_name, feed_url in FEEDS.items():
        print(f"Fetching {source_name}...")
        xml = fetch_url(feed_url, timeout=TIMEOUT)

        if not xml:
            print(f"  ✗ Failed to fetch {source_name}")
            sources_failed.append(source_name)
            continue

        parsed = parse_rss(xml)
        print(f"  ✓ Got {len(parsed)} items from {source_name}")
        sources_worked.append(source_name)

        # Add source and normalize dates
        for item in parsed:
            item['source'] = source_name
            item['published'] = ensure_iso8601(item.get('published', ''))
            items.append(item)

    print(f"\nSources working: {', '.join(sources_worked)}")
    if sources_failed:
        print(f"Sources failed: {', '.join(sources_failed)}")

    # Relevance filter (see news_filter.py — keeps Bristol City et al. out)
    before = len(items)
    items = filter_items(items, log=print)
    if len(items) < before:
        print(f"Relevance filter removed {before - len(items)} item(s)")

    # Dedupe by title and sort newest first
    items = dedupe_by_title(items)
    items = sort_by_date_desc(items)

    # Keep top N
    items = items[:MAX_ITEMS]

    is_sample = len(sources_worked) < len(FEEDS)
    if is_sample:
        print(f"\n⚠ Only {len(sources_worked)}/{len(FEEDS)} feeds live; using sample data")

    return items, is_sample, sources_worked


def generate_sample_data():
    """
    Generate realistic sample data for July 2026 Bristol Rovers pre-season.
    """
    samples = [
        {
            "title": "Bristol Rovers confirm squad signings ahead of 2026-27 season",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/19/squad-signings",
            "source": "Bristol Rovers",
            "published": "2026-07-19T14:30:00Z"
        },
        {
            "title": "Shrewsbury Town vs Bristol Rovers - Pre-season friendly preview",
            "url": "https://www.bbc.co.uk/sport/football/event/12345",
            "source": "BBC Sport",
            "published": "2026-07-19T10:00:00Z"
        },
        {
            "title": "Rovers complete pre-season tour of Spain",
            "url": "https://www.bristolpost.co.uk/sport/bristol-rovers/2026/07/18/spain-tour",
            "source": "Bristol Post",
            "published": "2026-07-18T16:45:00Z"
        },
        {
            "title": "New Rovers manager targets promotion push",
            "url": "https://www.bbc.co.uk/sport/football/rovers-manager",
            "source": "BBC Sport",
            "published": "2026-07-17T12:15:00Z"
        },
        {
            "title": "Bristol Rovers fan zone opens at Memorial Stadium",
            "url": "https://www.bristolpost.co.uk/sport/bristol-rovers/2026/07/16/fan-zone",
            "source": "Bristol Post",
            "published": "2026-07-16T09:30:00Z"
        },
        {
            "title": "Season ticket sales exceed expectations",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/15/season-tickets",
            "source": "Bristol Rovers",
            "published": "2026-07-15T15:00:00Z"
        },
        {
            "title": "Youth academy players join first-team training camp",
            "url": "https://www.bbc.co.uk/sport/football/youth-academy",
            "source": "BBC Sport",
            "published": "2026-07-14T11:20:00Z"
        },
        {
            "title": "Rovers sign promising midfielder on long-term deal",
            "url": "https://www.bristolpost.co.uk/sport/bristol-rovers/2026/07/13/new-midfielder",
            "source": "Bristol Post",
            "published": "2026-07-13T14:45:00Z"
        },
        {
            "title": "Memorial Stadium undergoes summer maintenance",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/12/stadium-maintenance",
            "source": "Bristol Rovers",
            "published": "2026-07-12T10:00:00Z"
        },
        {
            "title": "Bristol Rovers announce new shirt sponsor partnership",
            "url": "https://www.bbc.co.uk/sport/football/sponsors",
            "source": "BBC Sport",
            "published": "2026-07-11T13:30:00Z"
        },
        {
            "title": "Friendly match results from Rovers' Spanish tour",
            "url": "https://www.bristolpost.co.uk/sport/bristol-rovers/2026/07/10/friendly-results",
            "source": "Bristol Post",
            "published": "2026-07-10T17:00:00Z"
        },
        {
            "title": "Five new signings complete Rovers' summer transfers",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/09/summer-transfers",
            "source": "Bristol Rovers",
            "published": "2026-07-09T12:00:00Z"
        }
    ]
    return samples


def main():
    project_root = get_project_root()
    output_path = os.path.join(project_root, "data", "news.json")

    print("=== GasDex News Fetcher ===\n")

    items, is_sample, sources = fetch_news()

    # If all sources failed, use sample data
    if not items:
        print("\n⚠ All feeds failed to fetch; generating sample data")
        items = generate_sample_data()
        is_sample = True

    now_utc = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    output = {
        "fetched_at": now_utc,
        "sample": is_sample,
        "items": items
    }

    save_json(output, output_path)
    print(f"\n✓ Saved {len(items)} items to {output_path}")


if __name__ == "__main__":
    main()
