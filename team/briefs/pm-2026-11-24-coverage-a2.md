# Brief: fill the zero-coverage core specs, then add missing brands (PM round 2). Owner: A2. Read common.md + product/demand-survey.md.
Measured 2026-11-24 on published docs/api/v1. Priority is **fill rate on core opaque specs before new categories**.
P0 (extraction, data we already have):
1. Laptops: `mem.soldered`, `mem.slots`, `disp.panel_type`, `disp.nits_sdr`, `disp.refresh` are 0% across 2,419 rows, yet
   research/laptops/psref-mapping.yaml maps all of them and PSREF publishes them. Find out whether the parser, the mapping or the
   licensing gate drops them. Fix it, and re-check that `mem.max` (79%) and `stor.slots` agree with them. Target >= 90% on Lenovo.
   ASUS: per-SKU pairing from the model-code table (laptops/notes.md).
2. Monitors: `flk.pwm` is 0% of 4,133. Maker spec pages often say "Flicker-free" (an explicit claim; store as a maker claim). Target
   >= 50% on Dell/LG/ASUS/BenQ/MSI. `usb.usbc_pd_w` is at 4%: extract it wherever a USB-C upstream port is listed.
3. Power banks + chargers: parse PDO/PPS lines (maker pages often print "PPS 3.3-21V 5A") into `pd.pdo_table` (A1 adds the key).
   energy_wh is at 16%: most labels print Wh; take it from the label or manual, never compute it from mAh.
4. SSDs: `hw.dram_type` 39%, nand 6%, controller 5%. Maker datasheets first. For revision swaps, record `hw.revision_note` from
   press (Tom's Hardware/The Register cited in research/category-survey.md) as secondary-evidence notes.
P1 (brands, per demand-survey.md section 3; manufacturer sites only, robots respected, blocked → merchants.md):
- SSDs: Crucial, Kingston, SK hynix/Solidigm, Lexar, Corsair, ADATA (the PCPartPicker-requested category is useless without Crucial/Kingston).
- TVs: Sony, Hisense, TCL (US lines), **one row per size** with its panel type, where the maker states it.
- Laptops: Dell, HP (QuickSpecs list soldered memory), Apple, Acer, MSI. Routers: eero, Google/Nest, Ubiquiti, GL.iNet, Linksys, with hw version.
- Power banks: Baseus, Xiaomi, Samsung 45 W pack. Robot vacuums: Shark, eufy. Power strips: APC, Belkin.
Rules: new auto-accept policies land `approval: pending` with explicit allowlists. OpenWrt ToH (wiki CC BY-NC-SA) and RTINGS
(paywalled) are cross-check/link-only: never republish their values. Report per category: rows added, before/after fill for the
keys above. team/reports/2026-11-24-a2-coverage.md (<=60 lines).
