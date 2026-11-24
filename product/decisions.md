# specsheet product decisions (A5 PM log)

Format per entry: decision, options considered, why, reversibility, owner action. Newest round first.
Standing constraint (2026-11-24): **revenue on hold pending the owner's legal review.** The product launches
free/open; the paid tier is built and shipped **disabled**, with a one-step switch-on later (D3.4). Entity /
operating-structure questions are for counsel; this log makes no recommendation on them.

---

## 2026-11-24 PM round 1

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
**D1.1 Code: Apache-2.0** for the whole repo (crawler, scripts, frontend, api-worker).
- Options: MIT; Apache-2.0; FSL-1.1-Apache-2.0 / BSL / Elastic (source-available).
- Why: the moat is not the code. A competitor with our adapters still needs the crawl history, the identity
  decisions, the review ledger and the release cadence. Source-available licenses add friction for the users we
  want (agent builders, shopping sites, contributors of corrections/adapters) and FSL turns into Apache in two
  years anyway. Apache over MIT for the explicit patent grant and NOTICE handling. Runner-up: FSL on `api-worker/`
  only, if legal review finds a reason to protect the gate code; switching that one directory later is cheap.
- Reversible: going more restrictive only applies to future versions; released code stays Apache. Decide once.
- Today the repo has **no LICENSE at all** (public but all-rights-reserved, which is the worst of both): fix now.

**D1.2 Free data: ODbL 1.0** for the published dataset (the compilation), with a notice that individual facts
are not claimed and US-government-sourced values are public domain.
- Options: CC BY 4.0; ODbL 1.0; CC BY-NC 4.0; custom "free for lookup, no bulk redistribution".
- Why: ODbL is built for databases. Attribution plus share-alike applies to *derived databases*. *Produced works*
  (a comparison page, a chart, an answer an agent gives) only need attribution. That lets shopping sites, agents
  and reviewers use it freely, and stops a closed copy of the database from being resold without sharing back.
  It also leaves room for a later commercial license for anyone who wants to embed the data without
  share-alike, which is a revenue item and on hold. CC BY-NC is vague ("non-commercial" deters legitimate users)
  and protects facts no better. A custom no-bulk license is a browsewrap contract that would be hard to enforce
  against facts, and it is a red flag for adoption. Runner-up: CC BY 4.0 (maximum adoption, no share-alike); pick
  it if legal review says share-alike buys nothing in practice.
- Honest limit: US law gives facts and non-original compilations thin protection (Feist). The license is a
  norms and attribution tool, not a wall. The real moat is in D3.
- Docs/prose (README, guides, schema docs): CC BY 4.0.

**D1.3 Upstream constraints (rule for both tiers)**
- Publish **facts + identifiers + a link to the source** only. Never republish expression: marketing copy,
  images, PDFs, page text. Media and documents stay links, as the UI already does. Raw snapshots are never published.
- US federal sources (ENERGY STAR / EPA data.energystar.gov, DOE) are public domain: no restriction, credit them.
  State sources (CARB, ww2.arb.ca.gov) are public records: credit them, and the licensing audit confirms the terms.
- Maker sites: facts are not copyrightable. The risk is the site's terms of use (contract) and access, so:
  respect robots.txt and rate limits (already a hard rule), and honour any explicit "no commercial use / no
  reproduction of information" clause.
- Gating: `research/data-licensing.md` (in progress, not yet written) is the per-source authority. A source marked
  exclude/unclear is withheld from the **paid** artifacts (already done in `api-worker/licensing-exclusions.json`).
  It is also withheld from the **free** dataset unless the audit says fact-only republication with a link is
  acceptable. One list gates both tiers (see brief A3), so the free and paid tiers can't drift apart.
- Known gap: `psref.lenovo.com` is the largest single source (most laptop facts) and is currently excluded from
  paid. If the audit keeps it excluded, paid laptops lose most of their value. Asking Lenovo for permission is an
  owner question (open-questions Q2).

**D1.4 Repo stays public.** Nothing moves private except what already is (raw/, state/, .env).
- Options: all public; private adapters; private decisions ledger; private repo with public data mirror.
- Why: provenance and reviewable decisions are the brand ("trace a spec to its evidence"). A public ledger is what
  makes the data trustworthy enough to pay for later. Adapters are cheap to reproduce, so hiding them protects
  little and costs community fixes. The things worth protecting are already off-repo: raw snapshots
  (9.2 GB, gitignored), the working store `state/specsheet.sqlite`, and operational secrets.
- Guardrails: add secret scanning (gitleaks) to CI. `team/` and `research/` may stay public but must contain
  no personal data (A4/A3 briefs restate this). Remember that product/ is public too.
- Reversible: going private later is one click, but forks and clones already made persist.

### D2. Data of record
**Decision: git stays the system of record for *decisions*. Cloudflare R2 becomes the store of record for *published
releases* and the off-site copy of *raw evidence*. No hosted database now.**

