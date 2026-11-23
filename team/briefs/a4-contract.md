# A4 contract: published static dataset `docs/api/v1` (A3, v1, 2026-11-22)

What the frontend may rely on. Source of truth for shapes: `schemas/record.schema.json` (`resolved`,
`identifier`, `alias`, `asset`, `source` defs) and `schemas/category-profile.schema.json`. Design:
ARCHITECTURE.md section 15. Anything not listed here is unstable; don't read it.

## Compatibility
- Today's files (`categories.json`, `<cat>/products.json`, `<cat>/schema.json`,
  `<cat>/products/<id>.json`, `build.json`) keep working until A4 has switched to the files below.
  `build.py` emits both for one release; `products.json` is then removed.
- Additive changes (new fields, specs, enum values, categories) can ship anytime. Ignore unknown
  keys; don't fail on them. Removals/retypes bump `schema_version` in `manifest.json`.
- Every URL takes `?v=<build>` (from `build.json`), as now.

## Files
| File | Shape |
|---|---|
| `manifest.json` | `{dataset_version, build, generated_at, record_format: "specsheet.record/1", categories: [{id, schema_version, count, index: [shard paths], facets, demo}]}` |
| `categories.json` | `[{id, name, description, count, demo, status, schema, index, facets}]` (v0 `fields`/`products` kept while compat lasts) |
| `<cat>/schema.json` | `{id, schema_version, groups:[{id,label,order}], conditions:[...], fields:[{key,label,group,type,unit,display_unit,enum,items,tier,priority,column,display,facet:{kind,path,bins,unknown_bucket,default_visible}|null}]}`. Published from the category profile; `facet` is always an object or null (no bare `true`) |
| `<cat>/index.json` or `index-<n>.json` | Compact listing rows (below). Sharded past ~2 MB; load every shard listed in the manifest |
| `<cat>/facets.json` | `{key: {kind, counts:{value: n} \| min, max, bins:[{lo,hi,n}], unknown: n, not_applicable: n, conflicted: n}}`, precomputed over published rows |
| `<cat>/products/<id>.json` | Full record (below) |
| `lookup/identifiers.json` | `{"<scheme>:<normalized value>": [id, ...]}` covering key and alias identifiers. Normalization: uppercase, strip spaces/dashes/dots; scheme `gtin` is 14-digit zero-padded |
| `redirects.json` | `{old_id: {replaced_by: [ids], reason}}`. Resolve before a 404; several targets = split, show a chooser |

## Listing row (index)
```json
{"id": "lenovo-83dk0002us", "kind": "configuration", "brand": "Lenovo", "brand_id": "lenovo",
 "name": "Yoga 7i 14 Gen 11", "variant_label": "Core Ultra 7 258V / 32 GB / 1 TB / OLED",
 "family_id": "lenovo-yoga-7i-14-gen-11", "parent_id": "lenovo-83dk",
 "ids": ["mtm:83DK0002US"], "search": ["yoga 7i 2-in-1 14 oled laptop 2026", "..."],
 "v": {"cpu.model": "Intel Core Ultra 7 258V", "memory.size_gb": 32},
 "s": {"display.nits": "unknown", "power.pps_ranges": "conflicted"},
 "completeness": {"core": [7, 9]}, "lifecycle": "current", "demo": false}
```
- `v` = headline values of specs that have a facet or `column`, status known only. `s` = status
  for every such spec that is not known. A spec in neither = `not_yet_extracted`.
- **Filtering rule**: a row matches a facet value only via `v`. Unknown/conflicted/not_applicable
  never match "no"/false; show them in the facet's explicit unknown bucket.
- `search` = lowercased name + aliases (retail titles) + identifiers; match client-side.
- Listing entities are not rows; their titles appear in `search` of the entity they're linked to.

## Detail record
`id, category, kind, brand{id,name}, name, variant_label, lifecycle, identifiers[], aliases[],
relations[] (approved only: family/parent/children/contains/replaced_by), contents[] (package),
options[] (configure-to-order axes; render as option lists, never as configurations), specs{},
sources[], media[], documents[], notes, demo`.

`specs[key]` = `{value, unit, status, sources:[sN], claims:[ids], kind, confidence, source_scope,
conditional:[{conditions, value, kind, sources}], alternatives:[{value, kind, sources}],
inherited_from}`. Show `conditional` beneath the headline (e.g. per-port PPS), `alternatives` as
"official X · measured Y" (measured never silently replaces official), and `inherited_from` as
"from model <name>". `status` is one of known / unknown / conflicted / not_yet_extracted /
not_applicable / not_published; render each distinctly; never render absence as "No".
`sources[n].tier` drives the badge (regulatory, manufacturer, measurement, retailer, crowd).
Documents/media are links (`republish: link_only`); don't hotlink-embed unless `thumbnail`/`mirror`.

## Missing product requests and search misses (static host, no analytics)
PRODUCT.md forbids remote services and analytics, so nothing is logged passively.
1. **Zero-result search** (or a query that looks like an identifier with no `lookup` hit): show
   "Not in the catalogue yet. Request it." The link opens a **prefilled GitHub issue** (template
   `.github/ISSUE_TEMPLATE/missing-product.yml`, label `missing-product`) with: `category`, `query`
   (as typed), `query_norm`, `identifier_guess` `{scheme, value}` when it matches a known pattern
   (MTM `^[0-9]{2}[A-Z0-9]{2}[0-9A-Z]{4}[A-Z]{2}$`, GTIN 8/12/13/14 with a valid check digit,
   brand model patterns), `build`, plus optional free-text brand/URL. User-initiated only.
