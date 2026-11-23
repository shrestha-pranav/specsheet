# Power banks: identity rules (A1+A2, 2026-11-23)

Levels follow spec-profile.yaml: family > model > configuration (colour SKU) > package (bundle/GTIN). Adapters emit observations; the importer
('model' importer: one page = one model, mfr_model key, colour SKUs and GTINs as aliases) decides entities.

## Model number per brand (what is printed next to the rated energy on the label)
| brand | source | model (`mfr_model`) | colour/edition SKU (alias, `mfr_sku`) | aliases |
|---|---|---|---|---|
| Anker | anker-us-powerbanks | 5-char model shared by the page's non-bundle variant SKUs: A1695 (A1695H11 black, A1695H41 silver) | variant SKU A1695H11 | title "Anker Laptop Power Bank (25K, 165W ...)", marketing numbers (525/737) |
| Belkin | belkin-us-powerbanks | first 3 letters + 3 digits of the variant SKU = JSON-LD productGroupID minus `P-`: BPB012 | BPB012btBK, BPB012btWH, BPD010bkBK-MV | title "BoostCharge Power Bank 20K" |
| INIU | iniu-us-powerbanks | 'Product Model' in Tech Specs: P63-E1, P50-E1, B41 (fallback: model token in the handle) | Shopify variant SKU | title |
| CUKTECH | cuktech-us-powerbanks | 'Model:' in SPEC: PB200N, P23, PB100P | - | "CUKTECH 15 Power Bank" (number = line, not model) |
| UGREEN | ugreen-us-powerbanks | 'SKU' in Specs = UGREEN's 5-digit item number (25188, 90597A) | Shopify variant SKU (colour) | title; label model (PB205-style) is not on the store |

## Rules
1. **Colour = same model.** Every colour/edition SKU of one model number is an alias (configuration level) of that model, never its own model.
   Anker 'Black Myth Wukong edition' (A110G) has its own model number and stays a separate model (store says so; electrical specs are A110B's,
   but equality is not asserted without evidence).
2. **A different capacity or wattage is a different model even with a near-identical name** (Anker 10K 30W A1688 vs 10K 45W A1638; INIU P50 vs P50-E1).
   INIU suffixes (-E1/-E2/-P1) are regional/generation model numbers printed on the page: kept as distinct models, no merge.
3. **Bundles are never models.** Anker variants whose SKU starts BUNDLE-/COMBO-, `bundle-`/`combo-`/`-2-pack` handles, '(Bundle)' and '+' titles
   (UGREEN, INIU) are dropped at discovery or parse; a page whose non-bundle variants carry two model numbers is an absence.
4. **Belkin BBA0xx vs BPB0xx on one slug** (power-bank-10k-with-integrated-cable-and-display/BBA007 and BPB029): two printed model numbers,
   two models. They may be the same hardware for different channels; that is a `possible_match` for review, not a merge.
5. **One INIU page can describe two models** (P41 and P41-E1 handles both print 'P41'): exact normalised match -> one model entity, two sources.
6. Retail listings (Amazon titles, '26800mAh 4-Port') are aliases only. CPSC recall model strings (when added) are alias evidence keyed to the
   printed model; a recall naming 'A1263' attaches to Anker A1263 only by exact match.
7. Market: all five sources are US storefronts printing global model numbers; `identity_scope.cross_market_brands: "*"` (category.yaml).
