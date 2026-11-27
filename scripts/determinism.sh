#!/usr/bin/env bash
# Determinism check (A3-rob r11): build the static dataset (scripts/build.py) and the free Worker pack (scripts/build_r2.py --tier free
# --shard-hex 3, as `npm run pack`) TWICE from one snapshot of state/specsheet.sqlite, each in its own temp copy of the code+data tree,
# and diff docs/api + api-worker/pack byte for byte. Exit 0 = identical, 1 = drift (diff summary printed), 2 = a build failed.
#
#   scripts/determinism.sh            # standalone: takes /tmp/specsheet-release.lock only while snapshotting the DB
#   SPECSHEET_RELEASE_LOCKED=1 ...    # caller (release.sh) already holds the lock: do not take it again (flock on a new fd would deadlock)
#
# The live docs/, api-worker/pack and state/ are never written. manifest.generated_at is the one intended wall-clock field: both builds
# get the same SOURCE_DATE_EPOCH (build.py honours it), so any remaining difference is real instability.
set -euo pipefail
cd "$(dirname "$0")/.."
src=$PWD
[ -f state/specsheet.sqlite ] || { echo "determinism: state/specsheet.sqlite missing (run scripts/import.py)" >&2; exit 2; }
tmp=$(mktemp -d /tmp/specsheet-determinism.XXXXXX)
[ "${DETERMINISM_KEEP:-0}" = 1 ] && echo "determinism: keeping $tmp" >&2 || trap 'rm -rf "$tmp"' EXIT
t0=$(date +%s)

snapshot() { python3 -I -c 'import sqlite3,sys; s=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()' \
               state/specsheet.sqlite "$tmp/db.sqlite"; }
copy_tree() {   # code + research + data + docs shell; raw/ is linked (read-only use), outputs and caches are left out
  rsync -a --exclude=/.git --exclude=/raw --exclude=/state --exclude=/docs/api --exclude=/api-worker/node_modules --exclude=/api-worker/pack \
        --exclude=/api-worker/r2-data --exclude=/api-worker/.wrangler --exclude=__pycache__ "$src"/ "$1"/
  ln -s "$src/raw" "$1/raw"
  mkdir -p "$1/state"
}
if [ "${SPECSHEET_RELEASE_LOCKED:-0}" = 1 ]; then
  snapshot; copy_tree "$tmp/a"
else   # import.py / build.py by other agents run under this lock: snapshot + copy a consistent tree
  exec 8>/tmp/specsheet-release.lock; flock -w 1800 8 || { echo "determinism: release lock busy" >&2; exit 2; }
  snapshot; copy_tree "$tmp/a"
  flock -u 8; exec 8>&-
fi
cp -a "$tmp/a" "$tmp/b"
mv "$tmp/db.sqlite" "$tmp/a/state/specsheet.sqlite"; cp "$tmp/a/state/specsheet.sqlite" "$tmp/b/state/specsheet.sqlite"
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(date +%s)}
for side in a b; do
  ( cd "$tmp/$side" && unset SPECSHEET_ROOT \
    && python3 -I scripts/build.py > "$tmp/$side.build.log" 2>&1 \
    && python3 -I scripts/build_r2.py --tier free --shard-hex 3 --snapshots "$tmp/$side/state/r2-snapshots/free" > "$tmp/$side.r2.log" 2>&1 ) \
    || { echo "determinism: build $side failed" >&2; tail -20 "$tmp/$side.build.log" "$tmp/$side.r2.log" 2>/dev/null >&2; exit 2; }
done
rc=0
for out in docs/api api-worker/pack; do
  if ! diff -rq "$tmp/a/$out" "$tmp/b/$out" > "$tmp/diff.txt"; then
    rc=1; echo "determinism: $out differs between two builds of the same DB ($(wc -l < "$tmp/diff.txt") files):" >&2
    head -20 "$tmp/diff.txt" >&2
    grep '^Files .*\.json and ' "$tmp/diff.txt" | head -3 | sed -E 's/^Files (.*) and (.*) differ$/\1 \2/' | while read -r fa fb; do
      python3 -I - "$fa" "$fb" >&2 <<'PY'
import json, sys
def walk(a, b, p, out):      # first differing JSON paths (a byte diff of a one-line index is unreadable)
    if len(out) >= 4: return
    if type(a) is not type(b) or not isinstance(a, (dict, list)):
        if a != b: out.append(f"  {p or '/'}: {json.dumps(a)[:120]}  !=  {json.dumps(b)[:120]}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if a.get(k) != b.get(k): walk(a.get(k), b.get(k), f"{p}.{k}", out)
    elif len(a) != len(b): out.append(f"  {p}: {len(a)} vs {len(b)} items")
    else:
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y: walk(x, y, f"{p}[{i}]", out)
out = []; walk(json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), "", out)
print(sys.argv[1].split("/a/", 1)[-1] + ":"); print("\n".join(out) or "  (same JSON value, different bytes: key order / formatting)")
PY
    done
  fi
done
n=$(find "$tmp/a/docs/api" "$tmp/a/api-worker/pack" -type f | wc -l)
[ $rc = 0 ] && echo "determinism: OK, $n files byte-identical across two builds ($(( $(date +%s) - t0 ))s)" \
            || echo "determinism: FAILED ($(( $(date +%s) - t0 ))s)" >&2
exit $rc
