# Robot vacuums: merchants & non-manufacturer sources (A2, 2026-11-23)

Retailers are identifier bridges (UPC/ASIN <-> model) and never spec sources here (team rule: retail titles are aliases only). Nothing below was crawled.

| source | status | use | notes |
|---|---|---|---|
| Maker US stores (dreametech.com, us.roborock.com, us.narwal.com) | **adapter** | specs + SKUs | Shopify; products.json + product page; robots allow; 1 req/s |
| us.mova-tech.com, us.eufy.com, us.switch-bot.com, lefant.com | viable (products.json 200) | SKUs only | spec tables client-side or prose; see manufacturers.yaml |
| sharkclean.com | **blocked** | - | robots.txt itself 403 (WAF) to the honest UA; stopped |
| ecovacs.com/us | unstructured | - | no sitemap (404), JS product list, marketing pages |
| irobot.com | viable_unverified | model codes (C975020) | product pages 200; discovery is client-side |
| Amazon | not a source | ASIN alias | retail listings; no product-page scraping; Bright Data not used |
| Best Buy | not probed | UPC/SKU bridge | Products API terms cap caching at 72 h (ARCHITECTURE 0.7); needs a key |
| Home Depot / Target / Walmart | not probed | retailer-exclusive SKUs | robot SKUs with retailer suffixes (Shark RV2620WD vs RV2620WA) would bridge via UPC |
| RTINGS, Vacuum Wars | not probed | measured suction/noise (claim kind measured) | the independent basis; licence/terms unknown |
| CSA Matter DCL | not probed | certification of smart.matter | public REST ledger |
| FCC (fccid.io) | not used | fcc_id alias, label model code | fcc.gov 403, fcc.report Cloudflare (routers round) |

Retailer-exclusive suffixes: Shark and iRobot sell retailer-specific model codes (one robot, different box/accessories). When a retailer source is
added, those codes are configuration-level `mfr_sku` aliases with `parent` = the model, not new models, unless the hardware differs (dock type).
