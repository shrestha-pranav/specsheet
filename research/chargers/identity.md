# Chargers: identity rules (A1+A2, 2026-11-24)

Levels follow spec-profile.yaml: family > model > configuration (colour/region SKU) > package (bundle, N-pack, GTIN). Adapters emit one observation
per maker page; the 'model' importer keys it on (brand, normalised mfr_model). Retail titles, marketing numbers and marketing names are aliases.

## Model number per brand
| brand | source | model (`mfr_model`) | aliases (`mfr_sku`, names) |
|---|---|---|---|
| Anker | anker-us-chargers | 5-char stem shared by the page's non-bundle variant SKUs (A2688141 -> A2688; B120F) | variant SKUs; titles carry marketing numbers + names ("Anker 735 Charger (Nano II 65W)") |
| Belkin | belkin-us-chargers | productGroupID / 3 letters + 3 digits (WCH010, BBC013, CCA004, INC016, ENA007) | colour SKUs WCH010dqBK from the US variant sitemap |
| UGREEN | ugreen-us-chargers | the single 5-digit item number printed as SKU (15202, 35538A); a page with several item numbers mints nothing | label model (CD-codes) only when printed |
| Satechi | satechi-us-chargers | ST- SKU minus region (-US/-EU/-UK/-AU/-KR) and, when all SKUs differ only in the last letter, minus the colour letter | region SKUs |
| AUKEY / CHOETECH | aukey-/choetech-us-chargers | the one model code in the maker's own title (PA-C4, CC-P4, PD6011); 0 or 2+ codes = absence | - |
| HyperJuice | hyper-us-chargers | HJ + 4 digits (HJ1402 from HJ1402NA / HJ1202BUNA) | variant SKUs |
| Native Union | nativeunion-us-chargers | FAST- SKU minus colour and region (FAST-PD67 from FAST-PD67-BLK-INT; FAST-PD67-2CA stays its own model) | |
| INIU | iniu-us-chargers | D01- SKU stem (A11-E1, I710); N-pack SKUs (-2P-) and bare numbers are not stems | |
| CUKTECH | cuktech-us-chargers | Model row (AD653N); a model ending in EU/UK is not US and mints nothing | |
| mophie | mophie-us-chargers | the page's single 9-digit part number (no model printed) | |
| Plugable / Nekteck | plugable-/nekteck-us-chargers | the SKU (Plugable keeps the colour letter: PS-30C1B / PS-30C1W are separate maker models); Nekteck minus -SPNK | |
| SHARGE | sharge-us-chargers | no Product Model row on charger pages -> nothing minted | |

## Rules
1. Colour/region SKUs of one model are aliases; a different wattage or port layout is a different model even if the name barely changes
   (Anker A2663 "715 Nano II 65W" 1-port vs A2667 "735 Nano II 65W" 3-port).
2. A page that names several models, an N-pack, a bundle ('+', 'Bundle', '2-Pack'), a wireless/MagSafe/Qi or 2/3-in-1 set mints nothing.
   A charger page sold "with USB-C cable" is the charger model (Anker B2692/B2679/B2697).
3. Anker relabels: A- and B-prefixed SKUs (A2692/B2692, A121A/B121A) are NOT asserted equal; the page's own SKU stem is the model. Two pages
   for the same marketing name stay two models (A2735 / B2735 "323 Car Charger") until a label proves equivalence.
4. Channel twins stay separate: Belkin BBC013 (Amazon channel) vs WCH013, BBC015 vs WCH011, BBC035 vs WCH020.
5. v0 gan-chargers migration (2026-11-24): a v0 id is kept when the v1 model mints the same slug (45) or, for Anker, when the v1 model number is in
   the v0 record's model list and the v0 id has the same model-number shape (5 pre-bound in data/_ids/registry.jsonl: anker-a2692, -a121a,
   -a121b, -a120f, -a2697). Otherwise data/_ids/tombstones.jsonl redirects it (19, incl. 3 split into channel twins) or retires it with a reason
   (81: Baseus, Spigen, EcoFlow not built; models gone from the US stores). `category:gan-chargers` -> `chargers` redirects the category route.
