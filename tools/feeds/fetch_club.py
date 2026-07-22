#!/usr/bin/env python3
"""
fetch_club.py — Fetch official Bristol Rovers club announcements.

Strategy: Filtered Google News for site:bristolrovers.co.uk
Fallback: General "Bristol Rovers" news filtered manually

Output: data/club.json with schema:
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

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    get_project_root, fetch_url, parse_rss, normalize_title,
    dedupe_by_title, ensure_iso8601, sort_by_date_desc, save_json
)

# Configuration
FEED_OFFICIAL = "https://news.google.com/rss/search?q=site:bristolrovers.co.uk&hl=en-GB&gl=GB&ceid=GB:en"
FEED_FALLBACK = "https://news.google.com/rss/search?q=%22Bristol+Rovers%22+official&hl=en-GB&gl=GB&ceid=GB:en"

MAX_ITEMS = 8
TIMEOUT = 10


def fetch_club_announcements():
    """Fetch official club announcements."""
    items = []
    sources_worked = []

    # Try primary feed (site:bristolrovers.co.uk)
    print("Fetching official club site announcements...")
    xml = fetch_url(FEED_OFFICIAL, timeout=TIMEOUT)

    if xml:
        parsed = parse_rss(xml)
        print(f"  ✓ Got {len(parsed)} items from official site")
        sources_worked.append("Bristol Rovers Official")

        for item in parsed:
            item['source'] = "Bristol Rovers"
            item['published'] = ensure_iso8601(item.get('published', ''))
            items.append(item)
    else:
        print("  ✗ Failed to fetch official site feed")

    # If primary feed had few results, try fallback
    if len(items) < MAX_ITEMS // 2:
        print("Fetching fallback announcements feed...")
        xml = fetch_url(FEED_FALLBACK, timeout=TIMEOUT)

        if xml:
            parsed = parse_rss(xml)
            print(f"  ✓ Got {len(parsed)} items from fallback")

            for item in parsed:
                item['source'] = "Bristol Rovers"
                item['published'] = ensure_iso8601(item.get('published', ''))
                items.append(item)
        else:
            print("  ✗ Failed to fetch fallback feed")

    # Dedupe and sort
    items = dedupe_by_title(items)
    items = sort_by_date_desc(items)
    items = items[:MAX_ITEMS]

    is_sample = len(sources_worked) == 0
    if is_sample:
        print("\n⚠ No official feeds could be fetched; using sample data")

    return items, is_sample


def generate_sample_data():
    """
    Generate realistic sample data for July 2026 Bristol Rovers announcements.
    """
    samples = [
        {
            "title": "Bristol Rovers confirm summer signings",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/19/summer-signings",
            "source": "Bristol Rovers",
            "published": "2026-07-19T14:30:00Z"
        },
        {
            "title": "2026-27 Season ticket holder benefits announced",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/18/season-tickets",
            "source": "Bristol Rovers",
            "published": "2026-07-18T11:00:00Z"
        },
        {
            "title": "New manager appointed for upcoming season",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/17/new-manager",
            "source": "Bristol Rovers",
            "published": "2026-07-17T15:45:00Z"
        },
        {
            "title": "Pre-season friendly fixture schedule released",
            "url": "https://www.bristolrovers.co.uk/fixtures/2026/07/friendlies",
            "source": "Bristol Rovers",
            "published": "2026-07-16T10:30:00Z"
        },
        {
            "title": "Memorial Stadium summer maintenance programme complete",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/15/stadium-maintenance",
            "source": "Bristol Rovers",
            "published": "2026-07-15T09:00:00Z"
        },
        {
            "title": "Academy prospect signs first professional contract",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/14/academy-signing",
            "source": "Bristol Rovers",
            "published": "2026-07-14T13:20:00Z"
        },
        {
            "title": "New commercial partnership announced",
            "url": "https://www.bristolrovers.co.uk/news/2026/07/13/partnership",
            "source": "Bristol Rovers",
            "published": "2026-07-13T12:00:00Z"
        },
        {
            "title": "Early bird ticket offer extended",
            "url": "https://www.bristolrovers.co.uk/tickets/2026/07/early-bird",
            "source": "Bristol Rovers",
            "published": "2026-07-12T14:45:00Z"
        }
    ]
    return samples


def main():
    project_root = get_project_root()
    output_path = os.path.join(project_root, "data", "club.json")

    print("=== GasDex Club Announcements Fetcher ===\n")

    items, is_sample = fetch_club_announcements()

    # If no items fetched, use sample data
    if not items:
        print("\n⚠ Failed to fetch club announcements; generating sample data")
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
