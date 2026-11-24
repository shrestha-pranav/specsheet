#!/usr/bin/env bash
# Weekly KPI export: runs every `-- kpi:` block of scripts/kpi.sql against the Analytics Engine SQL API and writes
# ../state/metrics/<ISO week>.csv (gitignored, local only). Read-only Account Analytics token, owner held:
#   one-time / after rotation (interactive, needs gpg-agent):  scripts/kpi.sh --materialize
#   then (cron-safe, no pass):                                  scripts/kpi.sh
# Token file: ../state/secrets/cf-analytics-read (chmod 600). Account id: ../state/secrets/cf-account-id (not secret, but kept beside it).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../.." && pwd)"
sec="$root/state/secrets"; tok="$sec/cf-analytics-read"; acct_f="$sec/cf-account-id"
if [[ "${1:-}" == "--materialize" ]]; then
  umask 077; mkdir -p "$sec"
  pass show specsheet/cf-analytics-read | head -n1 > "$tok"; chmod 600 "$tok"
  [[ -s "$acct_f" ]] || { read -rp "Cloudflare account id: " a; echo "$a" > "$acct_f"; chmod 600 "$acct_f"; }
  echo "materialized $tok"; exit 0
fi
[[ -s "$tok" && -s "$acct_f" ]] || { echo "missing $tok or $acct_f: run scripts/kpi.sh --materialize" >&2; exit 1; }
[[ "$(stat -c %a "$tok")" == 600 ]] || { echo "$tok must be chmod 600" >&2; exit 1; }
acct="$(cat "$acct_f")"
umask 077; hdr="$sec/.kpi-auth-header"; printf 'Authorization: Bearer %s\n' "$(cat "$tok")" > "$hdr"  # token never in argv
trap 'rm -f "$hdr" "$sec/.kpi-blocks"' EXIT
week="$(date -u +%G-W%V)"; out="$root/state/metrics/$week.csv"; mkdir -p "$(dirname "$out")"
: > "$out"
python3 -I - "$here/kpi.sql" > "$sec/.kpi-blocks" <<'PY'
import sys, re
s = open(sys.argv[1]).read()
for name, body in re.findall(r"^-- kpi: (\S+)\n(.*?)(?=^-- kpi: |\Z)", s, flags=re.M | re.S):
    q = " ".join(l for l in body.splitlines() if not l.startswith("--")).strip()
    print(f"{name}\t{q}")
PY
while IFS=$'\t' read -r name q; do
  resp="$(curl -sS --fail-with-body -X POST "https://api.cloudflare.com/client/v4/accounts/$acct/analytics_engine/sql" \
    -H @"$hdr" --data-binary "$q FORMAT TabSeparatedWithNames")" || { echo "kpi $name failed: $resp" >&2; continue; }
  printf '%s\n' "$resp" | python3 -I -c 'import sys,csv; w=csv.writer(sys.stdout); n=sys.argv[1]
for i,l in enumerate(sys.stdin.read().splitlines()): w.writerow([n if i else "kpi"]+l.split("\t"))' "$name" >> "$out"
done < "$sec/.kpi-blocks"
echo "wrote $out"
