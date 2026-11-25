# Brief: zero-emitted schema keys. Owner: A2-keys. Read common.md, product/demand-r6.md, team/reports/2026-11-25-a5-pm-round6.md.
These keys exist in spec profiles but emit 0%: laptop port.* (which USB-C charges / DP alt mode / TB4/USB4), SSD therm.heatsink* (and height for PS5 <= 11.25 mm), monitor usb.kvm / usb.usbc_alt_dp, power station ups.* (switchover ms). Same failure class as mem.soldered in coverage r2.
- For each: find where makers state it in raw snapshots we already hold (PSREF port rows, maker spec tables), fix/extend the adapter parsers (not crawler/documents.py, _docparse.py, _docspec_*.py, import.py, presets.py, corrections.py — others own those). Affirmative only; negatives only from complete enumeration per D-rulings. Per-port facts need port attribution, never pooled.
- No new crawls unless a registered crawl: agent maker page is missing for a key; ~1 req/s, robots.
- Reissued extractors = pending @N policies (retire old verbatim). Tests per key.
- Report fill before/after per key (in-scope population per D8).
Do not run release.sh; bare builds under `flock /tmp/specsheet-release.lock`. Report: team/reports/2026-11-25-a2-zero-keys.md (<=40 lines). Deadline 12:00.
