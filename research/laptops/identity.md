# Laptop identity: what names a buyable configuration, per brand

Levels (matches provisional profile): family -> model (platform/generation) -> configuration (orderable SKU) -> package (regional suffix/colour/bundle).
Rule: the primary key is the manufacturer orderable ID; retail titles are aliases. Group by *platform*, never by marketing name.

## Per brand
| Brand | Config ID (primary key) | Decomposition | Model-level grouping |
|---|---|---|---|
| Lenovo | MTM, 10 chars, e.g. `83LX001VLS`; verified in PSREF (4696 rows, 12 Yoga products) | `83LX` = machine type (4, platform+screen size+CPU vendor) + `001V` = config serial (4) + `LS` = country/region (2: US, CA, GE, FR, ...) | PSREF ProductKey (e.g. `Yoga_Pro_7_14ASP10`, which is family+size+CPU-code+gen); every MTM belongs to exactly one ProductKey. Machine Type groups all configs of a platform. US = suffix `US` (Region `NA`, Country `USA`). EAN/UPC per MTM is in PSREF, the best retail join key |
| HP | Product number `8L5L4UA#ABA` | `8L5L4` = SKU base, `UA` = region (UA=US), `#ABA` = US-English localisation/keyboard. Same base + different `#`  = same hardware, other locale | HP product name e.g. "OmniBook X Flip 14-fm0xxx" (the `-fm0xxx` suffix = platform; model name `14-fm0097nr` carries region-ish suffix `nr`/`nr`=US retail). Group by series+platform, configs by base number |
| Dell | Retail: SKU like `210-BNGR`-style orderable configs; model name `Dell 14 Plus DB04250`, `XPS 14 9440` (ref + 4-digit platform code), regulatory model `P153G` ; support uses Service Tag (per unit, not per config) | Dell sells build-to-order: configuration = (platform + option SKUs). Retail "ready to ship" configs have a numeric SKU/`Product ID` in page JSON | Group by platform code (`9440`, `DB04250`) and regulatory model `Pxxx`. Unverified; Dell is 403/Akamai on support |
| Apple | Part number `MXD13LL/A` (5 chars + region `LL/A` US) and Model Number `A3112` (regulatory, per hardware gen, size) ; Model Identifier `Mac16,1` | Part number = config (chip/RAM/SSD/colour); `LL/A` = US (`B/A` UK, `ZP/A`...) ; A-number groups all regions of a hardware model; BTO configs have no part number until shipped (`Z...` codes) | Group by Model Identifier / A-number (e.g. MacBook Pro 14" M4 = `Mac16,1`). support.apple.com/en-us/108052 lists identifier <-> year <-> A-number |
| ASUS | Model code `UX3405MA-PP287W` | `UX3405MA` = platform (family `UX`, series, 05=gen/size, `MA`=Intel CPU suffix) + `-PP287W` = config/market SKU (PP = US/Intel Core Ultra 7; trailing letters: W = Windows Home, color) | Group by the part before `-`. US retail suffixes differ by CPU/RAM/colour; the same base appears across regions with different suffixes |
| Acer | `NX.KQAAA.001` (NX = notebook, 5-char model code, 3-digit serial) or `A315-24P-R7VH` | `A315-24P` = family+size+platform; `-R7VH` = config code | Group by `A315-24P` |
| MSI | `Katana 15 B13VFK-1060US` | name + `B13VFK` = platform/CPU/GPU code, `-1060US` = SKU + `US` region | Group by platform before `-` |
| Microsoft | Surface: SKU like `ZGW-00001`; model `1982`/`2036` regulatory model numbers | Config = SKU; family = Surface Laptop/Pro with edition ("7th Edition") | Group by edition + size |
| Samsung | Model code `NP960XGK-KG1US` | `NP960XGK` = platform, `-KG1US` = SKU, `US` region | Group by part before `-` |
| Razer | Retail SKU `RZ09-0528PUA3-R3U1` | `RZ09-0528` = model platform (RZ09 = laptops), `P` ..., `-R3U1` = region/keyboard (`U1` = US) | Group by `RZ09-xxxx` |
| Framework | Shopify variants of DIY/Pre-built SKUs; product = "Laptop 13 (Intel Core Ultra Series 1)" | Config = (batch generation + CPU + options); Framework publishes modular parts separately | Group by Laptop 12/13/16 + mainboard generation |
| LG | gram `16Z90S-G.AD78Y` | `16Z90S` = platform, `-G.AD78Y` = config (CPU/colour/region: `AAS9U1`, `ADB9U1`, `.AD78Y`) | Group by `16Z90S` |
| Gigabyte/AORUS | `AORUS 16X ASG-53US654SH` | name + platform code `ASG` + SKU/region | Group by name + code before `-` |
| Dynabook | `PMM10U-01Y013` style | platform + config | niche (business only) |

## Regional suffix rules (variant -> model)
- Strip trailing region/locale token before grouping: Lenovo last 2 chars, HP `#ABA`/UA, Apple `/A` letters (LL=US), Samsung/MSI trailing `US`, Razer `U1`/`U2`.
- Keep US-only listings in the main catalogue but retain non-US MTMs as `aliases` of the same platform, since spec tables are identical across them (PSREF shows every MTM; ~1% are US).
- A "model" never merges across CPU vendor or generation: `14ASP10` (AMD) vs `14IPH11` (Intel) are separate; screen size is part of the model.

## Mapping retail titles to IDs (priority order)
1. Exact ID in title/URL/MPN field (Amazon/Best Buy `Model` field often carries the MTM, HP product number, Apple `MXD13LL/A`).
2. EAN/UPC lookup: PSREF carries `EAN / UPC / JAN` per MTM; Apple/HP UPC from retail feeds.
3. Platform code in title (`UX3405MA`, `83DK`, `14-fm0097nr`, `A3112`, `Mac16,1`) -> model; then resolve config by CPU+RAM+SSD+screen+colour tuple against that model's config list. Ambiguity -> keep unresolved, never guess.
4. Marketing name only -> alias to family, flag low confidence.
Retail resellers rewrite configs: Best Buy/Costco/Amazon often carry exclusive SKUs (e.g. Lenovo `83DK0002US` vs retailer-only `82xx....` ) that still exist as real MTMs in PSREF; HP/Dell retail-exclusives may not appear on the brand site.


---
# Round 2 additions (2026-11-22): verification status + concrete grouping rules

## Verification status per brand (V = probed live and parsed this round, U = from knowledge, unverified)
| Brand | Verified facts | Unverified |
|---|---|---|
| Lenovo | V: MTM = 10 chars `<MT4><serial4><region2>`; 16 products/65k MTMs analysed; EAN/UPC per MTM; ProductKey -> machine types -> MTM[:8] -> MTM | meaning of the 4-char config serial |
| Apple | V: support.apple.com index gives per model: name, year, colours, Model Identifier(s) `Mac17,2`, part-number FAMILIES `MDE04xx/A` (xx = region; US = LL), Tech Specs KB id. 20 current laptop models (2022+), 178 part-number families | which part number = which chip/RAM/SSD/colour (not published there); A-numbers not on these pages |
| ASUS | V: list API returns 280 rows. rog.asus.com rows are PER CONFIG: `PartNo` 90NR0LF1-M00WU0 + `SalesModelName` G835LXG-DB96 (retail model code incl. config suffix). www.asus.com rows are series pages; their techspec table has one column per BASE model code (UX5406SA/UX5406AA), no US suffix (-PP287W) | where US retail suffixes like `-PP287W` are published (ASUS store / retailers) |
| Dell | V: sitemap dhs-product-urls-hreflang-sitemap-0001.xml.gz lists 48 en-us laptop pages `/en-us/shop/laptop-computers/spd/<slug>`; slug = marketing name + PLATFORM CODE (`dellpropremium14laptoppa14250` -> `pa14250`; `dc16251`, `mc16255`, `db04250`: 2-letter family + size + year(25) + variant digit). JSON-LD sku = `pa14250_reg_01`, a platform pseudo-SKU, not an orderable part | orderable per-config SKUs / Service Tag mapping (configure-to-order); support.dell.com is 403 |
| Microsoft | V: surface sitemap lists device pages (`/surface/devices/surface-laptop-7th-edition`); page sku `9ZZW` = Microsoft Store product-id prefix | per-config orderable SKUs (e.g. ZGW-00001) and regulatory model numbers |
| Framework | V: not Shopify; product slugs `/laptop13`, `/laptop13pro`, `/laptop12`, `/laptop16`; configurator `/products/laptop12-diy-intel-series3/configuration/new`; editions "DIY Edition" vs "Pre-built"; no JSON-LD/SKU in HTML; sitemap lists only top pages | orderable SKU codes |
| HP, Acer, MSI, Gigabyte, Samsung, Razer, LG | none (blocked or not probed) | everything in the table above |

## Grouping MTMs into models: concrete rules (Lenovo, from PSREF `ShowModel` rows)
Levels, tested on 16 products / 65,683 MTMs / 46 machine types / 3,136 multi-region config groups:
1. **Model = PSREF ProductKey** (`ThinkPad_E14_Gen_7_Intel`, `Yoga_Pro_7_14ASP10`). PSREF assigns every MTM to exactly one. Encodes family + screen size + CPU vendor/code + generation. Never merge two ProductKeys.
2. **Platform variant = Machine Type (MTM[:4])**. A ProductKey has ~2.9 machine types on average. Within one machine type nearly every column still varies (Processor 98% of groups, Memory 96%, Storage 96%, Battery 100%, Display 76%, Graphics 63%), but chassis-defining ones rarely do: Weight (7%), Case Color (9%), Pen (9%), NFC (4%), Security Chip (15%). Rule: weight/colour/pen/NFC/dimension-class differences ARE a machine-type difference, so keep machine type as `id.platform_variant`, not as a configuration.
3. **Configuration = MTM[:8]** (machine type + 4-char serial = the orderable hardware recipe). All regional MTMs sharing MTM[:8] have identical hardware columns. Across 3,136 groups of >1 MTM the only columns that vary: Model, EAN/UPC (99.97%), Keyboard (98%), Country/Region (97%), Operating System language (64%), Region (34%), Announce Date (22%); Power Adapter (plug type), End of Support and TopSeller are ~0%.
4. **Package / regional SKU = full MTM** (last 2 chars = country/market: `US`, `CA`, `GE`...). Differences = keyboard layout, OS language, power plug, EAN/UPC, announce date. Group sizes: 4,445 configs exist in only one MTM, others in 9-10 or ~48-49 country variants. US catalogue = `MTM.endswith("US")` (Country/Region == "USA", Region == "NA").
5. Hardware claims attach at **configuration**; `keyboard.layout`, `sw.os` language, `plug`, `gtin` attach at **package**; chassis facts (weight, colour, pen, NFC) at **model/platform variant**.
6. Retail matching: a retailer-exclusive Lenovo MTM often shares MTM[:8] with a regional PSREF row of another country, or is absent. Match order: exact MTM -> EAN/UPC (PSREF has it) -> MTM[:8] -> machine type + CPU/RAM/SSD/screen tuple.

## Other brands: grouping rules (from the verified fields above)
- Apple: model = Model Identifier set (`Mac17,6`+`Mac17,8` = one marketing model with Pro/Max variants listed in one spec page); configuration = part-number family `MDE04` (region `xx` stripped; US = `LL/A`); package = full part number.
- ASUS ROG: model = series page URL slug (`rog-strix-scar-18-2026`); configuration = `PartNo` (`90NR0LF1-M00WU0`); retail-model code `G835LXG-DB96` = base `G835LXG` (platform) + `-DB96` (config suffix; US/other markets differ: `-XB97`). Non-ROG: model = series slug, platform = base model code (`UX5406SA`); config suffix not published by ASUS pages.
- Dell: model = platform code (`pa14250`); configuration = configure-to-order tuple (no stable ID); do not create configuration entities from Dell pages.
- Microsoft: model = edition page; configurations exist only as store SKUs (not captured).
