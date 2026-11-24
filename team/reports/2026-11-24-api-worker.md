# api-worker report (2026-11-24)
Built `api-worker/` (Hono + @x402/hono 2.32, Worker, R2 binding), `scripts/build_r2.py`, `research/data-licensing.md`, README deploy steps.
No commit/push, no Bright Data, no login/deploy, no real keys. No live pay-to anywhere (PAY_TO env only; tests pass a placeholder via --var).
- Paid mode ships DISABLED (PAID_ENABLED=false): paid routes 503 "coming_soon", removed from openapi/llms.txt/MCP. Testnet default (eip155:84532); mainnet needs ALLOW_MAINNET=true + non-x402.org FACILITATOR_URL.
- Routes: free /v1/* 302 to STATIC_ORIGIN (guessed github.io URL, CONFIRM); paid query/changes/bulk working; match = 501 stub w/ TODO (no scripts/match.py yet).
- Prices in src/config.ts: query $0.001, match $0.002, bulk $0.05, changes $0.002 (my choice).
- Data: build_r2.py exports trusted docs/api/v1 (never preview) to r2-data/ (gitignored); local R2 seeded via miniflare (`npm run seed`).
- Changes: release manifests hold no record data, so diffs come from per-build snapshots in state/r2-snapshots; history starts at first build (only baseline now). Wire into release.sh later.
- Discovery: /openapi.json (3.1), /llms.txt, POST /mcp (stateless; tools query_specs, match_product; paid via _meta x402/payment). Hand-rolled, not agents/paidTool (needs Durable Objects); noted as TODO.
- Tests (all pass): `npm test` = real `wrangler dev` + mock facilitator + signed testnet payload: free redirect, 402 requirements (amount/network/payTo/asset) on all 4 paid routes, paid 200 w/ provenance, errors uncharged, MCP unpaid/paid, disabled-mode; plus tests/test_build_r2.py.
- Real facilitator: throwaway key got x402.org to answer invalid_exact_evm_insufficient_balance (round trip OK). Full 200 needs a faucet-funded wallet: manual step in README.
- Licensing: ALLOW ENERGY STAR (EPA, facts+attribution), CARB provisional; EXCLUDE from paid: Lenovo PSREF (403 blocked, restrictive), DisplayHDR (all rights reserved), CSA DCL (restrictive terms), retail/aggregators. Maker ToS not fetched: open item.
- Consequence: laptops paid export is tiny (PSREF excluded). Decision for owner. Exclusions in api-worker/licensing-exclusions.json.
- Shared-file changes: .gitignore (+4 api-worker lines). New: tests/test_build_r2.py.
- Open: confirm Pages URL; CDP auth wiring for mainnet; match port; counsel review before enabling.
