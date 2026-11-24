# Brief: API Worker for the free L1 launch (PM D2, D3, D4; rewritten PM round 3, 2026-11-24). Owner: api agent (Opus).
**Changed 2026-11-24 (R3):** supersedes the round-1 brief and its round-2 addendum. Dropped: serving the site shell
and dataset from R2, the `/v1/*` 302 catch-all, `/v1/presets`, and the per-IP-only limits. The spec is
`product/decisions.md` D3.4-D3.7 (route matrix, bounds, quota, breaker) and `product/measurement-plan.md` §1-3
(metrics contract). Where this brief and those differ, decisions.md wins. Ask A5 rather than improvising.
Read team/briefs/common.md, reviews/2026-11-24-astra-review-5-pm.md (P0-2), api-worker/README.md, src/*.ts.
Local only: never `wrangler login`, `deploy` or any real-account command. Nothing may take a payment.

1. **Names, one set everywhere.** Vars `PAYMENTS` = `off|on` (default `off`, committed) and `PREVIEW` = `on|off`.
   Delete `PAID_ENABLED` and `paidEnabled()` with no alias. Prices: `PRICES` in `src/config.ts` with keys `query`,
   `match`, `changes`, `bulk_category`, `bulk_all` at the D3.3 values, commented "provisional (D3.3)". README route
   table, OpenAPI, llms.txt, wrangler.jsonc comments and tests use exactly these names. A unit test greps the repo
   for `PAID_ENABLED` and for any price string not in `PRICES`.
2. **Route matrix as data.** Write `api-worker/test/route-matrix.json` encoding every D3.5 row: method, path, mode
   (off / on / on-bad / breaker / preview-off), input case, expected status, error code, `Retry-After` present,
   listed-in-discovery. One e2e test iterates it. Generate the README route table from it (script) or test that they
   match. Off-mode rows run against a recording mock facilitator and assert **zero calls and no 402**. Requests
   carrying `X-PAYMENT` or MCP `_meta["x402/payment"]` in off-mode are served free and the payment is never forwarded.
3. **Data = query pack.** `scripts/build_r2.py` gains `--tier free|paid` (gate from `scripts/source_policy.py`,
   A3's licensing-gate brief; coordinate, don't fork the logic). The free pack goes to `api-worker/pack/`
   (gitignored), served as Worker static assets with `run_worker_first: true` and read via the `ASSETS` binding. The
   R2 binding is removed from the L1 config (paid mode reads the paid pack the same way until L2 decides
   otherwise). The pack manifest carries `release`, `policy_version` and checksums. `/health` returns them. Every
   JSON response includes `release`.
4. **Match.** Port `scripts/match.py` to `src/match.ts` with parity tests on tests/fixtures (same inputs, same ids
   and confidence buckets). Until parity passes, `/v1/match` → 404 `not_available` and `match_product` is absent
   from MCP `tools/list`, OpenAPI and llms.txt. Report which state you landed in.
5. **Bounds** exactly per D3.6, checked before any data load. Unknown params → 400. Tests for each bound at limit
   and limit+1.
6. **Quota and breaker** per D3.7: Rate Limiting binding (60/min/client key), `Budget` Durable Object (SQLite
   backend) sharded 16 ways by HMAC(client key), in-memory counts flushed by alarm every 60 s, daily 1,000 shared by
   REST and MCP tool calls (batch of N = N; internal MCP→REST dispatch is not re-counted), separate beacon budgets
   (miss 30/day, event 200/day). `Retry-After` in seconds to reset. DO failure → binding-only plus a `quota_degraded`
   point. `Breaker` DO: global daily data-route total, threshold var `BREAKER_DAILY` (default 60000), state cached
   30 s, 503 `preview_capacity` when tripped. A test forces a low threshold. Key derivation: IPv4 /32, IPv6 /64
   from `CF-Connecting-IP`.
7. **Cache.** Canonical cache key = release + route + category + sorted validated params. 300 s for 200s and for
   404 `not_found`. Cache hits still count against quota.
8. **Metrics contract** per measurement-plan §1-2: one AE point per request (`specsheet_requests`), fields in that
   order, the daily salt in the `Breaker` DO (created on first use, deleted at 01:00 UTC next day by alarm), and the
   redaction function for miss text with unit tests (emails, URLs, phone-like runs, length). Traffic class
   `test` for header `X-Specsheet-Test: 1`. `POST /v1/event` allowlist and `POST /v1/miss`, both CORS for the site
   origin only, size-capped. Never write IP, full UA or filter values: a test inspects every written point.
9. **Load test (local).** `scripts/load-test.mjs` against `wrangler dev`: laptops queries at max filters/limit, and
   MCP batches. Report p50/p95 wall and CPU (`--inspect` or the CPU time Wrangler reports). If p95 CPU > 5 ms,
   report it as a Q6 risk with the hot path named.
10. **Discovery and docs.** OpenAPI/llms.txt list only routes that return data in the current mode, say "free
    preview, quotas may change, paid tier not enabled", explain the shared NAT budget, and point bulk users to the
    static files on Pages. README "Owner deploy steps" = checklist step 15 exact commands (workers.dev, no R2 at L1)
    and the L2 steps marked "after legal review". `scripts/kpi.sql` + `scripts/kpi.sh` (reads the token from a
    chmod-600 file materialized from `pass specsheet/cf-analytics-read`, writes `state/metrics/<week>.csv`) produce
    each measurement-plan §3 row.
Done when: `npm test` + typecheck pass; the route-matrix e2e covers every row in all modes; bounds, quota (REST+MCP
shared), breaker, miss/event, redaction and no-PII-written tests pass; load test reported. No commits. Report
team/reports/2026-11-24-api-gateway.md (<=60 lines), listing shared-file edits.
