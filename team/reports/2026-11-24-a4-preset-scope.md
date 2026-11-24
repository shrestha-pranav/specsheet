# A4: D8 preset scope (2026-11-24, no commit)
D8 fill / state, built and re-measured at the end (A2 data had not moved any number yet; re-measure after A2 lands):
purifier 94.9% PASS (62 brands) · 4K120 71.5% fail (3 brands) · ram 79.6% fail (1 brand: Lenovo; fill is just under 80%, brands also fail) · panel 65.0% fail
SSD 40.5% fail · router 37.8% fail · PPS 11.2% fail · monitor 0.0% fail (usb.usbc_inputs 0/1063; population 1063 of 4234). All match the expected numbers.
Index growth: new per-row `t` (sorted source tiers, full names) in v1_publish row_of: 8,339,045 -> 8,550,366 bytes of index shards (+211 KB, +2.5%, uncompressed).
No other keys had to be added: wifi.streams_6 left the preset in docs/presets.json, and every remaining gate key/column is a facet or column field.
Changes: scripts/presets.py (D8 measure, gate.scope incl. sources/include_discontinued, min_brands, count.out_of_scope; guards: gate key/column neither facet nor column,
scope.by not a filter key, rows missing `t` when scope.sources set). Extra not_covered reason "discontinued only".
Shared-file edits: scripts/v1_publish.py (1 line, `t`), docs/app.js (coverage line + basis + excluded/not-covered on cards, in-scope list, "Show all Y" toggle via &all=1),
scripts/smoke.mjs (gate assertion), scripts/frontend-smoke.mjs (independent D8 re-derivation, 0%-key assertion kept, synthetic cases), new tests/test_presets.py (5 cases).
Contract: a4-contract.md NOT updated for `t`; A3 sign-off pending (additive field on index rows, `t: [tier]`).
Verified under flock: build ok, test_presets, frontend-smoke, smoke pass. Browser: purifier card at 390 px has no overflow; monitors ?preset toggles 1,063 <-> 4,234.
Not done: browser-smoke.mjs (Playwright) not run; 1200 px card only checked via layout logic, not screenshot.
