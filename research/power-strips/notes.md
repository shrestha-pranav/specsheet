# Power strips: who publishes what (checked 2026-11-22)

## Standards in one paragraph
- UL 1363 = relocatable power taps (construction, cord, breaker). UL 1449 = surge protective devices; cord-connected strips are **Type 3** SPDs. A strip with >2 outlets and surge protection should meet both. UL 1449 5th ed. (2021). UL does not evaluate energy (joules) and states it does not assess attenuation or VPR adequacy for equipment.
- VPR = measured let-through voltage for 6 kV/3 kA pulse, per mode (L-N, L-G, N-G), rounded up to a bin (330/400/500/600/700...). Lower = better. This replaced "clamping voltage" marketing. Joules are a manufacturer-declared number with no common test.
- UL listing category: XBYS (relocatable power taps, includes SPD taps), file number E#.

## Sources inspected
| Source | Format | Granularity |
|---|---|---|
| Eaton Tripp Lite datasheet PDF (assets.tripplite.com/product-pdfs/en/<sku>.pdf; page = eaton.com/us/en-us/skuPage.<SKU>.html; tripplite.eaton.com 302s) | Clean two-column key/value table, ~60 fields | Best: AWG, breaker A, W out, mm outlet spacing, LED colors, EMI dB range, edition. Quirks: VPR only as one "UL1449 Let Through Rating 330V"; features text says 3rd ed while table says 5th ed Rev 2021; surge current 97,000 vs 135,000 in one PDF; HTML leaks into insurance field |
| Belkin product page (belkin.com/p/<name>/<SKU>.html) | HTML spec table + comparison table | Per-mode clamping (L-N 400, L-G 500, N-G 500), EMI "up to 75dB", LED colors, CEW $300k. No dimensions, no VPR label, no edition. Inconsistent joules (3780 in table vs 3940 in alt text). Unit text mixed ("3780J"). Some pages Cloudflare/404 on guessed URLs |
| CyberPower datasheet PDF (dl4jz3rbrsfum.cloudfront.net/documents/CyberPower_DS_CSB604.pdf, 2 pages) + product page | Key/value | One "Clamping Voltage 500V (H-N,H-G,N-G)", surge current per mode, 900 J (web page said 1800 J: check). CEW $50k. Product page returns 405 to WebFetch |
| TP-Link Kasa HS300 datasheet PDF (static.tp-link.com) | Bulleted specs | "VPR: 600 V (L-N, L-G, N-G), Type 3 SPD" - explicit term; USB "5 V 2.4 A each and total"; certs "FCC, ETL" (not UL); dims, weight. Hardware-version datasheets (v1/v2) |
| APC (se.com/us/en/product/P12U2) | JS-rendered; WebFetch got only nav | Needs browser/API; not verified here. apc.com redirects to se.com |
| Amazon Basics, GE/Jasco, Anker, Monster, Furman, Panamax | not fetched | Expected: Amazon/GE thin retail tables; Furman/Panamax datasheets rich (clamping per mode, SPD detail) - A2 follow-up |

## UL Product iQ
- productiq.ulprospector.com returns 403 to plain fetch. Individual profile pages (e.g. /en/profile/1000736/xbys.e192912) and older productspec.ul.com/document.php?id=XBYS.E152555 are search-indexed, so listing pages are publicly viewable in a browser, free account likely needed for search.
- Content: company, file number E#, CCN, model prefixes/series with wildcards ("SP-3573U2*"), listing status and date, Type 3 SPD marking, standard. It does **not** give VPR, joules, or full SKUs; page says it "does not show all models".
- Use: verify listing exists (by brand file number, e.g. Belkin E152555), not as a spec source. Matching is by model-prefix, fuzzy.

## Cross-brand pitfalls (for normalization)
1. Same word ("clamping voltage") is used for VPR, for a single number, or for a different standard (Eaton "140V RMS").
2. Joules: same SKU varies by page; revisions change number; unit "J" vs "joules".
3. CEW amounts vary ($50k, $300k) with different conditions; Belkin: void if indicator off.
4. Breaker < 15 A (Eaton 12 A) while label says 1875 W elsewhere.
5. Dimensions: order h/w/d vs l/w/h, unit vs shipping.
6. USB power given as per-port max, hidden shared total.
7. ETL listed items (Kasa) are valid, so listing facet must be "listing body", not just UL.
