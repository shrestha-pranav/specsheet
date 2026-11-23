# A1+A2: air purifiers (new category `air-purifiers`), 2026-11-23

## Decisions / open questions first
- **Result:** 1,142 models across 70 brands; 8,396 claims accepted, 92 candidates; 0 id conflicts, 0 parser drift; 193 stem proposals
  (`possible_match`), nothing merged. By source: 925 CARB-only, 150 ES+CARB, 38 ES-only, 12 Winix+CARB, 7 Levoit+CARB, 4 ES+CARB+Levoit,
  4 ES+CARB+Winix, 2 Winix-only. 212 models have a smoke CADR. Profile: 49 specs, 10 groups, 7 conditions; validates against the schema.
- **Coordinator: approve `claim/air-purifiers-structured@1`** (pending, locked by this import). Explicit extractors/source_ids (4 each),
  per-source keys (ES 21, CARB 4, Levoit 13, Winix 24). Preview only: cadr.unspecified_cfm (Levoit's "CADR: 231 CFM" names no pollutant),
  filter.price_usd (dated store price), cert.maker_listed (maker badges), phys.dimensions_text, Levoit standby ("< 2W").
- **Judgement call, CARB-only volume:** 925 entities hold only CARB facts (dated certification, Mechanical/Electronic, EO number). CARB mints
  entities only for 23 major brands with a 2019+ date (`carb_airpurifiers.MINT_BRANDS` / `MINT_SINCE`). Other brands only enrich an exact
  ES/maker string (95 refs). Narrowing is a one-line change, but the ids are already in the registry.
- **Identity:** model number as printed. Certification attaches only on an exact normalised (brand, model) match: no stem, no wildcard
  expansion, no transfer through declared aliases. Colour/channel tails are separate models, only proposed (AP-1512N(W) vs (BG),
  LAP-C401S-WUSR vs -KUSR). 13 ES wildcard filings skipped. One owner's brand spellings fold (Coway Airmega, Honeywell by Kaz); relabel
  brands do not.
- **Open (A3):**
  1. Levoit has two namespaces (marketing "Core 400S" vs label code "LAP-C401S-WUSR"). ES files both, no source crosswalks them; separate.
  2. An ES `declared_same_hardware` alias can equal another source's key (Blueair 4312112000 is also a CARB entity). Not merged; needs an
     alias-vs-key rule.
  3. 18 gtin conflicts = relabel brands sharing UPCs (AROEVE/BREEZOME/...); surfacing them is correct.
  4. Coway and Blueair pages are rich but print no ES/CARB model number; they need a reviewed name-to-code crosswalk.

## Review 3/4 lessons applied (tests/test_air_purifiers.py, 16 tests)
- **Affirmative only:** filter.true_hepa only from ES filter type exactly "HEPA" (dataset defines it as True HEPA) or a maker "True HEPA"
  row, never false ("HEPA-Type" -> filter.hepa_class only). CARB certified only from the CARB list (absence = unknown). A bool is false only
  when its own row says a bare "No".
- **Bases in conditions:** every CADR has cadr_basis (energy_star_certified / aham_verified_maker_stated, only when the same table says
  AHAM / maker_claimed). Room size has room_basis + ach; 1-ACH "coverage" has its own key. Noise has fan_speed (ranges -> range_min /
  range_max); power has power_basis. No watts derived from CADR/W.
- **Conflict-aware:** ES rows (several pd_ids) that disagree -> unresolved, values in raw. Multi-model ES cells name each model, no UPC.
  CARB type disagreements unresolved; multi-model cells (643) and non-purifier rows (230) dropped. Winix CADR order read from the label;
  ">450" pollen unresolved, the other two kept. No model row -> no entity (9 Levoit, 1 Winix, humidifier pages).
- **Declarations:** "same as X except model number / for color" -> declared_same_hardware (5). "Identical in performance, only difference
  is..." (Winix C710/C610) is not.

## Sources (crawler UA, robots honoured, no Bright Data, no UA spoofing)
- **Built:** energystar_airpurifiers (Socrata gaa3-swy6, 1 GET, 248 rows -> 212 refs); carb_airpurifiers (ARB list, 1 GET, 13,090 rows,
  Crawl-delay 5 -> 1,102 refs); levoit_airpurifiers (products.json + 22 pages); winix_airpurifiers (sitemap + 22 pages, 2 x 404; filter
  part number + list/sale price); _airpurifier (shared pure helpers).
- **Blocked: AHAM Verifide.** ahamdir.com is a JS app over an undocumented POST API (gbs.trutesta.io). One call was refused by the tool
  policy; not retried, no workaround. Getting in needs a human-downloaded xlsx export or AHAM permission.
- **Viable, not built:** Medify, Alen, Rabbit Air, AirDoctor, Molekule, Dreo (Shopify); Coway, Blueair (no model identity on their pages).
  Details in research/air-purifiers/manufacturers.yaml.

## Shared-file changes
- crawler/adapters/registry.py +4 SOURCES lines. data/decisions/policies.yaml +claim/air-purifiers-structured@1 (before
  `relation_policies:`; no other policy touched).
- Appended by the import: policy-lock.jsonl +1, data/_ids/registry.jsonl +1,142. releases/: dry-run manifest. docs/ rebuilt by release.sh
  (index.html build stamp only). No scripts/*.py change. The team/briefs/common.md diff is not mine.
- New: research/air-purifiers/ (6 files), crawler/adapters/{_airpurifier,energystar_,carb_,levoit_,winix_}airpurifiers.py,
  tests/test_air_purifiers.py, raw/{energystar,carb,levoit-us,winix-us}-airpurifiers/.

## Verification
`RELEASE_DRY_RUN=1 scripts/release.sh "air purifiers"`: rc=0; strict parsers, no drift; all tests and both smokes pass. Budget ok (API
90.8 MiB, 18,360 files). Local orphan gh-pages eb9033e2; manifest releases/20261123T233047Z-9e307181.json. Nothing committed or pushed; no
stash, checkout, reset or restore.
