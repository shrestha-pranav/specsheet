# Demand survey (A5 PM round 2, 2026-11-24)

Method: WebSearch (standard) plus one WebFetch (Glama listing). No Bright Data, no logins. "[s]" means the claim rests on a
search-result snippet only; "[f]" means the page was fetched. Reddit did not surface directly (site: queries returned
nothing). The demand evidence is therefore forums (PCPartPicker, AVS, FlatpanelsHD, LTT, TenForums), help guides and press.
Our fill rates were measured on 2026-11-24 from docs/api/v1 (index + products, published values only).

## 1. Top use cases
People:
1. **"Can I upgrade it later?"**: laptop and mini-PC RAM soldered or socketed, slot count, and max RAM, per exact config.
   One family can ship soldered and socketed variants, so the advice is to look up the full product number [s]
   https://www.xda-developers.com/find-laptop-upgrade-ram/ , https://www.newegg.com/insider/soldered-vs-upgradeable-ram-laptops-memory-shortage
2. **"Will this hurt my eyes?"**: PWM and flicker on monitors and laptops. TFTCentral retired its flicker-free database because
   "manufacturers now list it", yet buyers still rely on Notebookcheck, RTINGS and LaptopMedia measurements [s]
   https://tftcentral.co.uk/articles/flicker_free_database , https://www.notebookcheck.net/PWM-Ranking-Notebooks-Smartphones-and-Tablets-with-PWM.163979.0.html
3. **"Is this the good version?"**: SSD DRAM, HMB or neither, TLC vs QLC, and component swaps. PCPartPicker users have filed at
   least 7 requests for a DRAM/NAND filter, and staff declined: "lack of documentation from manufacturers", brands "swap
   components ... under the same part number" [s] https://pcpartpicker.com/forums/topic/368774-feature-request-ability-to-see-if-a-ssd-is-dram-less-or-not ,
   https://pcpartpicker.com/forums/topic/426984-additional-storage-filters-for-ssds . Community spreadsheets (NewMaxx) fill the gap.
4. **"Which panel will I get?"**: TV panel type by size. LG confirmed VA in some QNED90T sizes, and Samsung QN90 shipped VA or IPS
   without saying which [s] https://www.flatpanelshd.com/news.php?subaction=showfull&id=1710491852 ,
   https://www.flatpanelshd.com/flatforums/viewtopic.php?t=12546 . Zone counts are given as "up to" per series, not per size [s]
   https://www.digitalcitizen.life/what-up-to-4000-dimming-zones-means-mini-led-tv/
5. **"Will it fast-charge my phone or laptop?"**: PPS for Samsung 45 W. Many banks say only "PD 45W", and a CUKTECH bank's
   Global and CN versions differ in PPS support [s] https://www.dekoelectronics.com/en/blogs/inspirations/best-power-bank-for-samsung-galaxy-s26-ultra .
   ChargerLAB has a full PDO/PPS readout per review, but no searchable list [s] https://www.chargerlab.com/teardown-of-sharge-hypertower-170w-power-bank-x6
6. **"Will one cable run my desk?"**: USB-C video (DP Alt, Thunderbolt) per port, monitor USB-C PD watts and KVM, dock MST/DSC
   limits. Every guide ends with "check the exact model's spec sheet" [s] https://plugable.com/blogs/news/the-usb-c-port-decoder-how-to-tell-if-your-laptop-port-supports-video-charging-or-just-data ,
   https://kb.plugable.com/understanding-mst-multi-display-setups-with-windows-macos-and-displayport
7. **"What do I actually get?"**: Wi-Fi radio config behind "BE19000" (streams per band, 320 MHz only on 6 GHz) and SoC/RAM per
   hardware version [s] https://www.xda-developers.com/wi-fi-7-router-box-number-every-band/ , https://openwrt.org/toh/start
8. **"True running cost"**: purifier AHAM-verified CADR vs claimed, filter cost per year, noise. Today this lives in affiliate blogs [s]
   https://purelivinggear.com/best-air-purifiers-with-low-cost-filters/ ; AHAM Directory is JS-only [s] https://www.ahamdir.com/room-air-cleaners/

