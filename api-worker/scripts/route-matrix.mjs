// Live smoke (launch checklist step 16): run test/route-matrix.json rows for one mode against a deployed URL.
//   node scripts/route-matrix.mjs https://specsheet-api.<sub>.workers.dev [--mode off] [--site https://<user>.github.io]
// Cloudflare sets CF-Connecting-IP itself, so rows that need a fresh client key (setup: exhaust_daily, rate_minute, ...) and the
// quota-column probes are skipped here; they are covered locally by `npm test`. Every request is marked X-Specsheet-Test: 1 (class test).
import { runMode } from "../test/matrix-runner.mjs";
const base = process.argv[2];
if (!base) { console.error("usage: node scripts/route-matrix.mjs <base url> [--mode off] [--site origin]"); process.exit(2); }
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const mode = arg("--mode", "off"), site = arg("--site", "https://shrestha-pranav.github.io");
const res = await runMode(base, mode, { site, spoofIp: false, ipBlock: 0, daily: 0, allowance: 0, seen: [] });
let bad = 0;
for (const r of res) { if (!r.ok) bad++; console.log(`${r.ok ? "ok  " : "FAIL"} ${r.id}${r.skipped ? ` (skipped: ${r.skipped})` : ""}${r.problems?.length ? ": " + r.problems.join("; ") : ""}`); }
console.log(`${res.length - bad}/${res.length} rows ok (mode ${mode})`);
process.exit(bad ? 1 : 0);
