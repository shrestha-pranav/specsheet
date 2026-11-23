# A3 data model v1 (2026-11-22, Claude standing in for Codex; needs Codex review)

Deliverables: `schemas/category-profile.schema.json`, `schemas/record.schema.json`,
`schemas/units.json`, ARCHITECTURE.md §15 "Data model v1", `team/briefs/a4-contract.md`.
Validated: schemas pass the Draft 2020-12 meta-check; in-progress laptops + power-strips profiles
validate as-is; a sample laptop record validates; `fcc_id` with `role: key` is rejected.

## Decisions
1. **Provisional profile format = valid v1.** All additions optional. Unknown keys are errors
   except `x_*`, `note(s)`, `scope`. `type: enum` without a list = open enum (build warns).
2. **Conditional specs**: top-level `conditions` dimensions (port, active_ports, input_voltage,
   mode); specs opt in; `headline_condition` picks the table/facet value; the rest publish as
   `specs[k].conditional[]`. Per-instance lists (ports, outlets) use `items.fields` + `id_field`.
3. **Units**: one canonical unit per spec; claims store canonical value + literal `raw`;
   `units.display` gives market display units; registry in `schemas/units.json`.
4. **Facets**: `facet: true` still accepted; object form `{kind, path, bins, column,
   unknown_bucket}`. Published schema always emits the object form or null.
5. **Entity kinds** family/model/configuration/package/listing/revision, one JSON file each under
   `data/<cat>/<kind>/<id>.json`. Links are relations with proposed/approved/rejected status;
   only approved ones are used. Inheritance is model→configuration→package, never from family.
6. **IDs**: readable globally unique slugs, never reused; tombstones → `redirects.json`.
7. **Identifiers** are namespaced (`mfr_model, mfr_sku, mtm, gtin, fcc_id, ul_file, retailer:<store>`),
   with raw value, issuer, market, package_level and role. The schema forces `retailer:*` (ASIN)
   and `fcc_id` to `role: alias`.
8. **Claim kind** = official | measured | derived | reported. §0.8's declared = official,
   negotiated/sustained/peak = `measurement.mode`. Claim ids are content hashes, so reruns are
   idempotent. `conflicted` exists only on resolved specs. Stop reasons are recorded in `absences[]`.
9. **Storage**: raw is local, immutable, append-only `snapshots.jsonl` plus content-addressed
   blobs. `state/specsheet.sqlite` is the local working store and can be deleted.
   `data/` in git holds accepted claims and human decisions only. `docs/api/v1` is the published
   output. The git diff is the review queue.
10. **Adapter contract**: `discover(checkpoint)->Discovery(refs, complete)`,
    `fetch(ref, prior)->Snapshot`, `parse(snapshot)->ParseResult`. `parse` is pure. Adapters
    never mint entity ids or decide identity.
11. **Published index is compact** (`v` = known headline values, `s` = non-known statuses). The
    index is sharded past ~2 MB, with precomputed `facets.json` and `lookup/identifiers.json`.
    The old `products.json` is kept for one release.
12. **Missing-product and search-miss handling** has to work on a static host with no analytics
    (PRODUCT.md). The user clicks through to a prefilled GitHub issue (`missing-product`,
    `field-correction` templates). `gh` intake writes to a sqlite `requests` table. The payload
    is the same as the future `POST /v1/requests`.

## Gaps / not done
- `build.py` doesn't emit the v1 files yet (manifest, index, facets, lookup, redirects), and
  `scripts/promote.py`, the v0→v1 importer, `data/sources.yaml`, the issue templates and crawl.py snapshot log (A2) are not built.
- Laptop profile keys look like `id.mpn`/`id.family`: identity facts duplicated as specs. They
  should become identifiers/relations. Raise with A1.

## Open questions for Codex review
1. Readable slug IDs vs ULIDs (§7 said ULIDs). Slugs are URL-friendly, but brand renames hurt.
2. One file per entity in git: does it scale? Laptops could reach 10^4–10^5 configurations.
   Alternative: NDJSON per brand, or claims moved to sqlite with only decisions in git.
3. Should candidate (unreviewed) claims be publishable, flagged, for auto-extracted T1
   structured data (Shopify/JSON-LD), or accepted-only as specified now?
4. Is kind=reported right for retailer/crowd claims, or should crowd be its own kind?
5. Condition model: is a free `conditions` object enough for laptop CTO constraints and
   charger power-split tables (`active_ports` combinations), or do splits need a dedicated type?
6. Is the `headline_condition` rule enough for facets on conditioned specs (e.g. max PPS A at 11 V)?
7. Blob store: per-source now. Is a global CAS worth it for shared CDN images and PDFs across brands?
8. Is the GTIN-14 normalisation in lookup safe for UPC-A/EAN collisions across markets?
