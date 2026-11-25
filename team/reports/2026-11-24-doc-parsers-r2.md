# A2/A3 doc parsers r2 (2026-11-24): SSD and monitor documents
**`RELEASE_DRY_RUN=1 scripts/release.sh "doc parsers ssd+monitor"`: rc 0.** Strict parsers, all tests and smokes pass, budget ok, local gh-pages d064d479. Nothing committed or pushed.
- **Decide (pending, locked by the dry run):** `claim/document-spec-r2@1`. Extractor `docspec@1`, transform `docspec-attach@1` (fingerprint pinned). Keys: if.protocol, hw.dram_type, hw.nand_type, hw.controller, flk.pwm, usb.usbc_pd_w. It lives in a new module, so docattach@1 still hashes to its pinned value (`sha256:352d0e…`).
- **Decide (identity, one widening):** a datasheet that prints only a base model number now matches SKUs carrying a suffix ('SDSSDE70' matches SDSSDE70-2T00-G25). This is the same rule sandisk_datasheets@1 uses. Base must be 6+ chars with letters and digits.
- **Decide (multi-model):** a document that names a same-brand model which is not on any page linking it attaches nothing.
- **Fixed a discovery bug:** documents.py's dedicated-adapter skip matched the handler name `documentRequestHandler`. That skipped all 90 SanDisk links, including the portable/external datasheets no adapter reads. 53 of them are now `fetch`; 34 internal datasheets stay with sandisk_datasheets@1.

## Documents
- **Fetched:** 153 GETs at 1 req/s per host, honest UA, robots respected: 150 ok, 3 404.
  - 20 Samsung spec sheets, 64 TEAMGROUP, 53 SanDisk/WD, 16 monitor sheets (15 LG, 1 DisplayHDR).
  - No blocks. The ssd and monitor categories have nothing left unfetched except the 3 404s.
- **Extracted and parsed:** 134 SSD and 16 monitor documents, text layer only (0 OCR).
- **Proposals:** 143 model_not_named, mostly SanDisk portable datasheets and TEAMGROUP sheets that print a series name but no SKU. 14 multi_model.
- **Power-bank PPS (scope item 3):** no deferred documents exist. All power-bank PDFs were fetched last round and their 36 proposals are model_not_named, so there was no work to do.

## New claims (all accepted under @1; 145 total, 127 agree with an existing page value, 0 conflicts)
- **ssds (130 claims, 18 new values):**
  - if.protocol usb: 39 claims, 12 new (SanDisk Extreme Portable V3 SDSSDE70/7S, TEAMGROUP TX2MAX).
  - hw.dram_type: 85 claims (24 dram, 61 dramless), 6 new: dram on PC SN8050S.
  - hw.nand_type tlc: 6 claims, all agreeing with page values.
  - Thunderbolt and USB4 cells (P7/P9, PRO-G40, Extreme PRO USB4) and connector-only cells (M200) correctly set nothing (ruling 4).
- **monitors:** 14 flk.pwm none and 1 usb.usbc_pd_w (90 W). All corroborate existing LG page values, so fill is unchanged. The LG sheets cover old, mostly non-USB-C models.
- **Not emitted:** a sheet's "DRAM Cache NO" next to a page dramless_hmb. It is the same fact, less specific, and would show as a false conflict (4 TEAMGROUP MP44Q rows).

## D8 preset fill (docs/api/v1/presets.json), before -> after
- **ssd-dram-2tb, hw.dram_type:** 238/372 64.0% -> 244/362 **67.4%**. Still fails (needs 80%). 10 USB rows left the scope.
  - Left: WD SN850X/SN850P/SN7100/SN5x00 (no DRAM row on any maker document) and Kingston NV3 (dedicated adapter).
  - Also left: USB4/Thunderbolt portables, which stay unknown by ruling.
- **no-pwm-usbc-monitor:** flk.pwm 68.5% and usb.usbc_pd_w 82.3%, both unchanged. No in-scope monitor has a deferred document.
- **power-bank-samsung-45w:** pd.pps 15.6%, unchanged.

## Shared-file changes
- **Edited:** `crawler/documents.py` (new doc_basename() and handler docPath classification), `scripts/import.py` (+3 lines: DS import, fingerprint, DS.apply after DA.apply).
- **Data:** `data/decisions/policies.yaml` (+1 pending policy) and its lock line, `data/source-policy.yaml` .7 (images.teamgroupinc.com as a maker host).
- **New:** `crawler/adapters/_docspec.py`, `scripts/docspec_attach.py`, `tests/test_docspec.py`.
- **Regenerated:** raw/_documents/discovery.json, team/queue/coverage-audit.md, plus the build outputs.
- **Known gap:** coverage_audit.py counts only docattach categories, so it lists the 134 SSD documents as "fetched, no parser". Teach it about DS next.
