#!/usr/bin/env bash
# Resume the Codex UI-v1 coordinator session (gpt-6-astra + sol_implementer + astra_reviewer)
# after its usage/credits ran out. Probes first; exits 3 if Codex still refuses.
set -u
cd "$(dirname "$0")/.."
SESSION=01a204bc-54b4-7d70-80ff-d83f01c02e2b
A="$PWD/.codex/agents"
LOG=reviews/ui-v1-codex-resume.log

probe=$(timeout 180 codex exec -m gpt-6-astra -s read-only --skip-git-repo-check "Reply with exactly: ok" 2>&1)
if ! grep -qx 'ok' <<<"$probe"; then
  echo "probe failed: $(grep -m1 -iE 'credit|limit|error' <<<"$probe")"
  exit 3
fi

codex exec resume "$SESSION" -m gpt-6-astra --skip-git-repo-check \
  -c sandbox_mode='"workspace-write"' \
  -c features.multi_agent=true \
  -o reviews/ui-v1-codex-final.md \
  "You ran out of credits before finishing briefs/ui-v1.md. Since then a maintainer committed your
work and made these changes (keep them): build.py stamp_build() adds a build id to every asset
and data URL (a stale cached products.json crashed the category page in a real browser);
styles.css hides the focus ring on programmatic focus of <main>. Known issue found in browser
review: product page 'Port details' renders raw 'name: ... type: ... max w:' text; it must be a
proper per-port table, and port_sharing similarly readable. Now finish the process: (1) have
astra_reviewer run impeccable critique + audit on the current site and save the ranked report to
reviews/ui-v1-critique.md; (2) send P0/P1 findings plus the ports-table issue to sol_implementer
to fix; (3) re-run python3 -I scripts/build.py and node scripts/smoke.mjs; (4) final report, including which model each spawned agent ran on (the role files now load; in your first run they were ignored because they lacked a name):
what changed, check results, remaining gaps. Same constraints as the brief (no commits/pushes,
don't touch data/ raw/ crawler/ ARCHITECTURE.md)." > "$LOG" 2>&1
echo "exit=$?"
