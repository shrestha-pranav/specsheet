#!/usr/bin/env bash
# Probe Codex every 20 min until credits return (max ~8h). Exit 0 = available.
for i in $(seq 1 24); do
  out=$(cd /tmp && timeout 120 codex exec -m gpt-6-astra -s read-only --skip-git-repo-check "Reply with exactly: ok" 2>&1)
  if grep -qx ok <<<"$out"; then echo "codex ok at $(date)"; exit 0; fi
  echo "$(date +%H:%M) $(grep -m1 -o 'out of credits\|limit[^.]*' <<<"$out")"
  sleep 1200
done
exit 1
