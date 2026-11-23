# A3 review: data model v1
Date: 2026-11-22 · Reviewer: GPT-6-Astra · Scope: read-only architecture, schemas, identity rules, importer and publisher.

**Decision: retain the entity/claim/profile direction, but do not add category #3 to the production publisher yet.**
The implementation is a useful preview, not the accepted-only, replayable contract described in §0/§15.
The largest risks are evidence loss during import, implicit identity decisions, and treating all-region scale as a US-only projection.
P0 means a correctness gate before trusted publication; it does not assert that every existing row is wrong.

## Ranked findings

### P0 — 1. Publication bypasses the authoritative review layer
Evidence: `scripts/v1_publish.py:7–9,258–260` resolves all mapped claims without a review-state predicate.
`import.py:383–399,483–496` stores candidate states but has no durable relation/decision representation;
the publisher manufactures `approved` relations from parent pointers (`v1_publish.py:317–322`).
This contradicts §0.1/0.3 and §15.4/15.6. A detail-page disclaimer does not make candidate values accepted.
The implementation neither loads accepted v1 records from `data/` nor replays human decisions.
**Fix:** add a promotion/decision ledger; public resolution must require accepted claims and approved, evidenced identity links.
Deterministic auto-acceptance can be a versioned policy for audited adapter/field combinations; record its policy ID and decision.
Keep candidates in a separately identified preview dataset, excluded from the trusted index and facets.
Acceptance test: removing sqlite and replaying raw + decisions reproduces accepted IDs, links, claims and rejection states.

### P0 — 2. Import discards the semantics needed to resolve conditional evidence
Evidence: `import.py:392–393,495–496` omits `conditions`, `measurement`, `supersedes`, `derived_from`,
`via_relation`, most method metadata and confidence from stored claims.
`v1_publish.py:156–188` groups only by normalized value: different conditions become conflicts,
equal official/measured values collapse into one kind, and profile `headline_condition` is unused.
This is a proven serialization gap; its impact grows when charger splits, SSD benchmarks or appliance modes arrive.
**Fix:** preserve the complete validated claim document and index selected fields separately.
Resolve by entity + spec + canonical condition tuple + claim kind/measurement context; apply supersession first.
Emit typed conditional results and separate official/measured alternatives, then compute the requested headline projection.
Add an end-to-end fixture with two active-port combinations and official versus measured results.

### P0 — 3. Identity matching can silently merge distinct entities
Evidence: `import.py:36–41` strips all punctuation and accepts arbitrary digit strings as GTINs.
`World.get/merge` (`70–100`) merges on the first overlapping key without conflicting-key or level checks.
`do_strip` (`287–296`) uses GTINs as merge keys while subsequently labeling them package-level aliases.
Key scope omits issuer, market and entity level; separate category worlds only incidentally supply category scope.
Suffix grouping (`329–350`) approves relationships from suffix/base existence, without per-pair evidence or vetoes.
No current false merge was established; the destructive merge path is directly observable.
**Fix:** match on validated `(scheme, issuer, normalized value, market scope, entity level)` with scheme-specific scope.
A package GTIN must not collapse models/configurations; conflicting strong identifiers must quarantine the observation.
Make punctuation rules scheme/issuer-specific, and turn inferred suffix links into proposals until approved.
Store merge/split events and retain original observation attachments so decisions are reversible.

### P1 — 4. Inheritance corrupts provenance and assumes an unsafe universal hierarchy
Evidence: `v1_publish.py:275–282` copies a parent result, including record-local `sources: ["s1"]`,
while `314–315` emits only the child's source table. All 22 inherited specs in current output resolve to a different URL.
Example: `cyberpower-b602rc1tl` inherits `type.ul1449_listed` from `cyberpower-b602rc1`, but its `s1` identifies
`https://www.cyberpowersystems.com/product/surge/essential/b602rc1tl/` instead of the parent's `/b602rc1/` page.
The single pass also depends on entity iteration order for model→configuration→package propagation.
Every known parent field is inherited, regardless of profile `level`, package semantics or relation approval.
**Fix:** use globally stable evidence IDs or remap inherited source/claim references into the child document.
Resolve an approved acyclic graph in topological order, with explicit field-level inheritance policies.
Packages expose component facts separately from package facts: dimensions, weight and pack count cannot inherit blindly.
A missing extraction attempt should not have the same blocking meaning as an explicit lower-level unknown/conflict.

