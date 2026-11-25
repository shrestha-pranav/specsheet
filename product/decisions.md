# specsheet product decisions (A5 PM log)

Format per entry: decision, options considered, why, reversibility, owner action. Revisions are made in place and
each carries a dated **Changed** note saying what moved and why. The text it replaced is in git history.
Standing constraint (2026-11-24): **revenue on hold pending the owner's legal review.** The product launches
free/open. The paid tier is built and shipped **disabled** (`PAYMENTS=off`). Switching it on is an L2 project
with its own gates (D3.4), not a one-step switch. Entity and operating-structure questions are for counsel; this
log makes no recommendation on them.

Round 3 (2026-11-24) answers `reviews/2026-11-24-astra-review-5-pm.md` and applies coordinator decisions (a) to (e):
D1.1 to D1.3 (licence boundaries, the single source policy), D2 (L1 topology), D3 (route matrix, quotas, breaker, prices
provisional), D4 (metrics privacy contract, abuse) and D7 (takedown runbook), which is new.

---

## 2026-11-24 PM round 1 (revised in round 3 where marked)

### D0. Brand and domain: **"knownspec"**, domain `knownspec.com`
- Options: keep "specsheet" (taken: specsheet.dev/.org/.io/.app all resolve to registered zones; generic word,
  no distinctive mark); `plainspec.com`; `knownspec.com`; `citedspecs.dev`; `specatlas.dev`.
- Why: "knownspec" carries the product promise ("unknown is never no"; only known, cited values are facts),
  is short, and `.com`/`.dev`/`.org` showed no DNS delegation on 2026-11-24 (NXDOMAIN is a hint, not proof of
  availability). Runner-up: `plainspec.com` (same DNS result). The repo and code keep the name `specsheet`
  (internal name; a rename breaks links for no user value). Site title, llms.txt and MCP server name use the brand.
- Reversible: yes until marketing exists; cost of switching later is redirects only.
- Owner: check registrar availability + a quick USPTO trademark search for "knownspec" in classes 35/42; buy
  `knownspec.com` at Cloudflare Registrar (if taken: `plainspec.com`). Tell the coordinator which one you got.

### D1. Licensing
**D1.1 Code: Apache-2.0 for code files; CC BY 4.0 for prose; ODbL for the database; third-party material keeps its own licence.**
The per-file boundary table is in `DATA-LICENSE.md`.
- **Changed 2026-11-24 (R3):** was "Apache-2.0 for the whole repo". That hid the exceptions (prose, data,
  dependency notices). The licence choice is unchanged.
- Options: MIT; Apache-2.0; FSL-1.1-Apache-2.0 / BSL / Elastic (source-available).
- Why: the moat is not the code. A competitor with our adapters still needs the crawl history, the identity
  decisions, the review ledger and the release cadence. Source-available licences add friction for agent builders
  and contributors. Apache over MIT for the patent grant and NOTICE handling. Runner-up: FSL on `api-worker/` only,
  if legal review finds a reason to protect the gate code.
- Reversible: a more restrictive licence applies only to future versions. Done: `LICENSE` exists.

**D1.2 Free data: ODbL 1.0, limited to rights we hold.** It covers (1) the compilation (selection, arrangement,
schema, identity and review decisions, our notes and derived fields) and (2) values from sources marked
`licence_grant: true` in `data/source-policy.yaml`. Values from any other source are shown as facts with a source
link, and no licence grant from us covers them.
- **Changed 2026-11-24 (R3):** removed the blanket claims "US-government-sourced values are public domain" and
  "individual facts are not claimed". EPA hosting does not make every manufacturer-submitted value a federal work,
  and CARB's public-record status is not a reuse licence. Each source now has its own evidence and attribution
  rule (D1.3). Also corrected: ODbL does not let produced works off with attribution alone, since public use of a
  produced work from an adapted database can trigger the §4.4/§4.6 offer obligations. And ODbL does not stop
  anyone reselling copies, because commercial use is allowed. Wording: `DATA-LICENSE.md` (draft) and the Sources
  page text in `team/briefs/pm-2026-11-24-licensing-gate.md` §6.
- Measured consequence (docs/api/v1, 2026-11-24): 15,942 of 207,430 known values (7.7%) are under the
  value-level grant, all from ENERGY STAR in air-purifiers, monitors and tvs. The other 92% are published as linked
  facts, with only the compilation licensed.
- Options: CC BY 4.0; ODbL 1.0; CC BY-NC 4.0; custom no-bulk terms. Why ODbL: it is built for databases, and
  share-alike on adapted databases keeps public forks open. Runner-up: CC BY 4.0, if legal review says share-alike
  buys nothing in practice.
- Future alternative licence (revenue, on hold): it can cover only point (1), granted values whose source terms
  allow relicensing, and contributions under terms that grant us relicensing rights. Contribution terms are a
  prerequisite (open-questions Q1). Paid sells service convenience (fresh, pinned, filtered, identity-resolved
  answers). It does not depend on that licence.
- Docs/prose: CC BY 4.0.

