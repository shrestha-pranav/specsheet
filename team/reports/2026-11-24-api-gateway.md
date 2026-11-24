# API agent: API Worker for the free L1 preview (brief pm-2026-11-24-api-gateway R3), 2026-11-24
**Result:** done, local only, no commits. `npm run typecheck` is clean and `npm test` passes 21/21: units, match parity, the route matrix in all 5 modes on `wrangler dev`, no-PII and x402 flow. The only step left for the preview is the owner's `npx wrangler login && npx wrangler deploy` (README "Owner deploy steps", checklist step 15).
- **Names:** `PAYMENTS`/`PREVIEW` are used everywhere. `PAID_ENABLED` and `paidEnabled()` are gone, and a test fails on either name or on any price string not in `PRICES` (D3.3 keys and values, marked provisional).
- **Routes:** `test/route-matrix.json` holds 40 rows across off/on/on-bad/preview-off/breaker. `test/route-matrix.test.mjs` runs each mode on its own workerd. Off mode gives 0 facilitator calls and no 402, including requests carrying X-PAYMENT/PAYMENT-SIGNATURE or `_meta["x402/payment"]`. A row-by-row probe checks the quota column, and discovery listing is asserted. The README table is generated from the JSON and a test checks they match. `scripts/route-matrix.mjs <url>` is the live smoke for step 16.
- **Data:** the pack is served from Worker static assets with `run_worker_first`. The R2 binding is removed. `/health` returns release, policy_version and checksums, and every JSON body carries `release`. The pack was built at release 20261124T145507Z-a7beeed4, policy 2026-11-24.3.
- **Match: ported and live.** `src/match.ts` returns exactly what match.py returns on all 140 titles (both fixtures, the lookalike cases and adversarial titles), checked on ids, basis, confidence, evidence and the ambiguous flag. Precision/recall: tuning set 1.00/0.97, held-out 0.93/0.93. Match is listed in OpenAPI, llms.txt and MCP.
- **Bounds:** D3.6 is applied exactly, with tests at each limit and limit+1. Quota and breaker are as specified (16 SQLite shards, 60 s flush, 30 s breaker sync, REST and MCP on one budget, a batch of N costs N, Retry-After in seconds). The breaker is tested with BREAKER_DAILY=2. `quota_degraded` is written as a separate `ops` point.
- **Metrics:** one AE point per request with fields in contract order. The salt lives in the Breaker DO and is deleted at 01:00 UTC. Redaction is unit-tested. The test reads every point from the off-mode run and finds no IP, UA string, filter value or raw miss text.
- **Beacons:** `/v1/event` takes only the 5 allowlisted events, and `/v1/miss` is capped at 1 KB. Both allow CORS only from SITE_ORIGIN.
- **KPIs:** `scripts/kpi.sql` and `kpi.sh` cover every AE-measurable §3 row. The token is read from a chmod-600 file and never put in argv. Confirmed: AE keeps points for three months; Privacy should say so.
- **Not built: `/v1/presets`.** Your message asked for it, but the R3 brief and decisions D3.5 removed it (the UI reads docs/presets.json), and decisions wins. It returns 404 `not_found` and a matrix row checks this.
## Load test (laptops, `scripts/load-test.mjs` on workerd, plus `cpu-bench.mjs` for the Worker's own CPU in V8)
| case | Worker CPU p50 / p95 ms | workerd process CPU p50 / p95 ms (upper bound) | wall p95 ms | cold first request (Worker CPU) ms |
|---|---|---|---|---|
| laptops, 12 filters, limit 100 (471 KB) | 6.6 / 14.3 | 52.6 / 66.6 | 76 | 147 |
| laptops, q + offset, limit 100 | 8.0 / 15.2 | 33.8 / 107 | 111 | - |
| monitors, limit 100 | 3.5 / 8.2 | 47.6 / 83.0 | 77 | 38 |
| match title | 0.2 / 0.4 | 22.7 / 28.3 | 32 | 180 (catalogue parse + index build) |
| MCP batch of 10 query_specs, limit 100 | 94 / 232 | 135 / 403 | 419 | - |
| chargers, limit 1 | 0.45 / 1.5 | 24 / 39 | 52 | 18 |
The workerd process figure includes about 11 ms of local-dev overhead (the `/robots.txt` floor) plus the DO. Treat it as a ceiling, not billed time.
**Q6 risk: p95 CPU is above 5 ms.** Small and typical queries fit inside Free's 10 ms. Requests at the D3.6 maximums do not. The hot path is reading and re-serializing about 100 full laptop records (record-shard JSON.parse plus stringify), times 10 for an MCP batch. Cold isolates also parse the 4.25 MB laptops index (about 40 ms) and the 3.3 MB match catalogue plus building its index (about 90 ms).
**Verdict:** for the D3.6 bounds as written, Workers Paid ($5/mo) is needed. The other option is for A5 to tighten D3.6 (for example limit ≤ 25 without `fields`, and an MCP batch of ≤ 3 tool calls) and accept the cold-start overruns, which Cloudflare tolerates only when they are infrequent.
**DO budget risk:** at the 60k breaker level, the requests are about 60k spends plus up to about 30k breaker syncs plus beacons. That is close to the Free limit of 100k DO requests per day. Consider BREAKER_DAILY ≈ 45000 if staying on Free.
## Shared-file edits
- `scripts/build_r2.py`: adds `--shard-hex` (pack uses 3), a per-category `keys` field, `match/catalogue.json` built from match.Catalogue (skipped when there is no lookup data), and removal of stale shards. test_build_r2 and test_source_policy pass.
- `research/data-licensing.md` line 3: PAID_ENABLED=false → PAYMENTS=off.
- I ran `scripts/build.py` (under flock) because docs/ had been built with policy .2 while the policy file was at .3. This rewrote docs/ and created state/r2-snapshots/free.
- **For A4:** docs/app.js sends the miss beacon as an `application/json` Blob, which needs a CORS preflight. It should send `text/plain`, which the Worker accepts. `api_origin` stays empty until after the deploy.
