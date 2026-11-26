# Brief r10: monitor native refresh + 1440p preset. Owner: A2-ref. Read common.md first (crawl rules, no alternate fetchers on blocked sites, never fill approval fields, never run release.sh, gitleaks:allow for fake secrets).
Goal: preset monitor-1440p-144 is ~44.6% fill (res.refresh_native). Raise it from makers already crawl:agent in data/source-policy.yaml (check with scripts/source_policy.py validate; LG, ASUS, BenQ, MSI, Lenovo, Dell — NOT AOC/Samsung/HP/ViewSonic/Acer/Gigabyte which are human_only or blocked).
1. First mine raw/ already stored (LG, ASUS, BenQ pages/spec tables) for native vs overclocked refresh. Native = maker-stated refresh without OC; if only "up to N Hz (OC)" is stated, record native only if a separate non-OC rate is stated. Never infer native from panel model.
2. Then new fetches only on crawl:agent hosts, robots read in full before any GET.
3. Secondary: same pages' flicker-free/PWM statements for preset no-pwm-usbc-monitor (76.1%, gate 80%) — affirmative maker statements only.
4. New/changed adapters -> new pending policy version (reissue @N+1, retire old verbatim). Re-pin fingerprints. Report the before/after preset fill and population.
Finish: flock /tmp/specsheet-release.lock python3 scripts/import.py --strict-parsers && build.py rc 0; all tests/test_*.py pass. Report team/reports/2026-11-26-a2-r10-refresh.md (<=30 lines).
