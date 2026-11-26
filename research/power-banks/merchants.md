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

## Round 2 (A2, 2026-11-23): maker stores added
| source | status | notes |
|---|---|---|
| us.ecoflow.com | adapter (ecoflow-us-powerbanks) | Shopify; spec sections are copied between sibling pages (4/15 name another product) - only name-matched or title-consistent blocks are read. |
| sharge.com | adapter (sharge-us-powerbanks) | Shopify; accordion spec rows with 'Product Model'. |
| kuxiu.com | adapter (kuxiu-us-powerbanks) | Shopify; metafield spec grid with 'Model'. |
| www.mophie.com | adapter (mophie-us-powerbanks) | Shopify; thin Technical Specifications table; ~210 licensed/limited skin pages excluded at discovery. |
| www.baseus.com | unstructured (no adapter) | specs as images + Amazon-attribute template; colour SKUs only on new lines. |

## r7 PPS sweep (A2-pb, 2026-11-26): where PPS is stated, per maker (stored snapshots, 0 new requests)
| maker | PPS stated where | used |
|---|---|---|
| Anker | output protocol rows (3 pages, already); A1638 '45W max output for Samsung' in page notes (htmlContainer) | +1 derived (SFC 2.0 rule) |
| UGREEN | per-port protocol lists (already) | 0 new |
| INIU | 'Supported Protocol' row (already); per-port block 'Output port: USB-C / USB-C Cable : ... / PPS' on Qi2 / SnapGo pages | +5 |
| CUKTECH | feature bullet 'protocols, including PD, PPS, ...' | +2 (PB100P, PB200U); 10 Mini has no model in its spec block |
| EcoFlow RAPID | own-page FAQ ('Output supports PD3.0 PPS', protocol list) | +4; RAPID 20K 45W / 25K 140W pages fail the spec-name gate (copied sections) |
| SHARGE | 'Supported Protocols' rows (already) | Storm 2 / IceMag 2 print PPS but no model number: absences |
| KUXIU | only a customer review mentions PPS | 0 (reviews are not maker statements) |
| Belkin | never on product pages; support articles (D9) gave BPB024 | 0 new |
| mophie | never (pages and 37 hub manuals, A3 r6) | 0 |
| Baseus | no adapter (specs are images; www.baseus.com listed crawl agent) | not built |
| Samsung | www.samsung.com is crawl human_only (2026-11-25.6) | never fetched |
