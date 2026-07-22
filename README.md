# GasDex

**Unofficial Bristol Rovers aggregator** — a fast, text-dense index bringing together news, official announcements, YouTube highlights, latest results, and fan content in one daily-check-worthy page.

## What's here

A static site generator that pulls live feeds from:
- **News**: Google News + BBC Sport + Bristol Post RSS
- **Club announcements**: Official Bristol Rovers announcements (via Google News site filter)
- **YouTube**: Official channel + Community Trust verified videos
- **Results & fixtures**: TheSportsDB (free, live, no API key needed)
- **Fan content**: Match reports (reviewed by the maintainer) and player ratings (structured scores only)

Built with Python 3 (stdlib only), no external dependencies. Designed to rebuild every ~3 hours via GitHub Actions and deploy to GitHub Pages — fully automated, zero manual work except reviewing fan match reports.

## Quick start (local)

```bash
# Run fetchers to gather live data
python3 tools/feeds/fetch_news.py
python3 tools/feeds/fetch_club.py
python3 tools/feeds/fetch_youtube.py
python3 tools/feeds/fetch_results.py

# Build the site
python3 tools/build_site.py

# Validate output
python3 tools/validate.py out/index.html

# Open in browser
open out/index.html
```

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for step-by-step GitHub Pages setup and the Cloudflare Pages alternative.

## File structure

- `site/` — Approved design reference (index.html + internal pages)
- `templates/index.template.html` — Template for dynamic rendering
- `tools/build_site.py` — Static site generator
- `tools/feeds/` — Feed fetcher scripts
- `data/` — Live feed JSON + results rolling cache
- `out/` — Generated site (build output only)
- `docs/` — Technical documentation

## Design

- Dark theme (charcoal background) with Rovers blue (`#0d4f9e`) and gold accents (`#ffc400`)
- Mobile-responsive, Verdana 13px, rounded cards with subtle shadows
- 7 background themes via visitor-facing picker (choice saved to browser)
- External links open in new tab with `↗` marker
- Freshness signals: "NEW" tags on recent items, timestamps everywhere

## Credits

Data sources:
- [TheSportsDB](https://www.thesportsdb.com/) — Results & fixtures (free, no key)
- [Google News RSS](https://news.google.com/) — General news aggregation
- [BBC Sport RSS](https://www.bbc.co.uk/sport/) — Official sports coverage
- [Bristol Post RSS](https://www.bristolpost.co.uk/) — Local journalism
- [YouTube](https://www.youtube.com/) — Official Bristol Rovers FC channel

Built by a Gashead, with help from automation. This is an unofficial fan site.

---

**Live site**: [gasdex.co.uk](https://gasdex.co.uk)
