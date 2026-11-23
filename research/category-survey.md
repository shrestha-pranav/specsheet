# Category survey (2026-11-22)

Method: WebSearch standard mode only; no Bright Data, no page fetches. "V" = claim supported by a URL
that appeared in search results (page text not fetched, so read as "search-snippet verified"). Unmarked
= analyst judgment. Scores 1-5. Opacity: higher = more hidden/misstated. Official avail: higher = the
manufacturer publishes structured specs somewhere (regulator data is called out separately). Identity:
higher = stable manufacturer model numbers. Score = 1.5*Opacity + Demand + Official + Identity.
Laptops, GaN chargers and power strips already have pilots/research dirs; kept in the table for calibration.

## Ranked table (raw score)

| # | Category | Opacity | Demand | Official avail | Identity | Score | Hidden specs that matter | Best sources |
|--|--|--|--|--|--|--|--|--|
| 1 | Robot vacuums | 5 | 4 | 3 | 4 | 18.5 | Suction (Pa not comparable; sealed-inlet), brush type/airflow, obstacle-sensor type, dock/water tank capacity, parts cost/availability | Mfr page, RTINGS/Wirecutter/Vacuum Wars tests, FCC, retailer |
| 2 | Monitors | 4 | 5 | 3 | 4 | 18.0 | HDR local-dimming zones/real peak nits; panel type+sub-type (WOLED/QD-OLED, IPS Black); refresh-rate overdrive/VRR range, HDMI/DP version per port | Mfr spec page, VESA DisplayHDR list, TFTCentral/RTINGS, FCC |
| 3 | SSDs / NVMe | 5 | 4 | 2 | 4 | 17.5 | Controller + NAND vendor/layer count (silently swapped per revision); DRAM-less/HMB; sustained write after SLC cache | Mfr datasheet (vague), TechPowerUp SSD DB, Tom's/StorageReview teardowns, FCC (rare) |
| 4 | Tires | 3 | 5 | 4 | 4 | 17.5 | UTQG treadwear is self-reported; manufacture date/load/speed; true weight/rolling resistance | NHTSA UTQG, mfr, Tire Rack, Consumer Reports. Strong incumbents |
| 5 | Wi-Fi routers / mesh | 4 | 4 | 3 | 4 | 17.0 | SoC/RAM/flash; real radio config (2x2 vs 4x4, 160 MHz, 6 GHz band); hardware version (v1/v2) differences; EOL/update window | FCC ID filings+photos, OpenWrt ToH, DeviWiki, mfr pages, Wi-Fi Alliance cert DB |
| 6 | microSD / flash drives / memory cards | 4 | 4 | 3 | 4 | 17.0 | Real sustained write vs 'up to' read; A1/A2, V30/U3 class; counterfeit/ revision differences | Mfr datasheet, SD Association, independent bench tests |
| 7 | Power banks | 4 | 4 | 3 | 4 | 17.0 | Rated energy Wh at cell voltage vs 5V mAh; per-port PD PDO table, simultaneous output; cell chemistry (airline limit) | Mfr page/label, FCC, CPSC recalls, ChargerLAB/bench tests |
| 8 | TVs | 4 | 5 | 3 | 3 | 17.0 | Panel type by size (VA vs IPS, QD-OLED vs WOLED lottery); local-dim zones; true native refresh/HDMI 2.1 per port; retailer-exclusive suffix variants | Mfr spec pages, RTINGS, Energy Star/DOE (power), FCC |
| 9 | GaN USB-C chargers (pilot) | 4 | 4 | 3 | 4 | 17.0 | PPS ranges, per-port split power, PDO table; marketing names hide capabilities | Mfr page/images, FCC, ChargerLAB, USB-IF cert |
| 10 | Laptops (existing) | 4 | 5 | 3 | 3 | 17.0 | Panel (nits/gamut/PWM), RAM soldered/upgradable, TGP/PL1 power limits, MTM-specific config differences | Mfr PSREF/QuickSpecs/PDF, retailer MTM, Notebookcheck, FCC |
| 11 | Portable power stations | 4 | 3 | 4 | 4 | 17.0 | Usable vs rated Wh; continuous vs surge output; chemistry/cycle life with retention; idle draw | Mfr page+manual, FCC/UL 2743, independent bench tests |
| 12 | Headphones / earbuds | 3 | 5 | 3 | 4 | 16.5 | Battery life under ANC/codec conditions; codecs; multipoint; driver, mic quality | Mfr page, RTINGS, SoundGuys, FCC |
| 13 | Water filters / pitchers | 3 | 4 | 4 | 4 | 16.5 | Certified contaminants per NSF/ANSI std (not just 'certified'), flow, filter cost | NSF + IAPMO databases, mfr perf data sheets |
| 14 | CPUs / GPUs | 1 | 5 | 5 | 5 | 16.5 | Board-partner variant clocks/power | Mfr + TechPowerUp; saturated |
| 15 | Printers / ink | 4 | 4 | 2 | 4 | 16.0 | Cost per page, cartridge vs tank, DRM/firmware blocks on 3rd-party ink, duplex/ADF | Mfr, RTINGS/Wirecutter, FCC |
| 16 | Major appliances (fridge/dishwasher/washer) | 3 | 5 | 3 | 3 | 15.5 | Rated dB (test basis), usable vs claimed capacity, actual cycle energy/water, model-suffix differences | DOE CCMS, ENERGY STAR data.energystar.gov (Socrata), mfr spec/manual PDFs, CPSC |
| 17 | Air purifiers | 3 | 4 | 3 | 4 | 15.5 | CADR (AHAM-verified vs self-claimed), filter cost/life, noise at speed, ozone (CARB) | AHAM Verifide DB, CARB list, ENERGY STAR, mfr |
| 18 | USB-C cables | 5 | 4 | 2 | 2 | 15.5 | Data speed (power marking only), e-marker content, 240W real support, length | USB-IF cert DB, mfr, bench testers; few clear model numbers |
| 19 | Flashlights / batteries | 5 | 3 | 2 | 3 | 15.5 | Lumens ANSI FL1 vs inflated, real mAh, runtime curve, cell vs claimed | Mfr, ANSI FL1 reviews, bench tests |
| 20 | Smart-home sensors/hubs (Zigbee/Matter) | 4 | 3 | 3 | 3 | 15.0 | Radio (Zigbee/Thread/WiFi), Matter version, battery type/life, local-vs-cloud | CSA cert DB, FCC, Zigbee2MQTT DB (community) |
| 21 | Smartphones | 2 | 5 | 4 | 3 | 15.0 | Repairability, update years, per-band support by carrier model | GSMArena, mfr, FCC; saturated |
| 22 | Power strips (existing) | 3 | 3 | 3 | 4 | 14.5 | Joule rating, clamp voltage, UL 1449 listing, outlet spacing | UL Product iQ, mfr, FCC n/a |
| 23 | Mattresses | 5 | 4 | 2 | 1 | 14.5 | Foam density/ILD per layer, coil gauge, retailer-specific renamed SKUs | Mfr, MattressUnderground; identity unstable |
| 24 | Cars / EV trims | 3 | 5 | 3 | 2 | 14.5 | Usable vs gross battery, real DC charge curve, trim-package contents | EPA fueleconomy.gov, NHTSA vPIC, Edmunds; heavy incumbents |
| 25 | E-bikes | 4 | 3 | 2 | 3 | 14.0 | Battery Wh vs claimed range, motor continuous vs peak, UL 2849 cert, parts | Mfr, UL, CPSC recalls |
| 26 | Furniture | 4 | 4 | 2 | 2 | 14.0 | Assembled vs packed dimensions, material (solid vs veneer), weight capacity | Mfr, retailer; SKU churn, images |
| 27 | Bike components | 2 | 3 | 4 | 4 | 14.0 | Compatibility (freehub, cassette limits), weight | Mfr (SRAM/Shimano publish); niche |

