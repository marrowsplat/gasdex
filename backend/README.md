# GasDex Backend

Two serverless components for fan features (ratings & reports).

## Components

### 1. Ratings Worker (`ratings-worker/`)

Cloudflare Worker handling fan player rating ballots.

- **Files**: `worker.js`, `wrangler.toml`
- **Endpoints**: POST `/ballot`, GET `/aggregate?match_id=...`, GET `/ballot-config?match_id=...`
- **Storage**: Cloudflare KV
- **Deployment**: `cd ratings-worker && wrangler publish`

See `docs/backend-notes.md` for full setup.

### 2. Report Intake (`report-intake/`)

Python pipeline for rendering approved fan match reports to static HTML.

- **Files**: `render_report.py`, `sample-input.json`, `sample-output/`
- **Usage**: `python3 render_report.py INPUT.json [OUTPUT.html]`
- **Output**: Static HTML matching `site/report-example.html` design

See `docs/backend-notes.md` for deployment flow.

## Quick Start

### Test Report Rendering

```bash
python3 report-intake/render_report.py \
  report-intake/sample-input.json \
  report-intake/sample-output/test.html

# Validate generated HTML
python3 ../tools/validate.py report-intake/sample-output/test.html
```

### Deploy Ratings Worker

```bash
cd ratings-worker
wrangler login
# Update wrangler.toml with your KV namespace ID
wrangler publish
```

## Documentation

See `docs/backend-notes.md` for:
- Complete API specification
- Deployment instructions
- Cost estimates (free tier eligible)
- Security notes
- Provisional decisions awaiting sign-off

## Status

**PROVISIONAL** — all code written and tested, awaiting the maintainer's approval before wiring frontend (`site/rate.html` and `site/submit.html`).
