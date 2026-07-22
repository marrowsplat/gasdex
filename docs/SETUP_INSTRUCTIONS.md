> **OBSOLETE (19 Jul 2026):** No setup is needed any more. Results/fixtures now
> come from TheSportsDB's free keyless API (live-verified). The API-Football
> steps below only matter if upgrading to their PAID plan later
> (then: team ID is 1334, enable with USE_API_FOOTBALL=1 + FOOTBALL_API_KEY).

# GasDex Results/Fixtures Setup Instructions

This document walks through getting Bristol Rovers results & fixtures working for the GasDex site.

## Prerequisites

- Python 3.7+
- Network access (for API calls)
- ~10 minutes

## Step 1: Sign Up for API-Football

1. Go to https://www.api-football.com/
2. Click "Sign Up" (top-right)
3. Create free account (no credit card required)
4. Confirm email
5. Log in and navigate to Dashboard
6. Copy your API key (should be visible on the dashboard)

Keep this key safe; it's your authentication token.

## Step 2: Find Bristol Rovers Team ID

The script needs Bristol Rovers' team ID from API-Football. Currently it's hardcoded as `234`, but this should be verified.

### Option A: Quick verification (if 234 works)

```bash
export FOOTBALL_API_KEY=<your-key>
python3 tools/feeds/fetch_results.py
```

If it returns results, team ID 234 is correct. If it returns empty or error, use Option B.

### Option B: Lookup via API

Replace `YOUR_API_KEY` with your actual key:

```bash
curl -H "x-apisports-key: YOUR_API_KEY" \
  "https://api.api-football.com/v3/teams?search=bristol+rovers"
```

Look for "Bristol Rovers FC" in the response and note its `id` value.

Then update `fetch_results.py`:
```python
TEAM_ID = <the-id-you-found>  # Change from 234 to your ID
```

## Step 3: Test the Script

```bash
# Set API key
export FOOTBALL_API_KEY=<your-key>

# Run the fetcher
cd /path/to/gasdex
python3 tools/feeds/fetch_results.py
```

Expected output:
```
✓ [LIVE] Fetched 5 results, 5 fixtures → /path/to/data/results.json
```

Verify the file:
```bash
cat data/results.json | python3 -m json.tool
```

You should see 5 recent results (likely pre-season friendlies) and 5 upcoming fixtures (League Two matches for August onwards).

## Step 4: Integrate with Site Build

To use this in your site rebuild pipeline (GitHub Actions, cron job, etc.):

1. **Store API key securely:**
   - GitHub Actions: Settings → Secrets and variables → Actions → New repository secret
   - Name: `FOOTBALL_API_KEY`
   - Value: Your API-Football API key

2. **Update your build workflow** (e.g., `.github/workflows/rebuild.yml`):

```yaml
jobs:
  rebuild:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Fetch results & fixtures
        env:
          FOOTBALL_API_KEY: ${{ secrets.FOOTBALL_API_KEY }}
        run: python3 tools/feeds/fetch_results.py
      
      - name: Build site
        run: python3 tools/build_site.py
      
      - name: Deploy
        run: # your deploy command here
```

3. **Schedule rebuilds** (example: every 3 hours):

```yaml
on:
  schedule:
    - cron: '0 */3 * * *'  # Every 3 hours
  workflow_dispatch:        # Manual trigger
```

## Step 5: Verify Data is Used in Site

The site HTML/JS needs to read `data/results.json`. Ensure your templates include:

```javascript
// Load results from data/results.json
fetch('data/results.json')
  .then(r => r.json())
  .then(data => {
    console.log('Results fetched at:', data.fetched_at);
    console.log('Sample data?', data.sample);
    // Render results and fixtures...
  });
```

## Fallback: Sample Data

If the API key is not set or network fails, the script automatically falls back to sample data:

```bash
python3 tools/feeds/fetch_results.py
# Output: ✓ [SAMPLE] Fetched 5 results, 5 fixtures...
```

The `data/results.json` will include `"sample": true`, so the site can show a banner like "Using sample data; live scores disabled."

## Troubleshooting

### "⚠ API-Football key invalid or network error"

1. Check API key is set: `echo $FOOTBALL_API_KEY`
2. Verify key is valid: Copy-paste it directly from https://www.api-football.com/dashboard
3. Check internet connection: `ping api.api-football.com`
4. Try with a simpler endpoint: 
   ```bash
   curl -H "x-apisports-key: YOUR_KEY" \
     "https://api.api-football.com/v3/leagues"
   ```

### "Empty results/fixtures"

1. Verify team ID (see Step 2, Option B)
2. Check if Bristol Rovers has matches scheduled (off-season?)
3. Try fetching for a different team to confirm API works

### "Rate limit exceeded"

- API-Football free tier: 100 req/day
- If you're hitting this, either:
  1. Reduce rebuild frequency (e.g., every 6 hours instead of 3)
  2. Upgrade to $19/month plan

### JSON schema validation fails

Run the validation check:
```bash
python3 -c "
import json
with open('data/results.json') as f:
    data = json.load(f)
    print('Valid JSON. Keys:', list(data.keys()))
"
```

## Monitoring & Maintenance

### Weekly checklist:

- [ ] Check `data/results.json` last modified time (should be recent)
- [ ] Verify no "SAMPLE" flag in production
- [ ] Monitor API usage (free tier has 100 req/day limit)
- [ ] Spot-check a result to ensure data looks correct

### Monthly:

- [ ] Check for any deprecated API endpoints (API-Football changes rarely, but verify)
- [ ] Review costs (free tier should suffice for 3-hourly rebuilds)

## Optional: Add Fallback Provider

For redundancy, you can add football-data.org as a fallback:

1. Sign up at https://www.football-data.org/
2. Verify League Two is included in your plan tier (€49/month Standard recommended)
3. Edit `tools/feeds/fetch_results.py`:
   - Add `FootballDataProvider` class (similar to `APIFootballProvider`)
   - Update `main()` to try API-Football first, then fall back to football-data.org
4. Set `export FOOTBALL_DATA_KEY=<key>` in your workflow

This makes the site more robust if API-Football has an outage.

## Support

- API-Football docs: https://api-sports.io/documentation/football/v3
- API-Football status: https://status.api-sports.io/
- GasDex docs: See `/docs/data-sources.md` for full research & comparison

---

**Last updated:** July 19, 2026
