// CPU/wall load test against `wrangler dev --local` (workerd) on the largest category (laptops), D3.6 / open question Q6.
//   node scripts/load-test.mjs [--n 200] [--port 8840]
// CPU per request = delta of the workerd process's summed per-thread schedstat run time (ns) across one sequential request: real
// runtime CPU including workerd's own HTTP handling, so it is an upper bound on what Cloudflare bills as Worker CPU time. Wall is
// client-side. Each request uses a distinct CF-Connecting-IP and distinct parameters (no cache hits, no quota). "cold" = the first
// request of a case on a freshly started isolate (pack JSON parse included).
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { startWorker } from "../test/wrangler-dev.mjs";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? Number(process.argv[i + 1]) : d; };
const N = arg("--n", 200), PORT = arg("--port", 8840);
const BASE = `http://127.0.0.1:${PORT}`;

function descendants(pid) {
  const kids = {};
  for (const d of readdirSync("/proc")) {
    if (!/^\d+$/.test(d)) continue;
    try { const st = readFileSync(`/proc/${d}/stat`, "utf8"); const ppid = Number(st.slice(st.lastIndexOf(")") + 2).split(" ")[1]); (kids[ppid] ??= []).push(Number(d)); } catch { /* gone */ }
  }
  const out = [], q = [pid];
  while (q.length) { const p = q.shift(); for (const k of kids[p] ?? []) { out.push(k); q.push(k); } }
  return out;
}
function workerdPids(rootPid) {
  return descendants(rootPid).filter((p) => { try { return readFileSync(`/proc/${p}/comm`, "utf8").trim() === "workerd"; } catch { return false; } });
}
function cpuNs(pids) {
  let t = 0;
  for (const p of pids) for (const tid of readdirSync(`/proc/${p}/task`)) { try { t += Number(readFileSync(`/proc/${p}/task/${tid}/schedstat`, "utf8").split(" ")[0]); } catch { /* exited */ } }
  return t;
}
const pct = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))]; };
const r2 = (x) => Math.round(x * 100) / 100;

import { CASES } from "./load-cases.mjs";

const w = await startWorker(PORT, ["QUOTA_DAILY:100000000", "BREAKER_DAILY:100000000"]);
// startWorker spawned `npx wrangler dev` detached; find its workerd children via the listening port's process tree
const me = process.pid;
const pids = workerdPids(me);
if (!pids.length) { console.error("workerd process not found"); w.stop(); process.exit(1); }
let ip = 0;
async function one(spec) {
  const s = typeof spec === "string" ? { path: spec } : spec;
  const headers = { "cf-connecting-ip": `10.${(ip >> 16) & 255}.${(ip >> 8) & 255}.${ip++ & 255}`, "content-type": "application/json" };
  const c0 = cpuNs(pids), t0 = performance.now();
  const r = await fetch(BASE + (s.path ?? "/mcp"), s.body ? { method: "POST", body: s.body, headers } : { headers });
  const text = await r.text();
  const wall = performance.now() - t0;
  await new Promise((res) => setTimeout(res, 2)); // let workerd finish post-response work (metrics, waitUntil)
  const cpu = (cpuNs(pids) - c0) / 1e6;
  if (r.status !== 200) throw new Error(`${r.status} ${text.slice(0, 200)}`);
  return { wall, cpu, bytes: text.length };
}
const out = [];
for (const [name, mk] of Object.entries(CASES)) {
  const cold = await one(mk(0));
  const walls = [], cpus = [], bytes = [];
  for (let i = 1; i <= N; i++) { const x = await one(mk(i)); walls.push(x.wall); cpus.push(x.cpu); bytes.push(x.bytes); }
  out.push({ case: name, n: N, cold_cpu_ms: r2(cold.cpu), cpu_p50_ms: r2(pct(cpus, 50)), cpu_p95_ms: r2(pct(cpus, 95)), wall_p50_ms: r2(pct(walls, 50)), wall_p95_ms: r2(pct(walls, 95)), kb_p50: Math.round(pct(bytes, 50) / 1024) });
}
w.stop();
console.table(out);
console.log(JSON.stringify(out));
