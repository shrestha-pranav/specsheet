# SSDs: who publishes what (US, 2026-11-23)

Evidence this round: Samsung 990 PRO datasheet PDF (fetched, pdftotext), Kingston NV3 datasheet PDF (fetched),
WebSearch on the WD SN550 revision case. Crucial pages return a WAF "Request Rejected" to plain curl; WD product
pages returned a JS shell with no spec text; WD datasheet URL guess 404'd; Sandisk URL guess 404'd.

## Publishers
- **Samsung (V)**: proper datasheet PDF per line: controller ("Samsung in-house"), NAND (V-NAND TLC), DRAM size+type,
  form factor, seq + 4K QD1/QD32 IOPS, power (idle/active/L1.2), TBW per capacity, Opal V2/IEEE1667, part numbers
  per capacity (MZ-V9P1T0B/AM). Omits SLC cache size and post-cache speed. Test footnotes say writes are measured with
  TurboWrite active.
- **Kingston (V)**: 2-page datasheet, part numbers listed (SNV3S/1000G, 2230 SNV3SM3/..), TBW per capacity, but NAND is
  just "3D" and controller/DRAM are unnamed ("Gen 4x4 NVMe controller"). Seq speeds vary per capacity. No IOPS.
- **WD/SanDisk (U)**: product pages JS-rendered; datasheet PDFs exist on documents.westerndigital.com (URLs unguessable).
  WD confirmed the 2021 SN550 NAND+firmware change but did not rename the model.
- **Crucial/Micron (U)**: WAF blocks plain HTTP; pages list NAND type and TBW; P2 was the TLC->QLC case.
- **TechPowerUp SSD DB (V: blocked)**: /ssd-specs returns 403 to curl; robots.txt prohibits automated data mining
  and AI/commercial use without written permission. Do NOT scrape; cite individual review pages at most, or ask for permission.
- Others (SK hynix, Seagate, Corsair, Teamgroup, Sabrent, Lexar, PNY, ADATA/XPG, Acer Predator): not fetched; assumed HTML spec
  tables with seq/TBW and often no controller/NAND (U).

## Opacity (tier=core)
controller, NAND maker/type/layers, DRAM vs DRAM-less/HMB, SLC cache size, post-cache sustained write, revision marker (FW string,
label date code, NAND part). Official sources rarely carry these; reviewers/teardowns do, tagged with provenance and revision.

## Design notes
- Identity: capacity part number is the buyable configuration; `revision` is a real level here (differs from other categories because
  the part number does not change). Revision proof = `nvme id-ctrl` model/FW, label date code, NAND part.
- Capacity is a variant axis; seq speed, TBW, DRAM size, and sides vary per capacity, so those specs sit at configuration level.
- Portable SSDs: separate enum values (usb standard, bridge chip, IP rating); internal drive may differ per revision.
- PS5 compat is a derived claim: PCIe 4 x4, M.2 2280, heatsink fit (~11.25 mm height limit, Sony); PS4 uses only external/2.5in.
- Speed claims need condition `cache_state`; headline = in_slc_cache (as makers publish).
- Brands split: Samsung/WD/Micron/SK hynix/Solidigm make NAND and controller; others buy Phison/SMI/Maxio and NAND lots, which is why they swap.

