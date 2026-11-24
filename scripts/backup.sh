#!/usr/bin/env bash
# Nightly local backup of raw/ + state/specsheet.sqlite -> /mnt/hdd-3tb/backups/specsheet/
# (second physical disk; see vault host-storage). Never --delete: raw/ is append-only evidence.
# Reports to Uptime Kuma push monitor "specsheet backup" (success=up, any failure=down,
# silence past 36h also trips it). Target is NTFS (ntfs3): no perms/owner/symlinks.
set -uo pipefail
P="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
DEST=${SPECSHEET_BACKUP_DEST:-/mnt/hdd-3tb/backups/specsheet}
MNT=/mnt/hdd-3tb
KEEP_DB=${KEEP_DB:-7}
TOKENS=/home/pranavsh/code/homelab/scripts/kuma-push-tokens.env

report() { # status msg
	echo "[$(date -Is)] $1: $2"
	[ -r "$TOKENS" ] || return 0
	# shellcheck source=/dev/null
	( . "$TOKENS"; [ -n "${SPECSHEET_BACKUP_TOKEN:-}" ] && curl -fsS -m 15 -o /dev/null --get \
		"$KUMA_PUSH_BASE/$SPECSHEET_BACKUP_TOKEN" --data-urlencode "status=$1" --data-urlencode "msg=$2" ) || true
}
die() { report down "$1"; exit 1; }

# Never write into an unmounted mountpoint dir (would fill the root SSD / shadow dir).
mountpoint -q "$MNT" || die "$MNT not mounted"
touch "$MNT/.specsheet-wtest" 2>/dev/null && rm -f "$MNT/.specsheet-wtest" || die "$MNT not writable (dirty NTFS, read-only?)"
mkdir -p "$DEST/raw" "$DEST/state" || die "cannot create $DEST"

# 1. consistent sqlite snapshot (sqlite3 CLI absent -> python backup API; safe mid-write)
day=$(date +%F); tmp="$DEST/state/.tmp-$day.sqlite"; rm -f "$tmp"
python3 -I - "$P/state/specsheet.sqlite" "$tmp" <<'PY' || die "sqlite backup failed"
import sqlite3, sys
src = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True, timeout=60)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
chk = sqlite3.connect(sys.argv[2]).execute("pragma integrity_check").fetchone()[0]
sys.exit(0 if chk == "ok" else 1)
PY
mv -f "$tmp" "$DEST/state/specsheet-$day.sqlite"
# retention applies to our own dated sqlite copies only
ls -1t "$DEST"/state/specsheet-*.sqlite | tail -n +$((KEEP_DB+1)) | xargs -r rm -f --

# 2. raw/: blobs are content-addressed/immutable -> --ignore-existing; the rest is mutable.
RS=(rsync -rt --no-perms --no-owner --no-group)
"${RS[@]}" --ignore-existing --include='*/' --include='blobs/**' --exclude='*' "$P/raw/" "$DEST/raw/" || die "rsync blobs failed"
"${RS[@]}" --exclude='blobs/' "$P/raw/" "$DEST/raw/" || die "rsync index/products failed"

n=$(find "$DEST/raw" -type f | wc -l)
report up "ok: $n raw files, db specsheet-$day.sqlite"
