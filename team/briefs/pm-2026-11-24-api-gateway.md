# Brief: api-worker → public gateway, PAYMENTS=off launch mode (PM D2, D3, D4). Owner: api agent (Opus/Sonnet).
Read team/briefs/common.md, product/decisions.md (D2-D4), api-worker/README.md. Local only: never `wrangler login`,
`deploy`, or `r2` against a real account. Revenue is on hold pending the owner's legal review: nothing here may
take a real payment. Wait for the in-flight api-worker scaffold agent to finish before editing.

1. **Mode switch.** Var `PAYMENTS` = `off` (default, committed) | `on`.
   off: /v1/query, /v1/match, /v1/changes and MCP tools served free under preview quotas; /v1/bulk/* → 404
   `{"error":"not_available"}`; no 402 anywhere. on: x402 above free allowances (prices below); fails closed 503
   without PAY_TO / mainnet config (keep existing resolveX402 behaviour). Tests for both modes + "on without secrets".
2. **Prices** (src/config.ts): query $0.002, match $0.005, changes $0.01, bulk per category $1.00, bulk all $5.00
   (add `/v1/bulk/all.jsonl.gz`). Free allowance when on: query 100/day/IP, match 20/day/IP.
3. **Rate limiting**: Workers Rate Limiting binding, 60 req/min per IP on dynamic routes + MCP; daily 1,000/IP
   counter (in mode off) via a Durable Object or KV-free approach of your choice (justify cost; Workers Free plan).
   429 + Retry-After. Static file paths: edge cache only, no per-IP limit.
4. **Serve the dataset + site from R2/assets**: `/api/v1/*` read from R2 `releases/<current>/...` (current.json
   pointer, 60 s cache) with Cache API; site shell (docs/index.html, app.js, styles.css, favicon) as Worker static
   assets at `/`. Keep the 302-to-GH-Pages path as a fallback behind `STATIC_ORIGIN` until cutover. Same object
   layout A3 uploads (coordinate via team/briefs/pm-2026-11-24-release-r2.md). Root-level `/llms.txt`,
   `/openapi.json`, `/robots.txt` (disallow /v1/query, /v1/match, /mcp) served by the Worker.
5. **Metrics**: Analytics Engine dataset `specsheet_requests`: blobs = route, category, status, client class
   (browser/agent-UA/mcp), mode, would_be_paid; doubles = bytes, ms; cache hit. Never write IP, UA string verbatim,
   or query text. Add `scripts/metrics-weekly` query example (SQL API) to README, owner runs it.
6. **Search-miss intake**: `POST /v1/miss` {category, q (normalized, <=120 chars), build} → Analytics Engine
   `specsheet_misses`; 204; rate-limited; no IP stored. CORS for the site origin only.
7. **Discovery texts**: llms.txt/OpenAPI say "free preview, quotas may change; paid tier not yet enabled" in mode
   off; brand name from a `BRAND` var (default "specsheet"; owner domain decision pending: knownspec).
8. README "Owner deploy steps": exact commands for checklist step 15 and the L2 switch-on (step 23), bucket names
   `specsheet-data`, `specsheet-raw`, custom domain routes. No secrets in files.
Done when: `npm test` + typecheck pass, e2e covers mode off/on, miss beacon, 429. No commits. Report
team/reports/2026-11-24-api-gateway.md (<=60 lines), list shared-file edits.

**Addendum (PM round 2, 2026-11-24):** implement the event table in product/measurement-plan.md in Analytics Engine. That means
`api_call`, `query` (filter keys only), `match`, `mcp_tool`, `would_be_paid`, `bulk_download`, plus a `POST /v1/event` sink for the
UI beacons (killer_query, source_click, request_click, spec_unknown_shown) with a strict allowlist of event names and fields, and the
daily-rotating salted client hash (never stored raw). Put the weekly KPI SQL in `api-worker/scripts/kpi.sql`. Serve `GET /v1/presets` from docs/presets.json.
