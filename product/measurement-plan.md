# Free-deploy measurement plan (A5, 2026-11-24; revised PM round 3)

Goal: decide within 4 weeks whether the free deploy shows real interest, and which categories and specs drive it.
**Changed 2026-11-24 (R3):** added the privacy contract (§1). Events are folded into one data point per request.
The cross-day "returning clients" KPI is dropped, operational KPIs are added, and test/bot/retry traffic is
separated. Decision: D4 in `product/decisions.md`.

## 1. Privacy contract (the Privacy page must say exactly this, in plain words)
- Page views: Cloudflare Web Analytics (cookieless JS beacon on the GH Pages site). Nothing else runs in the browser.
- **Client key** (quota only, never written): IPv4 /32 or IPv6 /64. It lives in memory and in DO counters keyed by an
  HMAC of the key, and counters are deleted at the day reset.
- **`cid`** (pseudonymous, ≤ 25 h): first 16 hex of HMAC-SHA256(daily salt, client key ‖ UA family). The salt is 32 random
  bytes made by the breaker DO per UTC day and deleted at 01:00 UTC next day. It is never logged or exported. After
  deletion, no `cid` maps back to an IP, and `cid`s from different days cannot be linked.
- UA family: one of `browser | mcp | curl-like | python | node | other`, or `bot:<name>` for known crawlers. It is
  spoofable, so it is labelled "declared". The full UA string is never written.
- **Never written:** IP, full UA, request bodies, filter values, product ids in referrers.
- **Miss text:** lowercase, ≤ 80 chars, with emails, URLs and runs of ≥7 digits that contain spaces/dashes/parentheses
  (phone-like) replaced by `·`, *before* writing. It is published to the repo (`team/queue/requests.md`) only when
  ≥3 distinct `cid`s sent the same normalized text in one week.
- **Retention:** Analytics Engine's fixed platform retention (the api agent confirms the figure; Privacy states it).
  Weekly aggregates go to `state/metrics/<week>.csv` (local, gitignored) and never into the public repo.
- **Deletion:** individual AE points cannot be deleted. This is why nothing identifying is written (runbook §4).
- **Access:** one read-only Account Analytics token, owner-held (`pass specsheet/cf-analytics-read`), materialized
  chmod 600 only for `api-worker/scripts/kpi.sh` (runs `kpi.sql`). No dashboard is shared publicly.

## 2. Data points (Analytics Engine `specsheet_requests`; one point per request, ≤ 100k/day Free cap, breaker at 60k)
| Field | Content |
|--|--|
| index1 | event kind: `api` (REST), `mcp` (one per logical tool call), `beacon` |
| blob1-3 | route, category, status code |
| blob4 | outcome: `ok_results` / `ok_empty` / `match_fail` / `bad_input` / `quota` / `breaker` / `error` |
| blob5 | UA family (declared) |
| blob6 | mode `off|on`, plus `would_be_paid` route key when the D3.3 table would bill it |
| blob7 | traffic class: `real` / `test` (header `X-Specsheet-Test: 1` or our smoke UA) / `bot` / `retry` (same cid+canonical key within 10 s) |
| blob8 | release id |
| blob9 | MCP `clientInfo.name`, normalized `[a-z0-9-]{1,32}` (else `other`), MCP only |
| blob10 | `cid` |
| blob11 | filter keys used (sorted, schema keys only) for queries, beacon event name for beacons, or redacted miss text for misses |
| double1-4 | result count, response bytes, wall ms, cache hit (0/1) |
Beacon events (`POST /v1/event`, allowlist): `killer_query` (preset id, result count), `source_click` (category, source
domain), `request_click` (category), `spec_unknown_shown` (category, spec key), `product_view` (category, brand id).
Misses arrive via `POST /v1/miss` as kind `beacon`, name `miss`.

## 3. KPIs (one SQL block each in `api-worker/scripts/kpi.sql`, run weekly, `traffic class = real` only)
Operational, reported every week and checked before any interest reading:
- Successful useful calls (`ok_results`) per day, split REST / MCP; empty rate; match-failure rate (after port).
- p95 wall ms per route; 429 rate; 5xx rate; breaker trips; `quota_degraded` count.
- Response bytes per day; edge cache hit rate.
- Allowance use: Worker requests, DO requests, DO rows written and AE writes as % of the Free daily caps. Cost per
  successful call is "% of free allowance per 1k ok calls" until a paid plan exists.

Interest (in priority order):
1. **Agent adoption:** distinct `cid`s per day with kind `mcp` or a non-browser UA (7-day average), and **MCP client
   software names seen on ≥3 days/week**. It counts software, not people; it replaces the dropped
   "clients active ≥3 days".
2. **Killer-query use and engagement:** `killer_query` runs. CTR = (`source_click` + `product_view`) / `killer_query`
   per day, aggregated (no session linking).
3. **Misses and requests:** k≥3 misses + `missing-product` issues per week, distinct categories.
4. External referrers (CF Web Analytics), corrections received.
Usage that is not willingness to pay: `would_be_paid` calls. A commercial reading needs repeat use (criterion 1) plus
direct feedback (a Discussions poll and hello@ replies).

## 4. Thresholds
| Metric | 2 weeks: "keep going" | 4 weeks: "real interest" | Below this at 4 weeks |
|--|--|--|--|
| Unique human visitors/day (CF WA, 7-day avg) | >= 50 | >= 200 | < 50: rethink discovery, not data |
| Distinct non-browser `cid`s/day (7-day avg) | >= 5 | >= 25 | < 5: MCP listing/descriptions failing |
| MCP client names seen ≥3 days/week | >= 1 | >= 4 | 0: no workflow adoption |
| `ok_results` MCP tool calls/day | >= 50 | >= 500 | |
| Killer-query runs/week | >= 100 | >= 500 | |
| Killer-query CTR (daily aggregate) | >= 15% | >= 25% | < 10%: results not trusted/useful |
| Misses (k≥3) + requests/week | >= 10 | >= 30, with >= 5 distinct categories | |
| Inbound referrer domains (non-search) | >= 3 | >= 10 incl. 1 forum thread we did not post | |
| Corrections reported | >= 1 | >= 5 | Many with no fix flow = reliability alarm |
| Empty-result rate on `/v1/query` | track | <= 30% | > 50%: coverage or filter UX problem |
| `would_be_paid` calls/day | track | >= 1,000 + feedback | Prompts the owner's legal review sooner |
Decision at week 4: two or more "real interest" rows met → prioritize source clearances (paid content) and the next 3
categories. Only agent rows met → double down on MCP/API. Nothing met → week 5 on discovery, not data.

## 5. Weekly readout (coordinator, Mondays)
Operational block first. Then: top k≥3 misses by category, the killer-query table (runs, CTR, zero-result rate), top
`spec_unknown_shown` keys (the A1/A2 coverage backlog), agent `cid`s and MCP client names, and corrections. Output
goes to `state/metrics/` only. The coordinator summarizes counts (no miss text below k=3) in their report.