Agents:
- OpenAI reports its shopping research at **52% product accuracy** on multi-constraint queries, which include specs [s]
  https://openai.com/index/chatgpt-shopping-research/ . A 220-question benchmark found fabricated product claims in all
  chatbots tested [s] https://www.androidheadlines.com/2026/09/gemini-tops-ai-shopping-hallucination-pricing-error-rates.html
- Agents skip products with missing required fields rather than infer them [s] https://pimberly.com/blog/how-to-get-products-recommended-by-ai-agents/ ,
  so **explicit unknown plus source** is what they need, not a guess.
- RTINGS paywalled its measurements in 2026, citing AI reuse [s] https://www.back2gaming.com/news/rtings-locks-full-test-results-behind-a-paywall-to-combat-ai-scraping/ .
  Agents lost the largest free source of measured TV and monitor data, so a sourced, open, manufacturer-first set is more valuable.
- Existing MCP product servers are **price, stock and retailer** tools (Amazon, idealo, MediaMarkt, Shoptera), plus Icecat
  (22M records, mostly marketing data sheets, Open tier limited) [f] https://glama.ai/mcp/servers?query=product+comparison ,
  [s] https://iceclog.com/icecat-mcp-server-for-smarter-ai-commerce/ . Open Food Facts is the only open, sourced spec MCP.
  **No MCP answers opaque electronics specs (PWM, DRAM, PPS, panel per size) with provenance.** That is our slot.
  Typical agent tool set: search, get_product, options/variants, price/stock [s] https://dev.to/axidort/which-tools-should-an-e-commerce-mcp-server-expose-2e89
  We already have query_specs and match_product. The missing pieces are a compatibility check and "explain unknown".

## 2. Top 10 spec questions we should answer exactly (with source and per-variant identity)
| # | Question | Our status today (published fill) |
|--|--|--|
| 1 | Laptop RAM: soldered / slots / max, per MTM | mem.soldered **0%**, mem.slots **0%** of 2,419 (both mapped in psref-mapping.yaml but not emitted); mem.max 79% |
| 2 | Laptop panel per config: type, nits, refresh, PWM | disp.panel_type/nits_sdr/refresh **0%** (mapped, not emitted); no PWM key |
| 3 | Monitor PWM / flicker-free (+ frequency) | flk.pwm **0%** of 4,133 |
| 4 | SSD cache: DRAM / HMB / none; NAND TLC/QLC; controller; by revision | dram_type 39%, hmb **0%**, nand_type 6%, controller 5% |
| 5 | Charger/power-bank PPS range per port; Wh | pd.pps (bool) 14%, PPS range **0%**, energy_wh 16% |
| 6 | TV panel type per size + local-dimming zones per size | panel.lcd_type 3%, dimming_zones **<1%** |
| 7 | TV HDMI ports that do 4K120 (and which one is eARC) | hdmi.ports_4k120 23%, hdmi.earc 51% |
| 8 | Monitor USB-C: PD watts, DP Alt, KVM | usb.usbc_pd_w 4% |
| 9 | Router radios: streams + max width per band, 6 GHz, SoC/RAM per hw version | streams_5 31%, width_5 19%, has_6ghz 22%, SoC **0%** |
| 10 | Purifier verified CADR vs claimed, filter cost/yr, noise dB | CADR 18% (of 1,142 incl. 925 CARB cert-only), noise 1%, filter cost: no key |
Laptop USB-C per-port capability (charge, DP, TB/USB4) is the strong #11. It feeds docks (section 4).

## 3. Gaps in current categories
- **Coverage before breadth.** Questions 1-3 are our biggest demand and they show 0% on data we already crawl (PSREF publishes
  soldered memory and nits). This is an extraction bug or a gate, not a sourcing problem. Fix it first.
- Laptops: only Lenovo (2,103) and ASUS (316). Missing Dell, HP, Apple, Acer, MSI, Microsoft, Samsung, Framework.
  Dell/HP publish spec PDFs per model, and HP QuickSpecs list soldered memory.
