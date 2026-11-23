# TVs: identity rules (A1+A2, 2026-11-23)

Levels (spec-profile.yaml): family (series, browse only) > model (one size) > revision (panel/production version) > package (GTIN).
Adapters emit observations; the importer (`model` importer, exact normalised key) decides entities. Nothing below merges by stem or by spec match.

## What a "model" is
- **One screen size = one model number.** `QN65S90FAFXZA`, `OLED65B5PUA`, `65QM8K`. The shorthand `QN65S90F` / "S90F" / "C5" is the family,
  never a key. Panel facts are therefore per size by construction (see "Panel lottery").
- Key = the maker's string as printed on its US page, upper-cased, spaces removed (`value_raw` verbatim). Market tails are part of the string:
  Samsung `XZA` (US), LG `U` (US) + stand/colour letter. TCL US prints no tail.
- ENERGY STAR (EPA) certifies the maker's **certified string**: Samsung without `XZA` (`QN65S90FAF`), Hisense with a version tag
  (`100U77SUA(01)` -> key `100U77SUA`, tag kept in value_raw), LG as **wildcard families** (`OLED65C5***`, "may be any alphanumeric according to
  color of stand or enclosure"). Wildcards never name a product: the importer skips them (`skipped_wildcard_pattern`, 63 rows).
- ENERGY STAR-only models (Sansui, Philips hospitality, XITRIX, Emerson, Loewe, Insignia, RCA, Sceptre, Hisense, older Samsung) are models
  keyed by the certified string, tier regulatory.

## Retailer-exclusive / channel designations (the known trap)
- Samsung: `QN65S92FAF` (warehouse-club designation of S90F), `QN65S90FDF` (D = channel letter); LG: `OLED65C4AUA` vs `OLED65C4PUA`
  (A vs P channel), `65QNED80AQA` vs `65QNED80AUA`; TCL/Hisense sell retailer series (QM85 vs QM8) under different strings.
- **Grouped into one model only with corroboration**: the maker's own statement in its ENERGY STAR filing. `additional_model_information`
  clauses with "Same as basic model except model designation" / "X is the same as Y except for model designation" make those strings
  aliases of kind `declared_same_hardware` on the certified model (71 aliases, e.g. QN65S90DAF <- QN65S90DDF, QN65S92DAF). Undeclared
  tokens in the same field are `model_variant` (unverified sibling, alias only). Identical spec tables are NOT corroboration (review 3).
- **Otherwise a proposal link**: `stem_links` with the TVs stem (`category.yaml`) proposes `possible_match` for (a) Samsung site code vs
  ENERGY STAR certified string (`XZA` stripped: QN65S90FAFXZA ~ QN65S90FAF) and (b) LG OLED channel siblings on lg.com (OLED65B5PUA ~
  OLED65B5AUA; `same_source: true` because both come from lg-us-tvs). Proposals are never merges; no policy approves them.
- Not proposed on purpose: Samsung's production letter (`QN65S90FAFXZA` vs `QN42S90FAEXZA`, F vs E: differs between sizes and is a candidate
  panel-source marker), LG QNED/UHD tails (`80AUA` vs `80URA` vs `80UQA` encode model YEAR as well as channel: a stem would pair 2022 with 2023).
- Open (A3): the LG wildcard declarations ("OLED65C4AU* is the same as OLED65C4PU*") are the corroboration for LG channel pairs, but the
  importer cannot match a wildcard row to maker models; today they are skipped. A pattern-to-model relation (`declared_same_hardware`,
  method `energystar-declaration`) would let a policy group them.

## Panel lottery (size-dependent and within a model)
- Across sizes: one line uses different panels by size (Samsung S90 series WOLED at 42/48/83" and QD-OLED at 55/65/77"; LCD lines VA at
  55"+ and IPS/ADS at 43/50"). Modelled as **per-model facts** (panel.display_tech, panel.oled_subtype, panel.lcd_type, panel.backlight,
  refresh.native_hz). The family carries none of them (`inherits: false`); a value is never copied from another size.
- Within one size (same model string, two panel sources): a **revision** (`hw_rev`, e.g. a box/rear-label version code). No official source
  exposes it; `revision_scope: unspecified` on the panel keys keeps a model-level value from leaking onto a revision. Evidence must name
  the version (review, label photo), never be inferred from one unit.
- No US maker page prints the OLED subtype (WOLED vs QD-OLED) or, except TCL, the LCD type: those stay unknown.

## Per-source attribution (conflict-aware)
- Samsung: one spec API call returns every size of a line; a ref's own `modelCode` is picked (absence if absent). A printed size that
  contradicts the size in the model number is unresolved.
- TCL: a page sells all sizes; a spec box is attributed only via a `Model` row equal to the SKU, or a unique size match that agrees with the
  SKU's size and has no Model row naming another SKU. 14 of 83 SKUs have no attributable box: minted from the SKU with no claims.
- LG: one page = one model; UPC = package-level GTIN alias, `modelCode` = `x_lg_material_code`.

## Verified vs unverified
- Verified identifier: printed by the maker's own US page / API, or the ENERGY STAR certified string (regulatory).
- Unverified: retailer titles, retailer MPN fields, review sites. Retail strings are aliases only.
- GTIN: from LG `productIdentifier`, TCL `UPC - US` (not mapped yet) and ENERGY STAR `upc`; package level, never a merge key.
