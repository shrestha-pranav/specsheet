#!/usr/bin/env bash
# Build, run every check, then commit + push. Any failure aborts before git.
set -euo pipefail
cd "$(dirname "$0")/.."
msg=${1:?usage: release.sh "commit message"}
python3 -I scripts/build.py > /tmp/specsheet-build.log
node scripts/smoke.mjs
node scripts/frontend-smoke.mjs
for t in tests/test_*.py; do python3 -I "$t" > /dev/null; done
git add -A
git commit -q -m "$msg"
git push -q origin main
git log --oneline -1
