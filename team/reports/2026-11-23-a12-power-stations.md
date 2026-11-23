# A1+A2: portable power stations (category #11), 2026-11-23

## Decisions / open questions first
- **Result:** 95 model entities, 5 brands: BLUETTI 34, Goal Zero 21, Anker SOLIX 19, EcoFlow 14, Jackery 7. 71 of them have published specs
  (docs/api/v1/power-stations/index.json). The other 24 are minted from a solid SKU or model number, but their pages have no spec rows in the HTML.
  The import accepted 1,434 claims and left 207 as candidates. It minted 95 new ids with 0 id conflicts and 0 parser drift. Profile: 45 specs in
  10 groups, 9 condition dimensions. It validates against the schema.
- **Coordinator: approve `claim/mfr-power-stations-structured@1`** (state pending, locked by this import). It has explicit extractor, source and
  per-source key allowlists and accepts only normalised values. No prose-, title- or price-derived keys. `exp.batteries` is deliberately excluded
  because it comes from name extraction.
- **Review-3 rules were applied from the start** (fixtures in the new tests/test_power_stations.py, 11 tests):
  - **No negation-blind enums.** Waveform, chemistry, UPS, expandability and UL 2743/9540 come only from their own labelled rows. 'UL Standard'
    and 'UL 2743 pending' are not UL 2743. `false` is set only when the row's whole value is 'No' (Goal Zero 'Chainable: No').
  - **Totals need explicit membership.** AC continuous output comes from the row tagged total/rated/continuous. Combined solar input is taken only
    when the page prints it: '500W Max*2' becomes a per-port value of 500 W across 2 ports, never 1000 W. '2 ports, 140W Max' gives a port count,
    not a per-port figure. Nothing is summed across ports.
  - **Capacity bases stay separate.** Rated Wh, usable Wh (only when labelled usable), pack voltage and pack Ah are separate keys. A cell with two
    Wh figures is unresolved, and Wh is never computed.
  - **Bases live in conditions.** Cycle life carries retention_pct (Jackery rates to 70 %, the others to 80 %). Recharge time carries
    charge_to_pct and charger. UPS carries backup_mode (ups/eps/aps). The solar window carries voltage_basis and port. AC input carries
    ac_charge_mode.
  - **Grouping handles conflicts.** Unit variants and bundle variants are kept apart (details under Identity).
- **Semantics to confirm:**
  - Jackery prints no label model on 43 of 44 pages, so its key is the station name from the spec heading ('Explorer 1000 v2'). Item numbers are
    colour aliases. JE-1500C is a `mfr_label_model` alias.
  - Recharge times with no printed charge range stay unresolved. Goal Zero is the only brand that gives a range ('0-80%: 0.8 hrs').
  - EcoFlow 'Car Charging 800W' is the Alternator Charger rate, so figures above 400 W are unresolved.

## Identity (research/power-stations/identity.md)
- **Model keys:**
  - EcoFlow: the unit-SKU stem, e.g. EFDELTA3P.
  - Anker: the A17xx model shared by the unit variants, e.g. A1763.
  - BLUETTI: the SKU stem before -US-/-UN-, e.g. AC180P.
  - Goal Zero: the 5-digit item number, which must equal the page's SKU row (e.g. 36300).
  - Colour SKUs are aliases.
- **Bundles are packages, never the model.** Solar-generator, kit and '+' pages are not discovered. Bundle variants on a station page go to
  `fingerprints.packages`; they are neither aliases nor a source of specs.
- **Pages with no model identity (absences):** 4 EcoFlow pages ('... Series', RIVER mini standard vs wireless). These pages name 2 unit-SKU stems.
- **Pages whose spec block cannot be attributed (absences):**
  - BLUETTI blocks that split values per model, e.g. '1,152Wh (AC180) / 1,440Wh (AC180P)'.
  - Goal Zero Yeti PRO 8000, which is the PRO 4000 plus a Tank expansion battery.
  - Jackery 230 V blocks. One of these was copied onto the US black Explorer 1000 v2 variant and was skipped.
- **Data issue:** BLUETTI uses GTIN 00193022003033 on both PR100V2 and PR200V2. This is one identity_conflicts row.
- **Open:** the 'model' importer can only mint packages from MTM identifiers, so bundles are recorded in fingerprints but not minted as package
  entities. Fixing this needs A3.

## Sources (crawler UA, robots honoured, 1 req/s, no Bright Data, 157 fetches, all 200)
- **Built:**
  - `shopify_powerstations.py` covers EcoFlow, BLUETTI, Jackery and Goal Zero: products.json plus the spec rows of each page.
  - `ankersolix_stations.py` reads __NEXT_DATA__ variant metafields.specs. anker.com/products/a17xx redirects to ankersolix.com.
  - The shared mapper is `_powerstation.py`. It only imports `_powerbank`, so no power-bank fingerprint moved.
- **Blocked:** none.
- **Partial:**
  - 12 BLUETTI pages (Elite, Apex, Pioneer Na) render Tech Specs client-side.
  - 30 of 44 Jackery pages have no spec rows in the HTML.
  - 8 Anker pages have no specs metafield.
  - Anker S2000/S5000 use AS2 SKUs and are not minted.
- **Not built:** DJI Power. It is not Shopify, and its specs are prose on www.dji.com. UL Product iQ verification was not built either.

## Shared-file changes
- `crawler/adapters/registry.py`: +5 SOURCES lines (*-us-stations, importer `model`). Anker's brand_name stays 'Anker' because a global brand
  map would otherwise rename the power-bank brand.
- `data/decisions/policies.yaml`: +`claim/mfr-power-stations-structured@1` inserted before `relation_policies:`. No other policy was touched.
- Appended by the import: `data/decisions/policy-lock.jsonl` +1 line, `data/_ids/registry.jsonl` +95 ids.
- `releases/`: dry-run manifest `20261123T183728Z-13725409.json` plus its index line.
- `docs/api` and the docs/index.html stamp were rebuilt by release.sh. I did not edit docs/app.js, docs/styles.css or the smoke scripts; those diffs
  are A4's.
- **New files:**
  - `research/power-stations/` (6 files)
  - `crawler/adapters/{_powerstation,shopify_powerstations,ankersolix_stations}.py`
  - `tests/test_power_stations.py`
  - `raw/<5 sources>/`

## Verification
- `RELEASE_DRY_RUN=1 scripts/release.sh "power stations"` returned rc=0 with budget ok (API 74.1 MiB, 14,748 files). Local orphan gh-pages is
  e35ce700. The import ran with --strict-parsers. Smoke, frontend-smoke and all tests pass.
- Nothing was committed or pushed. No git stash, checkout, reset or restore was used.

## Open issues
- `idle.draw_w` and `cap.usable_wh` are on no store page; they need manuals or bench data. `cert.ul2743` is a maker claim (7 BLUETTI models)
  until checked in UL Product iQ.
- BLUETTI and Jackery pages rendered client-side would need a JSON endpoint; I found none in the page.
- Some USB counts and per-port maxima stay unresolved by design: Goal Zero 'USB-C QC (30 W x 2)' and EcoFlow '2 ports, 140W Max'.
