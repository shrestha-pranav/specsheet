# Monitors: merchants (US, A2 2026-11-22) - not probed this round beyond reasoning; no scraping done
Role: retailer data = aliases, MPN candidates, prices, availability; never primary identity (team rule).
- Best Buy: has a public Products API (key needed, free): model number + SKU + UPC + specs list; strongest US MPN source. Needs key (coordinator).
- Amazon: ASIN + title only; MPN field unreliable; heavy bot defence; use Bright Data only on approval, never bulk.
- Newegg: model/MPN in item JSON-LD (server HTML); mid-friendly; per-seller listings pollute.
- B&H: clean MPN + UPC in schema.org Product JSON-LD, tolerant of plain fetch (verify robots before use). Good for creators/pro monitors.
- Micro Center, Walmart, Costco: Costco/Walmart sell channel-exclusive SKUs (different suffixes, sometimes different panels): capture as package-level identifiers with market tag, never merge into model silently.
- Dell.com / Lenovo.com / HP.com / Samsung.com / LG.com: manufacturer stores, treat as manufacturer sources (pricing = merchant observation).
- PCPartPicker (aggregator): lists model + panel type + part numbers; useful secondary for size/refresh sanity, tier = aggregator.
- Open question for coordinator: Best Buy API key (free) is the single cheapest way to bulk-attach US MPN/UPC to model numbers.

## Maker-site access, A2 coverage r2 (2026-11-24; one polite GET each, crawler UA)
- **MSI (www.msi.com): BLOCKED** (Akamai "Access Denied" 403, robots.txt included). Not retried.
- BenQ US (/en-us/monitor.html) 200, robots allows; Dell US /apd/ monitor pages 200 (3.7 MB, no server-rendered tech-spec block: specs load
  client-side). No adapter built this round for either.