2. **Wrong-spec reports** use the same mechanism, `field-correction` template: `{entity_id, key,
   shown_value, claimed_value, evidence_url}`.
3. Locally the client may keep recent misses in `localStorage` (never sent) to prefill the form.
4. Intake (coordinator, not A4): `gh issue list --label missing-product --json` → `state/specsheet.sqlite`
   table `requests(query_norm, category, identifier_guess, count, first_at, last_at, issue_url,
   status: open|queued|added|rejected|duplicate)`; dedupe by identifier, then by query_norm.
   Added products close the issue with the entity link.
5. Dynamic v1 keeps this payload: `POST /v1/requests` with the same fields, plus a server-side
   `search_misses(query_norm, category, n, first_at, last_at)` counter (no IP, no user id stored).
   Build the UI against the payload, not against GitHub, so only the transport changes.

## Trusted vs preview (A3-impl r2, 2026-11-22; review P0-1)
- `<cat>/index*.json`, `facets.json`, `products/`, `lookup/identifiers.json` = **trusted**: only claims accepted by a recorded
  decision (`manifest.release.policies` / ledger) and approved relations. Details carry `review_scope: "trusted"`.
- `categories.json[i].preview` / `manifest.categories[i].preview` = `{review_scope, index: [paths], count, products: "preview/<cat>/products/", only_preview}`.
  Preview rows have the listing-row shape plus `review_scope: "preview"`, `in_trusted`. A preview detail is a **delta**: header
  fields + only the specs that differ from the trusted record (all specs for preview-only entities), `trusted: bool`,
  relations may be `status: proposed`. Never mix preview rows into trusted facets/counts.
- **A4 to do** (no data-contract change forces app.js edits; the current UI shows trusted only): an opt-in "Include unreviewed
  preview" toggle that loads the preview index, renders preview-only rows/values with an "Unreviewed" badge, and on a detail page
  overlays the preview delta below the trusted value ("Unreviewed: …"). Default stays trusted-only.
- New optional per-spec fields: `display` (exact larger unit, e.g. stor.size 1000 -> "1 TB"; render it instead of value+unit)
  and `qualifier` (`from` = "starting at", `approx`, `up_to`; render "from 1.54 kg"). Index rows carry them in `x: {key: {display, qualifier}}`.
  Specs may have `conditional[]` rows `{conditions, value, status, kind, sources, alternatives?}` and `alternatives[]` with
  `kind` + optional `measurement_mode` (label "measured (sustained)"); measured never replaces official.
- Sources may carry `via: <ancestor id>` when an inherited spec cites the ancestor's page.
- New laptop fields: `cpu.cores`, `cpu.threads`, `cpu.base_clock`, `cpu.cache` (split out of the PSREF/ASUS/Apple processor cell;
  `cpu.model` is now the bare model name).

## Revisions (A3-impl, 2026-11-23)
A `revision` is a hardware version of ONE model (TP-Link Archer AX55 V1 / V1.60 / V4 / V4.60 with different SoC/RAM; later SSD controller/NAND or monitor panel swaps). It is a child of its model
(`parent_id` = model, relation `variant_of`) and inherits every model spec; it states only what differs or is version-specific.
- **Model detail** gets `revisions[]` (absent when none; never on a revision): `[{id, label, name, lifecycle, specs{key: resolved}, sources[], differs[]}]`, sorted by name.
  `label` = short version string ("V4.60"); `specs` = the revision's OWN specs only (no `inherited_from`; render the model's table and overlay these);
  `sources` = only the sources those specs cite (ids local to the entry, like a detail record); `differs` = own spec keys whose value or status differs from (or is absent on) the model.
  Also listed in `children` (ids). Render a "Hardware versions" selector/tabs on the model page: default view = model; picking a version overlays its `specs`, falls back to the
  model's value elsewhere ("from model"), and links to the revision's own page. An empty `specs` (e.g. V1 on most TP-Link models) means "nothing known beyond the model": say so, don't imply identical hardware.
- **Revision detail** `products/<rev-id>.json`: normal record, `kind: "revision"`, relations `variant_of -> model`, specs = own + inherited (`inherited_from` = model). Published for every revision of a published model.
- **Index rows**: revisions are NOT rows by default (they'd double-count every model in facets and the count). A category opts in with `revision_rows: true` in `research/<cat>/category.yaml`; rows then
  have `kind: "revision"`, `parent_id`, `name` like "Archer AX55 (rev V4)" and `variant_label` per category.yaml. Facets (`facets.json`) are always computed over non-revision rows.
  UI: treat `kind=revision` rows as children (group under `parent_id`, or hide by default), never as separate products in counts.
- Trusted only: preview details of a model do not list revisions yet.
- Identity: scheme `hw_version`, value `"<model> <version>"` (model-scoped; the bare version is not unique), adapter extra `revision_label`. Unknown stays unknown: a source that shows one version's table
  (TP-Link) attributes revision-level specs (chipset, RAM, flash, firmware date) to that default revision only.
- **A4 to do** (docs/app.js, styles.css untouched by this round): model-page version selector as above; optional revision row handling if a category enables `revision_rows`; search results for revision rows.
