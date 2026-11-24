# Brief: implement the D8 preset population in presets.py and the cards (PM round 4). Owner: A4. Read product/decisions.md D8.
docs/presets.json now carries `default_scope`, `default_min_brands` and a per-preset `scope` {sources, include_discontinued, by, basis}.
Today's presets.py ignores them, so the build still gates on the whole category. Land this before or with A2's preset-fill data:
otherwise ram-upgradable flips to "pass" on Lenovo alone once 10 more rows arrive, which D8's min_brands forbids.

1. **presets.py `measure`**: population per gate key k = rows where
   (a) row source tiers ∩ scope.sources ≠ ∅ (null = all rows). The index has no tiers, so either read `products/<id>.json`
   `sources[].tier` at build time (no contract change), or add a compact `"t": [tiers]` to index rows. If you choose the index field,
   get A3's sign-off and update a4-contract.md. The UI needs the tiers for item 3, so the index field is probably the right call.
   (b) `lifecycle != "discontinued"` unless include_discontinued (`unknown` stays in);
   (c) no filter on a `scope.by` key returns "no" (`_verdict`), skipping the filter on k itself;
   (d) `s[k] != "not_applicable"`.
   Fill = known/len(population). Pass = every key ≥ min_fill **and** covered_brands ≥ min_brands, where covered = brands with ≥1
   known value on every gate key inside the population. Validate that every `scope.by` key is a filter key of that preset (fail the build otherwise).
2. **Output** (docs/api/v1/presets.json, additive): `gate.scope` = {basis, in_scope, category_total, covered_brands:[names],
   excluded:{source_tier:n, discontinued:n, by:{key:n}}, not_covered:[{brand, rows, reason: "no maker source" | "no value"}][:8]}.
   Per-key `total` becomes the per-key population. Keep `missing_brands` (now within scope).
   `count` (matches/maybe) is computed over the population, plus `count.out_of_scope`.
3. **Card + list (app.js)**: every card shows the line "Covers N brands: A, B, C · X of Y <category> in scope", followed by `basis`
   (a short line, details on hover or expand). Failing cards keep "Help fill this", now with the in-scope numbers. `?preset=` opens the
   in-scope rows (tier + lifecycle applied), with a visible "show all Y" toggle, so the list never silently hides rows.
4. **Build guard**: fail when a gate key (filter or require) or a column is neither a facet nor a column field. Those keys are not
   carried in the index, which is why `wifi.streams_6` measured 0% while 31 records have it. `usb.usbc_inputs` is a facet with 0 values
   today, which is fine.
5. **Smokes**: frontend-smoke re-derives the gate from the index. Re-derive the D8 population the same way (needs the tiers from item 1).
   Keep the "a 0%-fill key fails today" assertion: no-pwm-usbc-monitor is at 0% on `usb.usbc_inputs`. Add synthetic cases for
   unknown-stays-in, a key not scoped by itself, and min_brands=2 failing at 1 brand with 100% fill.
6. Ids changed: `ssd-dram-tlc-2tb` → `ssd-dram-2tb` and `router-4x4-5-6ghz` → `router-wifi7-6ghz`. Nothing else references them.
   The purifier preset passes on the next build even under the old rule (94.9%), so check its passing card at 1200 and 390 px.
Expected D8 gate today (from records): purifier 94.9% pass · 4K120 71.5% · ram 79.6% (1 brand) · panel 65.0% · SSD 40.5% ·
router 37.8% · PPS 11.2% · monitor 0%. Your build should reproduce these numbers to ±1 row, or explain the difference.
No commit, no deploy. Report: team/reports/<date>-a4-preset-scope.md (≤30 lines).
