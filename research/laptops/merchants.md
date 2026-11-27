# Laptop merchants (US) - aliases/prices only, never identity

Retailers rename configs; use them to harvest the ID in the MPN/model field and the UPC, then resolve against the manufacturer catalogue (identity.md).
- Best Buy: carries retailer-specific SKU numbers + `Model` (MTM / HP product no. / Apple part no.). Official products API exists (key required); best US coverage.
- Amazon: ASIN + `Item model number`; titles noisy, third-party configs (RAM/SSD swaps) common; scrape-restricted, treat as alias source only.
- Costco / Walmart / Sam's: exclusive configs, often model-code-only in the title (Lenovo `82xx...`, HP `15-fd...`).
- Newegg, B&H, Micro Center: show manufacturer part number prominently (good for exact match).
- Manufacturer stores (Lenovo.com US, HP.com, Dell.com, Apple.com/shop): configurators; prices/configs but Akamai-protected (Lenovo, HP, Dell).
- Not probed this round (budget: no Bright Data); ranked next: Best Buy, Newegg, B&H.

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
