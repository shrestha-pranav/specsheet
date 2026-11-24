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
