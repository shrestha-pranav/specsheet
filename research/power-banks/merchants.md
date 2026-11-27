# Power banks: merchant / evidence-source notes (A2, 2026-11-23)

Retail listings are aliases only (team rule). Nothing below was scraped.

| source | status | notes |
|---|---|---|
| Amazon | not a source | Brands' own titles repeat there with '26800mAh' class figures; listing titles are aliases. No product-page scraping. |
| Best Buy / Target / Walmart | not probed | Same rule; would only add retailer SKUs (alias level). |
| ChargerLAB (chargerlab.com) | **blocked (robots)** | robots.txt disallows ClaudeBot / anthropic-ai / Claude-Web explicitly; Content-Signal ai-train=no. Not fetched. Its measured PDO/capacity tests would be the independent `measured` tier; needs coordinator/human decision (manual reference use only). |
| CPSC recalls API | built r12 (A2-safe) | crawler/adapters/cpsc_recalls.py, one source per category (cpsc-recalls-<cat>); www.saferproducts.gov + www.cpsc.gov crawl agent (source-policy 2026-11-26.12). Exact printed model only; recall-only records flagged gen.record_kind recall_only. Policy claim/cpsc-recalls@1 pending. |
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

## r10 PPS sweep (A2-pb, 2026-11-26): 0 HTTP requests (stored pages + stored documents only)
| maker | finding | used |
|---|---|---|
| Anker / UGREEN / INIU / CUKTECH / EcoFlow / SHARGE / KUXIU | stored pages of the 52 in-scope rows without pd.pps: no own-product PPS statement. Anker hits are the cross-sell A2692 charger block; SHARGE X6 PPS text is a customer review; INIU B62 SFC 2.0 only in image alt text (also recharge context); INIU B43 manual linked from P62/P63 pages names another model | 0 |
| Belkin | NEW document type: regulatory leaflets INS_*.pdf ('Download Regulatory and sustainability information', www.belkin.com Demandware file path). They print Model No + full Output PDO list incl. '(PPS) 5-16V' / '3.3-21V'. Never parsed before: documents.py classified the 'Sites-master-product-catalog-blk' path as marketing. All 23 already on disk (adopted, no GET) | +2 (BPB029, BPB040), pending document-power-pdo@5 |
| Belkin | BPB027 / BPB028 pages link V2 leaflets (Model No BPB027V2 / BPB028V2, PPS 5-11V): identity rule needs an exact own model, so nothing attaches. BBA019 page links the BPB039 leaflet (another model): nothing | open (A1/coordinator) |
| Belkin | 10 in-scope rows have a leaflet with a complete Output list and no PPS (BBA010, BBA018, BBC010/BPD004, BPD006, BPD007, BPD008, BPD011, BPD015, BPD022): pd.pps false NOT written (complete-enumeration rule needs an A1 ruling) | logged |
| mophie | hub manuals (A3 r6): unchanged, no PPS | 0 |

## r11 (A2-bat, 2026-11-26): terms audit + NITECORE
- New crawl:agent maker: www.nitecore.com (robots allows * and ClaudeBot; no terms page). Source nitecore-us-powerbanks: sitemap -> 20 bank pages -> 16 models (kits / NBP68HD battery pack mint nothing). Policy claim/mfr-power-banks-nitecore@1 pending.
- Terms bar automated collection -> crawl human_only (source-policy 2026-11-26.7), no further agent fetches: www.anker.com, iniushop.com, www.cuktech.com, us.ugreen.com, sharge.com, us.ecoflow.com. Stored values unchanged pending coordinator/owner ruling.
- kuxiu.com, www.mophie.com: no such clause found (stay agent). Baseus: still unstructured (spec images); Zendure: no power banks. Satechi: chargers lane.
- CPSC recalls (saferproducts.gov API, robots 404 = no rules): 13 power-bank recalls name our brands (Anker A1263/A1366/A1642/A1647/A1652, Belkin BPB002/PB0003/BPD005, INIU BI-B41, Baseus PPCXM06/PPCXW06/BS-30KP365), but none matches a stored model: safety.recall needs either recall-only records (coordinator ruling) or nothing. Adapter not built.

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
