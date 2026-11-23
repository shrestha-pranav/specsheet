# Robot vacuums: identity rules (A2, 2026-11-23)

Levels follow spec-profile.yaml: family > model > configuration (colour / pack SKU) > package (GTIN). Adapters emit observations only; scripts/import.py
(importer `model`) mints entities. Key = (brand, normalised `mfr_model`); market is not in the key (category.yaml identity_scope).

## What the makers actually print (US stores, measured on the three built adapters)
| level | Dreame (dreame-us-robovac) | Roborock (roborock-us-robovac) | Narwal (narwal-us-robovac) |
|---|---|---|---|
| family (`series` on the identifier) | letter series: L, X, D, AQUA, MATRIX, GOVAC | QREVO, SAROS, S, Q, QV, QR | FREO, FLOW |
| model (`mfr_model`) | model name in the spec block / title: L40s Ultra | title head: Qrevo Edge S5A; dock variant '... RDS' | title head: Freo Z10 Turbo |
| configuration (`mfr_sku`, alias) | material code per colour 010204AA000742 | RR-QrevoEdgeS5A5-M2 (5 black / 0 white, -M<n> batch) | CP-ZD-A00331-00-00 (+ '-AC01' accessory pack) |
| package (`gtin`) | Shopify variant barcode when present | same | same |

- **No regulatory model code on any of the three US stores.** The label code (FCC grant product code, the CE/UL "Model:" on the rating label) is not
  printed; the marketing model name is the most stable identifier the makers publish, and it is what retailers echo. It is therefore the model key,
  with the material-code SKUs as configuration aliases. A later FCC/label source must attach as an alias (`fcc_id` is `alias_only`), never re-key.
- **'+' vs 'Plus'.** Roborock writes `Q7 Max+`, Dreame writes `D20 Pro Plus`. The model value is canonicalised to `Plus` (`_robovac.plus`, value_raw keeps
  the literal) so `Q7 Max` and `Q7 Max+` (different robots: the '+' has an auto-empty dock) never collapse into one id slug.
- **Grouping = shared SKU.** A store lists one robot several times: "App Only", "Live Only", "Membership", "Group Buy Perks", colour pages, and on
  dreametech.com "X50 Ultra Complete" (shares SKU 010204AA000863 with the X50 Ultra page). `_robovac.group` unions products that share any variant SKU
  or derive the same model name; the plainest page is canonical; all member titles become retail_title aliases, all SKUs configuration aliases.
- **Not models:** refurbished units (a condition of a model; dropped, would be a listing), trade-in and warranty products, SKU-less bundles
  ("L60 Ultra PE + D30 Ultra", "with Accessory Kit"), accessories, stick/wet-dry vacuums (Roborock F25/H60/Dyad/Flexi, Dreame H/R series).
- **Dock variants are models.** Roborock "S8 MaxV Ultra with Refill & Drainage System" is its own SKU (RR-S80MaxVUltraRDS-M1) with different dock
  hardware (plumbed refill/drain): model `S8 MaxV Ultra RDS`, not a colour of `S8 MaxV Ultra`. Same for Saros 10 RDS. "Qrevo 2 Pro Set" has its own
  SKU and stays separate from "Qrevo 2 Pro" (contents differ; unverified which).
- **Suffix letters are different robots, never variants:** Dreame L40s Ultra vs L40s Ultra AE vs CE (13,000 vs 19,000 Pa, different brush and
  sensors per the maker's own comparison), L60 Ultra FE/PE, Roborock Q10 S5 vs X5, Qrevo Curv S5X vs CurvX, Dreame "Gen 2" models.
- **Retail titles are aliases only** and are unreliable: they repeat a suction figure from a different generation and carry colour/bundle words.
- **Cross-brand twins** (MOVA is a Dreame sister brand with the same 010204AA material-code scheme; Yeedi is an Ecovacs brand) are NOT merged: a
  `possible_match` needs a human. No stem links are enabled (features: []).

## Round 2 (2026-11-23, A2)
- **iRobot**: mfr_model = the iRobot model code in the URL / PID (X285020, C975020), the strongest identifier in this category. Colour codes on the same
  slug (X285220 white) are configuration `mfr_sku` aliases with option = colour; UPC = gtin alias; the marketing name is an alias. Robot-only vs
  robot + dock bundles have different codes and are different models (Y314020 vs Y354020/Y351420).
- **ECOVACS**: no regulatory code on the US shop. mfr_model = head of the shop's product name (DEEBOT T80 OMNI), '+' -> PLUS, colour and 'Care'
  (care-plan page) dropped; the shop SKU (OZT80) and UPC are aliases. T30S COMBO / COMBO COMPLETE (robot + handheld) stay separate models.
- **MOVA**: as Dreame (shared material-code scheme 010201AA...): model name, SKUs as aliases; 'Live Only' and refurbished pages are dropped.
- **CSA DCL**: x_dcl_vid_pid alias + certifier_listing alias on the matched US model; the ledger never mints a model.