**D1.3 One versioned source policy gates all three outputs: `data/source-policy.yaml`.**
Per domain: `free`, `paid` and `licence_grant` (true/false), `evidence` (level, refs, date), conditions and what
would clear it. Invariants: a grant implies free; paid implies a grant; paid or grant requires `fetched` evidence
of permission.
- **Changed 2026-11-24 (R3):** replaced "one exclusion list; free tier unchanged; unknown domains default to
  free `facts_link_only`". The review (P0-1) found the permissive defaults unresolved. Now:
  - **Unlisted domains** are withheld from the licence grant and from paid. They may show free as fact plus link,
    but **a release build fails** while any published value cites an unlisted domain, so every published domain
    has an explicit disposition.
  - **Uncleared sources stay on the free site** (coordinator decision a): Lenovo PSREF, VESA DisplayHDR, CSA DCL,
    CARB (pending) and the 38 unaudited maker domains are `free: true, paid: false, licence_grant: false`. Laptops and
    monitors are not pulled. Risk accepted: free republication of facts does not cure upstream terms. That is why
    we grant nothing over these values and why the takedown path (D7) must work at launch.
  - **ENERGY STAR** is the only `paid: true, licence_grant: true` source, on fetched evidence (data.gov license field
    → EPA Data License). Retail, aggregator and review domains are `free: false`. No published value uses them today.
  - Makers moved from "paid, provisionally" to `paid: false` until their terms are audited. `iniushop.com` was
    reclassified from retail to maker (it is INIU's own store).
- A value is kept in a tier only if at least one of its own sources is allowed in that tier. Disallowed sources
  are removed from that tier's `sources[]` entirely. Otherwise the value becomes `not_published` with no value. A3
  implements the gate and its fixtures (`team/briefs/pm-2026-11-24-licensing-gate.md`).
- Rule for both tiers (unchanged): publish facts, identifiers and links only, never expression (copy, images,
  PDFs, page text). Raw snapshots are never published. Respect robots.txt and rate limits.
- Reversible: yes. Each disposition change is a new `policy_version`, stamped into every manifest.
- Owner: Q2 (Lenovo permission) and, optionally, the VESA, CSA and CARB permission emails (open-questions Q5).

**D1.4 Repo stays public.** Unchanged. Raw/, state/ and .env stay off-repo; gitleaks in CI; no personal data in
`team/`, `research/` or `product/`. Added in R3: weekly metrics output and miss text never go into the repo (D4).

### D2. Data of record and L1 topology
**Decision: git stays the system of record for *decisions*. For L1 the site shell and static dataset stay on GitHub
Pages. A Worker on `workers.dev` adds only the API, MCP and metrics. R2 holds private copies (raw backup, release
archive) and is not a live origin. The full hosting migration is deferred to before L2.**
- **Changed 2026-11-24 (R3):** replaced "move the shell to Worker static assets, serve the dataset from R2, redirect
  GH Pages" (coordinator decision c; review P1-3). That move is not needed to launch free. Reasons:
  (1) GitHub's limit is on sites *primarily* for commercial transactions or SaaS. A free data site does not hit
  it, so the move is due before any paid use, not now. (2) Serving 18k static files through a Worker would put the
  whole site on Workers Free's 100k requests/day budget and on the 20k-files-per-version cap (8% headroom).
  (3) A redirect while gh-pages keeps publishing risks overwriting the redirect and serving HTML to JSON clients.

| Layer | L1 home | Notes |
|---|---|---|
| Code, profiles, decisions ledger, policies, `data/source-policy.yaml`, id registry, release manifests | git `main` (public) | Unchanged. |
| Site shell + static dataset (`docs/`, `api/v1/**`) | GitHub Pages (gh-pages, one release) | Unchanged. Optional custom domain later. Takedown = rebuild + republish (D7). |
| API/MCP/metrics | Worker `specsheet-api` on `<sub>.workers.dev` | Data = a **query pack** (free-tier gated index + record shards, release-pinned) bundled as Worker static assets with `run_worker_first: true`, so nothing is served unmetered or ungated. One Worker version = exactly one `release_id`. No R2 read on the request path. |
| Quota + breaker state | Durable Objects (SQLite backend, Free plan) | D3.5. In-memory counters with periodic flush (Free plan: 100k DO requests/day, 100k rows written/day). |
| Metrics | Workers Analytics Engine | One data point per request (Free: 100k writes/day, 10k reads/day). D4. |
| Working store | `state/specsheet.sqlite`, local | Nightly local backup (brief backup). |
| Raw evidence | local `raw/` + second disk; later R2 `specsheet-raw` (private) | 9.2 GB raw is close to R2's 10 GB-month free storage. Overage is $0.015/GB-month, so cents, but it is not free. **No bucket lock**: versioning on, with a 30-day lifecycle on noncurrent versions, so source retention caps (e.g. 72 h) and takedowns can be honoured. |
| Release archive | R2 `specsheet-data/releases/<id>/` (private) | History for `/v1/changes` and rollback. Write-once by script, **no 365-day bucket lock** (it would block takedowns). |

- Release promotion (A3): build → gate → manifest with per-file sha256, counts and `policy_version` → verify →
  publish gh-pages → build the query pack for the same release id → (owner/coordinator) `wrangler deploy` → smoke
  `/health` reports that release. Rollback: `wrangler rollback` to the previous version (tested once before
  announce), plus a gh-pages republish of the previous release from the archive or local `releases/`.
  For a short time GH Pages and the Worker can be one release apart. Each response carries `release`, so neither
  ever mixes releases.
- Before L2 (deferred migration): move the shell and data to Cloudflare under the purchased domain, decide asset
  vs R2 serving with measured file counts and bytes, keep separate fallback artifacts (no HTML on JSON paths),
  test DNS/TLS, CORS, legal/discovery paths, cache invalidation and origin rollback. Budget it as its own project.
- Options considered: (a) status quo GH Pages only (no API controls or metrics); (b) full migration now (round 1,
  withdrawn); (c) Pages + API Worker (chosen); (d) hosted DB (not needed; reads are static per release).
- Reversible: fully. The Worker is additive, and Pages keeps working without it.

### D3. Free vs paid tiers
**D3.1 The static dataset stays fully public and free** on GH Pages, as gated by `free: true`. Bulk copying is
accepted. Unchanged, except the licence wording now follows D1.2.

**D3.2 Free preview on the Worker (PAYMENTS=off):** `/v1/query`, `/v1/changes` and MCP `query_specs` are free under
the shared quota in D3.5. `/v1/match` and MCP `match_product` are **not offered and not listed** until the matcher
is ported (`scripts/match.py` exists; the Worker still has the 501 stub). Bulk returns 404. No 402 anywhere, no
payment attempt, and any payment header is ignored.
- **Changed 2026-11-24 (R3):** was "per IP 60/min + 1,000/day; match free when implemented". Now REST and MCP
  share one per-client budget. The daily count is coordinated (Durable Object). There is a global circuit breaker,
  inputs are bounded, and discovery lists only routes that return data.

**D3.3 Paid prices: provisional, not a readiness claim.** Single source: `api-worker/src/config.ts` `PRICES`.
| Key | Route | Provisional price | Free allowance with PAYMENTS=on |
|---|---|---|---|
| `query` | `GET /v1/query` | $0.002 | 100/day per client key |
| `match` | `GET /v1/match` | $0.005 | 20/day |
| `changes` | `GET /v1/changes` | $0.01 | none |
| `bulk_category` | `GET /v1/bulk/<cat>.jsonl.gz` | $1.00 | none |
| `bulk_all` | `GET /v1/bulk/all.jsonl.gz` | $5.00 | none |
- **Changed 2026-11-24 (R3):** prices are now marked provisional. The review showed $0.002 per call loses half its
  gross to a $0.001 settlement fee before compute, failures and support. It also showed a $19/100k plan can't fund
  100k separate settlements, and that monetization research cites a $0.01 Stripe minimum. L2 gate: choose the
  settlement path, confirm its real minimum and fees, then price per call only if the fee is ≤10% of the price.
  Otherwise sell prepaid credit packs (one settlement per pack). The leading candidate is a $1 pack = 500 queries.
  Bulk sells a release-pinned, gated single file for convenience. It cannot stop anyone rebuilding the data from the
  free dataset, and it does not try to. Paid artifacts carry only `paid: true` values, which **today is ENERGY STAR
  only**. A paid tier worth selling therefore needs source clearances first (L2 checklist).

**D3.4 Mode var `PAYMENTS` = `off` | `on`** (replaces `PAID_ENABLED`; the old name is removed, not aliased).
`PREVIEW` = `on` | `off` is a manual kill switch: `off` makes every data route return 503 `preview_paused`.
`on` with invalid payment config fails closed: a 503 on every paid route, including its free allowance.
- **Changed 2026-11-24 (R3):** "one-step switch-on" withdrawn as a readiness claim. Mainnet facilitator auth is
  still a TODO in `src/x402.ts`, and paid content is near-empty under D1.3. Switch-on is the L2 checklist.

**D3.5 Route matrix (canonical; the executable copy is `api-worker/test/route-matrix.json`, and README and tests
are generated from or checked against it).**
Columns: off = `PAYMENTS=off`; on = `PAYMENTS=on` with valid config; on-bad = `PAYMENTS=on` with missing or invalid
config. "Q" = counts against the shared client budget. Everything returns JSON with `release`.
| Route | off | on | on-bad | Listed in discovery (off) | Q |
|---|---|---|---|---|---|
| `GET /` , `GET /health` | 200 (release, policy_version, payments, preview, breaker) | 200 | 200 (payments: not_configured) | yes | no |
| `GET /openapi.json`, `GET /llms.txt` | 200, only routes that return data in this mode | 200 + prices | 200, paid routes absent | yes | no |
| `GET /robots.txt` | 200 `Disallow: /` (API host; the site's own robots.txt is on Pages) | same | same | n/a | no |
| `GET /v1/query` (valid) | 200 free | 200 within allowance, then 402 | 503 `payments_not_configured` | yes | yes |
| `GET /v1/changes` (valid) | 200 free | 402 → 200 paid | 503 | yes | yes |
| `GET /v1/match` | 404 `not_available` until ported; then 200 free | after port: allowance then 402 | 503 | no until ported | yes |
| `GET /v1/bulk/<cat>.jsonl.gz`, `/v1/bulk/all.jsonl.gz` | 404 `not_available` | 402 → 200 | 503 | no | yes |
| `POST /mcp` `tools/call` | 200 JSON-RPC result, `query_specs` only (+`match_product` after port) | JSON-RPC payment-required error beyond allowance | JSON-RPC error `payments_not_configured` | yes | yes, per tool call (batch of N = N) |
| `POST /mcp` `initialize` / `tools/list` | 200 | 200 | 200 | yes | no (but rate-limited per minute) |
| `GET /mcp` | 405 | 405 | 405 | n/a | no |
| `POST /v1/miss` | 204 (CORS: site origin only) | 204 | 204 | no | separate 30/day |
| `POST /v1/event` | 204 for allowlisted events, else 400 | 204 | 204 | no | separate 200/day |
| any other path | 404 `not_found`, cached 300 s | same | same | n/a | no |
| Invalid input (any data route) | 400 / 413 / 414 before any data load, never charged | same | same | | yes |
| Over budget | 429 + `Retry-After` (seconds) | 429 (minute) / 402 (day allowance spent) | 429 | | |
| Breaker open or `PREVIEW=off` | data routes 503 `preview_capacity` / `preview_paused` + `Retry-After`; `/`, `/health`, discovery 200 | same | same | | |
- Removed in R3: the `/v1/*` 302 catch-all to GH Pages (it invites random-path traffic; static data is fetched from
  Pages directly), and `GET /v1/presets` (the UI reads `docs/presets.json` from Pages).
- Off-mode proof: a test runs every matrix row with a mock facilitator that records calls, and asserts **zero
  facilitator calls and no 402**. Requests that carry a payment header are served free and the header is ignored.

**D3.6 Input bounds** (rejected before data load; errors are never charged and count once against quota):
URL ≤ 2,048 chars (414). `category` must be in the manifest. `q` ≤ 120 chars. `title` (match) ≤ 200. `filters` ≤ 512
chars, ≤ 12 clauses, keys from the category schema, each value ≤ 64 chars. `fields` ≤ 40 schema keys. `limit` default 50,
max 100. `offset` ≤ 2,000 (deeper reads: use the static files). `changes`: `since` must be a retained release id or an ISO
date within 90 days, `limit` ≤ 1,000. Unknown query parameters → 400 (this blocks query-string cache-busting).
`POST /mcp` body ≤ 16 KB, JSON-RPC batch ≤ 10. `/v1/miss` ≤ 1 KB, `/v1/event` ≤ 2 KB, one event each.
CPU target: p95 ≤ 5 ms CPU per request (Free plan limit is 10 ms), proven by a local load test on the largest
category (laptops).

**D3.7 Quota, cache and breaker.**
- Client key: IPv4 /32, IPv6 /64 (rotating inside a /64 earns nothing). Shared NATs share a budget, which is
  accepted and documented in llms.txt with a "use the static files for volume" pointer.
- Two layers. (1) Workers Rate Limiting binding at 60/min per client key. It is approximate and per-location, a
  cheap first line. (2) Daily budget of 1,000 per client key in Durable Objects sharded by key hash (16 shards):
  in-memory counts, flushed every 60 s by alarm. REST and MCP spend the same budget. MCP tools dispatch internally
  without re-counting or re-metering. Day boundary is 00:00 UTC. `Retry-After` = seconds to the reset.
- If a DO is unavailable, that request falls back to binding-only limits (fail open) and writes a
  `quota_degraded` metric. Paid routes in on-mode fail closed instead.
- Global circuit breaker: shards report totals to one breaker DO. Shards cache its state for 30 s. It trips at
  **60,000 data-route requests per UTC day** (60% of the Workers Free 100k/day, which is also the AE write
  budget). Tripped, data routes return 503 `preview_capacity` with `Retry-After` to the reset. Static data on
  Pages is unaffected.
- Edge cache: successful `/v1/query` and `/v1/changes` responses are cached 300 s under a canonical key (release
  id + category + sorted, validated params). Cache hits still count against quota, because each one is a billed
  Worker invocation.
- Budget alerts (owner): Cloudflare usage notifications at 50% and 80% of Workers and DO daily allowances.
- Cost envelope at L1 is **$0 on the Free plan**. The binding risk is availability (breaker or daily caps), not money.
  Paid plan ($5/month Workers Paid) only if the CPU load test fails 10 ms (open-questions Q6). R2: storage beyond
  10 GB-month at $0.015/GB-month; the raw backup alone is near that.

### D4. Other productization blockers
- **Legal pages:** `/terms`, `/privacy`, `/sources`, `/about` are live as drafts (`docs/pages.js`), and the owner
  approves them before announce. **Changed 2026-11-24 (R3):** Terms and Sources drop "values from US federal
  sources are public domain" and "individual facts are not claimed". They use the D1.2 wording instead (text in the
  licensing-gate brief §6). Sources groups credits by grant/no-grant from `data/source-policy.yaml`, not by
  `public_domain`. Privacy follows the D4 metrics contract below, since its current "IPs not stored" and
  "anonymous count" claims must match what the Worker actually does.
- **Contact:** Cloudflare Email Routing for `corrections@`, `legal@`, `hello@`. **Changed (R3):** launch requires
  *verified delivery*: one test message to each address arrives and gets a reply. Until the domain exists,
  `site.email_enabled=false` keeps GitHub links.
- **Takedown and corrections:** D7.
- **Abuse:** D3.6 bounds + D3.7 quota and breaker. **Changed (R3):** removed "R2 edge caching makes bulk crawling
  cost nothing" (false: Worker and R2 operations are metered) and the WAF 10x rule (the breaker covers it on Free).
  The beacons are CORS-limited to the site origin, but CORS does not stop scripts. They get separate budgets, an
  allowlist and size caps, and miss text is published only under the k≥3 rule below. Corrections stay on GitHub.
- **Metrics contract (privacy-reviewed; full spec in `product/measurement-plan.md`).** **Changed 2026-11-24 (R3):**
  "unique API clients/day" is kept only because a short-lived pseudonymous id is now defined:
  - `cid` = first 16 hex chars of HMAC-SHA256(daily salt, client key ‖ UA family). The daily salt is 32 random bytes
    created by the breaker DO at the first request of each UTC day, never logged or exported, and **deleted at
    01:00 UTC the next day**. After that, no `cid` can be recomputed from an IP. Cross-day linking is impossible by
    design, so the "clients active ≥3 days/week" KPI is **dropped**. It is replaced by "MCP client software names
    (`clientInfo.name`, self-declared, normalized) seen on ≥3 days/week", which measures software, not people.
  - Never written: IP, full UA string, request bodies (except redacted miss text), query values (filter *keys* only).
  - Miss text: lowercase, ≤ 80 chars, with emails, URLs and phone-like digit runs replaced by `·` before writing.
    It reaches the public `team/queue/requests.md` only when ≥3 distinct `cid`s sent it in the week.
  - One AE data point per request. Tests, bots and retries are flagged, and an MCP call is counted once at its
    logical tool call.
  - Retention: AE's fixed platform retention (the api agent confirms the current figure and the Privacy page
    states it). We export only weekly aggregates to `state/metrics/` (gitignored, local). Individual points can't
    be deleted, which is why nothing identifying is written. Access: one read-only Account Analytics token, owner
    held (`pass specsheet/cf-analytics-read`), used only by `api-worker/scripts/kpi.sql` via a wrapper.
  - Interpretation: would-be-paid calls measure usage, not willingness to pay. A commercial reading needs repeat
    use plus direct feedback (Discussions poll, hello@).
