# Laptops: source observations (A1, 2026-11-22)
Fetched with curl/WebSearch only. Samples: Lenovo PSREF ThinkPad T14s Gen 6 (Intel) PDF; PSREF HTML page; Apple MacBook Air 13 (M5) specs; ASUS Zenbook S 14 UX5406 techspec; Dell XPS 13 9350.

## Lenovo PSREF (best source)
- psref.lenovo.com/syspool/Sys/PDF/ThinkPad/<Family>/<Family>_Spec.pdf: plain PDF, 200 OK, pdftotext -layout works, ~11 pages, dated footer ("November 10 2026").
- Detail HTML (/Detail/...?M=<MTM>) is a JS app: 6 KB shell, no specs via curl. Use the PDFs; MTM-level model list likely needs the JSON API behind the app (not investigated).
- Granularity: per FAMILY (platform variant), with bullet lists of all options. Not per MTM in the PDF. Per-config binding is a model table (not in the PDF text I read; grep found no MTMs).
- Strong on: soldered vs slot (Max Memory + Memory Slots), memory type with runtime-speed footnote, M.2 slot form/PCIe gen by CPU series, Wh, adapter W + PD version, display table (size/res/touch/type/nits/contrast/gamut/refresh), WLAN chip, ports incl. per-port "USB PD 15-65W and DisplayPort 2.1".
- Weak: weight is "starting at" per platform; no per-port side in text (diagram only); no PD-out per port; no TGP in sample; panel vendor absent; "**" marks region/config-dependent items.

## Apple tech specs
- apple.com/macbook-air/specs/ 200 OK, server-rendered, ~26 KB text. Per model, with BTO "Configurable to" lists. Chip/GPU-core, RAM, SSD tuples all soldered (unspecified). Gives Wh, charger W, nits, ports with TB4/USB4 40Gbps, display-out limits, weight, camera, Touch ID. No part number/model identifier or warranty on page; no wifi chip model beyond "N1".

## ASUS
- asus.com .../techspec/ 200 OK server-rendered. Family-level: one cell concatenates every CPU/panel option (e.g. 7 CPUs, 4+ panels with touch, Hz, nits, gamut, HDR cert). Cannot tell which combo ships in which SKU without the model code table; pairing needs the per-SKU listing. Includes NPU TOPS per CPU.

## Dell
- dell.com support pages return 403 to curl even with browser UA. dl.dell.com PDFs are fetchable but the one indexed for 9350 was the 2015 XPS 13 (old model with same name), a trap: name reuse across years. Current Owner's Manual has Memory / External ports / Display / Multiple display matrix sections (confirmed via search only). Dell spec data is per family; configs set at ordering by service tag.

## Not fetched
HP QuickSpecs (support.hp.com timed out; PDFs exist per product, per-SKU option tables, strong on memory slots and PD, from knowledge not verified); Framework (KB URL 404, store page 404 for guessed slug; Framework publishes per-edition + module specs); Microsoft Surface (guessed URL 404).

## Cross-brand takeaways
- Identity name collisions are pervasive (Dell XPS 13 9350 2015 vs 2024; Intel vs AMD "Gen N").
- Same family spans Lunar Lake and Arrow Lake with different weight, wifi, PCIe gen, Pluton, color, memory speed. Treat platform variant as its own level.
- Hidden/unpublished officially: CPU PL1/PL2, panel vendor, per-port PD out and side, real TGP for some, SSD model/vendor. These need reviews (notebookcheck) as secondary evidence with provenance.
- Unit traps: gamut NTSC vs sRGB vs P3; nits SDR vs HDR peak; Wh vs hours; GB vs GiB.

## Zero-fill audit (A2, 2026-11-24): what PSREF publishes vs what we dropped
- **We dropped it (fixed).** `mem.soldered`, `mem.slots`, `disp.panel_type`, `disp.nits_sdr`, `disp.refresh` (+ `mem.type`, `disp.resolution`)
  all live inside PSREF multi-target cells (Display, Memory Slots, Memory; psref-mapping.yaml `maps_to` lists). The adapter emits each cell
  once under one key (Display -> disp.size) and import.py only maps single-target columns, so the other targets were never claimed
  (`unmapped` reason `psref_column_multi_target_needs_parser`), and the Memory Slots literal could not normalise to an object. Fix:
  `import.py+psref-split@1` (crawler/adapters/_lcell.py), policy claim/psref-split@1.
- **PSREF does not publish it.** Refresh rate is absent from ~25% of US Display cells (mostly 2020-23 FHD TN/IPS 60 Hz panels):
  no 60 Hz is inferred. 23 Strix Halo rows state "Unified memory, 16-channel" / "LPDDR5X ... Unified Memory": neither slots nor
  soldered is stated, so both stay empty. Dual-mode panels ("240Hz / 440Hz") carry no single refresh value. "(peak)"-only nits are not SDR.
- **Agreement checks.** soldered rows: Max Memory == Memory size in 619 of 624 (5 rows have a family-level "64GB soldered" max on a 32GB MTM:
  a PSREF cell inconsistency, left as published). socketed rows: max > size in 969, == size in 177 (fully populated slots, fine).