## Open
- Verify Crucial and WD datasheet access (browser fetch or coordinator approval); confirm P3 vs P3 Plus DRAM/NAND per capacity.
- Revision-level sources need a ToS check (TechPowerUp, Tom's, StorageReview) before storing facts beyond citation.

## A2 coverage r2 (2026-11-24)
- sandisk_ssd@3 / teamgroup_ssd@3: silicon facts from explicit page prose (crawler/adapters/_ssdprose.py), quote kept as raw, only where the table
  is silent. Bare "DRAM-less" (SanDisk SN7100/SN7100S/SN7100X) is NOT mapped: the enum has no plain `dramless`, and the page states neither HMB
  nor no-HMB. Open for A1: add a `dramless` (HMB unstated) value, or keep these unknown.
- TEAMGROUP "use InnoGrit controller solutions by default" (G50/G70 lines) is hedged: not taken.
- New source kingston-us-ssd (datasheet PDFs only; product pages blocked). See merchants.md.
- Coverage r3 (2026-11-24): A1 question answered by the coordinator. A bare "DRAM-less" now maps to the new enum value `dramless` (HMB unstated;
  hw.hmb_support stays unknown, never assumed): SN7100S 16, SN7100 4, SN7100X 2 configurations (_ssdprose, sandisk_ssd@4). Open: `_ssd.dram()`
  still maps a TABLE cell "DRAM-less"/"None" to dramless_none, which assumes "no HMB"; switching it to `dramless` would touch every SSD parser.
- Kingston NV2 / NV1 / A2000 older datasheets now parse (kingston_ssd@2). NV2/NV1 print NAND "3D" only and no DRAM row, so those stay unknown.

## Preset fill (A2, 2026-11-24): coordinator rulings 4 and 5
- Ruling 5 (`_ssd.dram()`, every SSD parser bumped: samsung_ssd@3, sandisk_ssd@5, teamgroup_ssd@5, kingston_ssd@3): a TABLE cell reading
  "DRAM-less" / "None" / "No" = `dramless` (HMB unknown). `dramless_none` only when the cell explicitly denies HMB ("no HMB", "HMB: No").
  A cell naming HMB affirmatively = `dramless_hmb` (Samsung 990 EVO / 990 EVO Plus "Cache Memory: HMB (Host Memory Buffer)", 7 SKUs).
  TEAMGROUP "DRAM Cache: NO" (122 configurations) moves dramless_none -> dramless. Kingston "DRAM cache: No" would read the same (none printed today).
- Ruling 4 (portable `if.protocol`, affirmative only): new enum value `usb` (USB-attached; UASP/BOT not stated). Written only when the maker's
  interface cell names a USB 2/3.x interface; `usb_uasp` only if it says UASP. Thunderbolt or USB4 cells (PCIe may be tunnelled), connector-only
  cells (TEAMGROUP M200 "Connector: USB Type-C") and portables with no interface row (SanDisk Extreme Portable V3 etc.) stay unknown. Never not_applicable.
- Internal drives with no Interface row: nvme / sata_ahci from the maker's own product name when it states exactly one (SanDisk SKU title, else
  og:title: SN8100, SN5100, SN7100S, NAS 800, Optimus GX PRO 850P, WD Green SATA; Samsung JSON-LD name "... SSD NVMe™ M.2" for 990 PRO/990 EVO).
  _ssd.interface() now reads "PCIe® 5.0 x4" (the ® broke the regex: Samsung 9100 PRO, 980 PRO gen/lanes/protocol).
- Not done: SanDisk NVMe DRAM beyond the prose already read (no datasheet PDFs are linked from the crawled pages, and documents.sandisk.com has
  no data/source-policy.yaml entry); Kingston NV3/NV2/NV1 datasheets print no DRAM row.

## Preset fill r2 (A2, 2026-11-24): coordinator ruling 3, SanDisk datasheets
- New source `sandisk-us-ssd-datasheets` (`crawler/adapters/sandisk_datasheets.py`): the datasheet PDFs each sandisk.com internal-SSD line page
  links (`/tools/documentRequestHandler?docPath=...` -> documents.sandisk.com; www.sandisk.com robots allows /tools/, documents.sandisk.com has
  no robots.txt). 35 fetched, all 200. Only `hw.dram_type`, only from a DRAM / DRAM CACHE row that is one value spanning every capacity column,
  tied to the line page's configurations through the MODEL NUMBERS row. Yes = dram (SN8100, NAS 800, Optimus GX PRO 8100 / 850X / 850P);
  Host Memory Buffer = dramless_hmb (Optimus 5100, GX 7100 / 7100M / 7100X); "No" = dramless (SATA 320 / 520 / NAS 600, ruling 5).