### P1 — 5. Normalization can publish incorrect precision or units
Evidence: `v1_publish.py:42–48,51–77,111–149`.
Read-only probes: numeric `1000` with claim unit `g` under a `kg` spec returns `1000`;
integer `2.9` returns `2`; `"starting at 1.2 kg"` returns exact `1.2`.
`convert()` ignores the unit registry's offsets; custom profile units are not loaded.
List/object/range values receive only shallow shape checks, with no nested-field or range validation.
**Fix:** normalize before acceptance using claim units, dimensional compatibility and registered affine conversions.
Reject fractional integers; preserve lower/upper bounds and approximation rather than converting them to exact values.
Require complete parsing or explicitly preserve qualifiers. Validate canonical typed values against the compiled profile.
Keep category-specific source-text parsers in adapters, not `special()` branches in the publisher.

### P1 — 6. All-region identity is discarded at the ingestion boundary
Evidence: `registry.py:70–90` parses only US Lenovo rows; non-US data becomes a small tuple.
`import.py:163–168,396` retains only MTM/config8/type/family/country/GTIN, losing those rows' spec claims.
The implementation report's ~35–40 MB projection depends on publishing ~0.3% of MTMs, not supporting all regions.
**Fix:** ingest every observed MTM with its complete evidence; apply market selection only to publication views.
Process source bundles incrementally and deduplicate genuinely shared facts without erasing regional differences.
Maintain coverage metadata: regions, source enumeration completeness, unresolved rows and extraction coverage.
A US preview may remain small, but it is not evidence that one million MTMs fit the current design.

### P1 — 7. Stable IDs are reminted; partial imports replace the entire working store
Evidence: `import.py:459–464` assigns collision counters based on encounter order despite “mint once.”
`--source` restricts ingestion (`418–420`) but `527` replaces the whole database with that subset.
Adding/reordering sources can change IDs; a selective import can remove other categories from the next publication.
**Fix:** persist an identity→ID allocation registry and tombstones independently of the rebuildable database.
Make source updates transactional upserts or require an explicit full-rebuild command with coverage checks.
Do not publish an incomplete rebuild over the last good release without an explicit scope change.

### P1 — 8. The generic profile contract is not implemented or enforced
Evidence: importer category list and resolver dispatch are hardcoded (`409,437`);
publisher category metadata/columns are hardcoded (`22–27`), as are variant labels (`195–209`).
Neither profile loader validates the profile; `facet.path`, `derived`, `normalize`, custom units and inheritance
metadata are accepted by the schema but are not consistently executed.
Published documents declare `specsheet.record/1` but omit required `claims` and add forbidden compatibility keys.
A sampled current laptop detail failed schema validation for these reasons.
**Fix:** separate accepted-record and public-detail schemas; validate both plus profile-aware values/references.
Move category metadata, column selection, identity/inheritance policy and projections into versioned profiles.
Use an explicit adapter registration manifest and structured observation subjects/links, not identifier-list adjacency.
A new category should require a profile, adapters and fixtures; central resolver/publisher changes should fail an extension test.

### P1 — 9. Replay can pair stale extraction with new evidence
Evidence: `registry.py:109–127` reads `parsed/<key>.json` without checking snapshot/profile/extractor versions;
reparse exceptions log and skip the observation. `FnAdapter` reads mutable `resources.json` (`46`).
`_contract.py:128–139` hashes record-local source tokens rather than stable evidence identity, forces source `"s1"`,
and lacks canonical JSON ordering. Import dedupes only on that hash (`483–486`).
`http_snapshot` treats 304 as an empty-hash failure rather than linking the previous body (`118–121`).
**Fix:** extraction cache key = body/asset hashes + profile + adapter + model/prompt versions.
Include all parse dependencies in immutable snapshots; emit durable extraction failures, preserving last-good evidence.
Separate immutable assertion IDs from observation events and review decisions; include stable source/subject/context.
Handle 304 explicitly and distinguish last successful evidence from latest fetch status.

### P2 — 10. Tighten semantic validation and absence handling
`record.schema.json` allows key identifiers without issuer/level/evidence; defaults do not populate those fields.
It does not enforce GTIN validity, relation endpoints/kinds, source references or condition dimension types.
`options[].constraints` is prose; `resolved.conditional/alternatives` are nearly untyped.
`v1_publish.py:183–187` turns blocked/budget/not-attempted outcomes into `not_published`.
**Fix:** add semantic validators for uniqueness, cross-references, cycles, approved-link evidence and typed conditions.
Keep source omission, blocked access, unattempted extraction and explicit non-applicability distinct.
Use a typed constraint expression format where machine evaluation is required; preserve unsupported prose as notes.

