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

## Dell US monitors, A2-mon r5 scout (2026-11-25; crawler UA, 1 req/s, 8 GETs)
- **Crawlable; adapter not built this round (time).** robots.txt (`*`) allows `/en-us/shop/monitors/apd/...` (only `*/apd/*/quickview$`,
  `*/api/`, `/*/cart/*`, `*/pdr/` and refinement-combo listing URLs are disallowed); no AI-agent block. www.dell.com is in
  data/source-policy.yaml (maker, categories laptops + monitors); terms per the i.dell.com entry (no automated-access clause).
- Discovery: the listing page `/en-us/shop/computer-monitors/ar/all-monitors` is server-rendered and links `/en-us/shop/monitors/apd/<slug>/<model>/-`
  (first page: 11 unique monitors; pagination not probed). The mpn-sitemap pages list third-party SNP items, the product sitemap has no monitors.
- **Change since r2/r3:** the /apd/ page (SE2726H, 1.6 MB) now server-renders the full Tech Specs block: `div.spec__child__heading` groups with
  `div.spec__item > div.spec__item__title` label + value text ('Operating Power Consumption 17 W', 'HDMI Version 1.4', 'Total Number of HDMI
  Ports 2'), plus a hero key-spec strip ('Resolution / Refresh Rate: 1920 x 1080 at 144Hz') and schema.org PropertyValue feature copy.
- Flicker: SE2726H prints no flicker row (only 'TÜV-certified eye comfort' / '3-star eye comfort' copy), so flk.pwm will come only from an explicit
  row where one exists. Next round: dell_monitors adapter (model = the URL's model code, e.g. se2726h), keys flk.pwm/usb.*/res.*, new pending policy.

## Dell US monitors, A2-dell r6 (2026-11-25; crawler UA, 1 req/s, ~105 GETs, 0 non-200): adapter dell_monitors@2 (dell-us-monitors)
- Discovery: `/en-us/shop/computer-monitors/ar/all-monitors?page=1..9` (server-rendered, 12 tiles/page, 89 models; `?page=` is not disallowed,
  only comma-combined appliedRefinements are). Tile links end in `/<code>/-`: the bare `/<code>` URL serves a generic accessories page (3.7 MB,
  no spec block), which is what r2/r3 saw. Codes carry suffixes (`s2725qs_monitor`, `p2426h_wost` = without stand, `u2724de_withstnd_mon`).
- Spec block `#accessoriesTechSpecs` (two markups: minified unquoted and pretty-printed quoted). Content is syndicated-style and self-contradicts at
  times (U5226KW 'Number of DisplayPorts 0' vs port details '2 DisplayPort 1.4'; P2226H 'Total USB-C 1' vs '2 USB-C downstream'), so counts are
  cross-checked against 'Interface/Port Details'. 'Standard Refresh Rate' can be the overclock rate (AW2524HF 500 Hz vs 480 Hz preset).
- Flicker: 43 of 89 pages print 'Flicker Free: Yes' or a 'Flicker-free' Features item; AW2726DL prints 'Flicker Free: No' (not read as PWM);
  the rest are silent (S/SE/U lines mostly). Dell datasheets/user guides (www.delltechnologies.com, crawl agent) are the next flicker source.

## Dell monitor documents, A3-docs r7 (2026-11-25; crawler UA, 1 req/s, 7 GETs): no usable source, nothing fetched into raw/
- Stored dell-us-monitors pages (89) link exactly one product PDF (U3824DW, www.delltechnologies.com/asset/.../technical-support/...pdf).
- **www.delltechnologies.com: blocked** (403 to the crawler UA on that /asset/ PDF; robots allows /asset/). Not retried, not worked around.
- **www.dell.com/support/... : blocked** (403 on /support/home/.../product-support/product/<slug>/docs and /support/product-details/.../resources/manuals).
- **dl.dell.com** (Dell manual CDN, not in source-policy): robots = `Allow: /manuals`, `Allow: /topicspdf`, `Disallow: /`. Current user guides live
  under /content/manualNNN-... (disallowed). The allowed /manuals/.../esuprt_electronics_accessories_monitors/ index (7603 links) has only
  legacy models: of the 41 Dell rows without flk.pwm only P1917S appears, and its guide is a 5-model family guide (P1917S/P2017H/P2217...) whose
  only flicker line is shared prose ("flicker-free screen and ComfortView"): binds nobody under row scope. source-policy not edited.
- **i.dell.com**: search finds only JP datasheets of older models and catalogs (marketing, skipped). No current US monitor datasheets.
- Third-party mirrors (gzhls.at, manualslib, manua.ls) are not maker sources: not used.

## TÜV Rheinland Certipedia, A2-tuv r7 (2026-11-26; crawler UA, >=10 s apart, 4 GETs): blocked, nothing fetched into raw/
- **www.certipedia.com: blocked to the crawler.** robots.txt and /quality_marks/1111269412 both return `503 Service Unavailable`
  ("No server is available to handle this request") to the honest crawler UA from roxy, 4 times over ~6 min (00:22-00:28).
  In the same window a third-party fetcher reached the site, so this is a refusal of our client (UA or IP), not an outage. Not worked around.
- robots (read via that fetcher): `Crawl-delay: 10`; disallows /search (with and without query strings), product/system/person search
  results and /fs-products/certificates/getProdAppCategories/. /quality_marks/<ID> pages are allowed. Terms: the footer links only
  tuv.com imprint + privacy pages, which render no readable text; nothing found that bars or allows automated access.
- Discovery works without /search: web search returns /quality_marks/<10-digit ID> pages per model (e.g. 1111269412 = DELL "Display Unit
  U2724D, U2724Db", Flicker Free mark; 1111276213 = Eye Comfort 3.0 U2724D/U2724Dt). /keywords/1830 is the "Flicker Free" mark definition.
  These were seen as search snippets only: not verified, not stored, not used.
