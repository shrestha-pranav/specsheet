# A4 killer queries (2026-11-24)
Built: 8-card preset gallery on home; yes/no/unknown + "might match" split/toggle; PDO per-port pill; TV size grid; event beacons. No commit, no deploy.
Data: docs/presets.json (definitions) -> scripts/presets.py (build time) -> docs/api/v1/presets.json (gate, counts, missing brands). Agents read it as a static file (llms.txt links it; the worker's presets-removed 404 is untouched).
Gate (fill = weakest gate key, known/total over the whole category, min_fill 0.8) today: NO preset passes. Closest first:
 ram-upgradable 79.6% (mem.max 1926/2419; ASUS has none) | tv-panel-by-size 61.7% (display tech) | ssd-dram-tlc-2tb 28.3% (NAND type)
 tv-4-hdmi-4k120 23.6% | power-bank-samsung-45w 14.9% (PPS) | no-pwm-usbc-monitor 8.2% (USB-C PD W) | router-4x4 0% (6 GHz streams) | purifier-400sqft 0% (filter price)
Failing cards read "Help fill this: N of M known" for the field, list brands with no value, link a prefilled GitHub issue; ?preset=<id> on a failing preset applies no filters. They flip on the next build as A2 data lands.
Beacons: killer_query, source_click, request_click, spec_unknown_shown (once per key per page view) via sendBeacon text/plain to /v1/event; no-op while site.json api_origin is empty (it is).
Checked in browser at 1200 and 390 px: gallery, size grid, PDO table (cuktech-pb200), maybe-toggle; no horizontal overflow. Counts match build counts (151 matches, 118 unknown on laptops).
Smokes: frontend-smoke (gate re-derived from index, count parity, pill, grid, beacon off), smoke.mjs (presets.json shape), browser-smoke cases added but Playwright is not installed here (skipped).
Shared-file edits: scripts/build.py (2 lines, calls presets.write), scripts/site_meta.py (llms.txt line), docs/app.js, docs/styles.css, scripts/*smoke.mjs.
Not done: laptop memory sentence, verified-vs-maker badges, source link per core value (not in your list). 4x4 router preset uses exact streams_5=4 (integer facet is an enum there).
Note: filters on non-facet keys (e.g. wifi.streams_6) cannot be preset filters; presets.py fails the build on them.