Raw score ignores competition and crawl cost, so the shortlist below adjusts it (CPUs/GPUs, smartphones,
tires, cars score fine but are saturated by TechPowerUp, GSMArena, Tire Rack, EPA/Edmunds).

## Top-8 shortlist (adjusted order)

1. **Monitors** - biggest demand x opacity combo. HDR badge vs reality: VESA warns "HDR-400" without
   "DisplayHDR 400" is likely uncertified, and local-dimming zone counts only appear in detailed specs or
   reviews (V: https://www.pcworld.com/article/3128871/your-hdr-monitor-might-be-lying-to-you.html ,
   https://tftcentral.co.uk/articles/why-your-hdr-monitor-is-probably-not-hdr-at-all-and-why-displayhdr-400-needs-to-go).
   Panel lottery across same-model units reported (V: https://www.rtings.com/tv/learn/panel-lottery-samsung ;
   RTINGS found 3 sizes of one Samsung TV used 3 panel makers but small differences in 2016 test; the
   OLED mixed-panel claim is a news report, V: https://www.whathifi.com/news/samsung-refuses-to-deny-oled-panel-lottery-reports).
   Model numbers stable; VESA cert list is structured.
2. **SSDs / NVMe** - the cleanest "model number lies" case. Same name/number/sticker shipped with different
   controller/NAND; one ADATA revision lost 41% copy performance; Samsung 970 EVO Plus, Team MP34, Crucial/WD
   TLC->QLC (V: https://www.tomshardware.com/news/adata-and-other-ssd-makers-swapping-parts ,
   https://www.theregister.com/on-prem/2021/08/28/et-tu-samsung-electronics-giant-accused-of-quietly-switching-ssd-components/446984).
   Needs a revision-level key (model + date code/firmware), which is the product's differentiator. Official
   data is the weak spot (A=2), so rely on review-site teardowns with provenance tags.
3. **Robot vacuums** - top opacity. Pa has no mandatory test protocol, units mixed (Pa/kPa/AW/CFM), sealed-inlet
   numbers (V: https://progadgetpicks.com/robot-vacuum-suction-power-comparison/ , https://tech.yahoo.com/articles/suction-power-unreliable-measure-robot-130000730.html;
   blog/review-grade sources). Catalogue should store the claim AND the independent test result side by side.
4. **Wi-Fi routers / mesh** - official pages omit SoC/RAM/flash; FCC ID filings with internal photos plus OpenWrt ToH /
   DeviWiki fill gaps; FCC may not name the chip, coverage uneven (V: https://www.fcc.gov/oet/ea/fccid ,
   https://deviwiki.com/wiki/Netgear_Orbi_Router_(RBR850)). Hardware-version (v1/v2) identity matters. Good fit for
   FCC-adapter in the crawler.
5. **Power banks (+GaN chargers, shared schema)** - mAh at 3.7 V cell vs 5 V output; two mAh figures printed;
   airline limit is Wh; 26,800 mAh is 96.5 Wh at 3.6 V but 103.2 Wh at 3.85 V (V: https://heybmx.com/blogs/news/mah-vs-wh-in-power-banks-how-many-phone-charges-and-what-the-airline-limit-actually-means ;
   vendor blog, numbers are arithmetic). Natural extension of the existing charger pilot: same PD/PDO fields.
6. **TVs** - biggest demand. Panel varies by size within a line (anecdotal per forum), retailer-exclusive suffixes
   (Costco etc.) exist and defeat price matching (V: https://digitaltrends.com/home-theater/you-asked-model-number-mystery-new-tv-fomo);
   whether spec differences exist is disputed. Hidden: panel type per size, local-dim zones, HDMI 2.1 per port.
   Crawl cost high, but Energy Star / DOE power data is structured.
7. **Major appliances (fridge, dishwasher, washer, dryer)** - the regulator-seeded category. DOE CCMS exposes
   model-level certified efficiency/capacity data (V: https://www.regulations.doe.gov/certification-data/ ; note only
   current basic models from the past year, listing is not a compliance finding, model must match closely) and
   ENERGY STAR publishes 45,000+ certified models via Socrata API (V: https://www.energystar.gov/productfinder/advanced).
   Hidden: dB test basis, usable capacity, model-suffix variants. Lowest crawl cost of the list, so good for proving
   field-level provenance and "official regulator" confidence class.
8. **Portable power stations** - A=4 (manuals list specs), but rated vs usable Wh, continuous vs surge, idle draw,
   and cycle-life-with-retention are routinely blurred; bench data exists but is low-rigor (V: https://capytoolkit.com/blog/guides/portable-power-station-claims-dont-add-up-check-math-yourself/ ,
   https://wildsmartgear.com/portable-power-station-test-benchmarks/ ; vendor-ish sources, treat numbers as unverified).
   High ticket price makes buyers research hard. Same electrical fields as power banks.

Runners-up: microSD/flash (counterfeits, "up to" speeds), headphones (battery under ANC/codec conditions; SoundGuys:
earbuds usually within 10% of claim or a bit short, V: https://www.soundguys.com/headphones-battery-life-compared-to-price-139341/),
air purifiers (AHAM CADR), printers (cost/page, ink DRM), water filters (NSF listings structured). Laptops continue
under the existing pilot.

## Regulatory / cert databases worth an adapter (ranked by usefulness)

- FCC ID (https://www.fcc.gov/oet/ea/fccid): RF, internal photos, sometimes chipsets. Covers routers, chargers
  with radios, power banks w/ wireless, headphones, vacuums, sensors. V.
- DOE CCMS + ENERGY STAR Socrata: appliances, TVs/monitors power, HVAC. V (field names not confirmed; read column list).
- CPSC recalls API (https://www.saferproducts.gov/RestWebServices/Recall, format=json; ProductModel field per 2018
  guide, one July 2026 write-up says docs partly stale, test live before relying). V: https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information
  Use as a safety flag on any category, keyed by model.
- NHTSA vPIC (https://vpic.nhtsa.dot.gov/api/): free, no registration; missing value does not mean feature absent;
  battery capacity fields not confirmed. Only relevant if cars are entered. V.
- UL Product iQ, USB-IF, VESA DisplayHDR list, Wi-Fi Alliance, CSA (Matter), AHAM, NSF: category-specific cert lists;
  not individually checked this round.

## Categories to avoid (for now)

- **CPUs/GPUs, smartphones, bike components** - manufacturers publish complete specs (opacity 1-2); TechPowerUp and
  GSMArena already own the niche.
- **Tires** - UTQG treadwear is self-certified and manufacturers may under-report but not over-report (V:
  https://www.tirerack.com/upgrade-garage/what-are-the-uniform-tire-quality-grade-utqg-standards ), absolute miles
  vary 20-30% from claims per CR-sourced claim. Real pain, but Tire Rack/CR own the data and sizes x SKUs explode the key space.
- **Mattresses, furniture** - no stable manufacturer model number; retailers rename the same product (V, anecdotal:
  https://www.worseonpurpose.com/p/your-mattress-got-worse-on-purpose ; unverified). Violates the identity rule in ROLES.md.
- **Cars / EV trims** - identity is trim+options+model-year, heavy incumbents (EPA, Edmunds).
- **USB-C cables** - very high opacity (certified USB 2.0 cables may show only a 60W/240W mark, data speed unlisted;
  V: https://usbconnectioninformation.com/guides/usb-c-charging-speed-vs-data-speed/, seller source) but weak model
  numbers and mostly white-label listings. Revisit as a sub-table of chargers.
- **Flashlights/batteries, e-bikes** - spec gaming real, but small audience or no structured official data; defer.

## Caveats

- Only search-result snippets were read. No Reddit threads surfaced directly; complaints are via review/forum articles.
- Scores are analyst judgment, not measured. Demand scores are not backed by search-volume data.
- Many "V" URLs are blogs or vendor pages; the stronger ones are Tom's Hardware, The Register, RTINGS, TFTCentral,
  DOE, ENERGY STAR, FCC, CPSC.
