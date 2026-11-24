#!/usr/bin/env bash
# DISABLED until state/r2-token exists (see r2-materialize-token.sh) and rclone is installed.
# rclone COPY (never sync) raw/ -> r2:specsheet-raw/raw/, sqlite -> state/<date>.sqlite.gz keep 14.
# Not wired to any timer yet; add one once the owner token exists and a restore test passes.
set -euo pipefail
P="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
TOK="$P/state/r2-token"
[ -s "$TOK" ] || { echo "r2-offsite: disabled, no $TOK (owner token pending)"; exit 0; }
command -v rclone >/dev/null || { echo "r2-offsite: rclone not installed"; exit 1; }
export RCLONE_CONFIG="$P/state/rclone.conf"
if [ ! -s "$RCLONE_CONFIG" ]; then
	umask 077
	AK=$(sed -n 1p "$TOK"); SK=$(sed -n 2p "$TOK"); EP=$(sed -n 3p "$TOK")
	printf '[r2]\ntype = s3\nprovider = Cloudflare\naccess_key_id = %s\nsecret_access_key = %s\nendpoint = %s\n' "$AK" "$SK" "$EP" > "$RCLONE_CONFIG"
	chmod 600 "$RCLONE_CONFIG"
fi
rclone copy "$P/raw" r2:specsheet-raw/raw --transfers 8 --checksum
db=$(ls -1t /mnt/hdd-3tb/backups/specsheet/state/specsheet-*.sqlite | head -1)
d=$(date +%F); gzip -c "$db" | rclone rcat "r2:specsheet-raw/state/$d.sqlite.gz"
rclone lsf r2:specsheet-raw/state/ | sort | head -n -14 | while read -r f; do rclone deletefile "r2:specsheet-raw/state/$f"; done
