#!/usr/bin/env python3
"""GasDex validation: HTML tag-balance check + basic link audit.

Usage:
    python3 tools/validate.py            # checks every .html under site/
    python3 tools/validate.py FILE...    # checks the given files

Run this after ANY edit to an HTML file.
"""
import sys
import re
from pathlib import Path
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}


class BalanceChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: closing </{tag}> with empty stack")
            return
        open_tag, line = self.stack.pop()
        if open_tag != tag:
            self.errors.append(
                f"line {self.getpos()[0]}: </{tag}> closes <{open_tag}> opened at line {line}")


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    checker = BalanceChecker()
    checker.feed(text)
    errors = list(checker.errors)
    for tag, line in checker.stack:
        errors.append(f"line {line}: <{tag}> never closed")

    # Link audit: external links must carry class="ext" + target=_blank;
    # internal links must NOT. (Heuristic: href starting with http = external.)
    for m in re.finditer(r"<a\s[^>]*>", text):
        a = m.group(0)
        line = text[: m.start()].count("\n") + 1
        href_m = re.search(r'href="([^"]*)"', a)
        if not href_m:
            continue
        href = href_m.group(1)
        if href == "#":
            # Placeholder (sample data) — may be styled external or internal.
            continue
        external = href.startswith("http")
        has_ext = bool(re.search(r'class="[^"]*\bext\b[^"]*"', a))
        has_blank = 'target="_blank"' in a
        if external and not (has_ext and has_blank):
            errors.append(f'line {line}: external link missing class="ext"/target="_blank": {href}')
        if not external and (has_ext or has_blank):
            errors.append(f"line {line}: internal link marked external: {href}")
    return errors


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    if argv:
        files = [Path(a) for a in argv]
    else:
        files = sorted((root / "site").glob("*.html"))
    if not files:
        print("No HTML files found to check.")
        return 1
    failed = 0
    for f in files:
        errs = check_file(f)
        if errs:
            failed += 1
            print(f"FAIL {f}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {f}")
    print(f"\n{len(files) - failed}/{len(files)} files passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
