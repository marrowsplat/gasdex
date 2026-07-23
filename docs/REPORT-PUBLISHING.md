# Publishing fan match reports (approve-by-file)

Fan reports arrive by email via the submit-a-report form (Formspree). Publishing
an approved report is one small JSON file + one push — CI does the rest.

## The flow

1. A fan submits a report → it lands in the maintainer's email inbox.
2. Read it. If it's not suitable, do nothing — unpublished means unpublished.
3. To approve, create one JSON file in `data/reports/` and push. The next CI
   build renders it to `report-<match_id>.html` on the live site.

## Step by step

1. Copy `data/reports/_example.json` to a new file named after the match, e.g.

   `data/reports/york-city-a-20260815.json`

   The `<match_id>` slug matches the fixtures data / ballot slugs
   (opponent-venue-date). Files starting with `_` are ignored by the build.

2. Fill in the fields:
   - `match_id` — same slug as the filename
   - `title` — the report's title (plain text; quotes are added on the page)
   - `author` — the fan's display name (NEVER their email address)
   - `date_submitted` — from the submission email, ISO format
   - `competition` — League Two / League Cup / Vertu Trophy / Friendly
   - `match_team_home` / `match_team_away`, `match_score_home` / `match_score_away`
   - `match_date` (readable, e.g. "Sat 15 Aug 2026"), `match_venue`,
     `match_attendance` (optional)
   - `body` — the report text. Blank lines separate paragraphs. Plain text
     only; any HTML in it is escaped automatically.
   - `ratings` + `ratings_count` — OPTIONAL. Omit both until the match's fan
     ratings are final; the ratings block simply doesn't render without them.
   - Delete the `_comment` line.

3. (Optional but recommended) Preview locally:

   ```
   python3 tools/build_site.py
   python3 tools/validate.py out/report-<match_id>.html
   ```

   then open `out/report-<match_id>.html` in a browser.

4. Commit and push from the project folder:

   ```
   cd <project folder>
   git add data/reports/<match_id>.json
   git commit -m "Publish fan report: <match_id>"
   ./tools/push.sh
   ```

   `tools/push.sh` is the ONLY push command (since the session-13 git fix):
   it self-heals known problems and never opens vim or asks for conflict
   resolution. The old rebase-conflict dance is gone — the rolling caches
   now live on the CI-only `data-cache` branch, so main never conflicts.

5. The next scheduled CI run (hourly) builds and deploys the page. To publish
   immediately, run the workflow manually from the repo's Actions tab.

## Notes

- Edits and take-downs work the same way: edit the JSON and push, or delete
  the JSON file and push (the page disappears from the next deploy, since
  out/ is rebuilt from scratch each run).
- The rendered page inherits the report design reference
  (site/report-example.html) via templates/report.template.html — any approved
  design change to the reference must be mirrored in the template
  (marker-strip equality is checked the same way as the index template).
- The index "Fan Match Reports" box and the archive page
  (out/archive-reports.html) are rendered from the SAME data/reports/ files
  automatically (23 Jul 2026): the box lists the 5 newest reports, the
  archive groups every report by season. With zero published reports both
  show a "be the first!" invitation. Nothing extra to do — one JSON file
  publishes (or un-publishes) everywhere at once.
- site/archive-reports.html is now the STATIC DESIGN REFERENCE only (same
  convention as archive-news); the deployed page is rendered by
  build_site.py from templates/archive-reports.template.html.
