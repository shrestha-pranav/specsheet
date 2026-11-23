# SSDs: identity rules (A2, 2026-11-23)

Levels follow spec-profile.yaml: family > model > configuration > revision > package. Adapters only emit observations (identifiers
with scheme, package_level, market, optional `parent`); the importer/matcher decides entities. Rules below are what they should apply.

## What each level is, per brand (measured on the three built adapters)
| level | Samsung (samsung-us-ssd) | WD/SanDisk (sandisk-us-ssd) | TEAMGROUP (teamgroup-us-ssd) |
|---|---|---|---|
| family (`series`) | product slug before `-sku-` (990-pro-pcie-4-0-nvme-ssd-4tb) | line page slug (wd-black-sn850x-nvme-ssd) | model dir (cardea-z44l, mp44) |
| model (`mfr_model`) | part stem before the capacity token: MZ-V9P, MU-PC | line page slug (one model per line; Model Number prefixes are not stable stems) | P/N stem TM8FPP |
| configuration (`mfr_sku`; one scheme, no mfr_part alias) | MZ-V9P4T0B/AM (incl. region suffix) | Model Number WDS100T2X0E | TM8FPP002T0C129 |
| package | /AM vs no-slash OEM vs `CW`/`GW` heatsink/edition letters are separate parts (configurations), colours are separate parts too (MU-PE1T0K/R/S) | orderable `-00BCA0` tail (`x_orderable_sku`) | trailing `C1xx/C3xx` batch code (`x_batch_code`) |
Key facts:
- **Capacity is a configuration axis, not a model axis**: seq speed, TBW, DRAM size and even write speed change per capacity
  (Z44A5 512GB writes 2,500 MB/s vs 4,500 MB/s at 1-2TB; 990 PRO DRAM 1GB -> 2GB -> 4GB). Never put those claims on the model.
- Heatsink / colour / edition variants change the part number but not the silicon. They are configurations of the same model; the matcher
  should group them under one model via the stem (MZ-V9P1T0B/AM + MZ-V9P1T0CW) and `therm.heatsink` is the differing claim.
- Samsung suffix: `/AM` = Americas retail, `/BW`,`/EU`,`/WW` world/other, no slash = OEM or channel part. Do not merge across suffix on part number alone:
  keep `market`, and let `stem_links` (category.yaml: cut at `/`, strip market suffix) propose the cross-market alias.
- Samsung page defects exist (sitemap slug says 1tb but SKU is 2T0B; 990 PRO 2TB `GW` spec row says capacity 1TB; a Controller cell holding the DRAM string):
  the part number is trusted, the claim is stored with raw and will conflict visibly instead of being fixed.
- WD: the same `Model Number` can ship under two orderable suffixes (SN850X 8TB uses -00CDD0, the others -00BCA0). Treat the suffix as
  a package identifier AND as a revision candidate (see below), never as a different model.
- The WD `mfr_model` is the line slug on purpose: Model Numbers are SKU-shaped (WDS100T2X0E, SDSSDE61-1T00-G25) with no stable stem, and `WDS`
  alone would merge SN850X, SN770 and Blue SN580. Measured: 74 line pages = 309 orderable SKUs = 269 Model Numbers, so 40 SKUs are the same
  Model Number under another orderable suffix. SDSSDE61 alone ships under 12 suffixes (-G25, -G25M, -G25B, -GBH, 4T00-G25...): colour/bundle/region
  packages and possibly hardware lots; none is proof of a revision.

## Revision (silent hardware change under one part number): this category's real problem
Official pages almost never name controller or NAND (WD and TEAMGROUP: never; Samsung: controller as 'in-house', NAND family only), so the adapters
cannot see revisions. Evidence that creates a `revision` child (never inferred from a retailer title or one review number):
1. `nvme id-ctrl` / SMART model string + firmware revision (fw.version): the only hard marker; first-class `fw_string`.
2. Label date code / PCB revision photographed by a reviewer or buyer (`hw_rev`).
3. NAND part number or die marking from a teardown (hw.nand_part), controller part number.
4. Maker statement (WD confirmed SN550 TLC->QLC in 2021; Crucial P2 TLC->QLC).
5. Suffix change in the orderable SKU (WD `-00BCA0` -> `-00CDD0`, TEAMGROUP `C101` -> `C129`) is a CANDIDATE signal only: it also encodes
   region/channel. Record both suffixes under the configuration; a revision child needs evidence from 1-4.
Known multi-revision families (from reviews, not from the adapters; tier U until sourced): Samsung 970 EVO Plus (Phoenix -> Elpis, 2020),
Samsung 980 (DRAM-less, HMB), WD Blue SN550 (2021), WD Blue SN570/SN580 NAND changes, Crucial P2 / BX500, Kingston NV1 / NV2 (Phison vs SMI controller,
different NAND per batch), TEAMGROUP MP33 / MP34 (controller + NAND lots). Brands that BUY controllers and NAND (Kingston, Teamgroup, PNY, Lexar,
ADATA, Corsair, Sabrent) swap at will; brands that MAKE them (Samsung, WD/SanDisk, Micron/Crucial, SK hynix, Solidigm) swap less often but did.
Revision claims go on the revision child with `conditions`/locator `hw_rev` or `fw_string`; the configuration keeps the maker's claim and lists
the measured one under alternatives.

## Cross-source matching
- Part number is the hard key; GTIN/UPC only from maker pages or B&H/Best Buy (retail UPC = candidate alias). None of the three built sources prints a GTIN.
- Region suffix stripping (stem_links): Samsung `/AM`, `/WW`, `/BW`, `/EU`; HP-style `#`: not used here. WD: strip nothing from Model Number; the `-00XXXX`
  tail only exists on orderable SKUs.
- Retail titles ('SAMSUNG 990 PRO SSD 2TB PCIe 4.0 M.2 2280') are aliases (marketing_name/listing_title) only.
- Skip lists (profile `skip_alias_pattern`): HDDs, enclosures, memory cards, USB flash drives, enterprise U.2/E1.S. The sandisk adapter drops ultrastar, dc-, sn861/sn655,
  industrial ix-sn530, test-pages, recertified/clearance copies at discovery; keep that in the adapter, not the importer.

## Traps seen in the data
- Samsung 'V-NAND 3-bit MLC' means TLC (also '3bit MLC' on 870 EVO; the 990 PRO 4TB row says plain 'V-NAND TLC' while 1/2TB say '3-bit MLC' = a per-capacity NAND wording change worth a revision look). Adapter maps by bit count, raw kept.
- WD 'Endurance (TBW)' prints `600units`; 'Random Read 800K IOPS' has no queue depth, so it is NOT mapped to the qd32 key (profile keys carry QD).
- Headline speeds are in-SLC-cache (`perf.cache_state=in_slc_cache`); post-cache and sustained are never on these pages.
- Portable SSD 'Transfer Rate up to 800MB/s' is a read figure for the WD/SanDisk portables (mapped to seq_read with raw kept).
- TEAMGROUP 'DRAM Cache: NO' = DRAM-less, HMB use unstated: `hw.dram_type=dramless_none` is the page's statement, not a verified fact; reviewers decide dramless_hmb.
- Capacity is decimal GB as printed (1TB = 1000 GB); never convert to GiB.
