# Brief: one source-policy gate for free, Worker and paid outputs (PM D1.2, D1.3; round 3). Owner: A3 (Opus).
Read team/briefs/common.md, product/decisions.md D1-D3, `data/source-policy.yaml` (the policy, written by A5; do not
change dispositions, ask A5), DATA-LICENSE.md, research/data-licensing.md (read-only), scripts/build_r2.py.
Why: the review (reviews/2026-11-24-astra-review-5-pm.md P0-1) found the free tier ungated and permissive defaults.
This supersedes item 1 of pm-2026-11-24-release-r2.md.

## 1. One module, three consumers
- `scripts/source_policy.py`: load + validate `data/source-policy.yaml`. Expose `disposition(url) -> {free, paid,
  licence_grant, withhold_keys}` and `gate(record, tier) -> record | None` for tier in `free | paid`.
  Host matching: parse with urllib, lowercase, strip a trailing dot and port; userinfo never counts as the host;
  `match: exact` = host equal, `match: subdomains` = equal or `*.domain`.
- Consumers: `scripts/build.py` (free static JSON incl. index shards, `index-certonly`, facets, lookup,
  products.json, categories counts, `docs/sources.json`), the Worker query-pack builder (free tier; see the api-gateway
  brief, same layout as `build_r2.py` output) and `scripts/build_r2.py` (paid). Delete
  `api-worker/licensing-exclusions.json` and its `--exclusions` flag. No second list anywhere.
- Validation (fail the build): unknown keys; duplicate domains; `licence_grant` without `free`; `paid` without
  `licence_grant`; `paid`/`licence_grant` true with evidence level other than `fetched` or with no refs.
- Unlisted domains: use `defaults.unlisted`. Non-release builds print them with value counts. With
  `RELEASE=1` (release.sh sets it) the build exits non-zero and names them.

## 2. Gate semantics
- Per value, per tier: drop sources that tier disallows (or whose `withhold_keys` contains this key). Keep the value
  iff a remaining source **independently supports it**: its own accepted claim for that key equals the published
  value (check against the ledger/claims). If no remaining source supports it, the value becomes `status:
  not_published, value: null, sources: []`. The tier never cites, links or counts a dropped source.
- Per record: drop dropped sources from `sources[]` and `documents[]`. If no remaining source supports the identity
  (name/model/identifiers), omit the record from that tier entirely, including its index, facet and lookup entries.
  Always drop `media`, demo records and `exclude_categories`.
- Every kept `sources[]` entry carries `licence_grant: true|false` (from policy). Do not add per-value flags: a value is
  under our grant iff one of its listed sources has `licence_grant: true`.
- Indexes, facets, lookup, summaries and counts are computed **after** gating, from gated records only.
- Diffs (`changes`): computed per tier on gated output. A value that becomes withheld appears as
  `{key, change: "withdrawn"}` with **no previous value**.
- Manifest (all three outputs): `policy_version`, `policy_sha256`, `license: "ODbL-1.0"`, `license_url`,
  `license_scope: "compilation + values whose sources[] include licence_grant:true; other values are facts with links, not licensed by us"`,
  `attribution`, and per-category coverage (below).

## 3. Coverage output
`docs/api/v1/coverage.json` (and the same block in the paid manifest): per category, records and known values for
free, granted (value-level grant) and paid. Reference figures from ungated docs/api/v1 today: 12,225 records,
207,430 known values, 15,942 granted/paid-eligible (ENERGY STAR; air-purifiers 3,260, monitors 11,582, tvs 1,100).
Report your post-gate numbers and any category that drops.

## 4. Fixtures (tests/test_source_policy.py + tests/fixtures/source-policy/), all must pass
F1 Value sourced only from a `free:false` domain → `not_published` in the free record and absent from the index
   shard row, facet values/counts, lookup, products.json, categories counts, query pack, diff, paid record and bulk.
   The domain appears in no `sources[]` or `documents[]` and no URL string anywhere in the output tree (grep the
   whole output dir).
