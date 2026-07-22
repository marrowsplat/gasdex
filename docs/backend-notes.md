# Backend Implementation Notes — GasDex

Date: 2026-07-19
Status: PROVISIONAL (awaiting the maintainer's sign-off before wiring the frontend)

## Overview

This document covers the two backend components:
1. **Ratings Worker** — Cloudflare Worker handling fan player ratings ballots
2. **Report Intake** — Static-site-friendly report submission + rendering pipeline

Both are designed for minimal maintenance cost (free tier where possible) and zero database server management.

---

## Component 1: Ratings Worker (Cloudflare Worker)

### Architecture

- **Platform**: Cloudflare Workers (edge compute, serverless)
- **Storage**: Cloudflare KV (Workers Key-Value store, free tier: 1GB, 100k req/day)
- **Framework**: Plain JavaScript, no build step required
- **Location**: `backend/ratings-worker/`

### Files

- `worker.js` — Main handler; ~350 lines, fully self-contained
- `wrangler.toml` — Configuration for Cloudflare CLI deployment

### Endpoints

#### POST /ballot
**Accept a fan rating ballot.**

Request body (JSON):
```json
{
  "match_id": "gillingham-h-20260711",
  "scores": {
    "J. Ward": 8,
    "R. Sotiriou": 7,
    "P. Omochere": 5
  },
  "motm": "J. Ward"
}
```

Response (success, 200):
```json
{
  "ok": true,
  "ballot_id": "ballot_1721...xyz"
}
```

Response (validation error, 400):
```json
{
  "error": "invalid score for P. Omochere: must be integer 1-10"
}
```

Response (rate limited, 429):
```json
{
  "error": "rate limited"
}
```

**Validation**:
- All listed players must have a score (integer, 1–10)
- MotM player must be in the scores object
- Ballot window must be open (checked against ballot config)
- One ballot per fan: best-effort enforcement via hashed IP + browser token cookie
- Rate limit: 10 requests per 15 minutes per IP

**One-Ballot-Per-Fan Mechanism** (PROVISIONAL — **documented limitations**):
- Client IP is hashed (never stored in plaintext)
- Browser ballot token read from `gasdex-ballot-token` cookie (or generated if absent)
- Hash of IP + token checked against voter registry per match
- **Limitations**:
  - Shared IP (office, school, family wifi): multiple fans = one allowed vote
  - VPN/proxy: different exit IPs = multiple votes from one fan (undetectable)
  - Hard to verify ownership (same risk as any unauth'd form)
  - If needed, can upgrade to email-based verification (send confirmation link) — contact the maintainer
- This matches GitHub/Twitter poll patterns: convenience over perfect anti-fraud

#### GET /aggregate?match_id=...
**Fetch aggregated ratings for a match.**

Response (200):
```json
{
  "match_id": "gillingham-h-20260711",
  "count": 214,
  "players": {
    "J. Ward": {
      "avg": 8.2,
      "motm_votes": 131
    },
    "R. Sotiriou": {
      "avg": 7.1,
      "motm_votes": 42
    }
  }
}
```

Response (no ballots yet):
```json
{
  "match_id": "gillingham-h-20260711",
  "count": 0,
  "players": {}
}
```

**PROVISIONAL performance note**: This endpoint iterates ballots by fetching a rolling list. In production with many matches, consider:
- A dedicated aggregate key (`agg:{match_id}`) updated incrementally as ballots arrive
- Cloudflare Workers Analytics to track throughput

#### GET /ballot-config?match_id=...
**Fetch ballot definition for a match.**

Response (200):
```json
{
  "match_id": "gillingham-h-20260711",
  "players": ["J. Ward", "R. Sotiriou", "I. Hutchinson", ...],
  "openAt": "2026-07-11T17:00:00Z",
  "closeAt": "2026-07-13T17:00:00Z"
}
```

Response (ballot not open):
```json
{
  "error": "ballot not found"
}
```

### Deployment Steps

#### 1. Create Cloudflare Account & KV Namespace

1. Sign up at https://dash.cloudflare.com (free tier available)
2. Navigate to **Workers & Pages** → **KV**
3. Create a namespace, e.g. `gasdex-ratings`
4. Note the **namespace ID** (you'll need it in step 4)

#### 2. Install Wrangler CLI

```bash
npm install -g wrangler@latest
```

#### 3. Authenticate Wrangler

```bash
wrangler login
# Opens browser to authorize; creates ~/.wrangler/config.toml with API token
```

#### 4. Update wrangler.toml

Edit `backend/ratings-worker/wrangler.toml`:
- Replace `YOUR_KV_NAMESPACE_ID` with your actual namespace ID
- Replace `YOUR_PREVIEW_KV_NAMESPACE_ID` with a preview namespace ID (or use same for MVP)
- Update `routes` with your actual domain (e.g. `gasdex.co.uk`)

#### 5. Deploy

```bash
cd backend/ratings-worker
wrangler publish
```

This deploys to `https://gasdex-ratings.workers.dev` (dev domain) immediately. For custom domain:
- Verify domain in Cloudflare Dashboard
- Add zone route in `wrangler.toml`
- Redeploy

#### 6. Create a Ballot via wrangler CLI (Admin Task)

After a match is played, the maintainer (or the deployment script) creates a ballot config:

```bash
wrangler kv:key put --path=backend/ratings-worker \
  "config:gillingham-h-20260711" \
  '{
    "match_id": "gillingham-h-20260711",
    "players": ["J. Ward", "R. Sotiriou", "I. Hutchinson"],
    "openAt": "2026-07-11T17:00:00Z",
    "closeAt": "2026-07-13T17:00:00Z"
  }' \
  --binding=GASDEX_RATINGS
```

Or write a small admin script (future enhancement).

### Cost & Quotas

| Item | Free Tier | Limit | Cost Over |
|------|-----------|-------|-----------|
| Requests/day | 100,000 | Per day | $0.50 per 10M req |
| KV Storage | 1 GB | Total | $0.50 per GB-month |
| KV Reads | Unlimited | Per req | Included |
| KV Writes | Unlimited | Per req | Included |

**Estimate for GasDex**:
- ~8 site rebuilds/day at 1 request each = ~8 req/day to fetch configs
- ~50–100 votes per match over 48h = ~100 req total per match
- **Result**: Easily under 100k req/day. Monthly cost: **$0** (free tier).

If traffic explodes (1k+ votes per match), upgrade to Cloudflare Workers Paid ($10/mo) for higher limits.

---

## Component 2: Report Intake Pipeline

### Architecture

- **Submission form frontend**: `site/submit.html` (client-side mock; awaits wiring)
- **Report renderer**: `backend/report-intake/render_report.py` (Python, Python 3.8+)
- **Storage**: JSON input files + static HTML output
- **Approval flow**: Email (manual review by the maintainer) → call renderer → commit to site

### Files

- `render_report.py` — Renders approved reports to HTML (350 lines)
- `sample-input.json` — Example report data (JSON)
- `sample-output/` — Generated HTML files (production output)

### Submission Flow (PROVISIONAL)

1. **Frontend**: Fan fills `site/submit.html` form (display name, email, match, title, body, agree checkbox)
2. **Service**: Form POSTs to `/report` endpoint (recommended: same Cloudflare Worker, or third-party like Formspree)
3. **Intake**: Email sent to the maintainer with submission details
4. **Review**: the maintainer reads, possibly edits (typos, house rules check)
5. **Approval**: the maintainer creates `backend/report-intake/approved-reports/MATCH_ID.json` with reviewed content
6. **Render**: Run `python3 backend/report-intake/render_report.py approved-reports/MATCH_ID.json output/reports/MATCH_ID.html`
7. **Publish**: Git commit the HTML, push to GitHub Pages / Cloudflare Pages
8. **Email**: the maintainer replies to fan letting them know report is live

### Report Input Format (JSON)

Required fields:
- `match_id` — Slug for deduplication (e.g., `"gillingham-h-20260711"`)
- `title` — Report title (plain text; escaped during render)
- `author` — Display name (no email; escaped)
- `date_submitted` — ISO 8601 timestamp (e.g., `"2026-07-11T21:40:00Z"`)
- `body` — Plain text (blank-line-separated paragraphs; no HTML)
- `match_team_home`, `match_team_away` — Team names
- `match_score_home`, `match_score_away` — Integers (goals)
- `match_date` — Display string (e.g., `"Sat 11 Jul 2026"`)
- `match_venue` — Venue name
- `match_attendance` — Optional integer (spectators)
- `ratings` — Optional object: `{player_name: {avg: float, motm_votes: int}}`

See `sample-input.json` for a complete example.

### Rendering

```bash
python3 backend/report-intake/render_report.py INPUT.json [OUTPUT.html]
```

- Input: JSON file with report data
- Output: HTML file (defaults to `{match_id}.html` in cwd if not specified)
- All user text is HTML-escaped (safe from XSS)
- Respects design system (background colours, typography, spacing)
- Includes localStorage script to restore visitor's chosen background theme

### Testing

Run the test suite:

```bash
cd backend/report-intake
python3 render_report.py sample-input.json sample-output/test.html
python3 ../../tools/validate.py sample-output/test.html
```

Output: `OK` if HTML is valid (tag balance, link conventions).

### Alternative: Form-to-Email Service (for Frontend Wiring)

If the maintainer wants visitors to submit reports directly from the site (instead of emailing the maintainer), two options:

**Option A: Extend Ratings Worker to handle `/report` endpoint**
- Same Cloudflare Worker
- POST /report: Accept form data, send email via MailChannels (Cloudflare Workers partner)
- Requires MailChannels account (free tier: 100 emails/day)
- Honeypot field to catch bots
- Rate limit: 1 report per IP per hour

**Option B: Third-party service**
- **Formspree** (formspree.io): Free tier, 50 form submissions/month, email forwarding
- **Basin** (usebasin.com): Free, unlimited submissions
- Simpler setup, no code maintenance

For now, **manual email queue** (the maintainer reviews submissions) is the MVP. If it becomes a bottleneck, implement Option A above.

---

## PROVISIONAL Decisions (Awaiting the maintainer's Sign-Off)

1. **One-Ballot-Per-Fan Method**: Hashed IP + browser token. See section "One-Ballot-Per-Fan Mechanism" for limitations. If stricter verification needed, can add email confirmation.

2. **Report Approval Flow**: Manual email queue (the maintainer reads, approves, calls renderer). If volume grows, build a simple admin panel (Cloudflare Pages static site + KV metadata).

3. **KV vs. D1**: Started with KV (simpler for this workload; no schemas). If complex queries needed later (e.g., "all ratings from July"), migrate to Cloudflare D1 (SQL database).

4. **Report Submission Frontend**: Not yet wired. Forms exist as mocks. When ready, implement email service (Formspree or Cloudflare Workers + MailChannels).

5. **Ratings on Static Pages**: Once frontend is wired, the site's `rate.html` would fetch aggregate ratings via CORS from the Worker. This is deferred to Phase 3.

---

## Security Notes

- **No rate limit bypass**: Worker enforces hard limits per IP (not client-side)
- **No auth required**: Ballots are anonymous; name/email collected only for reports
- **CORS headers**: Worker only allows requests from site origin (configurable in `getSiteOrigin()`)
- **XSS protection**: Report renderer HTML-escapes all user text
- **No plaintext IPs**: Hashed before storage
- **No stored passwords**: Stateless (token-based one-ballot-per-fan)

---

## Maintenance & Scaling

### Low Traffic (< 10k votes/match)
- Current implementation sufficient
- Monitor free-tier KV quota via Cloudflare Dashboard
- No ongoing work needed

### Medium Traffic (10k–100k votes/match)
- Upgrade to Cloudflare Workers Paid ($10/mo)
- Implement incremental aggregation (avoid full iteration on `/aggregate`)
- Add monitoring for rate-limit hits

### High Traffic (> 100k votes/match)
- Migrate to Cloudflare D1 (SQL) for efficient aggregation queries
- Implement caching layer (Cloudflare Cache API)
- Consider separate read-only replica for `/aggregate` (D1 read replicas)

---

## Files & Locations

| Purpose | Path | Type |
|---------|------|------|
| Ratings Worker code | `backend/ratings-worker/worker.js` | JS (Node.js) |
| Worker config | `backend/ratings-worker/wrangler.toml` | TOML |
| Report renderer | `backend/report-intake/render_report.py` | Python 3 |
| Sample report input | `backend/report-intake/sample-input.json` | JSON |
| Sample report output | `backend/report-intake/sample-output/gillingham-h-20260711.html` | HTML |
| Deployment notes (this file) | `docs/backend-notes.md` | Markdown |

---

## Next Steps (for the maintainer)

1. **Decide**: Email queue (manual approval) vs. auto-submission + admin panel?
2. **Decide**: Frontend wiring? (Can be deferred to Phase 3)
3. **If deploying now**:
   - Create Cloudflare account
   - Run wrangler setup (section "Deployment Steps")
   - Deploy Worker
   - Create first ballot config via CLI
4. **Test**: POST a ballot to `/ballot`, fetch via `/aggregate`

---

## Questions / Contact

If uncertain about any decision, use the site contact page (contact.html) — this is a PROVISIONAL implementation pending final sign-off.
