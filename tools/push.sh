#!/usr/bin/env bash
# GasDex one-command push — self-healing.
#
# Usage (the maintainer's ONLY git routine):
#   cd to the GasDex folder, then:  ./tools/push.sh
#
# What it does, in plain English:
#   1. Cleans up any leftover git mess (stale lock files, abandoned rebases,
#      detached HEAD) — these have all happened before and scared people.
#   2. Fetches GitHub and safely picks up any remote commits.
#   3. Pushes local commits to GitHub.
# It never rebases interactively, never opens vim, and if anything
# unexpected happens it STOPS with a plain-English message to pass on.
#
# Design note: since session 13 the CI bot commits the rolling caches to the
# dedicated `data-cache` branch, NOT main — so main only moves when the
# maintainer pushes, and conflicts should never occur. The healing steps
# below are belt-and-braces for folder-sync weirdness, not the normal path.

set -u

# Always run from the repo root (the folder above tools/)
cd "$(cd "$(dirname "$0")/.." && pwd)" || exit 1

say()  { printf '%s\n' "$*"; }
fail() {
  say ""
  say "########################################################"
  say "#  STOPPED — nothing has been lost or broken.          #"
  say "########################################################"
  say "Problem: $*"
  say ""
  say "Just tell Claude: \"push.sh stopped: $*\" and it will sort it out."
  exit 1
}

[ -d .git ] || fail "this folder is not the GasDex git repository"

say "GasDex push starting..."

# --- 1. Heal: stale lock files (left behind by crashed git / folder sync) ---
if find .git -maxdepth 1 -name '*.lock' -mmin +2 | grep -q .; then
  find .git -maxdepth 1 -name '*.lock' -mmin +2 -delete 2>/dev/null \
    && say "Healed: removed stale git lock file(s)."
fi

# --- 2. Heal: abandoned rebase/merge state (we NEVER rebase on purpose) ---
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  git rebase --abort >/dev/null 2>&1 || true
  rm -rf .git/rebase-merge .git/rebase-apply 2>/dev/null || true
  say "Healed: cleaned up a leftover half-finished rebase."
fi
if [ -f .git/MERGE_HEAD ]; then
  git merge --abort >/dev/null 2>&1 || rm -f .git/MERGE_HEAD 2>/dev/null || true
  say "Healed: cleaned up a leftover half-finished merge."
fi

# --- 3. Heal: detached HEAD -> back onto main ---
if ! git symbolic-ref -q HEAD >/dev/null; then
  git checkout main >/dev/null 2>&1 \
    && say "Healed: you were on a detached HEAD — moved safely back to main." \
    || fail "could not get back onto the main branch"
fi
if [ "$(git branch --show-current)" != "main" ]; then
  git checkout main >/dev/null 2>&1 || fail "could not switch to the main branch"
  say "Switched back to the main branch."
fi

# --- 4. Info: uncommitted changes are fine, they just stay local ---
if ! git diff --quiet || ! git diff --cached --quiet; then
  say "Note: some uncommitted local changes exist — they stay on this"
  say "computer; only committed work gets pushed. (This is normal.)"
fi

# --- 5. Talk to GitHub ---
git fetch origin >/dev/null 2>&1 || fail "could not reach GitHub — check the internet connection and try again"

# --- 6. One-time: publish the data-cache branch if GitHub doesn't have it yet ---
if git show-ref --verify -q refs/heads/data-cache \
   && ! git show-ref --verify -q refs/remotes/origin/data-cache; then
  git push origin data-cache >/dev/null 2>&1 \
    && say "One-time step done: published the new data-cache branch to GitHub." \
    || fail "could not publish the data-cache branch to GitHub"
fi

# --- 7. Pick up any remote commits (should be rare now the bot avoids main) ---
BEHIND=$(git rev-list --count main..origin/main 2>/dev/null || echo 0)
if [ "$BEHIND" -gt 0 ]; then
  if git merge --ff-only origin/main >/dev/null 2>&1; then
    say "Picked up $BEHIND new commit(s) from GitHub."
  else
    # Local and remote both have new commits. Try a quiet rebase; if the
    # ROLLING CACHES conflict (legacy situation), auto-resolve with the
    # CI side per the long-standing convention. Anything else: back out
    # cleanly and ask for help — never leave a half-done rebase.
    GIT_EDITOR=true git rebase origin/main >/dev/null 2>&1
    while [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; do
      FIXED_ONE=0
      for f in $(git diff --name-only --diff-filter=U); do
        case "$f" in
          data/results-history.json|data/news-history.json|data/fixtures-audit.json)
            git checkout --ours -- "$f" 2>/dev/null || true
            git add -- "$f" 2>/dev/null || true
            FIXED_ONE=1
            ;;
        esac
      done
      if [ "$FIXED_ONE" -eq 1 ] && [ -z "$(git diff --name-only --diff-filter=U)" ]; then
        GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || true
      else
        git rebase --abort >/dev/null 2>&1 || true
        rm -rf .git/rebase-merge .git/rebase-apply 2>/dev/null || true
        fail "GitHub and this computer both changed the same files in a way I can't auto-fix"
      fi
    done
    say "Combined local work with $BEHIND new commit(s) from GitHub (auto-resolved)."
  fi
fi

# --- 8. Push ---
AHEAD=$(git rev-list --count origin/main..main 2>/dev/null || echo 0)
if [ "$AHEAD" -eq 0 ]; then
  say ""
  say "=============================================="
  say "  SUCCESS — nothing new to push; GitHub is"
  say "  already up to date. All done."
  say "=============================================="
  exit 0
fi
git push origin main >/dev/null 2>&1 || fail "GitHub refused the push"

say ""
say "=============================================="
say "  SUCCESS — pushed $AHEAD commit(s) to GitHub."
say "  The site will rebuild automatically."
say "  You can close this window."
say "=============================================="