- **Discovery:** llms.txt, OpenAPI, Dataset JSON-LD and sitemap. **Changed (R3):** Worker discovery lists only routes
  that return data in the current mode (match omitted until ported). MCP Registry/Smithery/Glama/mcp.so
  submissions are after the free launch passes, not acceptance criteria. x402 directories only after L2.
- **Support channel, request loop:** unchanged (GitHub Discussions + Issues, `hello@`; weekly ranking script; close
  the issue on publish).

### D5. Launch plan
**Changed 2026-11-24 (R3):** L1 = approved free legal/privacy/source pages, the source-policy gate live in the free
build, the API Worker on workers.dev per the D3.5 matrix with bounds, quotas, breaker and the metrics contract
working, verified contact delivery, a drilled takedown runbook, visible freshness/coverage/unknown states, a tested
restore and a tested rollback. Directory submissions and the paid switch are not L1 acceptance criteria. Ordered
steps: `product/launch-checklist.md`.

### D6 (2026-11-24, PM round 2): coverage of opaque core specs before new categories; measured free deploy
- Decision: fill the top-10 demand specs (product/demand-survey.md §2) in the existing 12 categories first, because several are at 0%
  on data we already crawl. Then add USB-C docks, mini PCs and headphones in that order. The free deploy showcases killer-query
  presets gated at >= 80% fill and is measured per product/measurement-plan.md (4-week go/no-go thresholds).
