# Data licensing audit for paid tiers (2026-11-24)

Not legal advice; review by counsel before enabling paid mode (it ships disabled, PAID_ENABLED=false).
Method: WebFetch/WebSearch only, robots.txt respected, no workarounds. Several legal pages returned 403/404 to
automated fetch; those are recorded as BLOCKED/unverified, not guessed. Evidence levels: [fetched] read the page,
[search] search-result snippet only, [none] no terms found.

## Frame
- Individual spec values (a wattage, a port count) are facts; US copyright does not cover facts (Feist v. Rural, 499 U.S. 340 (1991)).
  Selection/arrangement, marketing prose, images, logos and trademarks are protected.
- The risk for a reseller is mostly contract (site ToS "no copying/redistribution", "no automated access") and database/trademark
  rules outside the US, not copyright in the numbers. A ToS that forbids redistribution is a real exposure for a PAID product
  even if the free one tolerates it. Policy here: if redistribution terms are unclear or restrictive, exclude from paid tiers.
- Mechanism: `api-worker/licensing-exclusions.json` (domains) applied by `scripts/build_r2.py` removes excluded sources, and every
  spec attested only by them, from the paid artifacts (index, records, bulk). Free GH Pages data is unchanged (separate decision).
  Records also drop `media` (images are never licensed) and demo data.

## Per source (record counts = sources cited in docs/api/v1 on 2026-11-23)
| Source (cited sources) | Finding | Verdict for paid tiers |
|---|---|---|
| ENERGY STAR, data.energystar.gov (1845) | EPA publishes product data sets as Excel/XML/CSV and an API, updated daily, explicitly for download [search] https://www.energystar.gov/productfinder/advanced . data.gov lists the Model Index under the EPA data license (edg.epa.gov) with public access [search] https://catalog.data.gov/dataset/energy-star-model-index ; the cooking-products record states no license info [search]. US federal works are public domain (17 U.S.C. 105). The EPA data-license page and the ENERGY STAR legal page 404'd, so exact wording is unverified. "ENERGY STAR" is a registered EPA trademark: do not use the mark/logo as branding, only as a factual "certified" attribute. | ALLOW (facts + attribution "Source: U.S. EPA ENERGY STAR"). TODO confirm data.energystar.gov/developers terms. |
| CARB, ww2.arb.ca.gov (1102) | Public certified air cleaner list https://ww2.arb.ca.gov/list-carb-certified-air-cleaning-devices ; page shows no reuse/copyright terms in the fetched portion (page truncated, footer not read) [fetched, partial]. Disclaimer: certification is not an effectiveness or safety endorsement. State government public records; California's site-wide Conditions of Use not retrieved. | ALLOW with attribution and the disclaimer, provisionally. Email aircleaners@arb.ca.gov or read the CARB site conditions to close. |
| DisplayHDR / VESA, displayhdr.org (1828) | Footer "(c) VESA 2026. All rights reserved"; site says reuse of content incl. the certified products list should carry attribution [fetched] https://displayhdr.org/ . Dedicated terms-of-use URL guessed 404. Logo use requires a signed VESA trademark license https://vesa.org/about-displayhdr/ [search]. Status of the product list as reusable data: unclear. | EXCLUDE from paid until VESA permission (domain in exclusion list). Never show the DisplayHDR logo. Fallback: manufacturers' own spec pages that state the tier. |
| CSA DCL (Matter), on.dcl.csa-iot.org (28) | DCL is a public permissioned ledger; anyone can read, writes restricted [search] https://csa-iot.org/certification/distributed-compliance-ledger/ ; code is open on GitHub (zigbee-alliance/distributed-compliance-ledger). No data license found. CSA site terms [fetched] https://csa-iot.org/terms-of-use/ : no material may be "copied, reproduced, republished ... or distributed" without written consent; internal non-commercial use only; they do not mention the DCL specifically. | EXCLUDE from paid (unclear; restrictive site terms). Ask CSA whether ledger data is open. |
| Lenovo PSREF, psref.lenovo.com (3213) | psref and lenovo.com legal pages returned 403 to automated fetch: BLOCKED, not worked around. Search snippets: US terms say site content is copyrighted and copying or redistribution needs prior written permission https://www.lenovo.com/us/en/legal/ ; PSREF disclaimer: Lenovo may change specs without notice https://psrefstuff.lenovo.com/book/ [search]. | EXCLUDE from paid (restrictive, unverified). This removes most laptop specs from the paid tier (laptops bulk is ~160 KB vs 35 MB free); the single biggest commercial trade-off. Ask Lenovo, or re-source from retail-agnostic regulator data. |
| Maker sites (ASUS 643, LG 1414, TP-Link 596, SanDisk 417, TeamGroup 348, Samsung 323, CyberPower 290, Tripp Lite 249, ROG 210, EcoFlow 135, UGREEN 83, Vizio 79, others) | ToS pages NOT fetched in this pass [none]. Typical retail ToS forbid copying and automated access; spec numbers themselves are facts. We read product pages respecting robots.txt (crawler brief). | KEEP provisionally as facts-only with source links (no prose, no images); list the ToS check as an open item per brand before launch. Add any brand to the exclusion file on a takedown or adverse ToS. |
| Retail, aggregators, reviews (amazon, bhphoto, slickdeals, notebookcheck, techradar, androidauthority, gizmochina, chargerlab, others; ~60 total, mostly gan-chargers) | Third-party editorial/retail content with restrictive ToS; low-tier evidence. | EXCLUDE from paid (listed in the file). Manufacturer-first values remain. |

## Other obligations before enabling paid mode
- Attribution line per record (sources[] already included in every paid response); trademark disclaimer; takedown contact.
- Keep source URLs and retrieval dates (provenance is a feature and a defense).
- Decide whether the free tier should apply the same exclusions (consistency, and a free redistributor is the same ToS exposure).
- Terms of service/privacy page for the API, sales-tax question (research/monetization.md), counsel review.
