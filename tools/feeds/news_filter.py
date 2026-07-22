#!/usr/bin/env python3
"""news_filter.py — relevance filter for the GasDex news feed.

Policy (maintainer decisions, 22 Jul 2026):

1. BOXSCORE BLOCK (all sources): auto-generated stat pages are never news.
   Reject any headline matching "Boxscore" / "Box Score" / "Live Score"
   (FOX Sports produces these for every EFL match).

2. BRISTOL CITY RULE (all sources): reject any headline mentioning
   Bristol City UNLESS "Bristol Rovers" appears BEFORE "Bristol City" in
   the headline (keeps derby coverage framed from the Rovers side, e.g.
   "Bristol Rovers vs Bristol City preview"; rejects City-centric pieces
   that merely mention Rovers).

3. ROVERS-IN-HEADLINE RULE (Google News items only): the Google News
   search feed matches "Bristol Rovers" anywhere in article BODIES, so a
   headline test is required. Keep only if, after neutralising other
   clubs named Rovers (Blackburn/Doncaster/Tranmere/Forest Green/Raith),
   the headline still contains "Bristol Rovers", a standalone "Rovers",
   or "Gashead(s)". The BBC team feed and Bristol Post tag feed are
   Rovers-only by construction and are exempt from this rule (but not
   from rules 1-2).

Opposition-club coverage of Rovers matches (e.g. "Bristol Rovers 1
Pompey 1 - Portsmouth FC") is deliberately KEPT — the away view of a
Rovers match is of interest; it passes rule 3 naturally.
"""
import re

# Sources whose feeds are Rovers-scoped by construction; exempt from the
# Rovers-in-headline requirement (rules 1-2 still apply).
TRUSTED_SOURCES = {"BBC Sport", "Bristol Post"}

BOXSCORE_RE = re.compile(r'\b(box\s*score|live\s*score)\b', re.IGNORECASE)

# Other clubs named "Rovers" — neutralised before the standalone-"Rovers"
# test so e.g. "Forest Green Rovers sign striker" doesn't pass.
OTHER_ROVERS = [
    "blackburn rovers",
    "doncaster rovers",
    "tranmere rovers",
    "forest green rovers",
    "raith rovers",
]

STANDALONE_ROVERS_RE = re.compile(r'\brovers\b')
GASHEADS_RE = re.compile(r'\bgashead(s)?\b')


def is_relevant(item):
    """Return (keep: bool, reason: str) for a news item.

    reason is "" when kept, otherwise a short human-readable explanation
    (used by fetcher logs and the history scrubber).
    """
    title = (item.get("title") or "")
    t = title.lower()

    # Rule 1: boxscore / live-score stat pages
    if BOXSCORE_RE.search(t):
        return False, "auto-generated boxscore/live-score page"

    # Rule 2: Bristol City rule
    if "bristol city" in t:
        rovers_pos = t.find("bristol rovers")
        if rovers_pos == -1 or rovers_pos > t.find("bristol city"):
            return False, "Bristol City headline (Rovers not named first)"

    # Rule 3: Rovers must be in the headline (Google News only)
    if item.get("source") not in TRUSTED_SOURCES:
        cleaned = t
        for club in OTHER_ROVERS:
            cleaned = cleaned.replace(club, " ")
        if ("bristol rovers" not in cleaned
                and not STANDALONE_ROVERS_RE.search(cleaned)
                and not GASHEADS_RE.search(cleaned)):
            return False, "Rovers not in headline"

    return True, ""


def filter_items(items, log=None):
    """Filter a list of news items; optionally log rejections via log(msg)."""
    kept = []
    for item in items:
        keep, reason = is_relevant(item)
        if keep:
            kept.append(item)
        elif log:
            log(f"  ✗ FILTERED ({reason}): {item.get('title', '')[:90]}")
    return kept