- SSDs: only WD/SanDisk, TeamGroup and Samsung. Missing Crucial, Kingston, SK hynix/Solidigm, Lexar, Corsair, Seagate, ADATA.
  This is the PCPartPicker-requested category, and it is useless without Crucial (P3/P5, the QLC/DRAM-less poster child) and Kingston (NV-series swaps).
- TVs: **no Sony**, Hisense 5, TCL 70. LG makes up 915 of 1,371 rows. The panel-lottery brands (Samsung/LG/TCL/Hisense) need per-size rows.
- Routers: missing eero, Google/Nest, Ubiquiti, GL.iNet, Linksys. hw-version identity (v1/v2) is the key requirement. OpenWrt ToH is a
  structured cross-check (toh.json, nightly) [s] https://github.com/openwrt/toh-openwrt-org (license check needed: wiki is CC BY-NC-SA, so link only).
- Power banks: missing Baseus, Xiaomi and Samsung's own 45 W pack (the PPS reference). Anker has only 22.
  Chargers: OK brands; add per-port PDO/PPS tables as a structured object.
- Robot vacuums: missing Shark and eufy (US volume brands). Power strips: missing APC, Belkin.
- Purifiers: add `filter.replacement_cost_usd` + `filter.life_months` (cost per year derived) and `noise.db_low/high`.

## 4. Next 3 categories (after the gaps above; scored Demand / Poorly-served / Feasibility, 1-5)
| Category | D | P | F | Why |
|--|--|--|--|--|
| **USB-C docks & hubs** | 5 | 5 | 4 | MST/DSC/alt-mode/PD per port is hidden in manuals; identity is clean (CalDigit, Plugable, Anker, Belkin, Dell WD/HP model numbers); reuses the charger PD schema; joins laptop ports for a "will this work" query |
| **Mini PCs** | 4 | 4 | 4 | Soldered vs SO-DIMM, single-channel N100, OCuLink/USB4, 2.5GbE [s] https://woitzik.dev/blog/best-mini-pc-homelab-2026/ ; reuses the laptop profile; Lenovo Tiny is in PSREF, Beelink/Minisforum/ASUS NUC publish spec tables |
| **Headphones / earbuds** | 5 | 4 | 3 | Codecs, multipoint, and whether LDAC+multipoint coexist (sources contradict) [s] https://www.soundguys.com/the-best-bluetooth-ldac-headphones-29515/ ; RTINGS paywall left the gap; FCC IDs help identity |
Runners-up: ENERGY STAR major appliances (F=5 regulator data, low opacity; good reliability showcase), microSD
(sustained-write data is blog-grade [s] https://github.com/JoyousJohn/sd-bench ; counterfeits are a seller problem, not a model one).
Rejected again: USB-C cables (no model identity), CPUs/GPUs, phones (saturated).

## 5. Killer queries for the free deploy (each must return exact rows with source links and visible "unknown")
1. "Lenovo/ASUS laptops, 32 GB+ possible, RAM **not soldered**, 14 inch, under 1.4 kg" (Q1).
2. "Monitors 27 inch 1440p+ with **no PWM** and USB-C PD >= 65 W" (Q3+Q8).
3. "NVMe 2 TB, **DRAM (not HMB)**, TLC" with the revision caveat shown (Q4).
4. "Power banks that do **Samsung 45 W (PPS >= 4.5 A @ 9-11 V)**" with the PDO table rendered (Q5).
5. "65 inch TVs: what panel does each size use?" with a per-size panel/zone grid for one family (Q6).
6. "TVs with >= 4 HDMI ports at 4K120" (Q7).
7. "Routers with 4x4 on 5 GHz and 6 GHz, by hardware version" (Q9).
8. "Purifiers for 400 sq ft ranked by verified smoke CADR per filter-dollar" (Q10).
9. Agent demo: `match_product("ThinkPad T14 Gen 5 21ML003XUS")` then "is the RAM soldered?", showing the sourced answer or
   an explicit `unknown` with the missing source, never a guess.
Showcase a query only when its fill rate is >= 80% in the shown slice. Otherwise frame it as "help us fill this" (request loop).
