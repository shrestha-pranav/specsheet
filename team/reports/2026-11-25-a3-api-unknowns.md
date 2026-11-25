# A3-api: API returns explicit unknown status (brief coord-2026-11-25-api-unknowns), 2026-11-25
**Result:** done, local only, no commits, no deploy, PAYMENTS off. `tsc` clean; `npm test` 25/26. The one failure is the held-out match
precision gate (0.867 < floor). Its cause is the data: match.ts == match.py on 140/140 titles, on the pack and on docs/api/v1 alike, and
the docs data changed under today's imports. Neither the Worker nor this change caused it. **A2/coordinator: please look at the 2 held-out FPs.**
## Decisions
- **Per-filter status** (`src/verdict.ts`, used by `data.ts runQuery`, brief's "execQuery"): match | unknown | conflicted | disagree | no.
  The semantics are those of the **current working-tree `scripts/presets.py`**: another agent's uncommitted review-7 edit makes
  conflicted -> disagree, handles alternatives on both sides of a filter, and sorts rows into disjoint buckets. TS keeps `conflicted`
  as its own label (brief) and maps it to py `disagree`. Enum `=` is exact, as in py. Bool accepts yes/no/true/false.
- **Response:** `maybe: {total, unknown, conflicted, disagree}` is always reported (disjoint buckets: disagree > conflicted > unknown).
  `include=maybe|matches` (default matches; validated, in the cache key) lists maybe rows *after* the matches. Each result has
  `status`, `maybe_reason`, `filter_status{key}` and `unknown_core{key: status}` (core keys with no published value). No value is
  revealed, so this is the same on all tiers.
- **Parity** (`test/verdict-parity.test.ts`): py `_verdict` vs TS on fixtures (`test/fixtures/verdict-rows.json`, 6 rows x 9 filters,
  pinned) + every built preset over its docs index: 34,562 row x filter cells and 9,135 row buckets, all identical. Sanity check:
  ram-upgradable via the API gives 193 match / 38 maybe, the same as presets.json.
- **MCP:** new metadata tools `list_categories_keys` (no category: categories + key counts + core keys; with category: key,
  label, group, type, unit, enum, tier, facet, facet_kind, fill) and `list_presets` (app filters translated to query_specs filter
  strings by `presetFilter`, which mirrors the py branch choice, + gate + counts). They have no price: each call is 1 unit of the
  daily budget, never x402. `query_specs` gained `include`.
- **match_product "null":** the pack manifest has `match` set, and match_product is offered and passes. A5 read
  `api-worker/r2-data/meta/manifest.json`, the stale **paid** export from 2026-11-24 01:36 that predates match_catalogue. The
  Worker never reads it. Nothing to fix in the builder; r2-data can be rebuilt or deleted at the next paid export.
## Pack builder (shared file: `scripts/build_r2.py`, the only shared-file change)
- Index rows gain optional `s` (conflicted/not_applicable) and `a` (alternative values from docs x[key].alt, with or without a
  headline). The diff snapshot still uses `v` only, so /v1/changes is unaffected. It now writes `schema/<cat>.json` (+ manifest
  `schema`, `core`) and `meta/presets.json` (+ manifest `presets`). test_build_r2 passes.
- Pack rebuilt (flock): release 20261125T191219Z-0d25f1d5, policy 2026-11-25.3 (new state/r2-snapshots/free snapshot + changes entry).
## Bounds and CPU (limit 25, batch 3, breaker 45k: unchanged)
- `scripts/load-cases.mjs` was still at limit 100 / batch 10, which the bounds now reject, so I moved it to the maxima and added
  include=maybe and meta-tool cases. Worker CPU (V8 cpu-bench) p50/p95 ms: laptops 12 filters 4.9/11.7; +q+offset 5.2/13.8;
  include=maybe 12 filters 1.4/5.4; monitors 2.6/7.2; MCP batch 3 x include=maybe 14.7/18.6; meta tools 0.6/1.2; cold laptops 57,
  match cold 180. The verdict hot path has a fast path for rows with no alternatives. The max cases still exceed Free's 10 ms at p95,
  so the earlier verdict holds (Workers Paid, or accept the overruns). Typical queries fit.
- Route matrix: +4 rows (query-maybe, query-bad-include, mcp-list-keys, mcp-list-presets); all 5 modes pass; README table regenerated + semantics documented.
**Files (api-worker):** src/verdict.ts (new), src/data.ts, src/bounds.ts, src/mcp.ts, src/discovery.ts, test/verdict-parity.test.ts (new),
test/query-unknowns.test.ts (new), test/fixtures/verdict-rows.json (new), test/route-matrix.json, scripts/load-cases.mjs, README.md.
**Open:** presets.py semantics are from an uncommitted edit by another agent. If that edit is reverted, verdict-parity fails, which is the
  intended tripwire.
- /v1/presets REST is still 404 per D3.5. Presets are exposed through MCP only. Say if REST should mirror it.
