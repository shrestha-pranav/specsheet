# freezers identity (A2-appl2 r12). Rules: research/freezers/spec-profile.yaml identity + research/refrigerators (A1 r11).
- Key: (canonical brand, normalised model string) via importer 'model'. Brand folding (GE Profile / Cafe / Monogram -> ge, LG Signature -> lg,
  Danby Designer -> danby, ...) is in category.yaml brand_aliases; multi-brand filing cells are not folded.
- ES pattern rows (`*`, `#`, trailing R/L, trailing lowercase xxx, '(x = ...)' notes) -> key scheme x_energystar_model_pattern: never merge
  with a concrete mfr_model, never expanded. UPCs on a pattern row are covered_upc aliases only.
- Coverage edges concrete -> pattern (escover@1) are built but stay PROPOSALS: no relation policy names energystar_siblings@1, because the
  8t9c-g3tn metadata documents '*' as a LETTER while A1's matcher reads it as [A-Z0-9] (ruling requested).
- Re-filings (several pd_id for one string): latest date wins for the date; any disagreeing field is unresolved (unknown), never picked.
