# Brief: A4 presets r2 + disagree UI. Owner: A4. Read common.md, product/demand-r6.md, team/reports/2026-11-25-a5-pm-round6.md, team/reports/2026-11-25-a3-corrections-hardening.md, product/decisions.md D8/D10.
1. Add presets (D8 gate decides showcase vs help-us-fill; don't force): monitor-1440p-144, robovac-under-89mm, station-lfp-1kwh. Add surge-ul1449-2000j as help-us-fill.
2. Retitle tv-4-hdmi-4k120 so title matches what the gate checks (any 4K120 HDMI port); keep id stable or add redirect/alias so old links work. Note future gate hdmi.ports_4k120>=4 when that key reaches 80%.
3. power-bank-samsung-45w: off showcase, keep as help-us-fill.
4. docs/app.js disagrees(): match scripts/presets.py separate disagree bucket (15 SSD rows should show "sources disagree", not "Unknown value").
5. .github/ISSUE_TEMPLATE/field-correction.yml: privacy line mentions that the public maintainer handle on review lines is the only identity recorded.
Files: scripts/presets.py (presets defs only; A3 hardening finished there), docs/**, the issue template. Tests updated. Do not run release.sh; bare builds under `flock /tmp/specsheet-release.lock`. Report team/reports/2026-11-25-a4-presets-r2.md (<=30 lines). Deadline 12:00.
