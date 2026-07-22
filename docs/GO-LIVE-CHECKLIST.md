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

## 2. Ratings worker — ✅ DEPLOYED (22 Jul 2026)

Code: `backend/ratings-worker/` (worker.js + wrangler.toml). Full API notes
in `docs/backend-notes.md`.

- [x] Cloudflare account + wrangler set up; KV namespaces created (IDs in
      `wrangler.toml`).
- [x] Deployed to https://gasdex-ratings.gasdex.workers.dev (the custom
      route `ratings.gasdex.co.uk` can be added once the zone is on
      Cloudflare — optional, later).
- [x] `RATINGS_ENDPOINT` wired in `site/rate.html`; demo note removed. The
      results view now fetches the REAL aggregate after voting (placeholder
      numbers can never show after a live ballot).
- [x] CORS allow-listed for `gasdex.co.uk`, `www.gasdex.co.uk`,
      `marrowsplat.github.io` + localhost — if the site moves host, add the
      new origin to `ALLOWED_ORIGINS` in worker.js and redeploy.
- [ ] Live test: vote on the live rate page; the results screen should show
      "1 fan has voted" with your scores (then check a second visit can't
      easily double-vote — same browser should be rejected).

## 3. After both are live

- [ ] Remove the matching `.demo-note` CSS rule from any page whose note is
      gone (harmless to leave, tidy to remove).
- [ ] Update the site's rate/submit copy if wording needs to change from
      "coming soon" to live instructions.
- [ ] The gold masthead strip can start promoting "Rate the players" again.
