// Single place for modes, prices, allowances and input bounds (product/decisions.md D3.3 to D3.7).
import type { Budget, Breaker } from "./quota.ts";

// Provisional (D3.3). Prices are not a readiness claim: the L2 gate picks the settlement path first. x402 "money" strings (USD).
export const PRICES = {
  query: "$0.002",
  match: "$0.005",
  changes: "$0.01",
  bulk_category: "$1.00",
  bulk_all: "$5.00",
} as const;
export type PriceKey = keyof typeof PRICES;

// Free allowance per client key per UTC day when PAYMENTS=on (D3.3). PAYMENTS=off has no allowance: everything is free under QUOTA.
export const ALLOWANCE: Partial<Record<PriceKey, number>> = { query: 100, match: 20 };

// D3.7 quota. Daily budget shared by REST and MCP tool calls; beacons have their own budgets.
export const QUOTA = { daily: 1000, perMinute: 60, miss: 30, event: 200, breakerDaily: 45000, shards: 16 } as const;

// D3.6 input bounds, checked before any data load.
export const BOUNDS = {
  url: 2048, q: 120, title: 200, filtersChars: 512, filterClauses: 12, filterValue: 64, fields: 40,
  limitDefault: 25, limitMax: 25, offsetMax: 2000, changesLimitDefault: 1000, changesLimitMax: 1000, changesDays: 90,
  mcpBody: 16 * 1024, mcpBatch: 3, missBody: 1024, eventBody: 2048,
} as const;

export const NETWORKS = { testnet: "eip155:84532", mainnet: "eip155:8453" } as const;

export interface Env {
  ASSETS: Fetcher; // the query pack (api-worker/pack), Worker static assets with run_worker_first
  BUDGET: DurableObjectNamespace<Budget>;
  BREAKER: DurableObjectNamespace<Breaker>;
  RATE_LIMITER?: RateLimit; // Workers Rate Limiting binding, 60/min per client key
  METRICS?: AnalyticsEngineDataset; // specsheet_requests
  PAYMENTS?: string; // "off" (default) | "on"
  PREVIEW?: string; // "on" (default) | "off": manual kill switch for data routes
  SITE_ORIGIN?: string; // the only CORS origin for /v1/miss and /v1/event
  STATIC_ORIGIN?: string; // GH Pages site base, for discovery text
  BREAKER_DAILY?: string; // global data-route requests per UTC day before 503 preview_capacity
  QUOTA_DAILY?: string; // test override of QUOTA.daily
  ALLOWANCE_QUERY?: string; // test override of ALLOWANCE.query
  ALLOWANCE_MATCH?: string;
  METRICS_ECHO?: string; // TEST ONLY: "on" echoes written points in x-specsheet-points on X-Specsheet-Test requests. Never in wrangler.jsonc.
  X402_NETWORK?: string;
  FACILITATOR_URL?: string;
  ALLOW_MAINNET?: string;
  PAY_TO?: string; // secret; never hardcode
  CDP_API_KEY_ID?: string;
  CDP_API_KEY_SECRET?: string;
}

export type X402Setup =
  | { ok: true; network: string; payTo: string; facilitatorUrl: string; testnet: boolean }
  | { ok: false; reason: string };

/** Validate env into a payment setup. Fails closed: no PAY_TO or unsafe mainnet config => paid routes answer 503, never free data. */
export function resolveX402(env: Env): X402Setup {
  const network = env.X402_NETWORK || NETWORKS.testnet;
  if (!/^eip155:\d+$/.test(network)) return { ok: false, reason: `X402_NETWORK must be an eip155 CAIP-2 id, got ${network}` };
  const payTo = (env.PAY_TO || "").trim();
  if (!/^0x[0-9a-fA-F]{40}$/.test(payTo)) return { ok: false, reason: "PAY_TO is not set to a 0x EVM address (wrangler secret / .dev.vars)" };
  const testnet = network !== NETWORKS.mainnet;
  if (!testnet) {
    if (env.ALLOW_MAINNET !== "true") return { ok: false, reason: "mainnet requested but ALLOW_MAINNET is not 'true'" };
    if (!env.FACILITATOR_URL || /x402\.org\/facilitator/.test(env.FACILITATOR_URL))
      return { ok: false, reason: "mainnet needs FACILITATOR_URL set to a mainnet-capable facilitator (x402.org is testnet only)" };
  }
  return { ok: true, network, payTo, facilitatorUrl: env.FACILITATOR_URL || "https://x402.org/facilitator", testnet };
}

export type Mode = "off" | "on" | "on-bad";
/** PAYMENTS=off unless the literal "on". "on" with an invalid payment config is "on-bad" (fails closed). */
export function paymentsMode(env: Env): Mode {
  if (env.PAYMENTS !== "on") return "off";
  return resolveX402(env).ok ? "on" : "on-bad";
}
export const previewOn = (env: Env) => env.PREVIEW !== "off";

const num = (v: string | undefined, d: number) => (v && /^\d+$/.test(v) ? Number(v) : d);
export const limits = (env: Env) => ({
  daily: num(env.QUOTA_DAILY, QUOTA.daily),
  breaker: num(env.BREAKER_DAILY, QUOTA.breakerDaily),
  allowance: { query: num(env.ALLOWANCE_QUERY, ALLOWANCE.query ?? 0), match: num(env.ALLOWANCE_MATCH, ALLOWANCE.match ?? 0) } as Record<string, number>,
});