## Identity and variant grouping

- **Define levels by meaning, not a universal SKU substring hierarchy.**
  Family is browsing; model is an evidenced platform/design; configuration is a fixed hardware/software configuration;
  package is a sale bundle/packaging unit; listing is one source's offer; revision is an evidenced production change.
  Orderable identifiers can name configurations or packages. Market is not itself an entity kind.
- **Lenovo:** preserve full MTM as the orderable identity. Treat `MTM[:8]` as a proposed shared-hardware group,
  not a universal equivalence rule proven by a sample. Keyboard layout is physical hardware, not merely packaging.
  OS language, warranty, plug and availability also need explicit scope. Preserve differences even when grouping is valid.
  ProductKey can anchor a model/platform group and machine type a subordinate platform group; document the mapping.
  Current identity.md calls ProductKey “model,” while importer makes it “family”; reconcile before inheritance.
  Do not infer chassis invariants from columns that vary “rarely.”
- **ASUS:** PartNo↔SalesModelName pairing must be an explicit same-subject assertion, not adjacency in an identifier array.
  Series pages and base-model columns describe platforms/options; they are not fixed configurations.
- **Apple:** one support page containing several Model Identifiers does not prove those identifiers are equivalent.
  Keep distinct platforms where evidenced; represent shared page scope separately. `xx/A` part-number templates are patterns,
  not literal orderable SKUs. Retain unresolved config associations instead of manufacturing RAM/SSD combinations.
- **CTO and reseller upgrades:** store constrained options; instantiate only evidenced orders/configurations.
  Reseller-modified RAM/SSD configurations retain seller provenance and must not overwrite factory MTM facts.
- **Power strips:** keep model numbers intact. Cosmetic equivalence requires evidence; color pages can disagree electrically.
  OEM bulk and multipacks are package relationships, not blanket aliases. Store quantities and component IDs in `contents`.
  Missing joules alone cannot prove “plain strip” or non-applicability. Preserve market/plug/voltage and safety distinctions.
- **SSDs:** same model/SKU/capacity with changed controller, NAND or DRAM is an evidenced **revision**,
  not a new retail configuration and not grounds to overwrite original specs.
  Give revisions their own IDs and `revision_of`, plus evidence, observed/valid dates and batch/firmware/label discriminators.
  Retail identifiers may legitimately resolve to multiple revisions; unknown revision stays unknown.
  Benchmarks attach to the tested revision, capacity, firmware and test conditions. Never inherit them across revisions.
  Without distinguishing evidence, retain competing claims/possible revisions rather than inventing production dates.

## Answers to the eight open questions

1. **IDs:** prefer opaque immutable IDs for new entities, with readable URL slugs as aliases.
   Existing public slugs can remain permanent IDs if backed by a persistent allocation registry.
   Brand renames change display metadata, not IDs. ULIDs are acceptable; the allocator and no-reuse policy matter more.
2. **Files in git:** suitable for the reviewed pilot, not one million entities plus claims and generated details.
   Keep profiles, source policy, durable ID/decision events and small fixtures in git.
   Put bulk accepted evidence in versioned, checksummed immutable datasets with backups; sqlite is a projection, not sole authority.
   Bounded NDJSON partitions beat one giant brand file; compacted snapshots plus append-only events permit replay.
3. **Candidates:** accepted-only for trusted publication. Allow a separate explicitly provisional preview.
   Audited deterministic manufacturer extraction may be auto-accepted through a recorded policy; “T1” alone is insufficient.
4. **Reported/crowd:** keep `reported`; source tier/origin and submission metadata identify crowd versus retailer.
   A crowd instrumented test is `measured`, not automatically `reported`. Claim kind and contributor class are independent.
5. **Conditions:** retain an extensible object envelope, but validate dimensions, units, domains and canonical set ordering.
   Power splits need typed scenario rows mapping simultaneous active ports to allocations/budget;
   CTO needs typed option constraints. Neither needs a category-specific resolver if the common primitives are implemented.
6. **Headline facets:** one exact headline condition is useful but insufficient for interval or existential queries.
   Define named, versioned projections with predicate/aggregation semantics and evidence links.
   “≥3 A across 3.3–11 V” requires interval coverage under one compatible port/mode scenario, not maximum current at one point.
   Missing qualifying evidence yields unknown; never select the first condition or combine incompatible scenarios.