- Options: (a) breadth, meaning new categories now [rejected: demand evidence centres on opaque specs we already model];
  (b) appliances via ENERGY STAR next [runner-up: cheap and reliable, but low opacity, so it adds little that is unique].
- Reversible: yes. Owner action: none.

### D7 (2026-11-24, PM round 3): takedown and correction runbook
- Decision: `product/takedown-runbook.md` is the procedure. A takedown first changes **policy**: a new
  `policy_version` sets the source or field disposition, with evidence `takedown:<ticket>`. Then it rebuilds and
  republishes, so the removal sticks in every later release. Targets: acknowledge within 3 business days; removed
  from Pages and the Worker within 7 days of a valid request; purged from the private R2 archive and raw backup
  within 14 days. Forks and third-party copies are out of our control, and the runbook says so honestly.
- It is drilled once on a fake source before announce (checklist).
- Options: ad-hoc edits to built files [rejected: the next build reintroduces the value]; bucket-locked archive
  [rejected: blocks removal].
- Reversible: yes. Owner action: DMCA agent designation goes with the legal review (needs an address of record).

### D8 (2026-11-24, PM round 4): showcase presets are gated on an in-scope population, not the whole category
- **Decision.** A preset's fill for each gate key = known / in-scope rows. A row is in scope when all four hold:
  (1) it carries at least one source of a tier in `scope.sources` (default `manufacturer`; purifiers add `regulatory`,
  because ENERGY STAR is where certified CADR lives); (2) its lifecycle is not `discontinued`, unless
  `include_discontinued`; (3) no known value rules it out on a filter listed in `scope.by` (the population-defining
  filter: "NVMe", "Wi-Fi 7", "120 Hz panel", "has USB-C", "45 W+ port"); (4) its status for that key is not
  `not_applicable`. **Unknown always stays in**, and a key is never scoped by its own value, so the scope cannot
  hide our own gaps. The gate passes when every key reaches `min_fill` (0.8) **and** at least `min_brands` (2) brands
  have a known value on every gate key. The card must say what it covers: "Covers N brands (list) · X of Y
  <category> in scope", plus excluded counts by reason and the brands that are not covered. The default list view
  shows the in-scope rows, with a one-click "show all Y".
