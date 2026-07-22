#!/usr/bin/env python3
"""
GasDex Report Renderer

Renders an approved fan match report (from JSON/front-matter input) into
a static HTML page matching site/report-example.html template.

Usage:
    python3 render_report.py INPUT_FILE [OUTPUT_FILE]

Input format: JSON with keys:
  - match_id: e.g. "gillingham-h-20260711"
  - title: report title
  - author: display name (no email)
  - date_submitted: ISO 8601 timestamp
  - body: plain text (blank-line-separated paragraphs)
  - match_team_home, match_team_away: team names
  - match_score_home, match_score_away: integers
  - match_date: ISO 8601 date or readable string
  - match_venue: venue name
  - match_attendance: integer (optional)
  - ratings: optional { player_name: { avg: float, motm_votes: int } }
  - prev_report_id, next_report_id: for navigation (optional)

Output: HTML file honouring:
  - Design system: background colours, box styles, typography
  - Responsive layout: 840px-max sheet
  - localStorage bg-class restore
  - HTML escaping for all user text
"""

import json
import sys
from pathlib import Path
from html import escape
from datetime import datetime

def load_report(input_file):
    """Load report from JSON file."""
    with open(input_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def escape_html(text):
    """Escape HTML entities."""
    return escape(text)

def format_paragraphs(body_text):
    """Convert plain text (blank-line-separated) to HTML paragraphs."""
    paragraphs = [p.strip() for p in body_text.split('\n\n') if p.strip()]
    return '\n      '.join(
        f'<p>{escape_html(p)}</p>' for p in paragraphs
    )

def format_score_line(home_team, score_home, score_away, away_team):
    """Format match score display."""
    ndash = '&ndash;'
    return f"""      <div class="score-line">
        <span class="team">{escape_html(home_team)}</span>
        <span class="score">{score_home} {ndash} {score_away}</span>
        <span class="team">{escape_html(away_team)}</span>
      </div>"""

def format_match_meta(date_str, venue, attendance=None):
    """Format match metadata line."""
    meta_parts = [
        'League Two',
        escape_html(venue)
    ]
    if date_str:
        meta_parts.append(escape_html(date_str))
    if attendance:
        meta_parts.append(f'Att. {attendance:,}')

    return ' &middot; '.join(meta_parts)

def format_ratings_section(ratings):
    """Format player ratings if available."""
    if not ratings or len(ratings) == 0:
        return ''

    # Sort by average score descending
    sorted_players = sorted(
        ratings.items(),
        key=lambda x: x[1]['avg'],
        reverse=True
    )

    # Find Man of the Match (highest motm_votes)
    motm_player = max(ratings.items(), key=lambda x: x[1]['motm_votes'])
    motm_name = motm_player[0]
    motm_votes = motm_player[1]['motm_votes']

    rate_rows = []
    for player, data in sorted_players:
        avg = data['avg']
        bar_width = int((avg / 10) * 100)
        player_escaped = escape_html(player)
        rate_rows.append(
            f'      <div class="rate-row"><span class="nm">{player_escaped}</span>'
            f'<div class="bar"><i style="width:{bar_width}%"></i></div>'
            f'<span class="val">{avg:.1f}</span></div>'
        )

    total_votes = sum(r['motm_votes'] for r in ratings.values())
    motm_pct = int((motm_votes / total_votes * 100)) if total_votes > 0 else 0

    return f"""    <div class="ratings">
      <h3>Fan Player Ratings &mdash; this match</h3>
      <div class="rate-note">{len(ratings)} fans voted</div>
{chr(10).join(rate_rows)}
      <div class="motm">Man of the Match: <b>{escape_html(motm_name)}</b> ({motm_pct}% of votes)</div>
    </div>"""

def render_report(report_data, output_file=None):
    """Render report to HTML."""

    # Extract required fields
    match_id = report_data.get('match_id', 'unknown-match')
    title = report_data.get('title', 'Untitled Report')
    author = report_data.get('author', 'Anonymous')
    body = report_data.get('body', '')
    home_team = report_data.get('match_team_home', 'Bristol Rovers')
    away_team = report_data.get('match_team_away', 'Opponent')
    score_home = report_data.get('match_score_home', 0)
    score_away = report_data.get('match_score_away', 0)
    date_submitted = report_data.get('date_submitted', datetime.now().isoformat())
    match_date = report_data.get('match_date', 'TBD')
    venue = report_data.get('match_venue', 'The Memorial Stadium')
    attendance = report_data.get('match_attendance')
    ratings = report_data.get('ratings', {})

    # Format parsed submission time
    try:
        dt = datetime.fromisoformat(date_submitted.replace('Z', '+00:00'))
        submitted_fmt = dt.strftime('%a %d %b, %H:%M')
    except:
        submitted_fmt = 'submitted'

    # Build page title
    page_title = f'{escape_html(title)} &mdash; {escape_html(away_team)} vs {escape_html(home_team)} | GasDex fan reports'

    # Format sections
    score_line = format_score_line(home_team, score_home, score_away, away_team)
    meta_line = format_match_meta(match_date, venue, attendance)
    body_html = format_paragraphs(body)
    ratings_html = format_ratings_section(ratings)

    # Build prev/next nav (placeholder; can be filled by publishing system)
    prev_link = report_data.get('prev_report_id', '')
    next_link = report_data.get('next_report_id', '')
    nav_html = ''
    if prev_link or next_link or next_link:
        nav_parts = []
        if prev_link:
            nav_parts.append(
                f'<a href="{escape_html(prev_link)}">&larr; Previous report</a>'
            )
        nav_parts.append(
            '<a href="#">All fan reports &rarr;</a>'
        )
        nav_html = f'''    <div class="report-nav">
      {chr(10).join(nav_parts)}
    </div>'''

    # Assemble final HTML
    html = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{
    background-color:#0e0e10;
    background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.025) 0 2px,transparent 2px 14px),
                     repeating-linear-gradient(-45deg,rgba(255,255,255,.02) 0 2px,transparent 2px 14px);
    color:#ddd;font-family:Verdana,Geneva,Tahoma,sans-serif;font-size:13px;line-height:1.6;
  }}
  a{{text-decoration:none;transition:color .15s ease, background .15s ease}}

  /* ---- compact masthead: one line, doubles as the way home ---- */
  .mast-mini{{max-width:840px;margin:0 auto;padding:16px 22px 12px;display:flex;align-items:center;gap:12px}}
  .crest-mini{{width:34px;height:34px;border-radius:50%;flex-shrink:0;
    background:conic-gradient(#0d4f9e 0 90deg,#fff 90deg 180deg,#0d4f9e 180deg 270deg,#fff 270deg 360deg);
    border:2px solid #fff;box-shadow:0 0 0 2px #0d4f9e}}
  .mast-mini .wordmark{{font-size:19px;color:#4db8ff}}
  .mast-mini .wordmark b{{color:#fff}}
  .mast-mini a:hover .wordmark, .mast-mini a:hover .wordmark b{{color:#ffc400}}
  .mast-mini .home-link{{display:flex;align-items:center;gap:12px}}
  .mast-mini .back{{margin-left:auto;font-size:11.5px;color:#8a8a90}}
  .mast-mini .back a{{color:#4db8ff}}
  .mast-mini .back a:hover{{color:#ffc400}}
  .rule-mini{{height:3px;border-top:2px solid #0d4f9e;border-bottom:1px solid #ffc400;max-width:840px;margin:0 auto 22px}}

  /* ---- the opened-up card ---- */
  .sheet-wrap{{max-width:840px;margin:0 auto;padding:0 22px 40px}}
  .kicker{{display:inline-block;font-size:12px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;
    color:#fff;background:linear-gradient(180deg,#125db8,#0d4f9e);padding:5px 14px;
    border-radius:8px 8px 0 0;margin-left:12px;box-shadow:0 -2px 4px rgba(0,0,0,.35)}}
  .sheet{{background:linear-gradient(180deg,#fdfdfe,#ececee);border:1px solid #b9b9be;border-top:3px solid #0d4f9e;
    border-radius:12px;box-shadow:0 3px 8px rgba(0,0,0,.6);padding:22px 26px 26px;color:#1a1a1c}}
  .sheet a{{color:#0d4f9e;font-weight:600}}
  .sheet a:hover{{color:#d6a300}}

  /* match context header */
  .match-head{{border-bottom:2px solid #0d4f9e;padding-bottom:14px;margin-bottom:16px}}
  .match-head .score-line{{display:flex;justify-content:center;align-items:baseline;gap:14px;flex-wrap:wrap}}
  .match-head .team{{font-size:17px;font-weight:700;color:#123f77}}
  .match-head .score{{font-size:26px;font-weight:800;color:#c0392b;font-variant-numeric:tabular-nums}}
  .match-head .meta{{text-align:center;color:#6c6c72;font-size:11.5px;margin-top:6px}}

  h1.report-title{{font-size:21px;color:#1a1a1c;margin:2px 0 4px;line-height:1.3}}
  .byline{{color:#6c6c72;font-size:11.5px;margin-bottom:16px}}
  .byline b{{color:#0d4f9e}}

  .report-body p{{margin-bottom:13px;font-size:13.5px}}
  .report-body p:first-of-type::first-letter{{font-size:200%;font-weight:800;color:#0d4f9e;float:left;line-height:1;padding-right:6px}}

  /* ratings block reused from index */
  .ratings{{margin-top:22px;border-top:1px solid #c9c9ce;padding-top:16px}}
  .ratings h3{{font-size:12px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:#0d4f9e;margin-bottom:8px}}
  .rate-note{{font-size:11.5px;color:#444;margin-bottom:8px}}
  .rate-row{{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:12px}}
  .rate-row .nm{{width:92px;font-weight:600;color:#123f77}}
  .bar{{flex:1;height:9px;border-radius:5px;overflow:hidden;background:#d3d3d8}}
  .bar i{{display:block;height:100%;background:linear-gradient(90deg,#0d4f9e,#4db8ff)}}
  .rate-row .val{{width:28px;text-align:right;font-weight:700;font-variant-numeric:tabular-nums}}
  .motm{{font-size:11.5px;margin-top:8px;color:#333}}
  .motm b{{color:#0d4f9e}}

  /* prev/next reports */
  .report-nav{{display:flex;justify-content:space-between;gap:12px;margin-top:20px;font-size:12px;flex-wrap:wrap}}
  .report-nav a{{color:#0d4f9e;font-weight:700}}
  .report-nav a:hover{{color:#d6a300}}

  footer{{text-align:center;color:#77777d;font-size:10.5px;padding:18px}}

  /* ---- background themes (shared with index; visitor's choice is honoured) ---- */
  body.bg-navy{{background-color:#0a1826;
    background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.03) 0 2px,transparent 2px 14px),
                     repeating-linear-gradient(-45deg,rgba(255,255,255,.02) 0 2px,transparent 2px 14px)}}
  body.bg-flood{{background-color:#08131f;
    background-image:radial-gradient(ellipse 90% 55% at 50% -10%,rgba(23,94,181,.35),transparent 60%),
                     repeating-linear-gradient(45deg,rgba(255,255,255,.02) 0 2px,transparent 2px 14px);
    background-attachment:fixed}}
  body.bg-quarters{{background-color:#0b1a2b;
    background-image:conic-gradient(rgba(255,255,255,.035) 0 90deg,transparent 90deg 180deg,rgba(255,255,255,.035) 180deg 270deg,transparent 270deg 360deg);
    background-size:340px 340px;background-attachment:fixed}}
  body.bg-fade{{background:linear-gradient(180deg,#0d3d75 0,#0a2444 240px,#0a1420 720px,#070c12 100%);background-attachment:fixed}}
  body.bg-slate{{background-color:#22242a;
    background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.02) 0 2px,transparent 2px 14px)}}
  body.bg-light{{background-color:#ccd4dd;
    background-image:repeating-linear-gradient(45deg,rgba(13,79,158,.05) 0 2px,transparent 2px 14px)}}
  body.bg-light .mast-mini .wordmark{{color:#0d4f9e}}
  body.bg-light .mast-mini .wordmark b{{color:#062845}}
  body.bg-light .mast-mini .back{{color:#5c6b80}}
  body.bg-light footer{{color:#5c6b80}}
</style>
</head>
<body>

<div class="mast-mini">
  <a class="home-link" href="index.html" title="Back to the index">
    <span class="crest-mini"></span>
    <span class="wordmark"><b>Gas</b>Dex</span>
  </a>
  <span class="back"><a href="index.html">&larr; Back to the index</a></span>
</div>
<div class="rule-mini"></div>

<div class="sheet-wrap">
  <span class="kicker">Fan Match Report</span>
  <div class="sheet">

    <div class="match-head">
{score_line}
      <div class="meta">{meta_line}</div>
    </div>

    <h1 class="report-title">&ldquo;{escape_html(title)}&rdquo;</h1>
    <div class="byline">by <b>{escape_html(author)}</b> &middot; submitted {submitted_fmt} &middot; published after review</div>

    <div class="report-body">
{body_html}
    </div>

{ratings_html}
{nav_html}

  </div>
</div>

<footer>GasDex &middot; unofficial Bristol Rovers aggregator &middot; fan reports are reviewed before publishing &middot; sample content prototype</footer>

<script>
/* honour the visitor's background choice from the index */
try{{
  var saved = localStorage.getItem('gasdex-bg');
  if(saved) document.body.className = saved;
}}catch(e){{}}
</script>
</body>
</html>
"""

    # Write output
    if output_file is None:
        output_file = Path(match_id).with_suffix('.html')
    else:
        output_file = Path(output_file)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding='utf-8')

    return str(output_file)


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 render_report.py INPUT_FILE [OUTPUT_FILE]', file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        report = load_report(input_file)
        output = render_report(report, output_file)
        print(f'Rendered: {output}')
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
