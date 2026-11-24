// Worker-only CPU per request in Node's V8 (same engine as workerd), complementing scripts/load-test.mjs (which measures the whole
// workerd process, including local-dev overhead and the Durable Object). The pack is served from memory (no I/O), the Budget DO is a
// stub, so the number is the Worker's own CPU: routing, bounds, quota call setup, index scan, record-shard parse, serialization, metrics.
//   node --import ./scripts/cf-stub-loader.mjs scripts/cpu-bench.mjs [--n 200]
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
const N = Number(process.argv[process.argv.indexOf("--n") + 1]) || 200;
const files = new Map();
const walk = (d) => { for (const n of readdirSync(d)) { const p = join(d, n); statSync(p).isDirectory() ? walk(p) : files.set("/" + p.slice(join(root, "pack").length + 1), readFileSync(p)); } };
walk(join(root, "pack"));
const env = {
  ASSETS: { fetch: async (req) => { const b = files.get(new URL(req.url).pathname); return b ? new Response(b) : new Response("", { status: 404 }); } },
  BUDGET: { idFromName: (n) => n, get: () => ({ spend: async (_k, _u, b) => ({ cid: "0123456789abcdef", ok: b.map(() => true), counts: b.map(() => 1), tripped: false, total: 0 }) }) },
  BREAKER: { idFromName: (n) => n, get: () => ({ status: async () => ({ tripped: false }) }) },
  RATE_LIMITER: { limit: async () => ({ success: true }) }, METRICS: { writeDataPoint() {} },
  PAYMENTS: "off", PREVIEW: "on", SITE_ORIGIN: "https://site.example",
};
const ctx = { waitUntil() {}, passThroughOnException() {} };
const cpu = () => { const u = process.cpuUsage(); return (u.user + u.system) / 1000; };
const pct = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))]; };
const r2 = (x) => Math.round(x * 100) / 100;
const { CASES } = await import("./load-cases.mjs");
const out = [];
for (const [name, mk] of Object.entries(CASES)) {
  // cold: a fresh module instance (fresh isolate caches) per case
  const app = (await import(`../src/index.ts?case=${encodeURIComponent(name)}`)).default;
  const req = (i) => { const s = mk(i); const sp = typeof s === "string" ? { path: s } : s; return new Request("http://w" + (sp.path ?? "/mcp"), sp.body ? { method: "POST", body: sp.body, headers: { "content-type": "application/json" } } : {}); };
  let c0 = cpu(); let r = await app.fetch(req(0), env, ctx); await r.text(); const cold = cpu() - c0;
  const xs = [];
  for (let i = 1; i <= N; i++) { c0 = cpu(); r = await app.fetch(req(i), env, ctx); await r.text(); xs.push(cpu() - c0); if (r.status !== 200) throw new Error(`${name}: ${r.status}`); }
  out.push({ case: name, n: N, cold_ms: r2(cold), p50_ms: r2(pct(xs, 50)), p95_ms: r2(pct(xs, 95)), max_ms: r2(Math.max(...xs)) });
}
console.table(out);
console.log(JSON.stringify(out));