- **Why.** The whole-category denominator measured the wrong thing. 2,855 of 4,234 monitors are ENERGY STAR or
  DisplayHDR listing rows, and those lists never carry PWM or USB-C power. 637 of 1,371 TVs are discontinued LG
  models (back to 2014 plasma). A 60 Hz TV cannot take 4K at 120 Hz. Under that denominator no preset could pass,
  however good our maker coverage got. But "in scope" must not mean "rows where we happen to have the value":
  every exclusion is a known fact about the row (its source class, its maker-stated lifecycle, a known value on
  another key), never the absence of the measured value.
- **Rejected.** (a) "Sold in the last N years": we have no dates to measure it with (`gen.release_year` is 0% in
  monitors and routers). Maker-stated `discontinued` is the honest proxy, and the runner-up once release years fill.
  (b) "Brands whose source publishes this key": it selects on the outcome. A parser bug that drops a field for a
  whole brand (LG and ASUS monitors have 0 `gen.size_class` today while their pages print it) would vanish from the
  denominator instead of showing as a gap. (c) The full shown slice (every other filter applied): it is honest, but
  the weight and size filters push rows out unevenly. The match / might-match split already shows that uncertainty.
- **Structural fixes made in `docs/presets.json`:**
  - Purifier: filter price is preview-only by policy (`claim/air-purifiers-structured@1`: a dated store price), so the gate was 0% forever.
    Now **smoke CADR ≥ 260 cfm**. The basis is the AHAM room-size rule (room area = 1.55 × smoke CADR, and
    400 / 1.55 = 258). 191 of 206 values are ENERGY STAR-certified (AHAM AC-1). Per-dollar ranking is dropped until a
    trusted filter-cost source exists. It passes today at 94.9%.
  - Router: `wifi.streams_6` is printed only by ASUS and Ubiquiti (31 records). It is not carried in the index, so
    the build always measured it as 0. TP-Link and NETGEAR barely print per-band stream counts, not even for 5 GHz
    (TP-Link 0 of 106 rows, NETGEAR 4 of 60). Now: **"Wi-Fi 7 routers with a 6 GHz band, ranked by 5 GHz link rate"**. Every maker publishes per-band
    PHY rates. Stream counts are shown as a column and not filtered.
  - SSD: makers rarely print NAND type (TEAMGROUP 23 of 173, SanDisk pages 17 of 74). The preset is now
    **DRAM-only** (the PCPartPicker ask), with NAND type as a column. A TLC preset returns only with a cleared NAND
    source.
  - Monitor: adds "has a USB-C input" (`usb.usbc_inputs ≥ 1`) as the population filter for the power-delivery fill.
    Its fill drops to 0% until makers' port lists are parsed. That is the honest number: today we do not know which
    monitors have USB-C.
  - 4K120 TVs: the 120 Hz panel filter is now explicit. Power banks: scoped by the 45 W+ port.
