# Monitors: identity rules (A2, 2026-11-22)

Levels follow spec-profile.yaml: family > model > revision > package. Adapters only emit observations (identifiers
with scheme, package_level, market); the matcher decides entities. Rules below are what the matcher/importer should apply.

## What a "model" is
- model = manufacturer model number INCLUDING market suffix as published (27GR95QE-B, LS27DG602SNXZA, PG27AQDM, Q27G3XMN/BK).
  Normalise only by upper-case + strip spaces for matching; keep `value_raw` verbatim.
- Region/colour/channel suffixes are aliases of one `model` when specs agree, but stay separate identifiers with `market`:
  LG `-B` US vs `-B.AUS`/none; Samsung `XZA` US vs `/EN`,`/ZA`; HP `#ABA` US; AOC `/BK` `/WS` colour; ViewSonic `-MHD`
  suffix = port/speaker set (do not collapse); BenQ `9H.xxxxx.xxx` = package (mfr_sku).
- DisplayHDR "Family Models" and Energy Star `additional_model_information` are maker-declared sibling lists: treat as
  alias candidates (kind=model_variant), tier = verified-by-maker, still require spec agreement before merging.
- Lenovo: PSREF product key (Legion_27_10_Monitor / ThinkVision_P27h_30) = model; MTM (68C5GAC4AE, US = suffix `US`) = package.
  EAN on the MTM row = gtin alias for that package.
- Energy Star `model_number` is the maker's certified string: it often drops regional suffixes (Dell `E2026Hf` includes a factory
  suffix, so `E2026H` is the retail name). It matches `mfr_model` loosely: match on stripped-suffix prefix only as `candidate`.

## Revision (silent hardware change under one model number)
- Evidence that creates a revision: rear label REV, EDID product ID, panel part number/vendor differing between reviews or
  FCC photos, MSI/Acer generation suffix (E2, V5; those are model suffixes, not hidden revisions), Dell A0x on label.
- A revision is never inferred from a single retailer listing or a review's one-off measurement; the claim is stored on the
  model with `conditions`/locator `hw_rev` when known, and listed under alternatives rather than overwritten.
- Official catalogue sources (PSREF, Energy Star, datasheets) are model/package-level; none expose revision. Revision data is
  only reachable from reviews, FCC filings, or user submissions: out of scope for adapters in this round.

## Verified vs unverified
- verified identifier: appears verbatim in a manufacturer-owned source (PSREF, maker product page/datasheet, DisplayHDR list
  entry, ES certification). Energy Star = regulatory-verified model string, not orderable.
- unverified: retailer title/MPN field, aggregator, review site. Retail strings are aliases (kind=listing_title); an MPN
  printed by a retailer is `mfr_model` candidate only, until a maker source shows it.
- GTIN/UPC: official only from PSREF EAN column and ES `upc` (Dell rows). Retailer UPCs are candidate aliases.

## Traps seen in the data
- Marketed 27" vs viewable 26.5"; ES `screen_size_inches` is viewable-ish; keep gen.size_class and gen.viewable_diag apart.
- Lenovo `Color Depth: 8-bit (6-bit+FRC)`: the parenthetical is the real panel; adapter claims 6-bit+FRC, raw preserved.
- Energy Star signage and "Monitor" rows share the dataset; only `display_type='Monitor'` is used; TVs-as-monitors excluded.
- Same ES model re-certified several times (rows differ in date only): adapter takes latest row, records `cert_rows`.

## Cross-source model-string mapping (round 2, measured 2026-11-23 over the parsed raw/ stores)
Matching key = `stem(model)`: upper-case; cut everything from the first `/` or `#` (AOC `/BK`, HP `#ABA`, Samsung `/ZA`);
drop one trailing `-X`/`-XX`/`-X.YYY` market-colour suffix (LG `-B -W -C -P`, ASUS `-P -J -G -R -W -E`, BenQ `-B -L -T`);
then strip every non-alphanumeric. Never strip digits or inner letters. Stem match = `candidate` link, exact normalised = `verified`
only when both strings come from a maker/regulatory source. Do not stem across brands.
- Energy Star `model_number` vs maker site, verified examples: ES `24MP750C` = LG US `24MP750C-B`; ES `29WQ600` = `29WQ600-W`; ES `28MQ750`
  = `28MQ750-C`; ES ASUS `VA279QGSE-R` = ASUS US `VA279QGSE`; ES `VY249HF-J` = `VY249HF-W`; ES BenQ `EW2790U-L` = DisplayHDR `EW2790U`.
  Measured overlap: ES-LG vs LG site 26 stem / 0 exact (ES lists mostly older/regional strings); ES-ASUS vs ASUS site 108 exact + 9 more by stem.
- DisplayHDR vs maker site: brand token is `LGE` (not LG); `Family Models:` already lists the regional suffixes. DH-LGE vs LG US = 4 exact, 78 by stem
  (`27GP95R` = `27GP95R-B`, `34GX90SB` = `34GX90SB-W`); DH-ASUS vs ASUS US = 86 exact; DH vs ES (ASUS) = 69 exact + 43 stem.
- Energy Star artefacts: (a) wildcard families (`S24A40*###  (*=0-9, #=A-Z, blank)`, `17MT70*-*.******`) are patterns, stored as alias kind
  `model_pattern`, key = text before the first space: never link to a product by stem; (b) Dell lower-case tail (`E2026Hf`, `E2225HMt`)
  = factory/TCO variant letters, `model_name` (`E2026H`) is the retail name, link via model_name; (c) one cell may hold `A, B, C`
  (ASUS `BE24E, BE24EQSB, BE24EQSB-P`): first token = model, rest = model_variant aliases.
- DisplayHDR cell `ASUS ROG Swift PG32UQX` -> model = last model-like token (`PG32UQX`, letter+digit, <=24 chars); brand = first token. Laptop rows
  (`Lenovo Yoga Pro 7 14ASP10`) share the table; resolution assigns category. Cells with no model token fall back to a <=32 char slug
  (entity ids are length-limited: never use titles as the key).
- ASUS: US page model (`VA279HG3Y`) is bare; orderable `90LM...` part numbers sit on ROG pages (mfr_sku). LG: `sku` (`22MP410-B`) is the US model
  with suffix; `modelCode` (`MD08001830`) is LG's material code, kept as `x_lg_material_code`.
