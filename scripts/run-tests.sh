#!/usr/bin/env bash
# Test runner (A3-rob r11): run every tests/test_*.py (or the files given), print PASS/FAIL + time + skip count per file and a total,
# show the tail of each failing file's output, exit 1 if any file failed. Every file runs even after a failure (release.sh used to stop at the
# first one with no summary). Tests that need local-only data (raw/, state/specsheet.sqlite, a built docs/api) skip themselves.
#
#   scripts/run-tests.sh [tests/test_x.py ...]      PYTHON=python3 (default)
set -uo pipefail
cd "$(dirname "$0")/.."
py=${PYTHON:-python3}
files=("$@"); [ ${#files[@]} -gt 0 ] || files=(tests/test_*.py)
log=$(mktemp /tmp/specsheet-tests.XXXXXX); trap 'rm -f "$log"' EXIT
pass=0; fail=0; skipped=0; failed=(); t0=$(date +%s)
for t in "${files[@]}"; do
  s=$EPOCHREALTIME
  "$py" -I "$t" > "$log" 2>&1; rc=$?
  dt=$(awk -v a="$s" -v b="$EPOCHREALTIME" 'BEGIN{printf "%.1f", b-a}')
  sk=$(grep -oE 'skipped=[0-9]+' "$log" | tail -1 | cut -d= -f2); sk=${sk:-0}; skipped=$((skipped + sk))
  note=""; [ "$sk" != 0 ] && note=" (skipped $sk)"
  if [ $rc = 0 ]; then pass=$((pass + 1)); printf 'PASS %6ss  %s%s\n' "$dt" "$t" "$note"
  else fail=$((fail + 1)); failed+=("$t"); printf 'FAIL %6ss  %s (exit %s)\n' "$dt" "$t" "$rc"; tail -25 "$log" | sed 's/^/    | /'; fi
done
echo "tests: $pass passed, $fail failed, ${#files[@]} files, $skipped tests skipped ($(( $(date +%s) - t0 ))s)"
if [ $fail -gt 0 ]; then printf '  failed: %s\n' "${failed[@]}"; exit 1; fi
