#!/usr/bin/env bash
# Release: import (strict) -> build -> every check -> size budget -> publish the site as ONE orphan commit on gh-pages -> manifest in main.
#
#   scripts/release.sh [--dry-run] "commit message"
#
# Publication is out of main (review 2 risk 5): docs/ (app shell + api/) is copied into a separate worktree of a fresh orphan branch, committed
# as a single parentless snapshot and becomes refs/heads/gh-pages (force-pushed): old snapshots are never reachable from gh-pages, so the
# published branch never accumulates history. main keeps source, decisions, id registry and the small release manifests in releases/;
# docs/api/ is never staged in main (gitignored once the coordinator has removed it from the index).
# --dry-run (or RELEASE_DRY_RUN=1): everything except the pushes and the main commit; prints the commands instead.
# Any failure aborts before anything is pushed.
set -euo pipefail
cd "$(dirname "$0")/.."
dry=${RELEASE_DRY_RUN:-0}
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi
msg=${1:?usage: release.sh [--dry-run] "commit message"}

python3 -I scripts/import.py --strict-parsers > /tmp/specsheet-import.json
python3 -I scripts/build.py > /tmp/specsheet-build.log
node scripts/smoke.mjs
node scripts/frontend-smoke.mjs
for t in tests/test_*.py; do python3 -I "$t" > /dev/null; done
if ! python3 -I scripts/release_manifest.py measure > /tmp/specsheet-measure.json; then
  cat /tmp/specsheet-measure.json; echo "release: size budget FAILED (data/release-budget.json)" >&2; exit 2
fi
if grep -q '"budget_state": "warn"' /tmp/specsheet-measure.json; then
  echo "release: size budget WARNING: $(python3 -I -c 'import json; print(json.load(open("/tmp/specsheet-measure.json"))["budget_messages"])')" >&2
fi

# ---- gh-pages: orphan single-snapshot commit built in a separate worktree
wt=$(mktemp -d /tmp/specsheet-ghpages.XXXXXX)/site
tmpbranch="gh-pages-next-$$"
git worktree add -q --orphan -b "$tmpbranch" "$wt"
trap 'git worktree remove --force "$wt" 2>/dev/null || true; git branch -D "$tmpbranch" >/dev/null 2>&1 || true' EXIT
cp -a docs/. "$wt"/
touch "$wt/.nojekyll"
git -C "$wt" add -A
dirty=""; git diff --quiet HEAD -- scripts crawler schemas research data || dirty="+dirty"
git -C "$wt" -c commit.gpgsign=false commit -q -m "site snapshot: $msg (source $(git rev-parse --short HEAD)$dirty)"
new=$(git -C "$wt" rev-parse HEAD)
if [ -n "$(git rev-list --parents -n1 "$new" | cut -s -d' ' -f2-)" ]; then echo "release: gh-pages snapshot has a parent" >&2; exit 1; fi
prev=$(git rev-parse -q --verify refs/heads/gh-pages || echo none)
python3 -I scripts/release_manifest.py write --gh-pages "$new" --prev "$prev"
git update-ref refs/heads/gh-pages "$new"        # local gh-pages = exactly one parentless commit
git worktree remove --force "$wt"; git branch -D "$tmpbranch" >/dev/null; trap - EXIT

if [ "$dry" = 1 ]; then
  echo "DRY RUN: local gh-pages = $new (orphan, single commit). Nothing pushed or committed on main. To publish:"
  echo "  git push --force origin gh-pages"
  echo "  git add -A -- . ':(exclude)docs/api' && git commit -m \"$msg\" && git push origin main"
  exit 0
fi
git push -q --force origin gh-pages
git add -A -- . ':(exclude)docs/api'
git commit -q -m "$msg"
git push -q origin main
git log --oneline -1
