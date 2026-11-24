# Launch checklist (PM round 1, 2026-11-24)

Two milestones. **L1 = free/open launch** (target: within days). **L2 = paid switch-on**: revenue on hold pending
the owner's legal review, built and tested now, switched on later in one step. [owner] = only the owner can do it
(accounts, purchases, approvals). [agent] = coordinator dispatches a brief. Decisions: `product/decisions.md`.

## Owner, tomorrow (Cloudflare only; nothing payment-related)
1. [owner] Create a Cloudflare account (free plan). Enable 2FA.
2. [owner] Check availability + a USPTO search, then buy **`knownspec.com`** at Cloudflare Registrar (fallback
   `plainspec.com`). Tell the coordinator which.
3. [owner] Email Routing on the domain: create `corrections@`, `legal@`, `hello@` → forward to your inbox. Verify
   the destination address.
4. [owner] R2: enable it, then create buckets **`specsheet-data`** (private; served via the Worker) and
   **`specsheet-raw`** (private; backups). On `specsheet-raw` enable object versioning if offered, or a bucket lock
   rule; on `specsheet-data` add a bucket lock rule for prefix `releases/` (retain 365 days).
5. [owner] R2 API token **`specsheet-raw-backup`**: Object Read & Write, scoped to `specsheet-raw` only. Store as
   `pass specsheet/r2-raw-backup` (access key id + secret + account id). Second token **`specsheet-release`**:
   Object Read & Write on `specsheet-data` only → `pass specsheet/r2-release`.
6. [owner] Workers: note the account's `workers.dev` subdomain. Create Web Analytics for the domain (cookieless).
   Do **not** create Stripe or Coinbase CDP accounts (after legal review).
7. [owner] On GitHub: enable Discussions, private vulnerability reporting, and secret scanning push protection.

## L1: free/open launch
8.  [agent] Local raw/ + state second-disk backup, nightly (brief `pm-2026-11-24-backup`). Can start now.
9.  [agent] Add `LICENSE` (Apache-2.0), `DATA-LICENSE.md` (ODbL 1.0 notice + public-domain note), docs CC BY 4.0
    note, gitleaks CI (brief `pm-2026-11-24-site-legal`).
10. [agent] Draft `/terms`, `/privacy`, `/sources`, contact footer, brand text, `llms.txt`, Dataset JSON-LD,
    sitemap, robots.txt (brief `pm-2026-11-24-site-legal`).
11. [owner] Review and approve the terms/privacy/sources drafts (plain-language, free tier only).
12. [agent] Single licensing gate for both tiers, `release.sh` → R2 immutable release upload, dry-run until
    tokens exist (brief `pm-2026-11-24-release-r2`). Depends on `research/data-licensing.md` landing.
13. [agent] Worker: `PAYMENTS=off` mode, free preview quotas, rate limiting, Analytics Engine metrics,
    `/v1/miss`, serving the site shell + dataset from R2 (brief `pm-2026-11-24-api-gateway`). Local only.
14. [agent] Rclone R2 sync of raw/ wired once step 5 is done; first full upload + one-source restore test.
15. [owner] First deploy: `cd api-worker && npx wrangler login && npx wrangler deploy` with `PAYMENTS=off`
    (exact commands in api-worker/README after step 13). Add the custom domain to the Worker (root + `api.`).
16. [agent] Post-deploy smoke against the live domain (UI, free JSON, query preview, 429 path, MCP, llms.txt,
    no paid route returns data while bulk is off).
17. [agent] GH Pages → redirect page to the new domain; keep gh-pages publishing as a fallback for 14 days.
18. [agent] Publish to the MCP Registry (`mcp-publisher`, GitHub auth) [owner runs the login step], then
    Smithery/Glama/mcp.so submissions (forms may need the owner's GitHub login: [owner]).
19. [owner] Announce (optional): Show HN / relevant subreddits, with a link to Discussions.

## L2: paid switch-on (after legal review; nothing here runs before)
20. [owner] Legal review outcome recorded in `product/decisions.md` (by the coordinator, generic wording).
21. [owner] Create Coinbase CDP project **`specsheet-x402`** + Secret API key **`specsheet-worker`**; Stripe account
    + "Stablecoins and Crypto" request, if the Stripe settlement path is chosen. Create the receiving address.
22. [agent] Mainnet CDP facilitator auth (the TODO in `api-worker/src/x402.ts`), settlement log to Analytics Engine/R2
    for bookkeeping; paid-tier terms linked.
23. [owner] `wrangler secret put PAY_TO`, `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`; set `PAYMENTS=on`,
    `X402_NETWORK=eip155:8453`, `ALLOW_MAINNET=true`, mainnet `FACILITATOR_URL`; deploy. One $0.002 test purchase.
24. [agent] List in x402 Bazaar / directories; update llms.txt + OpenAPI to show prices.
