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

## A2 coverage r3 (2026-11-24)
- BenQ US: adapter `benq_monitors@1` (benq-us-monitors), /en-us/sitemap.xml -> 136 /monitor/<line>/<model>/spec.html (accessory/software lines
  dropped), server-rendered name/detail rows. flk.pwm from "Flicker-free Technology: Yes" only; USB-C PD from the Power Delivery row or upstream port label.
- Dell US: still no adapter. /apd/ monitor pages load the tech-spec block client-side and the product sitemap carries no monitor URLs; not retried.

## Lenovo.com monitor pages, A2 preset fill r2 (2026-11-24; crawler UA, 1 req/s, 13 GETs)
- robots.txt allows /us/en/p/; the US sitemap (sitemap-auto/089-intsitemap-us-en.xml) lists 64 monitor product pages; product pages answer
  200 with the spec table server-rendered as JSON (`organizedSpecs` headline/text rows). **No flicker statement in it**: the only related row
  is "Eye Caring: Yes" (11 of 11 pages sampled, gaming/home/office), which does not say flicker-free or name a TUV flicker certificate, so
  nothing is read and no adapter was built. Lenovo `flk.pwm` stays PSREF-only (certification cell naming TUV Rheinland Flicker Free).

## A2 coverage r4 (2026-11-25; crawler UA, 1 req/s)
- **Notebookcheck (notebookcheck.net, measurement, crawl agent): discovery BLOCKED, 0 seeds.** robots.txt (`*`) disallows only /nbcbattery/
  and /cdn-cgi/, but the sitemap (`/?type=102`) and every query-string listing (`index.php?...tagArray[]=92` = the Monitor tag; the page's
  own XHR goes to dev1.notebook-check.com, an unregistered host, not used) answer a Cloudflare challenge (403). Not retried. Plain `.html`
  pages answer 200 (Contact, Reviews.55.0.html: ~100 newest reviews, 1 monitor = KTC H27D9, not carried). Site search is Google CSE
  (search engine, not used). Three web searches for the in-scope Lenovo/LG/BenQ gap models found launch news only, no review naming an
  exact carried model. notebookcheck_reviews@2 stays unregistered with SEEDS empty.
- **Lenovo user guides (download.lenovo.com): BLOCKED by robots.txt.** robots is an allow-list ending `Disallow: /`; monitor guides live under
  /consumer/monitor/ (found by web search, e.g. p27h_30_user_guide_en.pdf), which no Allow line covers. One GET was made before the full
  robots file was read (P27h-30 guide); it carried only "Low Blue Light ... TÜV Rheinland Low Blue Light" and the CRT boilerplate, so even
  that gave nothing. Not fetched again. The allowed /pccbbs/options/ path holds only legacy (IBM-era) guides. support.lenovo.com is not in
  data/source-policy.yaml, so its guide pages were not read.
