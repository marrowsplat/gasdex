#!/usr/bin/env python3
"""Regenerate templates/index.template.html from site/index.html by
re-inserting the <!--BLOCK:x--> delimiters around the data-driven runs
and swapping the sample timestamp for <!--UPDATED-->."""
import re, sys, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
src = (root / "site/index.html").read_text()

# blocks: name -> regex matching a single data line
patterns = {
    "results": re.compile(r'^\s*<div class="score-row">'),
    "fixtures": re.compile(r'^\s*<div class="fix-row">'),
    "news": re.compile(r'^\s*<li><span class="ico">&#128240;</span>'),
    "club": re.compile(r'^\s*<li><span class="ico">&#128309;</span>'),
    "youtube": re.compile(r'^\s*<li><span class="ico">&#9654;&#65039;</span>'),
    "reports": re.compile(r'^\s*<li><span class="ico">&#9997;&#65039;</span>'),
}

lines = src.split("\n")
out = []
i = 0
while i < len(lines):
    matched = None
    for name, pat in patterns.items():
        if pat.match(lines[i]):
            matched = name
            break
    if matched:
        out.append("    <!--BLOCK:%s-->" % matched)
        while i < len(lines) and patterns[matched].match(lines[i]):
            out.append(lines[i])
            i += 1
        out.append("    <!--/BLOCK:%s-->" % matched)
    else:
        out.append(lines[i])
        i += 1

tpl = "\n".join(out)
assert tpl.count("<!--BLOCK:") == 6, tpl.count("<!--BLOCK:")
tpl = tpl.replace("<b>Sun 19 Jul, 08:00</b>", "<b><!--UPDATED--></b>")
assert "<!--UPDATED-->" in tpl

(root / "templates/index.template.html").write_text(tpl)

# verify: stripping markers + restoring timestamp reproduces site/index.html
check = re.sub(r'^    <!--/?BLOCK:[a-z]+-->\n', '', tpl, flags=re.M)
check = check.replace("<b><!--UPDATED--></b>", "<b>Sun 19 Jul, 08:00</b>")
if check == src:
    print("OK: template regenerated; strips back to site/index.html exactly")
else:
    print("MISMATCH!")
    sys.exit(1)
