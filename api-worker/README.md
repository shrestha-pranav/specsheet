# specsheet api-worker

Cloudflare Worker (Hono + `@x402/hono`) in front of the specsheet dataset. Local-only so far: nothing is deployed, no
account or key exists. **Paid mode ships disabled** (`PAID_ENABLED=false`): paid routes answer 503 "coming soon" and are
absent from `/openapi.json`, `/llms.txt` and MCP. Networking is Base Sepolia testnet only unless config says otherwise.

| Route | Tier | Price (src/config.ts) |
|---|---|---|
| `GET /v1/<anything else>` | free: 302 to GH Pages `STATIC_ORIGIN/api/v1/...` | 0 |
| `GET /v1/query?category=&filters=&q=&fields=&limit=&offset=` | paid x402 | $0.001 |
| `GET /v1/changes?since=<release id or ISO date>&category=` | paid x402 | $0.002 |
| `GET /v1/match?title=` | paid x402; **stub, 501 (uncharged)** until `scripts/match.py` is ported, see `src/match.ts` TODO | $0.002 |
| `GET /v1/bulk/<category>.jsonl.gz` | paid x402 | $0.05 |
| `/openapi.json`, `/llms.txt`, `POST /mcp` | discovery (paid tools: `query_specs`, `match_product`) | free |

Filters: `filters=cpu.cores>=8,brand=ASUS,name~zen` (ops `>= <= > < != = ~`); only known values match.
Errors (400/501) are never charged (the x402 middleware settles only on status < 400).
MCP: stateless JSON-RPC; paid tool calls forward to the REST route, payment in `params._meta["x402/payment"]`.

## Local development (no accounts)
```
cd api-worker && npm install
python3 -I ../scripts/build_r2.py          # docs/api/v1 -> r2-data/ (paid-tier export, licensing exclusions applied)
npm run seed                                # loads r2-data/ into the LOCAL simulated R2 (.wrangler/state)
cp .dev.vars.example .dev.vars              # placeholders only; .dev.vars is gitignored
#   set PAID_ENABLED=true and PAY_TO=<your Base Sepolia address> in .dev.vars to exercise paid routes
npm run dev                                 # http://localhost:8787
npm test                                    # e2e (wrangler dev + mock facilitator + signed testnet payload) + disabled-mode + unit
python3 -I ../tests/test_build_r2.py
```
Real-facilitator testnet probe: `TEST_PRIVATE_KEY=0x... node scripts/pay-test.mjs <url>`. Without a key it uses a throwaway
unfunded wallet and ends at the facilitator's `insufficient_balance` 402 (proves the signing + verify round trip).
Manual step for a full 200 on the public testnet: fund a Base Sepolia wallet with test USDC at https://faucet.circle.com
(browser, needs the owner), export its key as `TEST_PRIVATE_KEY` for that one command, and set `PAY_TO` to any other address.

Data in R2: `meta/manifest.json`, `index/<cat>.json`, `records/<cat>/<xx>.json`, `bulk/<cat>.jsonl.gz`, `changes/*`. Layout and
diff semantics are documented in `scripts/build_r2.py`. Release diffs come from snapshots (`state/r2-snapshots/`) taken at each
build, so history starts at the first build after a release; hook the script into `scripts/release.sh` to run per release.

## Owner deploy steps (only after legal review)
Prerequisite: review `research/data-licensing.md` and `licensing-exclusions.json`, plus terms/privacy and tax questions in
`research/monetization.md`. None of the below has been run.
1. Cloudflare: create a free account, `npx wrangler login` (interactive, owner only).
2. `npx wrangler r2 bucket create specsheet-data` (name must match `wrangler.jsonc`), then upload `r2-data/` (for example
   `rclone copy r2-data :s3:specsheet-data` with an R2 API token, or `wrangler r2 object put` per file).
3. Confirm `STATIC_ORIGIN` in `wrangler.jsonc` is the real GH Pages URL. `npx wrangler deploy` (workers.dev subdomain, no zone needed).
4. Testnet first: `npx wrangler secret put PAY_TO` (a testnet receiving address), set `PAID_ENABLED` to `"true"`, redeploy, run
   `scripts/pay-test.mjs` against the workers.dev URL with a funded testnet key.
5. Mainnet (separate decision): needs a Coinbase CDP account + API key (KYC) for the CDP facilitator (https://docs.cdp.coinbase.com/x402/core-concepts/facilitator),
   the `createAuthHeaders` wiring flagged TODO in `src/x402.ts`, then `X402_NETWORK=eip155:8453`, `ALLOW_MAINNET=true`,
   `FACILITATOR_URL=<cdp url>`, and `PAY_TO` as a secret. Make one small real purchase and verify settlement before announcing.
6. Optional Stripe path (fiat payout): request the "Stablecoins and Crypto" payment method, create a deposit address
   (`POST /v1/crypto/deposit_addresses`, network=base) and use it as `PAY_TO` (https://docs.stripe.com/payments/machine/x402); still preview.
7. Log every settlement (tx hash, USD value) for bookkeeping; register in discovery indexes (x402 Bazaar, MCP registries) once live.
Secrets live only in `wrangler secret` / `.dev.vars`; never commit them and never hardcode a pay-to address.
