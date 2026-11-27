# Category survey r2 (2026-11-26, A5)

Brief: team/briefs/coord-2026-11-26-r11-categories-a5.md. Owner direction 2026-11-26: datasets first, licensing later,
so the rank is **records obtainable from crawl:agent-compatible sources x demand**; licensing is a column only.
Method: every robots.txt and terms page below was fetched with the crawler UA (`specsheet-crawler/0.1`, ~1 req/s), read by
keyword scan of the full page text; dataset counts are live API counts on 2026-11-26. WebSearch standard for discovery only.
No Bright Data. A host that refused us (403/503/WAF/HTTP-2 reset) was not reached through any other fetcher, robots and
terms included. "Agent" below = robots allows us AND terms carry no anti-automation clause (the standard behind the
Samsung/Apple 2026-11-25.6, se.com 2026-11-26.2 and AOC rulings). Personal/non-commercial-only terms count as human_only.

## 0. Finding outside this brief (needs a coordinator ruling)
**www.lg.com/us/terms bars automated collection**: "(e) you shall not use any manual or automated software ... spiders,
robots, scrapers, crawlers ... data mining tools ... to 'scrape' or download data from any web pages" (search-engine
exception only). source-policy.yaml has www.lg.com as `kind: maker`, crawl absent (= agent), `evidence: none`, and ~1414 LG
values are cited (data-licensing.md). Under the Samsung/Apple standard this is `crawl: human_only`. Not edited (no data/
edits in this brief). Other `evidence: none` makers (tp-link, sandisk, asus, ...) carry the same unaudited risk.

## 1. Ranked table
Records = buyable-model records reachable by agent-compatible sources today. Lic = paid/licence outlook.

