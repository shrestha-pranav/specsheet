// Single place for prices and network policy. Prices are x402 "money" strings (USD, settled in USDC).
export const PRICES = {
  query: "$0.001",
  changes: "$0.002", // not specified by the brief; small diff payloads, priced like match
  match: "$0.002",
  bulk: "$0.05",
} as const;

export const NETWORKS = { testnet: "eip155:84532", mainnet: "eip155:8453" } as const;

export interface Env {
  DATA: R2Bucket;
  STATIC_ORIGIN: string;
  X402_NETWORK?: string;
  FACILITATOR_URL?: string;
  ALLOW_MAINNET?: string;
  PAID_ENABLED?: string; // master switch, default off: paid routes answer 503 'coming soon'
  PAY_TO?: string; // secret; never hardcode
  CDP_API_KEY_ID?: string;
  CDP_API_KEY_SECRET?: string;
}

export type X402Setup =
  | { ok: true; network: string; payTo: string; facilitatorUrl: string; testnet: boolean }
  | { ok: false; reason: string };

/** Validate env into a payment setup. Fails closed: no PAY_TO or unsafe mainnet config => paid routes answer 503, not free data. */
export function resolveX402(env: Env): X402Setup {
  const network = env.X402_NETWORK || NETWORKS.testnet;
  if (!/^eip155:\d+$/.test(network)) return { ok: false, reason: `X402_NETWORK must be an eip155 CAIP-2 id, got ${network}` };
  const payTo = (env.PAY_TO || "").trim();
  if (!/^0x[0-9a-fA-F]{40}$/.test(payTo)) return { ok: false, reason: "PAY_TO is not set to a 0x EVM address (set it via .dev.vars / wrangler secret)" };
  const testnet = network !== NETWORKS.mainnet;
  if (!testnet) {
    if (env.ALLOW_MAINNET !== "true") return { ok: false, reason: "mainnet requested but ALLOW_MAINNET is not 'true'" };
    if (!env.FACILITATOR_URL || /x402\.org\/facilitator/.test(env.FACILITATOR_URL))
      return { ok: false, reason: "mainnet needs FACILITATOR_URL set to a mainnet-capable facilitator (the x402.org one is testnet only)" };
  }
  return { ok: true, network, payTo, facilitatorUrl: env.FACILITATOR_URL || "https://x402.org/facilitator", testnet };
}

/** Paid mode ships disabled. Only the literal string "true" enables it. */
export const paidEnabled = (env: Env) => env.PAID_ENABLED === "true";