- **Today, under D8** (measured from records, not yet built): purifier 94.9% (passes) · 4K120 TVs 71.5% · ram 79.6%
  (fails min_brands: ASUS has no `mem.max`) · TV panel 65.0% · SSD DRAM 40.5% · router 6 GHz 37.8% · power-bank PPS
  11.2% · monitor 0%. The data work, ranked by effort per point: `team/briefs/pm-2026-11-24-preset-fill-a2.md`.
  The presets.py and UI changes: `team/briefs/pm-2026-11-24-preset-scope-a4.md`.
- **Reversible.** Yes. It is a build-time rule over a source file. Setting `scope.sources: null` and
  `include_discontinued: true` restores the whole-category gate for any preset. Owner action: none.

### D9 (2026-11-25, PM round 5): where the facts makers don't publish come from
Research method: WebSearch/WebFetch only, no Bright Data, no accounts. Robots were read for every candidate. Our crawler's
UA (`specsheet-crawler/0.1`) falls in the `*` group everywhere, but a site that names Anthropic or AI agents is read by its
stated intent, not by the letter of `*`. Evidence: [f] = fetched, [s] = search snippet only. Gap counts are from
docs/api/v1 on 2026-11-25 (in-scope rows per D8, unknown on the gate key).
- **Decision 1: a source ladder, cheapest and most official first.** (a) The maker's *other* publications: support
  articles, datasheets, user guides, press pages. (b) A certifier's per-product record, plus a **derived** rule from a
  certification the maker prints, where the certifier's published criteria imply the fact. (c) Independent measurement
  that is crawl-permitted, under terms that allow facts with a link. (d) Evidence-backed contributor corrections (D9.2)
  for anything a human can verify and our agents may not fetch. Only (c) and (d) are new kinds of source.
