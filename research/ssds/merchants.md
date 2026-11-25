# SSDs: merchants (US, A2 2026-11-23). Not scraped this round; reasoning + the two official-store facts that matter.
Role: retailer data = aliases, MPN candidates, prices, availability; never primary identity (team rule).
- Manufacturer stores are manufacturer sources: samsung.com/us (price + SKU in Product JSON-LD, adapter emits id.msrp_us as an observation),
  sandisk.com (WD and SanDisk; orderable SKU in the URL `?sku=`), teamgroupinc.com (no store; "Where to Buy").
- Amazon: dominant US channel for SSDs and the worst identity source. Titles are marketing strings, ASIN is not a part number, and
  third-party sellers re-list OEM/refurb stock under the retail title. MPN field often wrong or empty. Bright Data only on coordinator approval.
- Newegg: MPN in item JSON-LD (server HTML), seller marketplace pollutes; better than Amazon for part numbers. Verify robots first.
- B&H: schema.org Product JSON-LD with clean MPN + UPC; tolerant of plain fetch (verify robots before bulk). Strongest UPC->MPN bridge.
- Best Buy: public Products API (free key) gives modelNumber + sku + upc; a Best Buy exclusive sometimes has its own part number (e.g. a
  heatsink bundle) -> package-level identifier with market tag, never merged silently.
- Micro Center / Costco / Walmart / Sam's: channel-exclusive SKUs (Costco multipacks, Walmart "-WM" variants) are package-level, with `market` + retailer.
- PCPartPicker (aggregator): model + capacity + part number + interface, useful sanity cross-check; tier = aggregator.
- Revision evidence is NOT in any merchant feed. Where it can come from (review teardowns, label photos, user reports) is in identity.md.
- Open question for coordinator: Best Buy API key is still the single cheapest bulk UPC/MPN source (same ask as monitors).

## Maker-site access, A2 coverage r2 (2026-11-24; one polite GET each, crawler UA, no retries)
- **Crucial (crucial.com): BLOCKED.** robots.txt itself returns an F5 "Request Rejected" page. Not retried; no workaround.
- **Kingston product pages + /siteindex.xml: BLOCKED** (Cloudflare challenge 403). **Kingston datasheet PDFs (/datasheets/<stem>_us.pdf): reachable**
  (robots allows, 200 PDF). Used by crawler/adapters/kingston_ssd.py with a seed list from web search (no index is reachable). 404 stems: SKC600,
  SKC2500, SFYRD, SKC3000, NV3, SFYRDK, SNV3D. SNV2S / SNVS / SA2000 use an older two-column layout the parser does not read (0 rows, recorded).

## Maker-document access, A2-ssd (2026-11-25; crawler UA, 1 req/s)
- **semiconductor.samsung.com**: robots `Allow: /`; documents page 200 (static links). **download.semiconductor.samsung.com**: no robots.txt (404),
  PDFs 200. Both added to data/source-policy.yaml 2026-11-25.3 (maker, crawl agent). Used by samsung_datasheets.py.
- **www.kingston.com/en/company/press/article/***: 403 (Cloudflare), same as product pages. Blocked, recorded, not retried.
