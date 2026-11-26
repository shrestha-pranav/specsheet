# Power strips: merchants + certification databases (A2, probed 2026-11-22)

## Merchants (aliases only; identity stays manufacturer model number)
- Amazon: dp pages return 404/captcha to curl, robots restrictive. Use for title/price aliases and "Item model number" only,
  via coordinator-approved route (user's own view per memory aliexpress-pricing note is authoritative for prices).
- Home Depot / Lowe's / Best Buy / Walmart: not probed (no cheap API); Best Buy has a free developer products API (key required) with modelNumber + specs - worth registering.
- Manufacturer storefronts (Shopify products.json, WP REST) carry MSRP + UPC (variant barcode); UPC (Tripp Lite datasheet "UPC Code") is the best cross-merchant join key after model number.

## Certification databases
- UL Product iQ (productiq.ulprospector.com / iq.ulprospector.com): 403 anonymous to curl, free account unlocks category search
  (UL 1449 TVSS, UL 1363 relocatable power taps) with file number + model lists; no bulk export, ToS forbids scraping. Treat as manual verification, not crawl source.
- UL Online Certifications Directory: same backend, same gating. Not tested logged in (no credentials).
- Intertek ETL: ccnb.intertek.com / whereistheetlmark.com / etlwhereverywhere hosts did not respond; intertekinform.com 403. No free per-model public lookup confirmed.
- Eaton/Tripp Lite datasheets themselves print "UL1449 Let Through Rating  400V - UL Verified" and "Conforms to UL 1449 3rd Edition", i.e. vendor-asserted; certificate lookup would verify.
- ENERGY STAR product finder: data.energystar.gov (Socrata) is public JSON and has "Smart Home Energy Management"/advanced power strips; unprobed beyond reachability (400 on root, API exists).
Verdict: no free by-model public certification lookup that is crawlable; use UL Product iQ manually for spot checks.

## r7 surge brand check (A2-pb, 2026-11-26; revised after coordinator ruling the same night)
- Belkin (www.belkin.com, crawl agent, crawl.py v0 store raw/belkin fetched 2026-11-22): PUBLISHED under pending
  claim/mfr-strips-belkin-printed@1, printed keys only: type.ul1449_listed (9), surge.joules (54), outlets.count (53) from crawlpy-strips@1 and
  surge.clamping_v (17) from the supplement crawlpy-strips-belkin@1 (Technical Specifications cell, as printed; mode split -> highest mode).
  A bare 'Clamping Voltage 330V' is NOT the UL 1449 VPR: no Belkin page says VPR, so no surge.vpr_* is published for Belkin.
  Skipped: '340V(@50A)' / '340(@ 100A)' (at a test current), 'Clamping Voltage UL1449 1.2 KV' (kV, ambiguous). crawlpy_strips.py is untouched
  (rel/source-stated-hierarchy@10 pins it for Belkin page variants).
- APC / Schneider (www.apc.com -> www.se.com): robots User-agent * path disallows only; terms (2014-09-29) have no automated-access clause, so
  crawl agent (source-policy 2026-11-26.1), with a to_clear on the reproduction and no-hyperlink clauses. No adapter: SurgeArrest product URLs
  redirect to /us/en/all-products and the US product sitemaps (google-product-sitemapindex-US-en.xml) list no SurgeArrest strips.
- Eaton (www.eaton.com): robots.txt answers 403 Akamai Access Denied to our UA, so crawl human_only, evidence blocked. Tripp Lite (Eaton's US
  surge line) stays covered through tripplite.eaton.com sitemap + assets.tripplite.com.
- CyberPower: already covered.
