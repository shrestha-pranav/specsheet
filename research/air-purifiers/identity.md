# Air purifiers: identity rules (A1+A2, 2026-11-23)

Levels (spec-profile.yaml): family (line, browse only) > model (manufacturer model number) > package (GTIN). Adapters emit observations;
the importer (`model` importer, exact normalised key = brand + upper-cased model string without spaces) decides entities. Nothing merges by
stem, by spec match, or by a shared certification.

## What a "model" is
- The maker's model number as printed by the maker's US page, its ENERGY STAR filing or its CARB listing. `value_raw` keeps the literal.
- Colour / channel / market tails are part of the string: Coway `AP-1512N(W)` vs `AP-1512N(BG)`, `AP-1125G_WT`; Levoit `LAP-C401S-WUSR` vs
  `LAP-C401S-KUSR`. Each is its own model unless the maker declares identity (below). Stem matches (category.yaml `stem`) only PROPOSE
  `possible_match` (193 proposals in the first import), never merge.
- Levoit prints two kinds of model string: label codes (`LAP-C601S-WUS`, on 8 levoit.com pages) and marketing models (`Core 400S`,
  `CORE 200S`, `Core 300`). ENERGY STAR files both kinds as separate records (`Core 400S` and `LAP-C401S-WUSR` are two pd_ids). They stay
  separate entities: no Levoit source states which label code a marketing model is. r8: reviewed pairs live in `data/decisions/air-purifier-crosswalks.yaml` (only when one page prints both strings; none today, 4 proposals = possible_match).
- Pages without a model row give no entity (9 Levoit pages print no Model row; Winix 5530 prints no Model Name). The URL / title is never
  promoted to a model number.

## Certifier rows
- ENERGY STAR `model_number` with `*` or `#` (documented: * = letter, # = digit) is a wildcard family: never a product, skipped by the
  importer (13). No wildcard is expanded into the CARB or maker strings it might cover, so no certification transfers through a pattern.
- A `model_number` cell listing several exact strings (`Airmega 350(W);Airmega 350(BG)`) names each one: one model per string, each gets
  the record's facts. Its UPCs are not attached (cannot be attributed to one string). Cells with no plausible model (`W`, `B`, `Kilo`) give
  nothing (18 cells).
- ENERGY STAR rows of one (brand, model) under several pd_ids are one observation; a field the rows disagree on is unresolved (both values in
  raw), never one picked.
- `additional_model_information`: a token is `declared_same_hardware` only inside a clause with the partner's own same-hardware statement
  ("is same as model X, except model number", "identical except model number/name", "same as X, except for color"); "identical in
  performance ... only difference is ..." (Winix C710/C610) is NOT. Everything else is `model_variant` (unverified alias). Declared aliases are
  aliases on the certified model; they are not merged with a separate CARB entity of the same string. r8 rule (scripts/xwalk.py): such an
  alias entity gets a `same_hardware_as` edge to the certified base with the ES evidence; over an approved edge only the dated
  eff.energy_star transfers (3 today: Blueair 4312112000, 1831024000, Sharp SAP5682SAW). Ids never merge.
- CARB: one ref per (brand, model) exact string. CARB facts reach an ENERGY STAR / maker model only through that exact string (95 refs were
  admitted purely as exact peers). CARB-only models are minted only for 23 major brands with a certification dated 2019 or later.

## Brands
- One owner's spellings fold (crawler/adapters/_airpurifier.py BRAND_ALIASES): Coway / Coway Airmega / AIRMEGA; Honeywell / "Honeywell(TM) by
  Kaz" (Kaz licence); Dreo / Dreo Home; Blueair / Blueair AB; Medify Air spellings; GoveeLife -> Govee.
- Relabel brands that file one hardware under several brand names (AROEVE / BREEZOME / KLOUDIC / REEMKIZZ `MK01A`, Midea / PELONIS /
  Toshiba `CAF-A40US(H)`) are NOT folded: different brand = different model entity. Their shared UPCs show up as gtin identity conflicts
  (18) for review, which is the correct outcome.
