# Power banks: merchant / evidence-source notes (A2, 2026-11-23)

Retail listings are aliases only (team rule). Nothing below was scraped.

| source | status | notes |
|---|---|---|
| Amazon | not a source | Brands' own titles repeat there with '26800mAh' class figures; listing titles are aliases. No product-page scraping. |
| Best Buy / Target / Walmart | not probed | Same rule; would only add retailer SKUs (alias level). |
| ChargerLAB (chargerlab.com) | **blocked (robots)** | robots.txt disallows ClaudeBot / anthropic-ai / Claude-Web explicitly; Content-Signal ai-train=no. Not fetched. Its measured PDO/capacity tests would be the independent `measured` tier; needs coordinator/human decision (manual reference use only). |
| CPSC recalls API | viable, not built | saferproducts.gov REST JSON works without a key; model numbers are in free text. Planned key `safety.recall`. |
| FCC ID | not probed | only wireless (Qi/Qi2) packs have grants; fcc.gov EAS was 403 (Akamai) in the routers round. |
| WPC Qi certified database | not probed | would verify out.wireless_standard qi2 / qi2_2 claims. |
