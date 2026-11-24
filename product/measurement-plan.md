# Free-deploy measurement plan (A5, 2026-11-24)

Goal: decide within 4 weeks whether the free deploy shows real interest, and which categories and specs drive it.
Privacy is fixed by D4 (product/decisions.md): no cookies, no accounts, no stored IPs. Metrics come from Cloudflare Web
Analytics (pages) and Workers Analytics Engine (API/MCP). Search-miss text is stored truncated and never with an IP.
Client identity is a **daily-rotating salted hash** of IP + user-agent, computed in the Worker and never stored raw. It is
used only to count unique clients per day. Salt rotates at 00:00 UTC, so cross-day tracking is impossible by design.

## Events (Analytics Engine; one data point each; blobs = strings, doubles = numbers)
| Event | When | Fields |
|--|--|--|
| `page_view` | CF Web Analytics (automatic) | path, referrer host, country |
| `api_call` | every /v1 request | route, category, status, client_kind (browser/agent-UA/mcp/other), cache hit, latency |
| `query` | /v1/query and the UI filter apply | category, filter keys used (sorted, no values), result count, `has_unknown_filter` |
| `killer_query` | UI preset or API call with `?preset=<id>` | preset id (section 5 of demand-survey.md), result count |
| `match` | /v1/match and match_product | category, matched (bool), confidence bucket |
| `mcp_tool` | each MCP tools/call | tool name, category, result count, error code |
| `product_view` | product page or products/<id> fetch | category, brand_id (not product id, keeps cardinality low) |
| `source_click` | outbound click on a source link (UI beacon) | category, source domain |
| `spec_unknown_shown` | product page renders an `unknown` for a core spec | category, spec key |
| `miss` | POST /v1/miss (search returned 0 rows or the user pressed "not here") | category, truncated query (80 chars) |
| `request_click` | "request this product/spec" link opened | category |
| `bulk_download` | dataset file fetch (category bundle) | category, bytes |
| `would_be_paid` | call that the switch-on price table (D3) would bill | route, units |
Not logged: free-text beyond 80 chars, full IPs, product-level paths in referrers, anything from request bodies except `miss`.

## What counts as interest (in priority order)
1. **Returning agents.** Distinct client hashes making MCP or API calls on >= 3 separate days per week. Each day is counted
   separately because the salt rotates, so the proxy is "distinct agent UAs seen on >= 3 days". This is the strongest
   signal, because it means someone wired us into a workflow.
2. **Killer-query use and engagement**: killer_query runs, followed by product_view or source_click in the same session (UI only).
3. **Misses and requests**: people asked for something we lack. This is demand with a direction, and it feeds the A2 queue.
4. External links: referrers from forums, Reddit, HN, GitHub and MCP registries (Glama, Smithery, mcp.so, official registry).
Vanity, tracked but not decisive: raw page views, bulk downloads (one scraper can dominate).

## Thresholds
| Metric | 2 weeks: "keep going" | 4 weeks: "real interest" | Below this at 4 weeks |
|--|--|--|--|
| Unique human visitors/day (CF WA, 7-day avg) | >= 50 | >= 200 | < 50: rethink discovery, not data |
| Distinct agent/MCP clients/day (7-day avg) | >= 5 | >= 25 | < 5: MCP listing/descriptions failing |
| Clients active >= 3 days/week (agents) | >= 2 | >= 10 | 0: no workflow adoption |
| MCP tool calls/day | >= 50 | >= 500 | |
| Killer-query runs/week | >= 100 | >= 500 | |
| Killer query → source_click or product_view | >= 15% | >= 25% | < 10%: results not trusted/useful |
| Search misses + requests/week | >= 20 | >= 60, with >= 5 distinct categories | |
| Inbound referrer domains (non-search) | >= 3 | >= 10 incl. 1 forum thread we did not post | |
| Corrections reported (corrections@ + GitHub) | >= 1 | >= 5 | Many with no fix flow = reliability alarm |
| would_be_paid calls/day | track | >= 1,000 | Triggers the owner's legal review sooner |
Decision at week 4: two or more "real interest" rows met → prioritize the paid switch-on plus the next-3 categories. Only
agent rows met → double down on MCP/API, keep the UI minimal. Nothing met → spend week 5 on discovery (posting killer-query
answers into the forum threads cited in demand-survey.md), not on more data.

## Weekly readout (coordinator, Mondays)
Top 10 misses by category, killer-query table (runs, CTR, zero-result rate), top `spec_unknown_shown` keys (this is the
coverage backlog for A1/A2), agent clients and tools, correction count. Use one Analytics Engine SQL query per row, kept
in `api-worker/scripts/kpi.sql` (api brief).
