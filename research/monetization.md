# specsheet monetization research (2026-11-24, web only)

Caveat: many sources are vendor blogs; primary docs (Stripe, Cloudflare, Coinbase CDP, IRS) are marked [P].
Items not verified are flagged "unverified". Not legal/tax advice.

## Bottom line
GH Pages cannot do 402 (no server logic, no custom status or headers). Any pay-per-request path needs a thin
server in front of the paid endpoint. Cheapest: a Cloudflare Worker on workers.dev (no zone needed) with x402
middleware, serving data from the same JSON (R2 or bundled assets). Free tier and site stay on GH Pages.
Demand is thin today (see Reality check), so treat this as a cheap experiment, not a revenue plan.

## 1. HTTP 402 protocols
x402 (Coinbase, now an x402 Foundation with Cloudflare; open spec, zero protocol fee)
- Flow: server returns 402 + payment-required header; client signs a USDC payment, retries; facilitator verifies/settles.
- Coinbase CDP facilitator [P]: 1,000 onchain settlements/month free, then $0.001 each; verify free; batch-settlement
  vouchers let one tx cover thousands of payments; needs CDP account + API key.
  https://docs.cdp.coinbase.com/x402/core-concepts/facilitator
- CDP chains [P]: Base, Polygon, Arbitrum, Monad, World, Solana. Public test facilitator https://x402.org/facilitator
  (Base Sepolia; Cloudflare examples use it).
- Cloudflare [P]: x402 SDKs for Workers (`x402-hono`), "Charge for HTTP content" Worker proxy guide, paidTool for MCP.
  Facilitator does not hold funds. Lists Base, Ethereum, Polygon, Optimism, Arbitrum, Avalanche, Solana, Aptos, Stellar, Sui, Algorand.
  https://developers.cloudflare.com/agents/x402/
- Vercel: x402-mcp package (AI SDK) from Sept 2025 per secondary source; tooling only, no facilitator found.
  https://wavect.io/blog/x402-payments-comparison-2026/
- Payout: funds land in YOUR wallet (USDC). Fiat requires an off-ramp (Coinbase account/exchange, KYC) or Stripe (below).
- Coinbase Bazaar = discovery index where agents find paid x402 endpoints (secondary source).
L402 (Lightning Labs; macaroon + Lightning invoice)
- Server: Aperture reverse proxy; client: lnget. Sub-cent fees, BTC not USD; needs a Lightning node/LSP and BTC->USD off-ramp.
  Smaller agent adoption than x402; skip unless Bitcoin-native buyers matter.
  https://github.com/lightninglabs/L402  https://lightning.engineering/posts/2026-03-11-L402-for-agents/
- Aggregators supporting both x402 and L402 (PayAgents, Lightning Enable): vendor, unverified quality.

## 2. Big-player agent rails
- Stripe x402 [P]: LIVE (preview API version 2026-05-27.preview). US businesses except New York; request "Stablecoins and Crypto"
  payment method, Stripe reviews. USDC on Base/Solana/Tempo lands in your Stripe balance as PaymentIntents (fiat payout to bank).
  Still needs a CDP account for mainnet facilitation. Stripe fee ~1.5% per charge (secondary source, unverified). Stablecoin min $0.01.
  https://docs.stripe.com/payments/machine/x402  https://docs.stripe.com/payments/machine
- Stripe Machine Payments Protocol (MPP, launched 2026-03-18 per secondary): cards + stablecoin, session billing; card path min $0.50
  (card fees ~2.9%+$0.30 kill micro-prices). https://workos.com/blog/x402-vs-stripe-mpp-how-to-choose-payment-infrastructure-for-ai-agents-and-mcp-tools-in-2026
- OpenAI/Stripe ACP: live in ChatGPT since Sept 2025 but for merchant checkout of physical goods; scaled back. Not for API pay-per-call.
- Google AP2: announced Sept 2025, donated to FIDO Alliance 2026-04-28; mostly pilots. Not usable for us.
- Visa Intelligent Commerce / Trusted Agent Protocol, Mastercard Agent Pay (+ "Agent Pay for Machines", June 2026): card-network
  tokens for merchants; Mastercard prod only in Singapore/Malaysia. Announced/pilot, not self-serve for a data API.
  https://www.refontelearning.com/blog/agentic-commerce-ai-agent-payment-protocols
- Anthropic/OpenAI: no first-party paid-MCP-tool marketplace found. Official MCP Registry is free metadata only.

## 3. Cloudflare Pay Per Crawl / AI Crawl Control
- Pay Per Crawl: private beta (eligibility gate), 402 with crawler-price headers, min $0.001/crawl, paying crawlers must use Web Bot Auth.
  Domain MUST be proxied through Cloudflare (so not github.io; would need your own domain with CF DNS in front of Pages).
  Payout through a dedicated Cloudflare Stripe Connect account. Targets AI crawlers (content), not developer API clients. July 2026 note:
  evolving to "Pay Per Use". https://developers.cloudflare.com/ai-crawl-control/features/pay-per-crawl/what-is-pay-per-crawl/
  https://developers.cloudflare.com/ai-crawl-control/features/pay-per-crawl/use-pay-per-crawl-as-site-owner/
- Verdict: poor fit (beta, needs zone, crawler-oriented). x402-on-Worker is the better Cloudflare route.

## 4. Marketplaces (they handle billing, you hand over distribution + a cut)
- RapidAPI ("Rapid"): flat 25% marketplace fee since 2025-11-15 (secondary). Human devs, subscription model, requires API behind it.
- Apify Store: pay-per-event; you keep ~80% minus platform compute (docs). Actor must run on Apify; fits "query endpoint" as an Actor/MCP.
  https://docs.apify.com/platform/actors/publishing/monetize/pay-per-event
