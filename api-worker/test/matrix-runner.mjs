// Runs test/route-matrix.json rows for one mode against a base URL. Used by test/route-matrix.test.mjs (wrangler dev, all modes) and by
// scripts/route-matrix.mjs (live smoke, checklist step 16). Returns [{id, ok, problems[]}] plus every response seen.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export const MATRIX = JSON.parse(readFileSync(resolve(import.meta.dirname, "route-matrix.json"), "utf8"));

const fill = (s, ctx) => s.replace(/\{release\}/g, ctx.release).replace(/\{site\}/g, ctx.site).replace(/\{long(\d+)\}/g, (_, n) => "a".repeat(Number(n)));
function body(row, ctx) {
  if (row.body === undefined) return undefined;
  if (row.body === "{batch11}") return JSON.stringify(Array.from({ length: 11 }, (_, i) => ({ jsonrpc: "2.0", id: i, method: "ping" })));
  if (row.body === "{batch3calls}") return JSON.stringify(Array.from({ length: 3 }, (_, i) => ({ jsonrpc: "2.0", id: i, method: "tools/call", params: { name: "query_specs", arguments: { category: "chargers", limit: 1 } } })));
  return fill(JSON.stringify(row.body), ctx);
}
function url(base, row, ctx) {
  const u = new URL(row.path, base);
  for (const [k, v] of Object.entries(row.query ?? {})) u.searchParams.set(k, fill(v, ctx));
  return u.toString();
}
const get = (o, path) => path.split(".").reduce((a, k) => (a == null ? undefined : a[k]), o);

export async function call(base, row, ctx, ip) {
  const headers = { "x-specsheet-test": "1", "user-agent": "specsheet-matrix/1 (node)", ...(ctx.spoofIp ? { "cf-connecting-ip": ip } : {}) };
  for (const [k, v] of Object.entries(row.headers ?? {})) headers[k] = fill(v, ctx);
  const b = body(row, ctx);
  if (b !== undefined && !headers["Content-Type"]) headers["content-type"] = "application/json";
  const r = await fetch(url(base, row, ctx), { method: row.method, headers, body: b, redirect: "manual" });
  const text = await r.text();
  let json; try { json = JSON.parse(text); } catch { json = undefined; }
  ctx.seen?.push({ id: row.id, status: r.status, headers: Object.fromEntries(r.headers), text, json });
  return { r, text, json };
}

const errorCode = (j) => j?.error?.message ?? (typeof j?.error === "string" ? j.error : undefined) ?? j?.result?.structuredContent?.error ?? j?.error?.code;
const validQuery = { id: "probe", method: "GET", path: "/v1/query", query: { category: "chargers", limit: "1" } };

export async function runMode(base, mode, ctx) {
  const out = [];
  const health = await (await fetch(new URL("/health", base))).json();
  ctx.release = health.release;
  const openapi = await (await fetch(new URL("/openapi.json", base))).json();
  const llms = await (await fetch(new URL("/llms.txt", base))).text();
  const tl = await (await fetch(new URL("/mcp", base), { method: "POST", body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }) })).json();
  const toolsListed = (tl.result?.tools ?? []).map((t) => t.name);
  let n = 0;
  for (const row of MATRIX.rows) {
    const exp = row.expect[mode];
    if (!exp) continue;
    if (row.setup && !ctx.spoofIp) { out.push({ id: row.id, ok: true, skipped: "setup needs a dedicated client key" }); continue; }
    const ip = `198.51.${ctx.ipBlock}.${++n}`;
    const problems = [];
    if (row.setup === "exhaust_daily") for (let i = 0; i < ctx.daily; i++) await call(base, validQuery, ctx, ip);
    if (row.setup === "exhaust_allowance") for (let i = 0; i < ctx.allowance; i++) await call(base, row, ctx, ip);
    if (row.setup === "rate_minute") for (let i = 0; i < 60; i++) await call(base, { method: "POST", path: "/mcp", body: { jsonrpc: "2.0", id: i, method: "tools/list" } }, ctx, ip);
    const { r, text, json } = await call(base, row, ctx, ip);
    if (r.status !== exp.status) problems.push(`status ${r.status} != ${exp.status}: ${text.slice(0, 160)}`);
    if (exp.error && errorCode(json) !== exp.error) problems.push(`error ${JSON.stringify(errorCode(json))} != ${exp.error}`);
    if (exp.retry_after !== undefined && !!r.headers.get("retry-after") !== exp.retry_after) problems.push(`retry-after ${r.headers.get("retry-after")}`);
    if (r.headers.get("retry-after") && !/^\d+$/.test(r.headers.get("retry-after"))) problems.push("retry-after not in seconds");
    for (const [k, v] of Object.entries(exp.json ?? {})) if (get(json, k) !== v) problems.push(`${k} = ${JSON.stringify(get(json, k))} != ${JSON.stringify(v)}`);
    for (const [k, v] of Object.entries(exp.header ?? {})) if (r.headers.get(k) !== v) problems.push(`header ${k} = ${r.headers.get(k)}`);
    if (exp.text && !text.includes(exp.text)) problems.push(`text lacks ${exp.text}`);
    if (exp.cors && r.headers.get("access-control-allow-origin") !== ctx.site) problems.push("missing CORS for the site origin");
    if (!r.headers.get("x-specsheet-release")) problems.push("no x-specsheet-release header");
    if (json && !Array.isArray(json) && !json.jsonrpc && json.release !== ctx.release) problems.push("JSON body lacks release");
    if (mode === "off" && r.status === 402) problems.push("402 in PAYMENTS=off");
    if (row.setup === "then_rest_query_429") {
      const p = await call(base, validQuery, ctx, ip);
      if (p.r.status !== 429) problems.push(`batch of 3 did not spend 3 (next REST query ${p.r.status})`);
    }
    // quota column: spend the row `daily` times from a fresh key, then probe with a valid query
    if (mode === "off" && ctx.spoofIp && !row.setup && row.quota) {
      const qip = `198.52.${ctx.ipBlock}.${n}`;
      for (let i = 0; i < ctx.daily; i++) await call(base, row, ctx, qip);
      const p = await call(base, validQuery, ctx, qip);
      const want = row.quota === "yes" ? 429 : 200;
      if (p.r.status !== want) problems.push(`quota=${row.quota} but probe after ${ctx.daily} calls returned ${p.r.status}`);
    }
    if (mode === "off" && typeof row.discovery === "boolean") {
      const inApi = row.tool ? toolsListed.includes(row.tool) : row.path in (openapi.paths ?? {});
      const inLlms = row.tool ? llms.includes(row.tool) : llms.includes(row.path.replace(/\.jsonl\.gz$/, ""));
      if (inApi !== row.discovery || (row.path !== "/" && inLlms !== row.discovery)) problems.push(`discovery listed=${inApi}/${inLlms}, expected ${row.discovery}`);
    }
    out.push({ id: row.id, ok: problems.length === 0, problems });
  }
  return out;
}
