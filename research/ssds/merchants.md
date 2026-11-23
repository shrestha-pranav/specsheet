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