F2 Mixed sources [A free:false, B free:true], both claiming the same value → kept, `sources == [B]`.
F3 Mixed sources where only A's claim matches the published value (B claimed a different value) → `not_published`
   (no "borrowed" provenance).
F4 `paid:false` source (PSREF-like) → value present free, absent in paid record/index/facets/bulk/paid diff.
F5 Grant flags: ENERGY STAR + maker → maker entry `licence_grant:false`, ES entry true; maker-only value → no
   granted source.
F6 Unlisted domain → free build warns with count; `RELEASE=1` exits non-zero naming it; not in paid.
F7 Host matching: `psrefstuff.lenovo.com` is not matched by `psref.lenovo.com` (exact), so it is unlisted.
   `amazon.com` (subdomains) matches `amazon.com`, `www.amazon.com` and `smile.amazon.com`, but not `notamazon.com`.
   Uppercase host, trailing dot, `:443` port, and `https://psref.lenovo.com@evil.example/` (host = evil.example).
F8 Record whose identity is supported only by a dropped source → omitted from that tier entirely, with no orphan
   index, facet or lookup entry.
F9 `withhold_keys: [x]` on a domain → only key x is withheld for that source; its other keys stay.
F10 Diff across two fixture releases where a value becomes withheld → `withdrawn`, no previous value printed.
F11 Invalid policies rejected: paid without grant; grant without free; grant with `evidence.level: search`;
    duplicate domain; unknown key.
F12 `policy_version` + sha stamped in free manifest, query-pack manifest and paid manifest; they agree.
F13 `docs/sources.json` is generated from the policy, grouped `granted` / `facts_only`, with no `public_domain` field.
F14 Certification-only index and preview paths are gated identically (no bypass via `index-certonly`).
F15 Expression guard (kept from round 1): record text fields are only names, identifiers, enums, numbers and notes
    we wrote.
F16 Only one policy reader: build.py, build_r2.py and the query-pack builder import `source_policy`; no file
    named `*exclusions*` exists.

## 5. Constraints
Shared-script edits minimal and listed. `flock /tmp/specsheet-release.lock` for bare build.py runs. Never run
release.sh without RELEASE_DRY_RUN=1. No commits.

## 6. Site wording (A4 applies to docs/pages.js after the gate lands; coordinator dispatches)
Terms, "Licence and attribution" paragraph, replace with:
> The database is available under the Open Database License 1.0 for what we hold rights in: the compilation (its
> selection, structure and identity work) and values from sources we have permission evidence for. Other values are
> shown as facts with a link to their source, and we grant no licence over them. Check that source's terms before you
> reuse them. Site text is CC BY 4.0 and the code is Apache-2.0. If you publish something made from the data, include:
> "Data: ${brand} (ODbL), sources linked per value". Details: Sources and DATA-LICENSE.md.

Sources page: replace "How to cite" and the two credit sections with:
> **How to cite.** Data: ${brand} (ODbL), sources linked per value.
> **What our licence covers.** The ODbL covers the compilation and the values from the sources listed under
> "Licensed with permission". Everything else is shown as a fact with a link, and we grant no licence over it.
> **Licensed with permission** (list `granted`, each with its required attribution line, e.g. "Source: U.S. EPA
> ENERGY STAR").
> **Shown as facts with links, not licensed by us** (list `facts_only`). We republish specification values and links,
> not text, images or documents. Rights in each source's content and marks stay with their owners.
> **Coverage** (table from coverage.json: per category, values shown / values under our licence).
> **Takedowns** (keep the current paragraph; add "within 7 days of a valid request" for removal from the site and API).
Remove every "public domain" claim from Terms, Sources and About.
Report: team/reports/2026-11-24-a3-licensing-gate.md (<=60 lines): coverage table, fixture results, shared-file edits.