| Layer | Lives in | Why |
|---|---|---|
| Code, category profiles, decisions ledger, policies + lock, id registry/tombstones, release manifests | git `main` (public) | Small (data/ 3 MB, history 17 MB packed). Diffs are the review. Already works. |
| Working store (candidates, extraction cache, intake) | `state/specsheet.sqlite`, local | Rebuildable from raw + data. Not of record, but backed up nightly (cheap, saves hours). |
| Raw evidence (snapshots + blobs) | local `raw/` **+ R2 bucket `specsheet-raw` (private)** | 9.2 GB on one machine with **no backup today: P0 risk**. Content-addressed, append-only, so sync is cheap. Retention rules from source policy (e.g. 72 h caps) apply to the backup copy too. |
| Published releases | **R2 bucket `specsheet-data`**, `releases/<release_id>/...` immutable + `current.json` pointer | gh-pages is a single orphan commit, so no past release is retrievable today. R2 gives immutability and history (`/v1/changes` needs it). Same objects feed the free and paid paths. |
| Usage metrics, search misses | Workers Analytics Engine | Write-only time series, no DB to run, no PII. |
| Future write paths (API keys, submissions, accounts) | D1, when needed | Not needed for free launch or for x402 (stateless). ARCHITECTURE §0.11 Postgres stays the plan for the *claims* backend if it ever leaves the home server. |

- Options considered: (a) status quo git + gh-pages; (b) Postgres (Neon/Supabase) as of-record; (c) D1 as of-record;
  (d) R2 objects (chosen).
- Why not a DB now: reads are static per release (about 11k trusted records, a 4.5 MB index). The Worker filters an
  in-memory index per category, which a database wouldn't speed up. A DB adds a migration, credentials and a
  second source of truth while every write still originates in the local pipeline. Revisit when records pass
  ~200k, or when user write paths ship.
- Why move the site off GitHub Pages: (1) the GitHub Pages terms disallow sites primarily for commercial
  transactions/SaaS, and the site will front a paid API; (2) GH Pages gives zero metrics and no rate limiting;
  (3) a custom domain plus a Worker gives both. Cloudflare Pages / Workers static assets cap free deployments at
  20k files, and the dataset is already **18,365 files**. So the shell (5 files) ships as Worker static assets and
  the dataset is served from R2 through the Worker (edge-cached). That leaves one origin, one metrics plane and
  one rate limiter.
- Migration order:
  1. **Now, no account needed:** nightly local second copy of `raw/` + a `sqlite3 .backup` of state onto a different
     physical disk (brief backup).
  2. **After the owner creates R2:** nightly `rclone sync` raw → `specsheet-raw` (no deletes except by retention
     policy; versioning/bucket lock on). Verify a restore of one source.
  3. `release.sh` also uploads the release to `specsheet-data/releases/<id>/` (write-once) and flips
     `current.json`, after the gh-pages publish succeeds (brief A3).
  4. Worker serves `/api/v1/*` from R2 (free) plus the paid/preview routes. The site shell moves to the Worker on
     the new domain (brief api + A4).
  5. Cut over: the domain goes live, GH Pages gets a static redirect page to the new domain, and gh-pages
     publishing continues 14 days as a fallback, then stops.
- Reversible: yes. Each step is additive; gh-pages remains a fallback until step 5 ends.

### D3. Free vs paid tiers
**D3.1 The static dataset stays fully public and free** (every trusted record, index shards, facets, schema),
under ODbL. Yes, this allows bulk copying, and that is accepted. Hiding it would break the UI (client-side
filtering), SEO and agent adoption, while the facts can be re-crawled anyway. The paid product is
*convenience, freshness, identity resolution and a commercial license*, not secrecy.

**D3.2 Free, rate-limited (Worker), from launch:** `/api/v1/*` static files; `/v1/query` and `/v1/match` (when
implemented) and the MCP tools in **preview mode**: 60 req/min and 1,000 req/day per client IP. Over the limit
returns 429 with `Retry-After` (no payment prompt while revenue is on hold). The goal is demand measurement:
every call to a would-be-paid route is counted.

**D3.3 Paid (built, disabled until legal review), prices set now so the switch is mechanical:**
| Route | Price (USDC via x402) | Free allowance when paid is on |
|---|---|---|
| `/v1/query` (filtered, provenance) | $0.002 / call | 100 calls/day per IP, then 402 |
| `/v1/match` (listing title → product id; the identity service) | $0.005 / call | 20/day per IP |
| `/v1/changes?since=` (release diff feed) | $0.01 / call | none |
| `/v1/bulk/<cat>.jsonl.gz` (one category, current release) | $1.00 | none (the free static files remain) |
| `/v1/bulk/all.jsonl.gz` | $5.00 | none |
- Why: per-call prices sit above the facilitator's $0.001/settlement after the free 1,000/month, so no route
  loses money. Bulk at $0.05 (current scaffold) was below the value of a curated dump and invited per-release
  scraping of the paid artifact. Match is priced highest per call because identity resolution is the hardest-won
  asset (ARCHITECTURE §7). Runner-up: a Stripe-billed API-key plan ($19/mo, 100k calls) for human developers.
  Also on hold, and only worth building if Worker metrics show non-agent demand.

