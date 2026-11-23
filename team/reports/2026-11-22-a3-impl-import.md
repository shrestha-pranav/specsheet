# A3-impl: unified contract, scripts/import.py, v1 publish (2026-11-22)

## Decisions / open questions first
- **Contract**: `crawler/adapters/_contract.py` is the single contract module (superset: Ref/Discovery/Snapshot/ParseResult + `sources[]`, BlobStore, http_snapshot, claim()). `_run.py` already imported it, so snapshot log
  (`raw/<src>/snapshots.jsonl`) and blob layout were already identical for all 5 adapters. Added only: `BlobStore.latest()/read_rec()` and the docstring naming it THE module. New `crawler/adapters/registry.py` = the one
  entry point (`iter_observations(source)`) incl. `FnAdapter`, the compat shim giving tripplite/cyberpower the class-style `parse(snap, blobs, profile)`. **Not touched**: `_run.py`, `lenovo_psref.py` (PSREF fetch still running, pid alive).
  TODO after it finishes: turn tripplite/cyberpower into class adapters on `_run.py`, delete FnAdapter, and have lenovo emit mtm-level claims with the profile keys directly.
- **Interim publish rule** (promote.py does not exist): adapter claims (`review: candidate`, manufacturer tier) are resolved directly from `state/specsheet.sqlite`. Say if you prefer a promote step first.
- Adapter vs mapping disagreement: lenovo COLMAP sends `Country/Region` to `id.region`->`gen.region`; psref-mapping.yaml says `gen.country_region` (`Region`->`gen.region`). Importer lets **psref-mapping win** (727 claims overridden, logged in `unmapped`). A2 should fix COLMAP.
- `build.py` now needs `state/specsheet.sqlite` (run `scripts/import.py` first) or `--no-state` (chargers only; it would otherwise delete published laptops).
- UI safety: new categories ship v0 compat (`fields` = column + core facets, slim `products.json`, v0 keys on detail records) so the current app.js should not crash; **browser-smoke not run**. categories.json `index` is a list of shard paths (same as manifest).

## scripts/import.py (rebuild ~10 s, deletes/recreates the sqlite, never writes raw/)
Entities: Lenovo family=PSREF ProductKey, model=machine type, configuration=US MTM (MTM[:8] group); non-US MTMs are not entities (301k rows in `packages`, count per config). ASUS: model=base code, configuration=PartNo with
adjacent SalesModelName as same config (150 pairs); Apple: model = Model Identifier set, part numbers = sku aliases (cannot be tied to a config). Power strips: model = normalised model number (hyphen/space/case-insensitive, gtin merge);
documented suffixes only when the base model exists: colour->configuration (20), multi-pack->package (4), OEM->alias merged (2). HG/RA/RMS/cord stay separate models.
Claims -> keys: profile key, profile `aliases`, else psref-mapping single-target column; shared targets (key fed by 2+ columns) excluded as ambiguous. psref-mapping also adds 9k+ claims for columns the adapter never emitted (extractor `import.py+psref-mapping@1`).

## Numbers (PSREF PARTIAL: 70 of 282 products at last import)
| | observations | entities (non-family) | claims |
|---|---|---|---|
| laptops: lenovo / asus / apple | 70 / 142 / 20 | 720 configs + 77 MTs / 128 configs + 194 models / 20 models | ~31.8k total (US-only for lenovo) |
| power-strips: tripplite / cyberpower | 249 / 293 | 235 models + 12 configs / 280 models + 8 configs + 4 packages | 6.4k |
Families: 70 lenovo + 142 asus series. Lenovo: 251k MTM rows seen, 720 US configs (0.3%), avg 1.0 regional MTMs per US config (max 11). 0 duplicate key identifiers.
**Unmapped**: 0 claim keys outside the profile (1 key overridden by mapping); 210 source labels the power-strip adapters left unmapped (17k occurrences: shipping dims/weight, outlet type, USB charge port, warranty, colour, plug style, safety, input voltage);
PSREF columns: 4 ignored by mapping, 8 multi-target (need a parser: Processor, Graphics, Storage... emitted raw by adapter), 12 absent from psref-mapping (NFC, SIM Card, Physical Locks, System Management, Smart Card Reader, ThinkShield, Optional Ports, Optical, ISV Certifications...).
All in table `unmapped`.

## Publish (docs/api/v1, node --check + smoke.mjs pass, stamp_build adds manifest.build)
Added manifest.json, per-cat schema/index/facets/products/<id>, lookup/identifiers.json, redirects.json (from tombstones). Laptops: 1063 rows (849 configs, 214 models) + 268 ancestor-only detail files (family/model); power-strips: 539 rows. US filter
applied at import (lenovo US MTMs only) and re-checked at build (0 further dropped). Spec status laptops: 27.5k known, 3.9k not_yet_extracted (raw literal kept: multi-quantity strings like `1x 16GB SODIMM`, ranges), 16 conflicted; strips: 6.0k known, 280 not_published, 454 not_yet_extracted.
Normalisers are deliberately conservative (unit conversion via units.json; first-number only when single-quantity; `special()` for touch/fingerprint/NPU TOPS/dimensions).
**Size**: docs/api/v1 = 17.6 MB total (laptops 13.1 MB, power-strips 3.2 MB, chargers 1.9 MB); laptops index.json 1 shard. Extrapolation for a full PSREF run (~1M MTMs, ~0.3% US): ~3k Lenovo configs -> ~35-40 MB laptops, fine.
smoke.mjs: new v1 branch (manifest/build match, schema, index rows vs detail, v/s consistency, no private fields, relation/children/lookup targets published).

## Files
crawler/adapters/{_contract.py (additive), registry.py (new)}, scripts/{import.py, v1_publish.py (new), build.py, smoke.mjs}, state/specsheet.sqlite (gitignored), docs/api/v1/**. Nothing committed; raw/ untouched.
