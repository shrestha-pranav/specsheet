# A2 round 3: power strips (2026-11-22)

## Results first
- **Unmapped (import.py `unmapped` table)**: 307 -> **100** rows overall; power-strips 210 -> **3** rows (17,149 -> 5 occurrences). Remaining 97 are laptops (PSREF columns / dell etc. labels), not touched.
  Mechanism: `research/power-strips/label-mapping.yaml` (rules first-match; `maps_to`+transform -> claim `import.py+label-mapping@1`, or `ignore` with reason; table `ignored_labels`: 175 label rows / 13,053 occurrences). Left unmapped on purpose: Tripp Lite `Switches` (1 odd value), CyberPower `Plug Style` "Low Profile" (3), `USB Charge Port Type` "2" (1).
- **Entities / claims (power-strips, whole DB)**: 883 entities, 12,024 claims (was 539 entities, 6,428 claims).
| brand | models | configs | packages | claims |
|---|---|---|---|---|
| tripplite | 235 | 12 | 0 | 5,074 (3,882 adapter + label-mapping) |
| cyberpower | 280 | 8 | 4 | 5,073 (2,546 + dataline/label-mapping) |
| byjasco (GE/Philips) | 215 | 0 | 0 | 1,215 |
| belkin | 51 | 5 | 1 | 466 |
| anker | 11 | 11 | 0 | 56 |
| baseus | 11 | 4 | 0 | 53 |
| furman | 30 | 0 | 0 | 48 |
| austere | 5 | 0 | 0 | 39 |
| ugreen | 0 | 0 | 0 | 0 (174 products, none has AC outlets: Nexode USB chargers/docks) |
All 1,859 new crawl-brand claims and their identifiers validate against `record.schema.json`.

## What changed
1. **Class adapters**: `tripplite.py` -> `TrippLite`, `cyberpower.py` -> `CyberPower` (discover/fetch/parse(snap, blobs, profile), runner `_run.py`; `cyberpower.py docs` downloads datasheets). Re-parsed offline from existing snapshots: output identical to round 2 (claims 0 diffs).
   `FnAdapter` shim removed from `registry.py`. `_run.py`: `wants()` hook + tolerant of round-2 discovery.json rows. Both adapters now emit ONE `surge.dataline` list claim (was a bool in a list key for Tripp Lite).
2. **crawl.py brands**: new `crawler/adapters/crawlpy_strips.py` reads `raw/<slug>/products/*/{extract,feed,http}.json` (+ Belkin page text 'Technical Specifications') read-only; registered in `registry.SOURCES` (anker, belkin, ugreen, baseus, byjasco, furman, austere). Gate counts: anker 11/296, belkin 54/4401, baseus 11/241, byjasco 216/1419 (769 smart/lighting/battery, 310 accessories, 124 plain extension cords excluded), furman 30/65 (15 are 230 V), austere 5/18, ugreen 0/174.
   Claims carry locator `where` + quote. Two different joule figures on one page are two claims (-> `conflicted`).
3. **Grouping**: Belkin colour codes -> configuration with own claims (identity.md round-3 section); Anker/Shopify extra variants -> configurations; `import.py` do_strip builds configs, model inherits when it has no page of its own; PACKS extended (5PK/6PK/10PK).
4. **APC/Schneider**: `https://www.se.com/us/en/product/download-pdf/P11VNT3` via shared client -> **404** (not 403). `/us/en/product/P11VNT3/` -> 200 but a 1.4 MB SPA shell that never mentions P11VNT3 (no spec data). Stopped; nothing stored, no workaround tried. APC stays open.
5. `python3 -I scripts/import.py` run clean (state/specsheet.sqlite rebuilt; build/publish not run - Codex owns those).

## Open questions
- Retail-copy claims (Belkin/Jasco/Baseus/Anker) are `official` manufacturer storefront text but regex-extracted; spot-check `usb.total_w` (title wattage) and Jasco `type.kind` before promote.
- Belkin pack/colour codes are guessed from SKU shape (BG, CW, CH...); A1 should confirm the colour table.
- Label-mapping ignores several yes/no twins (see yaml reasons); profile candidates for A1: per-mode surge current, outlet spacing, phys.form from "Form Factors Supported".
- Only 54 of Belkin's 4,401 crawled pages are strips; the crawl's Belkin sitemap clearly under-covers surge protectors (BSV804TT etc. absent).
- laptops unmapped (97 rows) left for the laptops A2.