- Zuplo: gateway with metering + Stripe billing, monetization on free plan; but needs API keys/accounts for buyers (not agent-frictionless).
- AWS Data Exchange: seller qualification via Support case, W-9 + US bank account, DAC7 tax questionnaire; fee ~3% public offers (secondary).
  Enterprise buyers, slow. https://docs.aws.amazon.com/data-exchange/latest/userguide/provider-getting-started.html
- Snowflake Marketplace, Datarade: listing/lead-gen oriented, sales-led; not researched in depth (unverified); poor fit for per-request.
- Paid MCP registries: none bill for you; MCPize (85/15, secondary), Apify, AWS Marketplace do. Most free-listing directories are discovery only.
  https://eseospace.com/blog/where-to-sell-or-list-your-mcp-server/

## Reality check
Secondary reports: <5% of MCP servers monetized; typical earners $500-3,000/mo; ~half of x402 volume described as artificial;
daily agent payment volume small. Expect near-zero revenue until discoverability (Bazaar, registries, llms.txt, MCP) exists.

## 5. Architecture and obligations
Minimum add-on (keeps free static site + free tier on GH Pages):
- Free: current GH Pages JSON (rate-limited by nature; per-product lookups, sample, schema).
- Paid (x402 Worker, e.g. api-paid.<name>.workers.dev): bulk dump / full-category snapshot / fresh "since" feed / cross-field query,
  priced per call ($0.001-$0.05 by size). Data from R2 or bundled; a Worker needs no zone, no domain.
- Publish OpenAPI + x402 discovery metadata; add an MCP server (Cloudflare paidTool) to be findable.
Owner obligations (US individual) [secondary except IRS]:
- USDC received for services/data = ordinary business income at USD value on receipt (Schedule C, SE tax); that value is your basis;
  later USDC->USD sale is a disposition (~zero gain, still reported on Form 8949). IRS 1099-DA covers dispositions via brokers, not your receipts.
  https://www.irs.gov/instructions/i1099da  https://stablecoininsider.org/stablecoin-taxes-in-the-us-2026-what-the-irs-expects/
- Many tiny payments = a bookkeeping burden: log every settlement (tx hash, USD value) in the Worker/KV; export for tax. Use Stripe path to get 1099-K-style records.
- KYC: Coinbase/CDP account, any exchange off-ramp, and Stripe all require identity verification (SSN). Stripe needs a Stripe account (sole prop OK).
- Sales tax on data: state-specific (digital data/SaaS taxability varies); Stripe Tax or low-volume exemption; unresolved, check before scaling.
- Licensing: dataset provenance/ToS of source data must permit resale (spec facts mostly uncopyrightable but scraped marketing text/images are not). Add ToS + privacy page.
- Sanctions/OFAC: facilitator screens; keep wallet non-custodial and use a facilitator.

## Ranking (fastest, least ops)
1. x402 on a Cloudflare Worker, settle via Stripe deposit address (fiat payout, bookkeeping handled). ~1-2 days. Ops: ~0.
   Caveat: Stripe x402 still preview; NY residents excluded; also needs CDP key.
2. Same Worker but pay straight to a self-custody/Coinbase USDC wallet (no Stripe). Fewer approvals, fiat off-ramp + tax records are manual.
3. Apify Store Actor / MCP (Apify bills, 20% + compute). Reaches human devs and agents inside Apify; no wallet. ~2-3 days.
4. RapidAPI listing (25%), needs subscription flow; low agent fit.
5. AWS Data Exchange / Snowflake / Datarade: enterprise, slow, sales-led.
6. Pay Per Crawl (beta, proxied zone required) and L402 (node ops): skip for now. ACP/AP2/Visa/Mastercard: not applicable (commerce checkout).

## Step list: Option 1 (Worker + x402 + Stripe)
Owner personally: Stripe account (identity/SSN, bank), Stripe "Stablecoins and Crypto" request (wait approval), Coinbase CDP account +
API key (KYC), Cloudflare free account, GitHub secrets. Agent can build everything else.
1. [owner] Create Cloudflare + CDP accounts; request Stripe stablecoin method (start early, review time unknown).
2. [agent] Build /paid endpoints as Hono Worker: `@x402/hono`, `@x402/evm`, `@coinbase/x402`; paymentMiddleware routes e.g. GET /v1/bulk/{category},
   /v1/changes?since=. Price in USDC on Base (eip155:8453). Store JSON in R2, build step in the specsheet pipeline uploads it.
3. [agent] Test on Base Sepolia with https://x402.org/facilitator and Stripe sandbox + `purl` CLI (https://github.com/stripe/purl).
4. [owner] Create Stripe deposit address (`POST /v1/crypto/deposit_addresses`, network=base); set as payTo secret via `wrangler secret`.
5. [agent] onAfterSettle: record PaymentIntent (transaction_verification mode) + log to KV for tax.
6. [agent] Add OpenAPI/llms.txt/x402 discovery doc to the GH Pages site pointing to the paid endpoints; register in Bazaar and MCP registries.
7. Flip to mainnet, make one real $0.01 purchase yourself, verify the Stripe payout path. Add ToS/privacy page. Set price floors above the $0.001 facilitator fee after 1,000 free tx.
## Step list: Option 2 (no Stripe)
Skip steps 4-5's Stripe parts: payTo = Coinbase-held Base USDC address; log each tx; periodically sell USDC for USD and keep records.