- **Why.** Two of the three "maker silences" turned out not to be silence:
  - **Power-bank PPS.** Belkin prints PPS in its per-SKU support articles ("Meet the BoostCharge Power Bank 20K 45W ...
    (BPB036)": "45W max USB-C fast charging (PPS supported)"; the 10K FAQ says "PD 3.1 and PPS") [f]. www.belkin.com
    robots allows `/support-article/` [f]. Belkin is 35 of the 114 unknown rows.
  - **Monitor PWM.** 95 of the 105 unknown Lenovo rows print a TÜV Rheinland Eye Comfort certification on PSREF, but not
    "Flicker Free". TÜV's published star table (Certipedia ID 0217009904 [f]) says **1 to 4 stars = "Flicker reduced",
    5 stars = "Flicker free"**. 33 rows print "(5-star)", so a derived rule fills them. 3-star, 4-star and unstarred rows
    stay unknown: "reduced" is not "none".
  - **SSD DRAM.** WD/SanDisk really is silent on SN850X/SN7100/SN5000 (ServeTheHome says WD does not publish it [s]).
    Every structured independent SSD source fails a test (table below), so SSD DRAM goes to (d) as human-cited family facts.
- **Ruled out, with evidence.** TCO Certified gen 9 and gen 10 display criteria have no flicker criterion (both PDFs
  read [f]). Eyesafe 2.0 covers blue light only [s]. ENERGY STAR and EPREL carry none of the three facts. The USB-IF
  Integrators List needs a login [f], so it is excluded (no accounts). The public usb.org/products list loads by JS and
  its fields are unverified, so it is a probe, not a source. No Wikipedia per-model DRAM table exists [s].
- **Dispositions** (proposals; A3 adds the keys `crawl: agent|human_only|none` and kind `measurement`, then lands the YAML in
  `team/briefs/pm-2026-11-25-independent-sources-a2.md` §1 as policy `2026-11-25.1`). All rows: paid false, licence_grant false.
| Source | Robots (for us) | Terms | Format | Disposition |
|---|---|---|---|---|
| Belkin support articles (www.belkin.com, listed) | allowed [f] | maker, unaudited | prose per SKU | maker, as today: free, `crawl: agent` |
| psrefstuff.lenovo.com datasheets, download.lenovo.com `/pccbbs/` guides | no rules / PDFs allowed [f] | Lenovo (blocked, Q2) | PDF | maker like PSREF: free, `crawl: agent` |
| mophie manuals (zagg.com PDFs) | not read | maker | PDF | maker once robots read: free, `crawl: agent` |
| TÜV Certipedia `/quality_marks/<id>` | allowed, crawl-delay 10; `/search` disallowed [f] | legal notice unreadable | per certificate | certification: free, `crawl: agent` (cert pages only, ≥10 s), to_clear: TÜV legal notice |
| Notebookcheck reviews | allowed except `/nbcbattery/` [f] | no copying without permission except quotes ≤100 words with a visible link and the name [f]; no automated-access clause | per review | **measurement: free, `crawl: agent`**, value + link + name, quote ≤100 words (we keep ≤125 chars) |
| ChargerLAB | ClaudeBot, anthropic-ai and Claude-Web `Disallow: /`; `*` gets `ai-train=no, use=reference` [f] | terms page 404 | per review PDO readout | **measurement: free, `crawl: human_only`** (was `free: false`). Agents never fetch it; a person may cite it |
| Tom's Hardware and other Future plc sites | `*` allowed [f] | US terms ban robots/crawlers that "extract, copy or collect information", and robots.txt grants no permission; linking allowed [f] | review spec table | measurement: free, `crawl: human_only` |
| StorageReview, TFTCentral, PCMonitors.info | allowed [f] | all rights reserved or none found | review | measurement: free, `crawl: human_only` until terms read |
| TechPowerUp SSD DB `/ssd-specs/` | ClaudeBot/GPTBot group disallows it, Claude-User and anthropic-ai `Disallow: /`, `*` header reserves AI use [f] | n/a | structured DB | **excluded**: free false, `crawl: none` (re-check unchanged since the earlier exclusion) |
| TechPowerUp reviews | Claude-User and anthropic-ai `Disallow: /` [f] | n/a | review | measurement: free, `crawl: human_only` |
| RTINGS | `*` allowed [f] | paywalled since 2026 because of AI reuse [s]; terms URL 404 | paywalled | **excluded**: free false, `crawl: none`. We respect the paywall's intent, and a reader can't check a paywalled link |
| ssdwiki.com | allowed [f] | none | table | **excluded**: says "DRAM Cache: Yes" for SN7100 while its own notes say HMB [f] |
| hardware-corner.net, displayspecifications.com, monitornerds, pwmtests, NewMaxx sheet | mostly allowed | all rights reserved or none | aggregator, unsourced | **excluded as sources**; a human may use them as leads |
- Reversible: yes. Each row is a `policy_version` bump. Owner action: none (Q5 gains an optional TÜV line).

**D9.2 Evidence-backed corrections: GitHub issue form → reviewed claim file in git → ledger decision.**
Spec: `team/briefs/pm-2026-11-25-corrections-flow.md`. Summary:
- Who submits: anyone with a GitHub account (we run no accounts), email to `corrections@` (a maintainer transcribes),
  and agents, which file proposals as claim files with `submitted_by: agent:<role>` and evidence they were allowed to fetch.
- Evidence, one of: **E1** a photo of the product's own label, box or manual page showing the model number and the fact
  in one frame; **E2** a link to a maker page or document; **E3** a link to a `measurement` source allowed in D9 (with
  `crawl: human_only` the person read it, we did not); **E4** the contributor's own instrumented measurement (meter or
  analyser photo plus method). Text alone is never evidence.
