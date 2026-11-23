# A3-impl: custom units + revision entities (2026-11-23)

## 1. normalize custom units
- `scripts/normalize.py units()` reads `units.custom[].unit` (schema) and still accepts legacy `id`. Before, any schema-conformant custom unit raised KeyError("id").
- No profile declared `units.custom`, so every non-built-in unit was an identity unit (no conversion). Re-checked all 5 profiles against the schema:
  - routers: declared `MB`, `sqft`, `month`; set `hw.ram_mb`, `hw.flash_mb` = MB, `mesh.coverage_sqft` = sqft, `sup.firmware_age_months` = month (were `unit: null`).
  - ssds: `MB/s` (B/s x1e6), `IOPS`, `h`, `year`, `mW` (W x0.001). monitors: `ppi`, `year`, `deg`, `ms`.
  - Left as identity: power-strips AWG (gauge, no units block). All profiles validate against the schema.
- Test: `test_resolve.test_custom_units_follow_schema` (both spellings; "1 GB" -> 1000 MB).

## 2. Revision entity, end to end
- import.py `do_model`: revision identifiers may carry `revision_label` (value is model-scoped, e.g. "Archer AX55 V4.60"); entity named "<model> (rev V4.60)", id `tp-link-archer-ax55-v4-60`.
  Claims reach a revision via locator `{"hw_rev": label}` (this was dead code: `owners` was built but never consulted).
- v1_publish: revisions are NOT index rows by default (they would double-count facets); `category.yaml revision_rows: true` opts in (rows `kind=revision`, facets always exclude them).
  Every revision of a published model gets a detail file; model detail gets `revisions[{id,label,name,lifecycle,specs(own only),sources,differs}]` + `children`.
  public-detail.schema.json gained `revisions`; smoke.mjs allows row kind `revision` and checks revisions[] (links, parent relation, own-spec sources, no inherited specs, entry/detail value match).
- Contract: `team/briefs/a4-contract.md` section "Revisions" (exact shape + UI to-do). Not touched: docs/app.js, styles.css.
- tplink_routers: one revision per support-selector version (4 for AX55); `sup.hardware_versions` model list dropped (policy key swapped to `sup.hardware_version`).
  Spec table = default version only, so hw.cpu_*/ram/flash/firmware date go to the default revision (V4.60) via `radd`, not the model; models with no version list keep them on the model.
  Adapter VERSION stays 1 (bumping orphans snapshots); re-parsed offline.
- Result: 245 revision entities, 72 model details carry `revisions[]`; AX55 V4.60 has cpu_cores=2, other versions state only sup.hardware_version (chipset/RAM/Wi-Fi differences are not published by plain HTTP; unknown stays unknown).

## 3. Verification (all pass)
import.py x3 (accepted_digest 707f0510... identical, 0 registry lines appended on re-run), build.py, smoke.mjs (8038 products), frontend-smoke.mjs, tests/test_*.py (identity 10, new_category 5 incl. new `test_revisions_published_in_model_detail`, replay 2, resolve 15).

## Caveats / for the coordinator
- I removed 245 uncommitted routers `revision` lines from data/_ids/registry.jsonl (backup /tmp/registry.bak): they had been minted with doubled-slug ids from an earlier run; re-minted as `tp-link-archer-ax55-v1`.
- data/decisions/policies.yaml edited in place (claim/mfr-routers-structured@1 key list) -> new accepted digest; sup.latest_firmware_date stays unaccepted (candidate), so revisions show it only in preview.
- Routers model rows lose hw.ram_mb/cpu columns where a version list exists (now revision-level). Preview details do not yet list revisions.
- A4: version selector on model page; handle `kind=revision` rows if a category enables `revision_rows`.
