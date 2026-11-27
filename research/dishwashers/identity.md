# dishwashers identity (A2-appl r11). Rules: research/dishwashers/spec-profile.yaml identity + A1 report 2026-11-26.
- Key: (canonical brand, normalised model string) via importer 'model'. Brand folding (Cafe/Profile/Monogram -> ge, Gallery -> frigidaire, ...)
  is in category.yaml brand_aliases; multi-brand filing cells are not folded.
- ES pattern rows (`*`, `#`, trailing R/L, trailing lowercase xxx, '(x = ...)' notes) -> key scheme x_energystar_model_pattern: never merges
  with a concrete mfr_model, never expanded. UPCs on a pattern row are covered_upc aliases only.
- A model_number cell listing several strings (',' / ';') names each; no UPC is attributed from such a row.
- Coverage edge concrete -> pattern (covered_by_certification, extra.certifications): es-pattern:listed (additional_model_information names it)
  or es-pattern:unique-match (whole string, * = [A-Z0-9], # = digit, R/L = R|L, exactly one pattern) are approvable;
  es-pattern:ambiguous and es-pattern:undocumented-token stay proposals. No claim transfers over the edge (escover@1).
- Re-filings (several pd_id for one string): latest date wins for the date; any disagreeing field is unresolved (unknown), never picked.
