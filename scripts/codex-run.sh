#!/usr/bin/env bash
# codex-run.sh <brief.md> <sandbox: read-only|workspace-write> <out.md> [model]
set -u
cd "$(dirname "$0")/.."
brief=$1; sb=$2; out=$3; model=${4:-gpt-6-astra}
log="reviews/$(basename "$out" .md).log"
codex exec -m "$model" --skip-git-repo-check -C "$PWD" \
  -c sandbox_mode="\"$sb\"" -c features.multi_agent=true \
  -o "$out" "$(cat "$brief")" > "$log" 2>&1
rc=$?
if grep -q -E 'out of credits|usage limit' "$log"; then
  ~/projects/usage-limits/wake add --provider codex --at auto --agent "${WAKE_AGENT:-2ec90b79}" \
    --prompt "Codex 5h window reset. Codex run for $brief hit the limit (log $log, out $out). Resume it with: codex exec resume <session id from the log> (cwd ~/projects/specsheet), or rerun scripts/codex-run.sh $brief $sb $out." || true
fi
echo "exit=$rc out=$out log=$log"
