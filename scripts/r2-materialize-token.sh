#!/usr/bin/env bash
# Run interactively (pass needs gpg-agent; timers/cron cannot use pass).
# Materializes `pass specsheet/r2-raw-backup` -> state/r2-token (chmod 600, gitignored via state/).
# Expected pass entry: line 1 = access key id, line 2 = secret access key, optional line 3 = account id/endpoint.
set -euo pipefail
P="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
umask 077
pass show specsheet/r2-raw-backup > "$P/state/r2-token.tmp"
mv "$P/state/r2-token.tmp" "$P/state/r2-token"; chmod 600 "$P/state/r2-token"
echo "wrote $P/state/r2-token"
