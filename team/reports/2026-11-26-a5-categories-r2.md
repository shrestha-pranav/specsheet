# A5 report: new-category research r2 (2026-11-26)
Brief: coord-2026-11-26-r11-categories-a5. Output: research/category-survey-r2.md. No code, no data/ edits, no Bright Data.

## Decisions / recommendation
- **Start major appliances next round.** ~8,950 records from ENERGY STAR Socrata (fridge 4,942, dishwasher 753, dryer 706,
  freezer 680, room AC 608, dehumidifier 576, washer 421, cooking 265), public domain and already paid+grant ALLOW; adapters
  only (one parameterised energystar_appliances.py + UPC crosswalk + bosch_us.py for dBA). Identity trap: `**` wildcard model numbers.
- #2 smart-home: CSA DCL 5,640 Matter models (agent, free only) + Zigbee2MQTT 5,463 devices via GitHub (converters MIT).
- #3 USB-IF overlay: www.usb.org's own product-search JSON = 16,472 certified products in one GET (4,078 cables, 718
  bricks/banks); best as a cert attestation on chargers/power banks; cables mostly OEM listings (weak retail identity).
- Runner-ups: UPS (ES 923, extends power-strips), printers (ES 2,847, but cost/page only reachable at Brother).

## Needs coordinator action
- **www.lg.com/us/terms bars scrapers/crawlers/data mining** ("manual or automated ... to scrape or download data"), yet
  www.lg.com is crawl agent with ~1,414 cited values. Same standard as the Samsung/Apple ruling -> human_only? Not edited.
- Water filters are unreachable for agents: NSF terms page is Cloudflare-blocked (snippet: data mining needs permission),
  WQA bars AI/scraping, Brita/PUR/ZeroWater terms bar bots or limit to personal use. Suggest emailing NSF (info@nsf.org).
- Headphones and tires dropped: Sony/JBL/nhtsa.gov blocked, Bose bars robots, Sennheiser reserves TDM; UTQG on DOT portal is a link stub to nhtsa.gov.
- New human_only candidates for source-policy if those makers are ever added: GE Appliances, Epson, Aqara, Bose, Sennheiser, Brita/Clorox, PUR, ZeroWater, WQA.

## Shared-file changes
None. New files: research/category-survey-r2.md, this report. Scratch probes in /tmp/a5probe (outside repo).
