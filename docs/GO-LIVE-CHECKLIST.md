# Backend go-live checklist

Everything code-side is finished and wired. The two remaining backends only
need accounts + an endpoint URL pasted in. Until then every form/ballot runs
in **demo mode** (the `FORM_ENDPOINT` / `RATINGS_ENDPOINT` constants are empty
strings, so nothing is sent and the demo notes stay accurate).

## 1. Contact + report forms — ✅ DONE (22 Jul 2026)

Formspree's free tier (50 submissions/month, no backend to run) is the
recommended start; a Cloudflare Worker + email routing is the free-forever
upgrade path if volume grows.

- [x] Formspree account created; two forms added ("GasDex contact",
      "GasDex match reports").
- [x] Endpoints pasted into `FORM_ENDPOINT` on contact + submit pages.
- [x] Demo notes removed from both pages (rate.html keeps its note until
      the ratings worker ships).
- [x] Live test passed (22 Jul 2026): invalid email correctly rejected
      with the retry message; valid submission arrived by email.

Both forms POST JSON with `Accept: application/json`, which Formspree
supports natively (no redirect; the page shows its own confirmation).

## 2. Ratings worker (~30 minutes, Cloudflare free tier)

Code: `backend/ratings-worker/` (worker.js + wrangler.toml). Full API notes
in `docs/backend-notes.md`.

- [ ] Create a Cloudflare account (free) and install wrangler:
      `npm install -g wrangler`, then `wrangler login`.
- [ ] Create the KV namespace:
      `wrangler kv namespace create GASDEX_RATINGS`
      (and `--preview` variant) — paste the two IDs into `wrangler.toml`.
- [ ] Deploy: `wrangler deploy` from `backend/ratings-worker/`.
      This gives a `*.workers.dev` URL that works immediately — the custom
      route `ratings.gasdex.co.uk` only becomes possible once the gasdex.co.uk
      zone is on Cloudflare (optional, later).
- [ ] Paste the worker URL (no trailing slash) into `RATINGS_ENDPOINT` in
      `site/rate.html`, and delete its `.demo-note` line.
- [ ] CORS is already allow-listed for `gasdex.co.uk`, `www.gasdex.co.uk`
      and `marrowsplat.github.io` (plus localhost) in `worker.js` —
      if the site ever moves host, add the new origin to `ALLOWED_ORIGINS`.
- [ ] Commit + push; submit a test ballot on the live site and check
      `GET <worker-url>/aggregate?match_id=...` returns it.

## 3. After both are live

- [ ] Remove the matching `.demo-note` CSS rule from any page whose note is
      gone (harmless to leave, tidy to remove).
- [ ] Update the site's rate/submit copy if wording needs to change from
      "coming soon" to live instructions.
- [ ] The gold masthead strip can start promoting "Rate the players" again.
