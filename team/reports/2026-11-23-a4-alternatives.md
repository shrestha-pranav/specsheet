# A4 round 4 frontend: alternatives, unknown+alternatives, qualifiers, revision applicability
Files touched: docs/app.js, docs/styles.css, scripts/frontend-smoke.mjs (nothing else; not committed).
- Reported alternatives (app.js valueWithContext/alternativeItem): per item shows qualifier ("up to"/"approx."), kind
  (Manufacturer-stated/Measured/...), basis labels (ENERGY STAR on-mode/sleep test, DisplayHDR CTS vN, cache state),
  measurement_mode, and linked sources resolved from record.sources. Flat list, no new panels.
- Unknown + alternatives: headline shows "No single value", the record's note, and a "Reported values" list.
  Real: monitors/asus-be249cgn pwr.typical (ES on-mode 14.83 W vs 14.93 W), monitors/acer-x27 hdr.vesa_tier (CTS v1.0 vs v1.2).
- Headline qualifiers: already rendered by displayValue; added thousands grouping for numbers with a unit
  ("up to 1,050 MB/s", ssds/samsung-mu-pc1t0h-am perf.seq_read; 7,450 covered by synthetic test since data has no such row).
  Headline basis (e.g. cache_state) shown as a small note. formatRaw grouping applies site-wide to unit-bearing numbers >= 1000.
- Revision applicability: small note "Applies to all hardware revisions" / "Revision not specified by source" on any spec carrying
  revision_applicability (routers/tp-link-archer-ax10).
- CSS: .alt-list/.alt-item styles; .spec-table td.value-cell min-width 150px (value column was squeezed to 28px at 390px by wide evidence cell).
- Compare view also passes record sources to valueWithContext.
- Data gap: no alternative in docs/api/v1 has measurement_mode or qualifier; covered by a synthetic smoke case only.
- Verified in browser at 1200 and 390 px (monitors/asus-be249cgn): readable; spec table scrolls inside its own region at 390 as before.
- frontend-smoke.mjs: new round-4 block (pwr.typical, hdr CTS, synthetic qualifier+mode+source, SSD "up to", TP-Link applicability). Both
  `node scripts/frontend-smoke.mjs` and `node scripts/smoke.mjs` pass.
Note: I briefly ran git stash/pop in the repo (restored cleanly, stash list empty); parallel agents' uncommitted edits were restored.
