# A2 discovery: power strips / surge protectors (US) - 2026-11-22

## Decisions
- **Tripp Lite is the best spec-sheet source**: sitemap `tripplite.eaton.com/en_sitemap.xml` (6618 products, ~250 strips/surge) gives SKUs; per-SKU datasheet PDF
  `assets.tripplite.com/product-pdfs/en/<sku>.pdf` has ~60 labelled spec rows (joules, UL1449 let-through, AWG, cord, breaker, UPC). Product pages are not
  usable (Crawl-delay 15, 302 to eaton.com which resets non-browser TLS), so the adapter never touches them.
- **CyberPower is the best structured source and the next adapter**: WP REST `/wp-json/wp/v2/product` (1456 products, pa_joules/pa_outlets-quantity/pa_cord-length/pa_certifications...).
- **APC is blocked** (Akamai 403 on everything incl. sitemap) -> defer or coordinator-approved browser fetch. Panamax/Wemo hosts unreachable.
- Added to `crawler/manufacturers.yaml` (Shopify, verified): `byjasco` (GE + Philips, ~61 strips), `furman` (~45), `austere` (5). anker/belkin/ugreen/baseus already crawled; their strips are in raw/.
- Certification DBs: UL Product iQ 403 anonymous (free account, no bulk, ToS), Intertek ETL hosts unreachable/403. **No crawlable free by-model lookup**; manual spot-check only.

## Adapter + sample
- `crawler/adapters/tripplite.py` (resumable, 1 req/s, pdftotext, spec table -> spec.json). Output `raw/tripplite/`.
- Run: 249 matching SKUs, sampled 70 spread across the SKU range: **70 PDFs ok, 0 missing**, ~38 parsed spec fields/SKU, 1 request/s.
  Includes TLP, ISOBAR, IBAR, SPS, PS, SK, Waber (3SP, 6NX6) families.
- Known wart: parser also captures the Eaton address footer as 3 spurious rows; trailing rows from wrapped labels may merge. Ignore keys "1000 Eaton Boulevard", "Cleveland, OH 44122", "United States".
- Crawler wasn't run for the 3 new Shopify entries (not requested).

## Identity (research/power-strips/identity.md)
Model number is the key; TLP + outlets + cord ft + suffix; CyberPower CSB/CSP digits = outlets+cord; Belkin -08 = cord ft. Cord length / outlet count / joules / HG change the model;
color = variant; multi-pack = package. ASINs are never model numbers.

## Open questions
- Coordinator: approve a browser-grade fetch for APC (and Panamax)? Amazon route for title aliases?
- Best Buy developer API (free key) could give model + specs for merchants layer.
- Tripp Lite US vs Canada/EU SKUs share the catalogue; filter by NEMA input plug in the spec.
- Files: research/power-strips/{manufacturers.yaml,identity.md,merchants.md}.