7. **CAS:** retain source-scoped retention/access metadata; global hash-addressed bytes can be introduced behind BlobReader later.
   Deduplicate large shared PDFs/images when measurements justify it. Retention, deletion and rights remain source-specific,
   so shared bytes need reference tracking. Compression must be deterministic or hashing must use canonical uncompressed bytes.
8. **GTIN-14:** zero-padding valid GTIN-8/12/13 representations is appropriate; equivalent UPC/EAN forms should coincide.
   Validate supported length, digits and check digit first; do not strip arbitrary text into a key or expand UPC-E implicitly.
   Preserve raw representation and packaging level. A nonzero GTIN-14 packaging indicator must not be discarded.
   GTIN is globally scoped; market metadata does not justify splitting the same valid GTIN into unrelated products.
   A valid check digit proves syntax, not that the source assigned the number correctly; conflicts require review.

## Storage and publication scaling

Observed current artifacts, not the earlier report's stale 17.6 MB total:
- Laptops: 3,385 JSON files, 32,857,448 bytes; index shards 1,992,927 + 1,302,013 bytes;
  compatibility `products.json` 6,933,257 bytes. Index gzip estimates: 89,787 + 49,404 bytes.
- Power strips: 543 JSON files, 3,189,661 bytes; index 321,653 bytes; compatibility products 915,330 bytes.
- Global identifier lookup: 248,534 bytes. Compression estimates are offline gzip measurements, not verified host transfer sizes.

**Proposed engineering budgets, not host limits or forecasts:**

| Category/view | Eager JSON budget | On-demand publication policy |
|---|---:|---|
| Laptops, all regions | ≤2 MB decoded / ≤500 KB compressed per initial view | Platform/model browse; market/brand partitions; MTMs on demand |
| Power strips | ≤2 MB decoded / ≤500 KB compressed | Single index until threshold, then brand/market shards |
| Monitors, SSDs, routers, power banks | Same per view | Brand/platform shards; SSD revisions loaded with details |
| TVs and appliances | Same per view | Market + product-type/brand shards; avoid a universal appliance index |
| Robot vacuums, power stations | Same per view | Single index initially; identical automatic sharding policy |

- Bound every index/lookup shard at **2 MB UTF-8 JSON**; target detail ≤100 KB, split exceptional histories/claims.
  Give schema/facet/manifest metadata a combined initial-view budget of 250 KB, included in the eager budget above.
- Budget by view and artifact, not merely category total. At 1M rows, even 1 KB/row is 1 GB of index;
  10 KB/detail is 10 GB before history and duplicate exports. These are illustrative capacity calculations.
- Set a provisional **100 MB uncompressed/category review threshold** and **250 MB total generated-site gate**;
  exceeding them triggers object-storage/release-artifact distribution rather than larger git commits.
  These are operational choices to benchmark and revise, not a claim that all-region laptops will fit.
- Use stable hash-prefix or explicit range partitions with shard hashes, row counts, byte sizes and routing metadata.
  Current ordinal name-sorted shards (`v1_publish.py:363–375`) churn after insertions.
- Shard identifier lookup by normalized scoped-key hash and expose a small directory.
  Precomputed global facet counts do not support arbitrary combined filters; either load a bounded partition,
  ship compatible bitmap/posting indexes, or move large-query execution to the planned backend.
- Remove the monolithic compatibility export after a defined migration window. Sharding the index alone cannot fix it.
- Stream observations and claim batches into indexed storage; current in-memory Worlds/claims/resolved/details grow with category size.
  Publish only changed partitions/details and atomically switch a versioned manifest after validation.
- Keep full raw/accepted history out of frontend downloads. Release manifests must record input coverage,
  profile/resolver versions and content hashes so a published dataset can be reproduced.

## Before category #3

1. Implement durable ID/decision replay and accepted-only publication; isolate candidate previews.
2. Preserve complete claims and fix condition-aware resolution, typed normalization and inherited provenance.
3. Reconcile laptop levels; retain all-region observations; add revision and package fixtures.
4. Enforce scoped identifier validation and reversible relation decisions, including GTIN/package conflicts.
5. Separate/validate public schemas and make one new fixture category work through profile + adapter registration alone.
6. Add stable byte-budgeted shards, coverage/atomic-release checks and a bounded-memory million-row benchmark.

Validation: static inspection of all requested files, current artifact measurements, inherited-source URL comparison,
three direct normalization probes and validation of one current published detail against `record.schema.json`.
No crawler, importer, build, network fetch or production mutation was run; no claim of exhaustive dataset validation.
