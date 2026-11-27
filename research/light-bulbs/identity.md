# light-bulbs identity (A2-bulb r12, 2026-11-26)
- Identity = brand + maker model number (Signify 12NC for Philips/Hue/WiZ, GE 8-digit product code, Feit OM60/927CA/AG). Retail titles are aliases.
- One bulb = one model. Pack SKUs (GE -2P/-4P, Philips 12NC sub-codes) listed in ENERGY STAR additional_model_information are model_variant
  aliases, never entities. If a source only prints a pack SKU, the pack is the identity with gen.pack_count (none this round).
- Regional variants are different models: E26/120 V (US) vs E27/230 V (EU) never merge. Canada-only ENERGY STAR rows are dropped.
- ENERGY STAR wildcard rows (Globe 34208*, Nanoleaf NL67E1##: 17 refs) are not entities this round (no lamp pattern ruling); counted as skipped.
- Brand folding: "Philips Hue" + "PHILIPS" + "Phillips" -> philips (12NCs unique across Signify; same key as A2-home smart-home, identity
  coordination only, no shared adapter); "GE Lighting" -> ge; "LEDVANCE LLC" -> sylvania; "Feit Electroc" -> feit_electric. WiZ stays wiz.
- Re-filings of one model string (13% of US refs have 2-7 filings, e.g. per CCT or per pack): any field on which they disagree is unknown.
  No US re-filing disagreed on lumens on 2026-11-26.