**D3.4 Switch design:** one Worker var `PAYMENTS` = `off` (launch) | `on`. With `off`, paid routes serve free
under the D3.2 limits, except bulk, which returns 404 `{"error":"not_available"}`. With `on`, x402 applies above
the free allowance. Switch-on = set the secrets (`PAY_TO`, CDP key) + `PAYMENTS=on` + one deploy. A test must
prove `on` without secrets fails closed (503), as the scaffold already does.
- Reversible: fully. Commitments to users: the static dataset and the free allowance are promised to stay free.
  The preview quotas are explicitly labelled "may change", so turning paid on later doesn't break a promise.

### D4. Other productization blockers
- **Legal pages (agent drafts, owner reviews before publish):** `/terms` (data as-is, not purchase advice, no
  warranty, liability cap, attribution requirement, acceptable use: no attacks, honour rate limits), `/privacy`
  (no cookies, no accounts; cookieless Cloudflare Web Analytics; IPs used transiently for rate limiting and not
  stored; search-miss text stored truncated, never with IP), and `/sources` (attribution: per-source credit, public
  domain notes, ODbL notice, how to cite). Footer links on every page. Paid-tier terms are drafted but not linked
  (on hold).
- **Contact:** Cloudflare Email Routing on the domain forwards `corrections@`, `legal@` (takedowns) and `hello@` to
  the owner's inbox. No personal address appears anywhere public. Takedown SLA: acknowledge within 3 business days,
  remove the field/source from the next release. US Copyright Office DMCA agent designation goes with the legal
  review (it needs a contact address of record).
- **Abuse:** Worker Rate Limiting binding (D3.2), a Cloudflare WAF rule blocking clients above 10x the limit, a
  `robots.txt` that allows crawling the site and disallows `/v1/query` and `/v1/match`, R2-backed edge caching so
  bulk static crawling costs nothing, and an MCP endpoint behind the same limiter. Corrections and requests stay on
  GitHub (moderated by GitHub), plus the anonymous search-miss beacon (count only).
- **Metrics:** GH Pages measures nothing (GitHub repo Insights only cover repo views/clones). After the move:
  Cloudflare Web Analytics for page views, and Workers Analytics Engine for each API/MCP request: route, category,
  status, client class (browser / agent UA / MCP), would-be-paid flag, cache hit. Logged: no IPs, no query text
  except search misses. Weekly KPIs: unique API clients/day, MCP tool calls, would-be-paid calls/day (the evidence
  for how urgent the legal review is), top search misses, and request→published turnaround.
- **Discovery:** `llms.txt` + `/openapi.json` at the site root (served by the Worker), a schema.org `Dataset`
  JSON-LD on the home page (Google Dataset Search), and `sitemap.xml`. MCP: publish to the official MCP Registry
  (`io.github.shrestha-pranav/specsheet` namespace via GitHub auth, which needs no DNS), then Smithery, Glama and
  mcp.so. **x402 Bazaar and x402 directories: after paid switch-on only** (listing a 402 endpoint that never charges
  confuses indexers).
- **Support channel:** GitHub Discussions (Q&A + Announcements) for public questions, GitHub Issues for
  corrections/requests (existing templates), and `hello@` for private matters. No Discord/Slack (nobody to staff it).
- **Request-a-missing-product loop:** keep the GitHub issue draft. Add (1) an anonymous `POST /v1/miss` beacon on
  every zero-result search (category, normalized query ≤120 chars, build id, no IP), (2) a weekly script that ranks
  misses + `missing-product` issues into `team/queue/requests.md` for the coordinator, and (3) on publish, a comment
  plus close on the matching issue (agent drafts, coordinator posts). Without step 3 the loop isn't actually closed.

### D5. Launch plan
"Free/open launch" within days = D0 domain + D2 steps 1–5 + D3.2 preview + D4 pages/discovery. The paid switch-on
is a separate, later step gated on legal review. Ordered steps: `product/launch-checklist.md`. Agent work:
`team/briefs/pm-2026-11-24-*.md`.

### D6 (2026-11-24, PM round 2): coverage of opaque core specs before new categories; measured free deploy
- Decision: fill the top-10 demand specs (product/demand-survey.md §2) in the existing 12 categories first, because several are at 0%
  on data we already crawl. Then add USB-C docks, mini PCs and headphones in that order. The free deploy showcases killer-query
  presets gated at >= 80% fill and is measured per product/measurement-plan.md (4-week go/no-go thresholds).
- Options: (a) breadth, meaning new categories now [rejected: demand evidence centres on opaque specs we already model];
  (b) appliances via ENERGY STAR next [runner-up: cheap and reliable, but low opacity, so it adds little that is unique].
- Reversible: yes. Owner action: none.
