# Power stations: merchant / evidence-source notes (A2, 2026-11-23)

Retail listings are aliases only (team rule). Nothing below was scraped.

| source | status | notes |
|---|---|---|
| Amazon / Best Buy / Home Depot / Costco | not a source | Retail titles ('Solar Generator 1000 v2 with 200W panel') are aliases; bundles are packages. No product-page scraping. |
| DJI store (store.dji.com) | unstructured, not built | Not Shopify (/products.json 404); robots.txt allows product pages; specs in prose on www.dji.com/<product>/specs. |
| BLUETTI Elite / Apex / Pioneer Na pages | partial (client-rendered) | Tech Specs tab is filled by JavaScript; the HTML has no rows. No headless browser used (budget/rules). Models minted from SKU, specs absent. |
| Jackery HomePower / Explorer v2 (non-v5 template) | partial | 30 of 44 pages print no spec rows in HTML (images / JS). |
| UL Product iQ | not probed | Would verify cert.ul2743 / cert.ul9540 maker claims. |
| Bench-test sites (survey row 11) | not used | Low-rigor vendor-ish measurements; would be the `measured` tier for usable Wh / idle draw. |

No source was blocked by robots or a WAF this round (all 157 fetches 200 with the crawler UA).
