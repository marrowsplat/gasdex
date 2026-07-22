"""
Shared helpers for GasDex feed fetchers.
Utilities for parsing RSS, handling timestamps, deduplication, etc.
"""

import os
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse


def get_project_root():
    """
    Resolve project root robustly from this script's location.
    Expected: tools/feeds/common.py → walk up to find the root.
    """
    current = os.path.dirname(os.path.abspath(__file__))
    while current != os.path.dirname(current):  # Stop at filesystem root
        if os.path.exists(os.path.join(current, "templates", "index.template.html")):
            return current
        current = os.path.dirname(current)
    # Fallback: assume 2 levels up from this file
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_url(url, timeout=10):
    """Fetch URL content. Return decoded text or None on error."""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='replace')
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        return None
    except Exception:
        return None


def parse_rss(xml_data):
    """
    Parse RSS feed. Return list of dicts: {title, link, pubdate}.
    Handles standard RSS 2.0 with common namespaces.
    """
    items = []
    if not xml_data:
        return items

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return items

    # Extract items; works with or without namespaces
    for item in root.findall('.//item'):
        title = item.findtext('title', '') or item.findtext('{*}title', '')
        link = item.findtext('link', '') or item.findtext('{*}link', '')

        # Try multiple pubDate field names
        pubdate = (item.findtext('pubDate', '') or
                   item.findtext('{*}pubDate', '') or
                   item.findtext('published', '') or
                   item.findtext('{*}published', '') or
                   '')

        if title and link:
            items.append({
                'title': title.strip(),
                'url': link.strip(),
                'published': pubdate.strip()
            })

    return items


def normalize_title(title):
    """
    Normalize title for deduplication: lowercase, remove extra whitespace,
    strip common punctuation.
    """
    s = title.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'[^\w\s]', '', s)
    return s


def dedupe_by_title(items):
    """
    Deduplicate items by normalized title. Keep first occurrence.
    items: list of dicts with 'title' key.
    """
    seen = set()
    result = []
    for item in items:
        norm = normalize_title(item['title'])
        if norm not in seen:
            seen.add(norm)
            result.append(item)
    return result


def parse_rfc2822(date_str):
    """
    Parse RFC 2822 date (e.g. 'Sat, 18 Jul 2026 15:54:00 GMT').
    Return ISO 8601 UTC string or None.
    """
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
        return dt.isoformat()
    except ValueError:
        try:
            # Try without timezone
            dt = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
            return dt.replace(tzinfo=None).isoformat() + 'Z'
        except ValueError:
            return None


def ensure_iso8601(date_str):
    """
    Convert various date formats to ISO 8601 UTC or return as-is if already ISO.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Already ISO 8601?
    if 'T' in date_str and date_str[-1] in ('Z', '+', '-'):
        return date_str

    # Try RFC 2822
    iso = parse_rfc2822(date_str)
    if iso:
        return iso

    # Fallback: return as-is
    return date_str


def sort_by_date_desc(items):
    """
    Sort items by published date, newest first.
    Gracefully handles unparseable dates.
    """
    def sort_key(item):
        published = item.get('published', '')
        if not published:
            return datetime.min.isoformat()
        # Try parsing
        try:
            if published.endswith('Z'):
                return published
            dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
            return dt.isoformat()
        except (ValueError, AttributeError):
            try:
                dt = datetime.strptime(published, '%a, %d %b %Y %H:%M:%S GMT')
                return dt.isoformat()
            except ValueError:
                return published

    return sorted(items, key=sort_key, reverse=True)


def save_json(data, filepath):
    """Save data dict to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(filepath):
    """Load JSON file, return dict or None."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def get_source_from_url(url):
    """Extract source name from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')

    if 'bbc' in domain:
        return 'BBC Sport'
    elif 'bristolpost' in domain or 'bristol' in domain:
        return 'Bristol Post'
    elif 'news.google' in domain:
        return 'Google News'
    elif 'youtube' in domain or 'youtu.be' in domain:
        return 'YouTube'
    elif 'bristolrovers' in domain:
        return 'Bristol Rovers'
    else:
        return domain.split('.')[0].title()
