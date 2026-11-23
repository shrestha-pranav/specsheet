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
