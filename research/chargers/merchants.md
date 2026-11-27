# Chargers: merchant / evidence-source notes (A2, 2026-11-24)

Retail listings are aliases only (team rule). Nothing below was scraped; deal titles are handled by scripts/match.py, not by crawling.

| source | status | notes |
|---|---|---|
| Amazon / Best Buy / Walmart / Target | not a source | Listing titles are aliases; the matcher maps them to maker model numbers. |
| ChargerLAB | blocked (robots) | robots.txt disallows ClaudeBot/anthropic-ai (power-banks round); measured PDO tests would be the `measured` tier. |
| USB-IF certified products | agent (r12, see r12 section) | cert.usb_if overlay, exact maker model only; most listings are under OEMs. |
| voltme.com | blocked | products.json 403, not retried (no workarounds). |
| cablematters.com | blocked | robots.txt disallow. |

## r11 (A2-chg, 2026-11-26): maker-site terms audit, new stores, regulators

Provisional dispositions are in data/source-policy.yaml 2026-11-26.9 (`note: provisional r11, licensing review later`).

| host | crawl | why |
|---|---|---|
| www.belkin.com, s3.belkin.com | human_only | terms-of-use.html bars data mining, robots and similar data-gathering tools |
| www.choetech.com, www.hypershop.com, www.aukey.com, plugable.com, www.nekteck.com | human_only | Shopify-template terms bar spiders/crawlers/scrapers |
| satechi.net | human_only | Permitted Use is personal and non-commercial only |
| www.baseus.com | human_only | systematic or automated data collection barred (also affects A2-bat) |
| www.otterbox.com, www.esrtech.com, gonimble.com, www.lention.com | human_only | personal/non-commercial use only, or a no-automation clause |
| kuxiu.com | agent | robots allow /products; terms have no automated-access clause. New adapter kuxiu_chargers (4 models) |
| www.nativeunion.com, www.mophie.com | agent | reproduction clauses only, no automated-access clause |
| www.spigen.com | agent, no adapter | 2 car chargers with prose-only specs; robots.txt prompt text ignored |
| regulations.doe.gov (DOE CCMS) | human_only (blocked) | robots.txt returned 403; not retried, no other fetcher used |
| cacertappliances.energy.ca.gov (CEC MAEDBS) | not a source | terms allow public use with credit, but its battery-charger and UPS tables contain no EPS (external power supply) data |

Anker, INIU, UGREEN, CUKTECH and SHARGE were already human_only (A2-bat, 2026-11-26.7). Values already stored from human_only hosts are still
published under claim/mfr-chargers-structured@4 and are not refetched. That needs a coordinator/owner ruling. AUKEY, Plugable and Nekteck
pages carry specs in images or prose only. Torras and LISEN identify products by Amazon ASIN/FNSKU, which is not a maker model; not built.
Zendure, Scosche, ZAGG and Twelve South have no plain wall chargers. EcoFlow RAPID chargers sit on a human_only host.

## r12 (A2-usbif, 2026-11-26): USB-IF Certified Product List overlay

- Host www.usb.org: crawl agent (source-policy 2026-11-26.11, provisional r12). robots.txt only disallows /core/, /profiles/, /admin/, /search/,
  /user/*; no site terms of use exist (footer has only the Privacy Statement; /terms-use, /terms-of-use, /terms, /legal all 404); privacy
  statement has no automated-access or reuse clause. Free only, no paid, no licence grant (no reuse grant published).
- Source usbif-certified-products: one GET of /vtm-products/v1/all (16,472 rows) stored in raw/usbif-certified-products. Overlay scripts/usbif.py
  (usbif-attach@1) attaches cert.usb_if / _tid / _date / _product_type to existing chargers / power-banks / laptops entities by exact maker
  model (listing company = brand AND part number = our mfr_model / mfr_sku / mtm). Policy claim/usbif-certified-products@1 pending.
- Match rate is very low, by construction: the list names the LISTING company, mostly OEMs (Luxshare, CE Link, Channel Well, Best Buy China,
  Xentris). None of Anker, Belkin, Apple, mophie, Satechi, AUKEY, Choetech, Baseus, INIU, CUKTECH, KUXIU, Sharge, Nitecore, EcoFlow lists
  under its own name. Laptops: the newest Retail > Systems > Notebooks listing is 2017, so no current laptop can match.
- OEM listings whose part number equals one of our models are proposals only (identity_events usbif_proposal oem_listing), e.g.
  Channel Well TID 11361 "30W USB-C PD Cube Wall Charger with PPS" = WCA008 (Belkin's model code). A reviewed OEM -> brand crosswalk would be
  needed to bind those.
