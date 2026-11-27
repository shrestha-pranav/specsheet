# Robot vacuums: merchants & non-manufacturer sources (A2, 2026-11-23)

Retailers are identifier bridges (UPC/ASIN <-> model) and never spec sources here (team rule: retail titles are aliases only). Nothing below was crawled.

| source | status | use | notes |
|---|---|---|---|
| Maker US stores (dreametech.com, us.roborock.com) | **adapter** | specs + SKUs | Shopify; products.json + product page; robots allow; terms re-read r11: no automated-access clause; 1 req/s |
| irobot.com, us.mova.tech (r2) | **adapter** | specs + SKUs/UPC (iRobot: model codes) | SFCC grid + Product-Variation JSON / Shopify + compare-page inputs; terms re-read r11: no automated-access clause |
| ecovacs.com/us, us.narwal.com | **human_only (r11)** | stored values only | terms bar automated collection / page-scrape robots (read 2026-11-26, refs in data/source-policy.yaml); no further agent fetches; stored rows pending coordinator ruling |
| us.eufy.com, us.switch-bot.com, lefant.com, yeedi.com, proscenic.com, wyze.com, tapo.com | **human_only (r11)** | - | terms bar crawling/scraping (eufy robots also 'Disallow: /*.json'); SwitchBot pages have a labelled Specs table: permission request candidate |
| bissell.com | **human_only (r11)** | - | robots.txt 'User-agent: ClaudeBot Disallow: /' |
| sharkclean.com | **blocked** | - | robots.txt itself 403 (WAF) to the honest UA; stopped |
| Amazon | not a source | ASIN alias | retail listings; no product-page scraping; Bright Data not used |
| Best Buy | not probed | UPC/SKU bridge | Products API terms cap caching at 72 h (ARCHITECTURE 0.7); needs a key |
| Home Depot / Target / Walmart | not probed | retailer-exclusive SKUs | robot SKUs with retailer suffixes (Shark RV2620WD vs RV2620WA) would bridge via UPC |
| RTINGS, Vacuum Wars | not probed | measured suction/noise (claim kind measured) | the independent basis; licence/terms unknown |
| CSA Matter DCL | **adapter** (csa_dcl_robovac) | certified smart.matter | public REST ledger; exact-name match to US-store models only |
| FCC (fccid.io) | not used | fcc_id alias, label model code | fcc.gov 403, fcc.report Cloudflare (routers round) |

Retailer-exclusive suffixes: Shark and iRobot sell retailer-specific model codes (one robot, different box/accessories). When a retailer source is
added, those codes are configuration-level `mfr_sku` aliases with `parent` = the model, not new models, unless the hardware differs (dock type).