- Queue: issue label `field-correction` → `scripts/corrections.py` (read-only `gh`) writes `data/corrections/<issue>.yaml`
  with the claim, evidence type, a sha256 of each evidence image, a short transcription, the issue URL, and a
  contributor-terms acknowledgement. Images stay on GitHub and are never copied. A human reviewer appends `accept_claim`
  or `reject_claim` to `data/decisions/ledger.jsonl` with a reason. LLMs may propose, only humans decide (decisions.py rule).
- How accepted values are labelled: the source is the issue URL (tier `crowd`) or the cited page, whichever is the
  evidence. **The claim kind follows the evidence, not the channel**: E1/E2 = `official` ("maker label, contributor photo"),
  E3/E4 = `measured`. A correction never overwrites a maker value. A disagreement publishes as `conflicted`/alternatives.
- Abuse: ≤10 open corrections per account, a conflict-of-interest checkbox (maker staff are welcome, but their claim is
  E2 or nothing), the identity check (model number visible), a later `reject_claim` wins, and every crowd-sourced change is
  listed in `/v1/changes` with its kind. We store the issue URL, never the handle.
- **Contributor terms (D1 prerequisite):** a required checkbox: "I license this contribution under ODbL 1.0 (database)
  and DbCL 1.0 (contents). It is my own observation or a fact from the source I cite, and my photos stay mine: I only
  link them." The relicensing clause needed for a future alternative licence (D1.2) is **held for counsel (Q1)**. Until
  it is approved, crowd values are excluded from any alternative licence. First-hand E1/E4 values may carry our ODbL
  grant. E2/E3 values inherit their cited source's disposition.
- Options considered: a site-hosted form with our own accounts (rejected: accounts, PII, spam surface); Discussions
  (rejected: unstructured); email only (kept as a fallback, but it does not scale). Reversible: yes. Owner: approve the
  checkbox wording (Q1, can ship without the relicensing clause).

### D10 (2026-11-25, PM round 5): measured vs claimed values: display and presets
- **Kinds stay as in the schema**, with two `measurement.mode` values added (A3): `inspection` (teardown, PCB photo) and
  `optical` (photodiode flicker). `advertised_by_device` already covers a USB-PD analyser's PDO readout. A **derived**
  value names its rule id and the certification it rests on.
- **Display.** Every value carries a provenance badge: *Maker* · *Maker label (contributor photo)* · *Certified:
  <body>* · *Derived from <cert>* · *Measured by <source>, <date>* · *Reported by <source>*. The tooltip gives method,
  sample and link. Headline order is unchanged (resolve.py: official > derived > reported > measured). A measurement never
  replaces a maker value. A disagreement shows both values.
- **Presets count measured values, labelled.** A gate key counts a row as known whatever the kind, provided an accepted
  decision covers it. The card breaks fill down by kind (illustrative: "PWM known N/442: 303 maker · 33 derived from TÜV
  5-star · M measured"), and names any brand covered only by non-maker values. A row whose filtered key has a **disagreeing
  alternative of another kind** (maker "none" vs measured "low-freq") moves from *match* to *might match*, marked "sources
  disagree". It is never matched silently. Why: the user's question is the fact. Who observed it is a label, and refusing
  measured data would leave the presets maker-gated forever. Rejected: (a) official-only gates (the PPS and DRAM presets
  could never pass); (b) a 25% cap on non-official values (arbitrary; disclosure does the job). Runner-up: (b), if users
  read measured fill as maker-backed.
- Revision guard: a measured value binds to the configs named in its evidence. A family-wide measured claim needs either
  two independent samples, or a sample plus a maker statement that the line has one design (SSD `level: revision` trap).
- Paid/licence: unchanged (D1.3). Measured third-party values are free, linked facts and are never granted or sold.
- Reversible: yes (build rule plus UI). Owner action: none.
