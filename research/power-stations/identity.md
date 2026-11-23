# Power stations: identity rules (A1+A2, 2026-11-23)

Levels follow spec-profile.yaml: family > model > configuration (colour / unit SKU) > package (bundle). Adapters emit observations; the importer
('model' importer: one page = one model, mfr_model key, colour SKUs and GTINs as aliases) decides entities. Same model on several pages = one
entity with several refs (Jackery Explorer 5000 Plus has 4 pages, BLUETTI Elite 30 V2 has 6 colour pages, Anker f2000 redirects to c2000-gen2).

## Model key per brand
| brand | source | model (`mfr_model`) | configuration aliases (`mfr_sku`) | packages (never aliases) |
|---|---|---|---|---|
| EcoFlow | ecoflow-us-stations | stem of the unit-only variant SKUs, region + colour stripped: EFDELTA3P (EFDELTA3P-US), EFD3M (EFD3M-G-US), ZMR620 (ZMR620-B-US) | unit SKUs | variants whose title/SKU names +, solar, panel, battery, charger, bag, kit, members (D3P-220, DP3+EB) |
| Anker SOLIX | ankersolix-us-stations | 5-char model shared by the unit variants (A1763 from A17631A1); pages without metafields.specs still mint from the A17 unit SKU | unit SKU A17631A1 | B1xxxx / G1xxxx solar-panel variants |
| BLUETTI | bluetti-us-stations | SKU stem before -US-/-UN- (AC180P, EL30V2, PIONEERNA) | colour SKUs (EL30V2-US-PK-ID-SPFUS-00) | MODEL-<n>-<code> SKUs (AC180P-2-62-SPFUS-00), '+' titles |
| Jackery | jackery-us-stations | station name in the spec drop-down heading, colour suffix dropped (Explorer 1000 v2, HomePower 3000); no label model is printed except Explorer 1500 Ultra (JE-1500C -> `mfr_label_model` alias) | unit item numbers 21-0001-000220 / -000432 (Dune White) | '+' variants (60-0820-USB1D1 = + SolarSaga 200W) |
| Goal Zero | goalzero-us-stations | 5-digit item number of the single variant (36300 = Yeti 1500X); must equal the page's 'SKU:' row, else absence | - | Yeti PRO 8000 (PRO 4000 + Tank) page: absence |

## Rules
1. **Colour = same model** (configuration level). Wireless vs standard (EcoFlow RIVER mini vs RIVER mini Wireless) are different models: a page whose
   unit variants carry two stems is an absence, not a merge (also EcoFlow 'DELTA 3 Max Series', 'DELTA 3 Ultra Series', 'TRAIL Series').
2. **A different capacity or inverter rating is a different model** (DELTA 3 / 3 Plus / 3 Classic; AC180 vs AC180P; Yeti 1000X vs Yeti 1000 (LFP)).
3. **Bundles are packages, never the model**: 'Solar Generator', 'Kit', '+', 'Bundle', 'Extra Battery', open-box/refurbished pages are not
   discovered; bundle variants on a station page are listed in `fingerprints.packages` and are neither aliases nor spec sources. The model importer
   has no non-MTM package path, so bundle packages are recorded, not minted (open issue).
4. **Spec blocks must belong to the model**: an EcoFlow 'Specs - <name>' block naming another product, a BLUETTI block splitting values per model
   ('1,152Wh (AC180) / 1,440Wh (AC180P)'), a Goal Zero section naming another Yeti, or a Jackery 230 V block on a US page are absences. Jackery
   blocks of different unit variants are read separately; identical claims dedupe, different ones stay as a conflict.
5. Retail listings (Amazon titles, 'Solar Generator 1000 v2') are aliases only. Market: US storefronts with global model numbers
   (`identity_scope.cross_market_brands: "*"`).
6. Data issue to review: BLUETTI prints GTIN 00193022003033 on both PR100V2 and PR200V2 (identity_conflicts row; GTIN is alias-only).
