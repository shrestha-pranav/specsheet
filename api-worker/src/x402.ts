import type { MiddlewareHandler } from "hono";
import { paymentMiddleware, x402ResourceServer } from "@x402/hono";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { PRICES, resolveX402, type Env, type X402Setup } from "./config.ts";

type Ok = Extract<X402Setup, { ok: true }>;

export const PAID_ROUTES = {
  "GET /v1/query": { price: PRICES.query, description: "Filtered spec query with per-value provenance", mimeType: "application/json" },
  "GET /v1/changes": { price: PRICES.changes, description: "Record-level diff between dataset releases since a release id or date", mimeType: "application/json" },
  "GET /v1/match": { price: PRICES.match, description: "Resolve a retail listing title to a specsheet product id", mimeType: "application/json" },
  "GET /v1/bulk/*": { price: PRICES.bulk, description: "Full category dump, gzipped JSON lines (trusted records)", mimeType: "application/gzip" },
} as const;

export function buildRoutes(s: Ok) {
  return Object.fromEntries(
    Object.entries(PAID_ROUTES).map(([k, v]) => [
      k,
      { accepts: [{ scheme: "exact", price: v.price, network: s.network as `${string}:${string}`, payTo: s.payTo }], description: v.description, mimeType: v.mimeType },
    ]),
  );
}

let cache: { key: string; mw: MiddlewareHandler } | null = null;

/** Payment middleware, rebuilt only when the relevant env changes (env is per-request in Workers). */
export function getPaymentMiddleware(env: Env, s: Ok): MiddlewareHandler {
  const key = [s.network, s.payTo, s.facilitatorUrl, env.CDP_API_KEY_ID ?? ""].join("|");
  if (cache?.key === key) return cache.mw;
  const facilitator = new HTTPFacilitatorClient({ url: s.facilitatorUrl });
  const server = new x402ResourceServer(facilitator).register(s.network as `${string}:${string}`, new ExactEvmScheme());
  // TODO(mainnet): CDP facilitator needs JWT auth headers (createAuthHeaders from @coinbase/x402 with CDP_API_KEY_ID/SECRET).
  const mw = paymentMiddleware(buildRoutes(s) as never, server);
  cache = { key, mw };
  return mw;
}