| # | Category | Records obtainable (agent) | Main sources + crawl status | Lic | Identity | Killer queries | Demand |
|--|--|--|--|--|--|--|--|
| 1 | Major appliances (fridge/freezer, washer, dryer, dishwasher, room AC, dehumidifier, cooktop) | **~8,950** ENERGY STAR (fridge 4,942; dishwasher 753; dryer 706; freezer 680; room AC 608; dehumidifier 576; washer 421; electric cooking 265) + Bosch pages (dBA) | data.energystar.gov Socrata: agent, 24-40 cols/dataset, updated daily. Bosch: agent. LG: robots ok, **terms bar scraping** (s.0). GE Appliances: terms bar "systematically extract ... data fields" = human_only. Whirlpool, Maytag, Frigidaire, Electrolux: blocked (HTTP/2 INTERNAL_ERROR, like Acer). Samsung: human_only. DOE CCMS: blocked (prior round) | ES = public domain, already paid+grant ALLOW. Bosch: facts+link, paid no | Maker model no. with `**` wildcards (e.g. Samsung `BRB106003**`) + `additional_model_information` variants; ES UPC crosswalk dataset 8edu-y555 (39,975 rows) | counter-depth fridge <=36 in wide with >=20 ft3 adjusted volume and <=600 kWh/yr; 120 V ventless heat-pump dryer >=4 cu ft; 24 in dishwasher <=44 dBA with <=3.5 gal/cycle and >=14 place settings; washer IWF + drum cu ft | 5 |
| 2 | Smart-home (Matter / Zigbee devices) | **~5,640** Matter models (904 vendors, 15,814 certified model-versions) + **5,463** Zigbee device pages | CSA DCL REST (on.dcl.csa-iot.org): agent, already in policy (free yes, paid no). Zigbee2MQTT device DB via GitHub API (Koenkk/zigbee2mqtt.io docs GPL-3.0; device definitions in zigbee-herdsman-converters MIT): agent. Makers: Philips Hue, Eve: agent (no automated clause); TP-Link agent (unaudited); Aqara: personal non-commercial = human_only; Apple/Samsung human_only. Bluetooth SIG qualification: robots `Disallow: /`; bluetooth.com Cloudflare; apps.fcc.gov 503: blocked | DCL: excluded from paid (CSA site terms). Z2M converters MIT = strongest licence candidate of any new source | DCL vid/pid + productName/partNumber (partNumber often "-"); Z2M model = maker model id (IKEA E1743), stable | Thread or Zigbee motion sensor that works locally (Z2M-supported or Matter-certified, no vendor hub) with lux; Matter plug with energy metering; which Matter software version is certified | 3 |
| 3 | USB-IF certification overlay: USB-C cables + chargers/power banks | **16,472** certified products; 4,078 cables (3,455 with part no., speed class, connector, EPR e-marker); 718 power bricks/banks with total W | www.usb.org public JSON `/vtm-products/v1/all` (the product-search page's own feed; robots allow; 14.7 MB, one GET): agent. Anker, Belkin, UGREEN: agent (existing). Cable Matters: robots blocked (prior round). Apple human_only | usb.org document-library legal text: "limited, personal, internal use only ... not ... redistribution"; product list page states no terms -> free facts+link, paid no; ask USB-IF | Weak for cables: mostly OEM listings (Luxshare 499, Elecom 469); retail brands thin (Samsung 186, Best Buy/Insignia 178, Cable Matters 53, UGREEN 8, Anker 7). Good for chargers (model no. e.g. Samsung EP-TA800) | USB-IF-certified 240 W / 40 Gbps USB-C cable; is this charger/power bank actually certified, at what W | 4 |
| 4 | UPS (extends power-strips) | **923** ES UPS (APC 222, Vertiv 141, CyberPower 125, Liebert 94, Tripp Lite 86, Eaton 68); consumer subset ~300 | ES ifxy-2uty (102 cols: topology, VA/W, outlets battery vs surge-only, 0%-load input W, efficiency curve): agent. CyberPower, assets.tripplite.com: agent (existing). APC/se.com human_only; Eaton blocked | ES ALLOW | Maker model no. (CP1500PFCLCD) | line-interactive UPS >=900 W with <=X W idle draw and >=6 battery outlets; pure sine (maker page) | 3 |
| 5 | Printers | **2,847** ES imaging (Epson 564, HP 296, Canon 270, Brother 143) | ES t2v6-g4nf (speed ipm, duplex, colour, marking tech, TEC kWh): agent. Brother: agent (no automated clause). Epson terms "may not scrape the Site, or use ... robots, spiders" = human_only (global.epson.com 403). HP human_only. Canon 403 Akamai | ES ALLOW | Maker model no. | cost per page (ISO yield / cartridge price) - **only Brother obtainable**; ink DRM not in any agent source | 4 |
| 6 | microSD / memory cards | ~300-600 (SanDisk + PNY + Lexar pages) | SanDisk agent (existing SSD pipeline, unaudited). PNY: robots ok, legal page no automated clause (full terms not located). Lexar: no robots (404 = unrestricted), terms 404. Samsung human_only. Kingston product pages Cloudflare (datasheet PDFs reachable). No certifier product list found | facts+link | Stable model no. (SDSQXAV-256G-GN6MA) | min sustained write (V30/V60/V90) vs "up to"; A1/A2; high-endurance TBW/hours | 4 |
| 7 | Water filters | **~0 agent** (NSF has ~2,200 NSF/ANSI 53, 2,248 NSF 58, 1,521 NSF 401, 13,899 NSF 42 listings; 956 pour-through products / 28 makers) | info.nsf.org listings: robots allow, structured HTML (model, replacement element, service gal, gpm, per-claim); **NSF terms page www.nsf.org Cloudflare 403** = blocked; search snippet says reuse incl. data mining needs written permission -> human_only until NSF answers. WQA terms explicitly bar AI/scrapers. Brita (Clorox terms bar bots/data mining), PUR (personal non-commercial), ZeroWater (bars robots): human_only | restrictive everywhere | Good: model + replacement element | pitcher certified to NSF 53 for lead AND NSF 401/53 PFOA/PFOS, cost per gallon | 4 |
| 8 | Headphones / earbuds | ~0 agent | Sony 403 Akamai; JBL 403 (DataDome); Bose terms bar robots/scrapers; Sennheiser reserves text-and-data-mining (UrhG 44b); Apple/Samsung human_only; Bluetooth SIG + FCC blocked | - | Stable model no. | battery under ANC, codecs, multipoint | 5 |
| 9 | Tires | ~0 agent | UTQG on data.transportation.gov (7wch-zrff, rfqx-2vcg, sku7-utyd) are `href` stubs pointing to nhtsa.gov, which is 403 Akamai: blocked. Goodyear 403; Bridgestone 301 (not followed); Michelin/Continental/Pirelli/Firestone robots allow, terms not read | - | line x size x load/speed; key explosion | treadwear vs price, rolling resistance | 5 |
| 10 | CPUs/GPUs | ES Computers 1,848 (CPU names) | Intel robots explicitly allows ClaudeBot (terms not read); AMD blocked (HTTP/2 reset). Saturated (TechPowerUp) | - | Excellent | low opacity | 5 |
| 11 | Flashlights / batteries | unknown, small | Fenix (Shopify, robots allow), Energizer (robots allow ClaudeBot); terms not read; Olight/Nitecore/Duracell 301 not followed. No DB | - | Fair | ANSI FL1 lumens/runtime vs claim | 3 |
| 12 | Smartphones | ~0 agent | Apple/Samsung human_only; FCC blocked; saturated (GSMArena) | - | Fair | bands per carrier model | 5 |
Not ranked: EU EPREL (EU market; robots path returns the SPA), ES EVSE (482 AC + DC sets, a possible EV-charger category later).

## 2. Top 3 pilot plans

### 2.1 Major appliances (RECOMMENDED to start next round)
Why: largest agent-obtainable record count of any candidate, public-domain licence already approved for paid AND grant,
demand 5, and the existing `energystar_*.py` Socrata pattern (monitors/TVs/air purifiers) makes it adapters-only work.
Identity: levels [family, model, variant]; primary_key = ES `model_number` (wildcards `*`/`**` = colour/trim family) per
brand, `additional_model_information` = variant aliases, UPC from 8edu-y555 as alias. Subcategory slugs, not one profile.
Adapters (A2): one parameterised `energystar_appliances.py` (dataset id + column map per subtype: p5st-her9, 8t9c-g3tn,
bghd-e2wd, t9u7-4d2j, q8py-6w3f, 5xn2-dv4h, mgiu-hu4z, m6gi-ng33) + `energystar_upc.py` (alias crosswalk) + `bosch_us.py`
(us/en/product/... pages: dBA, dimensions, kWh, gal; JSON-LD present). Expected ~8,950 ES records + ~200 Bosch enrichments.
Spec keys (core): dims.width_in, dims.height_in, dims.depth_in, capacity.total_ft3, capacity.adjusted_ft3 (fridge),
fridge.configuration (top/bottom/side/french), fridge.counter_depth, fridge.ice_maker, fridge.dispenser,
energy.annual_kwh, energy.pct_below_federal, water.gal_per_cycle / water.iwf (washer), washer.drum_ft3, washer.load (front/top),
dryer.vented, dryer.heat_pump, dryer.voltage, dishwasher.place_settings, dishwasher.tub_material, dishwasher.noise_dba (maker),
roomac.cooling_btu, roomac.ceer, roomac.variable_speed, dehum.pints_day, dehum.ief, refrigerant.type_gwp, connected.
Traps for A1: ES lists only certified (efficient) models, so coverage is a subset - show "not ENERGY STAR listed" as unknown,
not absent; wildcard model numbers must match by pattern, not equality; dBA is maker-claimed and test basis varies.
Open: whether to also cover non-ES models (DOE CCMS blocked; LG/GE/Whirlpool unusable for agents).

### 2.2 Smart-home (Matter + Zigbee)
Adapters: `csa_dcl_models.py` (generalise csa_dcl_robovac.py to all deviceTypeIds; vendors + models + certified-models +
compliance), `z2m_devices.py` (GitHub API tree of zigbee2mqtt.io docs/devices, plus herdsman-converters definitions for
exposes/vendor/whiteLabel), `hue_us.py` / `eve_us.py` maker enrichment. Expected ~5,640 Matter + ~5,463 Zigbee records,
overlap small (join on vendor+model, needs identity.md rules). Keys: radio.protocol (zigbee/thread/wifi/ble), matter.certified,
matter.device_type, matter.sw_versions_certified, zigbee.z2m_supported, zigbee.white_label_of, power.source (battery/mains),
power.battery_type, sensors.* (exposes: occupancy, illuminance, temperature, humidity, contact), metering.power,
local_control (derived: Z2M or Matter). Licence: ask coordinator whether MIT converter data may move to licence_grant yes.

### 2.3 USB-IF certification overlay (cables + chargers/power banks)
Adapter: `usbif_products.py` - one GET of /vtm-products/v1/all per refresh (no per-product crawl). Use first as a
`cert.usb_if` attestation joined by model number onto existing chargers/power-banks records (~718 bricks/banks), then a
cables table for retail brands only (~300-450 records after dropping OEM listings). Keys: cert.usb_if (bool + pass date + tid),
cable.max_speed_gbps, cable.pd_epr_240w (e-marker PD 3.1), cable.connectors, charger.total_w_certified.
Risk: usb.org document-library licence text; treat as facts+link, paid no, until USB-IF confirms.

## 3. Recommendation
Start **major appliances** next round (adapters-only, ~9k public-domain records, no new crawl risk). Run the USB-IF
overlay as a one-adapter side task (it strengthens the chargers/power-banks pilots). Queue smart-home after. Separately:
coordinator ruling on www.lg.com (s.0); email NSF (info@nsf.org) for listing-reuse permission - water filters is the
highest-opacity category we cannot reach today, and NSF listings alone would give ~2k+ models.

## 4. Evidence log (2026-11-26, crawler UA)
- robots 200 + terms read, agent: data.energystar.gov (catalog API: 53 datasets), www.bosch-home.com (us/about/imprint/legal,
  us/owner-support/terms-and-conditions: no automated clause), www.brother-usa.com/terms-of-use (copy restriction, no
  automated clause), www.philips-hue.com/en-us/support/legal/terms-conditions, www.evehome.com/en-us/terms-use-privacy-statement,
  www.usb.org (robots; legal text on /document-library/usb4ett), on.dcl.csa-iot.org (REST totals), info.nsf.org (robots; terms on www.nsf.org).
- terms bar automation (human_only): www.lg.com/us/terms, www.geappliances.com/privacy/terms.htm, epson.com/terms-of-use,
  www.thecloroxcompany.com/terms/ (Brita), www.pur.com/pur-terms-of-use/, zerowater.com/policies/terms-of-service,
  www.wqa.org/terms-of-use/, www.bose.com/legal/terms-of-use, www.sennheiser.com/en-us/legal/terms-of-use (TDM reserved),
  www.aqara.com/en/terms/ (personal non-commercial).
- blocked (not retried, no other fetcher): www.nhtsa.gov 403, www.goodyear.com 403, www.usa.canon.com 403, global.epson.com 403,
  www.sony.com + electronics.sony.com 403, www.jbl.com 403, www.nsf.org (Cloudflare on /privacy-copyright), www.bluetooth.com
  (Cloudflare), apps.fcc.gov 503, www.whirlpool.com / www.maytag.com / www.frigidaire.com / www.electrolux.com / www.amd.com
  (HTTP/2 INTERNAL_ERROR, no response). qualification.bluetooth.com: robots `Disallow: /`.
- robots allow, terms not read (not top candidates): michelinman, continentaltire, pirelli, firestonetire, intel, fenixlighting,
  energizer, pny (legal overview only), lexar (terms 404), aquasana, brita (site robots), pur, zerowater.
