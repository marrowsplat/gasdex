#!/usr/bin/env python3
"""
fetch_youtube.py — Fetch Bristol Rovers videos from YouTube channels.

Fetches RSS feeds from configured YouTube channels (official + fan channels).
Merges, dedupes, sorts by date, and keeps top 8 videos.

OUTPUT SCHEMA:
  data/youtube.json:
  {
    "fetched_at": "<ISO8601 UTC>",
    "sample": <bool>,
    "items": [
      {"title": str, "url": str, "channel": str, "published": "<ISO8601>"},
      ...
    ]
  }

CHANNEL CONFIGURATION:
Edit CHANNELS dict below to add/remove YouTube channels.
To find channel IDs: visit youtube.com/channel/[ID] or YouTube Data API docs.
"""

import os
import sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    get_project_root, fetch_url, ensure_iso8601,
    dedupe_by_title, sort_by_date_desc, save_json
)

# ============================================================================
# CHANNEL CONFIGURATION - Edit this section to add/remove channels
# ============================================================================
CHANNELS = {
    # Official Bristol Rovers channel — VERIFIED 19 Jul 2026 (active, posts matchday
    # content; confirmed via Wikidata + live RSS test)
    "UC7dLKUWi0j2nvokTme6U4TQ": "Bristol Rovers FC",

    # Bristol Rovers Community Trust — VERIFIED 19 Jul 2026 (official trust channel)
    "UCKlHaPHM5Dq-QTtgJbZGEgw": "Community Trust",

    # Fan channels — CHOSEN 22 Jul 2026:

    # Talking Gas Podcast — VERIFIED 22 Jul 2026 (6K subs, match reactions
    # within a day; live RSS test green)
    "UCitIveDPjYRO5zj0x3e22NQ": "Talking Gas",

    # GasCast Podcast — VERIFIED 22 Jul 2026 (YouTube channel dormant since
    # Sep 2025 but included deliberately: contributes nothing while quiet,
    # picks up automatically if they resume video)
    "UCMMxnHDiNtrTbhwsHOSwiuw": "GasCast",

    # Rejected (22 Jul 2026): Gas to Glory (FM26 gameplay, off-topic for the
    # feed); The Rovers Report + willbrfc (dead). Old duplicate "Bristol
    # Rovers" channel UChbOETMgX-0QsjauJfvuNPQ is dead (nothing since 2012)
    # — do not use.
}
# ============================================================================

MAX_ITEMS = 8
TIMEOUT = 10


def parse_youtube_rss(xml_data):
    """
    Parse YouTube RSS feed.
    Return list of dicts: {title, url, published}.
    """
    items = []
    if not xml_data:
        return items

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return items

    # YouTube uses Atom feed format; look for entry elements
    # Namespace: http://www.w3.org/2005/Atom
    ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015/metadata.xsd'}

    for entry in root.findall('atom:entry', ns):
        title = entry.findtext('atom:title', '', ns) or ''
        link_elem = entry.find("atom:link[@rel='alternate']", ns)
        url = link_elem.get('href', '') if link_elem is not None else ''

        published = entry.findtext('atom:published', '', ns) or ''

        if title and url:
            items.append({
                'title': title.strip(),
                'url': url.strip(),
                'published': published.strip()
            })

    return items


def fetch_youtube_videos():
    """Fetch videos from all configured channels."""
    items = []
    channels_worked = []
    channels_failed = []

    for channel_id, channel_name in CHANNELS.items():
        print(f"Fetching {channel_name}...")
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

        xml = fetch_url(feed_url, timeout=TIMEOUT)

        if not xml:
            print(f"  ✗ Failed to fetch {channel_name}")
            channels_failed.append(channel_name)
            continue

        parsed = parse_youtube_rss(xml)
        print(f"  ✓ Got {len(parsed)} videos from {channel_name}")
        channels_worked.append(channel_name)

        for item in parsed:
            item['channel'] = channel_name
            item['published'] = ensure_iso8601(item.get('published', ''))
            items.append(item)

    print(f"\nChannels working: {', '.join(channels_worked)}")
    if channels_failed:
        print(f"Channels failed: {', '.join(channels_failed)}")

    # Dedupe by title and sort newest first
    items = dedupe_by_title(items)
    items = sort_by_date_desc(items)
    items = items[:MAX_ITEMS]

    is_sample = len(channels_worked) < len(CHANNELS)
    if is_sample:
        print(f"\n⚠ Only {len(channels_worked)}/{len(CHANNELS)} channels live; using sample data")

    return items, is_sample, channels_worked


def generate_sample_data():
    """
    Generate realistic sample data for July 2026 Bristol Rovers YouTube.
    """
    samples = [
        {
            "title": "Pre-season highlights: Shrewsbury Town 1-2 Bristol Rovers",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "channel": "Bristol Rovers FC",
            "published": "2026-07-19T16:30:00Z"
        },
        {
            "title": "New signing announcement: Midfielder joins on 3-year deal",
            "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "channel": "Bristol Rovers FC",
            "published": "2026-07-18T12:00:00Z"
        },
        {
            "title": "Behind the scenes: Spanish pre-season tour vlog",
            "url": "https://www.youtube.com/watch?v=OPf0YbXqDm0",
            "channel": "Rovers Daily",
            "published": "2026-07-17T18:15:00Z"
        },
        {
            "title": "Manager interview: 2026-27 season expectations",
            "url": "https://www.youtube.com/watch?v=e-IWRmpefzE",
            "channel": "Bristol Rovers FC",
            "published": "2026-07-16T14:45:00Z"
        },
        {
            "title": "Stadium tour: Memorial Stadium renovation update",
            "url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
            "channel": "Gas Nation",
            "published": "2026-07-15T11:30:00Z"
        },
        {
            "title": "Fan reaction: New season shirt reveal",
            "url": "https://www.youtube.com/watch?v=BJ0xBCwkg3E",
            "channel": "Rovers Daily",
            "published": "2026-07-14T19:00:00Z"
        },
        {
            "title": "Academy graduates make first-team debut",
            "url": "https://www.youtube.com/watch?v=aqz-KE-bpKE",
            "channel": "Bristol Rovers FC",
            "published": "2026-07-13T15:20:00Z"
        },
        {
            "title": "Season preview: Promotion hopes and squad depth",
            "url": "https://www.youtube.com/watch?v=rN-V_SZpRG8",
            "channel": "Gas Nation",
            "published": "2026-07-12T13:10:00Z"
        }
    ]
    return samples


def main():
    project_root = get_project_root()
    output_path = os.path.join(project_root, "data", "youtube.json")

    print("=== GasDex YouTube Fetcher ===\n")
    print("Configured channels:")
    for channel_id, channel_name in CHANNELS.items():
        print(f"  - {channel_name} ({channel_id[:8]}...)")
    print()

    items, is_sample, channels_worked = fetch_youtube_videos()

    # If no channels worked, use sample data
    if not items:
        print("\n⚠ No YouTube channels could be fetched; generating sample data")
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
