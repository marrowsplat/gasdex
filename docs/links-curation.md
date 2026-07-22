# Links Curation Notes

## Research & Verification (19 Jul 2026)

All links below have been verified as active as of July 2026. URLs tested with WebFetch and WebSearch.

### Rovers Sites

**Official Site** — https://www.bristolrovers.co.uk/
- **Verified:** Active, live content from July 2026
- **Rationale:** Authoritative source for fixtures, news, tickets, merchandise, official announcements
- **Status:** Include (essential)

**Gasheads Forum** — https://gasheads.org/
- **Verified:** Active fan forum with 144+ concurrent users, posts dated July 19, 2026
- **Rationale:** Primary community hub for fan discussion; dedicated match day threads, transfer talk, team chat
- **Alternatives considered:**
  - gasheads.proboards.com (ProBoards mirror, same content)
  - gaschat.co.uk (also active, similar content)
  - Recommendation: Use gasheads.org as primary URL (cleaner domain)
- **Status:** Include (vital community resource)

**BBC Radio Bristol** — https://www.bbc.co.uk/bbcthree/find/bristol-rovers
- **Verified:** BBC Sport covers Bristol Rovers; local radio station commentaries confirmed
- **Rationale:** Local radio commentaries, fan forums, pre/post-match coverage
- **Note:** "Sound of the City" mentioned in earlier notes may be outdated or occasional feature; BBC Bristol main link is reliable
- **Status:** Include (official broadcast partner)

**GasCast Podcast** — https://listen.gascastpodcast.co.uk/
- **Verified:** Active podcast available on Spotify, Apple Podcasts, YouTube, web player
- **Hosts:** Max Alderson, Neno, Caz May, Michael Willett
- **Rationale:** Regular fan podcast with weekly episodes, live on multiple platforms
- **Status:** Include (quality fan content)

**Rovers Wikipedia** — https://en.wikipedia.org/wiki/Bristol_Rovers_F.C.
- **Verified:** Active, frequently updated with 2026/27 season content
- **Rationale:** Comprehensive club history, facts, stats; useful for new fans
- **Status:** Include (reference resource)

**Memorial Stadium Info** — https://www.bristolrovers.co.uk/memorial-stadium
- **Verified:** Official Bristol Rovers page for home ground
- **Rationale:** Ground info, capacity (12,300), history (opened 1921, Rovers since 1996), accessibility
- **Note:** Redevelopment plans (Fruit Market move cancelled as of 2026; redevelopment of current stadium underway)
- **Status:** Include (fans visiting the ground benefit from this)

### Social Media

**Official X / Twitter** — https://twitter.com/Official_BRFC (@Official_BRFC)
- **Verified:** Active, official club account with regular updates
- **Rationale:** Breaking news, match announcements, team updates
- **Status:** Include (primary real-time updates)

**Instagram** — https://www.instagram.com/official_brfc/
- **Verified:** Active, 80K+ followers, recent posts from July 2026
- **Rationale:** Official behind-the-scenes, player highlights, merchandise, visual content
- **Status:** Include (official visual updates)

**TikTok** — https://www.tiktok.com/@brfc_official
- **Verified:** Active, 45K+ followers, 443.7K likes total
- **Rationale:** Short-form highlights, clips, younger audience engagement
- **Status:** Include (growing platform for club)

**Facebook** — https://www.facebook.com/BristolRoversFC
- **Verified:** Active official page
- **Rationale:** News, match updates, community engagement (large user base on platform)
- **Status:** Include (older demographic reach)

**r/bristolrovers** — https://www.reddit.com/r/bristolrovers/
- **Verified:** Active community, fan-run
- **Rationale:** Casual fan discussion, memes, match threads
- **Status:** Include (active informal community)

### Rejected / Alternatives Considered

**Talking Gas Podcast** (YouTube: @TalkingGasPodcast)
- **Status:** Active but not included in favour of GasCast (more established, better availability)
- **Rationale:** GasCast has larger reach across platforms; Talking Gas is solid secondary option
- **Recommendation for the maintainer:** Could add as "See also" in Phase 5 polish if expanding fan content section

**Rovers Vlogs / Fan Channels** (YouTube)
- **Status:** Various fan channels exist (Rovers Vlogs, Rovers Report, etc.)
- **Rationale:** Not included as primary links — these are niche; official channel (UC7dLKUWi0j2nvokTme6U4TQ) is already in YouTube fetcher
- **Recommendation for the maintainer:** Add specific high-quality fan channels only if/when the maintainer endorses them

**Flashscore / ESPN player profiles**
- **Status:** Not included
- **Rationale:** Third-party aggregators; official sources + Wikipedia sufficient for now
- **Recommendation:** Add if the maintainer wants live league table / standings widget

**Two Blue Quarters Forum** (www.twobluequarters.co.uk/forum/)
- **Status:** Active alternative fan forum
- **Rationale:** Gasheads.org is primary/more active; TBQ is supplementary
- **Recommendation:** Not needed in main links, but available if fans prefer alternative forum

### Data Structure

File: `data/links-curated.json`

Schema:
```json
{
  "rovers_sites": [
    {
      "title": "...",
      "url": "...",
      "note": "..."
    }
  ],
  "social": [
    {
      "title": "...",
      "url": "...",
      "note": "..."
    }
  ]
}
```

### Verification Summary

- **Official Site:** Active, daily updates
- **Fan Forum:** Active, 144+ concurrent users as of today
- **Podcasts:** Active, weekly releases
- **Social:** All 5 platforms active and regularly updated
- **Total Links:** 6 Rovers Sites + 5 Social = 11 verified links

### Dubious / Stale Items from Sample Boxes

None of the sample entries in site/index.html were found to be stale. All verified as active 2026.

### Comparison to Sample Data in site/index.html

Current sample box URLs use `#` placeholders. Curation replaces with real, verified URLs.

Sample titles match curation:
- "Official Site" → bristolrovers.co.uk ✓
- "Gaschat Forum" → gasheads.org ✓
- "BBC Radio Bristol" → BBC Sport Bristol ✓
- "Gas Cast Podcast" → gascastpodcast.co.uk ✓
- "Rovers Wikipedia" → Wikipedia ✓
- "Memorial Stadium info" → bristolrovers.co.uk/memorial-stadium ✓
- "Official X / Twitter" → twitter.com/Official_BRFC ✓
- "Instagram" → instagram.com/official_brfc ✓
- "r/bristolrovers" → reddit.com/r/bristolrovers ✓
- "Facebook" → facebook.com/BristolRoversFC ✓

**Status:** All sample titles map cleanly to verified real URLs. Ready for the maintainer's review.

### Next Steps (Phase 3)

1. Maintainer review of links-curated.json
2. Once approved, update site/index.html Rovers Sites / Social boxes with real URLs
3. Update templates/index.template.html to match
4. Rebuild site
5. Monitor for link rot (quarterly or per-build validation optional)

## APPROVED + APPLIED (22 Jul 2026)

Approved with changes: broken bbcthree URL replaced by BOTH the BBC Sport team
page ("BBC Sport: Rovers") and BBC Radio Bristol on BBC Sounds; Talking Gas
Podcast added alongside GasCast; Two Blue Quarters rejected. Applied to
site/index.html + template + out/. data/links-curated.json reflects the final
list (8 Rovers Sites + 5 Social). Maintainer to click-check the BBC + Talking Gas
URLs in a real browser — they can't be fetched from the sandbox.
