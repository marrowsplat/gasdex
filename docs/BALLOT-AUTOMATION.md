# Ballot automation — how it works and how to run it

The ratings worker now opens, upgrades and closes player-ratings ballots
automatically. No more manual KV seeding and no more hard-coded match ids
in the pages.

## What happens on a matchday (all automatic)

1. A cron inside the Cloudflare Worker runs every 5 minutes. On quiet days
   it does nothing and makes **zero** API calls.
2. The worker reads the site's own published fixtures
   (`https://marrowsplat.github.io/gasdex/fixtures.json`, cached 6 hours)
   to know when the next match kicks off.
3. From 60 minutes before kick-off it polls API-Football for the confirmed
   line-up (one call every ~5 minutes, stops as soon as it's found).
4. When the XI is published, the worker writes the ballot config to KV and
   points `current` at it. **Voting opens at kick-off** and closes 50 hours
   later (~48h after full time).
5. If the line-up hasn't appeared by kick-off (API hiccup), a fallback
   ballot opens anyway with the **full squad**; it is upgraded in place to
   the real XI the moment the line-up arrives. Votes already cast survive.
6. After full time, the worker fetches the substitution events and appends
   the subs who actually played to the ballot.
7. The rate page and the index ratings box both ask the worker
   (`GET /current`) what's on — nothing on the site is hard-coded any more.

Budget: roughly 15–20 API calls per matchday (~1,000/season), far inside
the paid plan's 7,500/day.

## One-time setup (you)

Do these once, in Terminal, after subscribing to the API-Football paid
plan (~$19/mo — you can subscribe August–May and cancel for the summer):

1. `cd ~/Documents/gasdex/backend/ratings-worker`
2. `wrangler secret put FOOTBALL_API_KEY`
   — it will prompt; paste your api-sports key and press Enter. The key is
   stored encrypted by Cloudflare and never appears in any file or commit.
3. `wrangler deploy --env=""`
   — deploys the worker AND registers the 5-minute cron trigger.

To confirm it's alive, open
`https://gasdex-ratings.gasdex.workers.dev/auto-status` in a browser —
it returns the last cron run's log (`ran_at`, `actions`, `api_calls`).
On a quiet day expect `"actions": ["no matchday window"]`.

## Manual override (rarely needed)

Everything the automation writes is plain KV, so the old manual commands
still work if you ever need to force something:

- Re-point the live ballot:
  `wrangler kv key put "current" '{"match_id":"<id>"}' --binding GASDEX_RATINGS --preview false --remote`
- Wipe test votes for a match:
  `wrangler kv key put "ballots:<match_id>" '[]' --binding GASDEX_RATINGS --preview false --remote`
- A hand-written `config:<match_id>` is respected; the cron only replaces
  a config when it has better data (squad → lineups → +subs).

## Failure behaviour

- No API key set: cron logs "FOOTBALL_API_KEY secret not set" and does
  nothing — the site keeps working, ballots just don't open.
- API down pre-KO: squad-fallback ballot opens at kick-off regardless
  (squad list is cached 30 days in KV).
- Worker unreachable from the site: rate page shows a friendly
  "Ratings are unavailable right now" notice; index box keeps its neutral
  text.
- Postponed/TBC fixtures are skipped (the `tbc` flag in fixtures.json).

## Where the moving parts live

- `backend/ratings-worker/worker.js` — cron (`runCron`), `/current`,
  `/auto-status`, plus openAt + player-list enforcement on `/ballot`.
- `backend/ratings-worker/wrangler.toml` — `[triggers] crons = ["*/5 * * * *"]`.
- `tools/build_site.py` — publishes `out/fixtures.json` on every build.
- `site/rate.html` / `site/index.html` — fetch `/current`; no match ids.

First real-world test: Peterborough (H), League Cup, Saturday 8 August
2026, 15:00 — watch `/auto-status` from ~14:00 that day.
