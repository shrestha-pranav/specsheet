// Testnet payment probe. usage: node scripts/pay-test.mjs <url> [base=http://localhost:8787]
//   TEST_PRIVATE_KEY=0x...  a Base Sepolia wallet funded with test USDC (https://faucet.circle.com, pick Base Sepolia)
// Without TEST_PRIVATE_KEY a random throwaway key is generated (never stored): the flow then proves 402 -> signed
// payload -> facilitator verify, and is expected to end in "insufficient funds" rather than 200.
import { wrapFetchWithPaymentFromConfig } from "@x402/fetch";
import { ExactEvmScheme } from "@x402/evm";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

const url = process.argv[2] ?? "http://localhost:8787/v1/query?category=power-strips&limit=2";
const funded = !!process.env.TEST_PRIVATE_KEY;
const account = privateKeyToAccount(process.env.TEST_PRIVATE_KEY || generatePrivateKey());
console.log(`payer ${account.address} (${funded ? "funded key from env" : "throwaway, unfunded"})`);
const pay = wrapFetchWithPaymentFromConfig(fetch, { schemes: [{ network: "eip155:84532", client: new ExactEvmScheme(account) }] });
const r = await pay(url);
console.log("status", r.status);
for (const h of ["payment-response", "payment-required"]) if (r.headers.get(h)) console.log(h + ":", Buffer.from(r.headers.get(h), "base64").toString().slice(0, 400));
console.log((await r.text()).slice(0, 600));