- No DRAM row (silence, unknown): WD_BLACK SN850X, SN850P, SN770M, SN7100, SN7100X, WD Blue SN5000 / SN5100, WD Green SN3000, PC SN5000S /
  SN5100S / SN8000S, SN7100S, SSD Plus NVMe. The Optimus GX PRO 850X datasheet says DRAM Yes, but it is a separate line page: nothing transfers
  to the WD_BLACK SN850X configurations by name similarity.

## SSD DRAM from maker publications (A2-ssd, 2026-11-25; brief coord-2026-11-25-ssd-dram-sources)
- New source `samsung-ssd-datasheets` (`crawler/adapters/samsung_datasheets.py`, pending claim/mfr-ssd-samsung-datasheet@1): the 27 internal-SSD
  datasheets linked from semiconductor.samsung.com/consumer-storage/support/documents/. hw.dram_type only, only when every cell of the (DRAM) Cache
  Memory row gives one value; binds to printed model codes equal to samsung-us-ssd configurations. 28 claims, 27 agree with the page, 1 new
  (980 PRO 1TB MZ-V8P1T0B/AM). 980 PRO with Heatsink / 970 / 860 / 850 / 950 / 960 sheets name no configuration we carry.
- WD/SanDisk: every maker document the line pages link was read (35 datasheets + SN700 / SN350 / PC SN810 product briefs, the client-NVMe brochure,
  the Internal SSD Colors Portfolio brochure). Only SN7100 is called "DRAM-less" (already filled). SN850X, SN850P, SN770M, SN700, SN5000/5100,
  SN3000, SN350, PC SN810/5000S/5100S/8000S: no DRAM statement anywhere on sandisk.com documents. Silence, not DRAM-less.
- Lead, NOT used: SanDisk support KB a_id 51469 (support-eu.sandisk.com) says a firmware update fixes "an issue with the HMB" on certain 2TB
  models (third parties list WD Blue SN5000 2TB). That says HMB is used, not that the drive is DRAM-less: inference, so not taken.
- Kingston: the NV3 product page / press release say "DRAM-less ... Host Memory Buffer", but www.kingston.com HTML returns 403 (Cloudflare) to
  the crawler (press article 74018 checked once). Datasheets (reachable) print no DRAM row. Route: human-cited E2 maker URL via corrections.
- TEAMGROUP M200 / PD40 / Thunderbolt 3: the DRAM Cache column prints "N/A" = no statement.

## SSD NAND type from maker publications (A2-st r7, 2026-11-26; brief coord-2026-11-26-r7-ssd-tv)
- No new fetches: stored datasheets and pages only. Explicit TLC / QLC / MLC for the SKU's own table only; "3D NAND" / "V-NAND" alone = nothing.
- samsung_datasheets@2: "NAND Flash Memory" row, one spanning cell ("V-NAND TLC", "3bit MLC" = tlc, "4bit MLC" = qlc, "2bit MLC" = mlc).
- sandisk_datasheets@2: NAND / NAND TYPE row bound per table to its own MODEL NUMBERS (SN3000: QLC 1-2 TB, TLC 500 GB table). SN5000 prints
  TLC | QLC per capacity column (nothing); PC SN5000S / SN5100S / SN8000S / SN7100S / SN850X sheets print no MODEL NUMBERS row (nothing binds).
- teamgroup_ssd@6: intro paragraph read alone when the page pass found nothing (Z44Q, Z44A7Q). Lead not used: VULCAN Z QLC (SATA) says QLC
  only in its product name and meta description; the body prose never states it.
- Still silent anywhere we may fetch: TEAMGROUP G50 / G70 / MP33 / MP44 / GE PRO / NV5000 / NV10000 etc., Kingston NV1/NV2/NV3 ("3D"),
  WD SN700 / SN350 / SN810 / SN850P, SanDisk SSD Plus NVMe, Samsung 990 (MZ-V9V, no datasheet), portables.
