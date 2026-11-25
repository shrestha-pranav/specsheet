# Launch checklist (PM round 1, 2026-11-24; revised PM round 3, same day)

Two milestones. **L1 = free/open launch**. **L2 = paid switch-on**: revenue on hold pending the owner's legal review.
L2 is a project with its own gates, not one step. [owner] = only the owner can do it (accounts, purchases, approvals).
[agent] = coordinator dispatches a brief. Decisions: `product/decisions.md`.
**Changed 2026-11-24 (R3):** L1 topology is GH Pages + an API Worker on workers.dev (D2). R2 bucket lock dropped. Old
step 16 ("no paid route returns data") replaced by the route matrix (D3.5). Acceptance criteria added (end of L1).
Directory submissions and announce moved after acceptance.

## Owner, now (Cloudflare only; nothing payment-related)
_Cloudflare items (1-4, 6, 7): owner HOLD 2026-11-25._
1. [owner] Create a Cloudflare account (free plan). Enable 2FA.
2. [owner] Check availability + a USPTO search, then buy **`knownspec.com`** at Cloudflare Registrar (fallback
   `plainspec.com`). Needed at L1 for contact email only; the site stays on GH Pages.
3. [owner] Email Routing: `corrections@`, `legal@`, `hello@` → your inbox. Verify the destination.
4. [owner] Workers: note the `workers.dev` subdomain. Create Web Analytics for the GH Pages site (cookieless JS
   snippet). Set usage notifications at 50%/80% for Workers and Durable Objects. No Stripe/Coinbase accounts.
5. [owner] On GitHub: enable Discussions, private vulnerability reporting, secret scanning push protection.
   **DONE 2026-11-25:** all three ENABLED (by coordinator on owner approval).
6. [owner] Create a read-only Account Analytics API token → `pass specsheet/cf-analytics-read` (for kpi.sql).
7. [owner, can wait until after L1] R2: enable, create private buckets `specsheet-raw` (versioning on, noncurrent
   versions expire after 30 days, **no bucket lock**) and `specsheet-data` (archive, **no bucket lock**). Tokens
   `specsheet-raw-backup` → `pass specsheet/r2-raw-backup` and `specsheet-release` → `pass specsheet/r2-release`,
   each scoped to its own bucket.

## L1: free/open launch
8.  [agent] Local raw/ + state second-disk backup, nightly (brief `pm-2026-11-24-backup`). Prove a one-source restore.
9.  [agent] Licensing gate on `data/source-policy.yaml` for the free build, Worker query pack and paid export, with
    fixtures (brief `pm-2026-11-24-licensing-gate`). Includes post-gate coverage per tier and the Sources page
    data. Blocks 11 and 13.
10. [agent] Licence text: `DATA-LICENSE.md` (R3 draft done), Terms/Sources/Privacy wording per D1.2 and D4
    (A4, from licensing-gate brief §6 and measurement-plan §1).
11. [owner] Review and approve terms/privacy/sources/about drafts and `DATA-LICENSE.md`.
    **APPROVED by owner 2026-11-25.**
12. [agent] Release promotion: manifest checksums + policy version, verify, gh-pages publish, query pack for the
    same release, rollback procedure; R2 archive upload dry-run until step 7 (brief `pm-2026-11-24-release-r2`).
13. [agent] API Worker per the D3.5 route matrix: `PAYMENTS`/`PREVIEW` vars, bounds, shared REST/MCP quota with
    Retry-After, DO daily counters, global breaker, metrics contract, `/v1/miss`, `/v1/event`, matcher port (or match
    stays 404 and unlisted), local load test, kpi.sql (brief `pm-2026-11-24-api-gateway`). Local only.
14. [agent] Takedown drill on a fake source (`product/takedown-runbook.md` §5).
15. [owner] First deploy with the coordinator: `cd api-worker && npx wrangler login && npx wrangler deploy`
    (`PAYMENTS=off`, `PREVIEW=on`). Set `site.json` `api_origin` to the workers.dev URL and republish Pages.
16. [agent] Post-deploy smoke: run the route matrix against the live workers.dev URL (every row, expected status),
    zero facilitator calls, 429 with Retry-After from REST and MCP on one shared budget, breaker forced via a test
    threshold, `/health` release equals the Pages release, then `wrangler rollback` and roll forward once.
17. [agent] One contact test per address (`corrections@`, `legal@`, `hello@`): delivered and answered. Then
    `site.email_enabled=true`.
18. [agent] First weekly kpi.sql run returns every row, with test traffic from step 16 classed `test`.

18b. [agent] Corrections flow (D9.2, brief `pm-2026-11-25-corrections-flow`): issue form, claim files, queue, ledger
    accept/reject, provenance badges. It does not block L1. Without it, the SSD DRAM preset stays "help us fill this".

**L1 acceptance (all true before announce):** pages approved (11); gate fixtures green and coverage published (9);
route matrix green live (16); one-source restore (8) and release rollback (16) done; contact verified (17); takedown
drill done (14); metrics query works (18); freshness, coverage and unknown states visible in the UI.

19. [owner] Announce (optional): Show HN / relevant subreddits, linking Discussions.
20. [agent] After acceptance: MCP Registry (`mcp-publisher`, owner runs the GitHub login), then Smithery/Glama/mcp.so.

## L2: paid switch-on (after legal review; nothing here runs before)
21. [owner] Legal review outcome recorded in `product/decisions.md` (coordinator, generic wording), including
    contribution terms and the scope of any alternative licence (D1.2).
22. [agent+owner] Source clearances: Lenovo, VESA, CSA, CARB, top makers by value count. Each cleared source gets
    `paid`/`licence_grant` true with fetched evidence. Without these, paid = ENERGY STAR only.
23. [agent] Hosting migration off GH Pages before any paid use (D2 "before L2" list), budgeted separately.
24. [agent] Economics: the chosen settlement path's real minimum and fees; per-call only if fee ≤ 10% of price,
    else prepaid packs (D3.3); update `PRICES` and the D3.3 table together.
25. [owner] Coinbase CDP project + key and/or Stripe crypto method; receiving address.
26. [agent] Mainnet facilitator auth (TODO in `src/x402.ts`), settlement log, paid-tier terms linked, fail-closed
    on-mode tests in the route matrix.
27. [owner] `wrangler secret put PAY_TO`, `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`; `PAYMENTS=on`,
    `X402_NETWORK=eip155:8453`, `ALLOW_MAINNET=true`, mainnet `FACILITATOR_URL`; deploy; one test purchase.
28. [agent] x402 Bazaar / directories; llms.txt + OpenAPI show prices.
