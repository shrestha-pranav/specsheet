// Minimal stateless MCP (Streamable HTTP, JSON responses, batch <= 10, body <= 16 KB). Tool calls spend the same daily budget as REST
// (a batch of N tool calls = N, spent in one DO call) and dispatch to the executors directly, so nothing is counted or metered twice.
// PAYMENTS=on only: a call beyond the free allowance goes through the REST route's x402 middleware via an internal request that carries a
// per-isolate random token (not counted again). PAYMENTS=off never looks at params._meta["x402/payment"].
import type { Hono } from "hono";
import { BOUNDS, limits, previewOn, type Env, type PriceKey } from "./config.ts";
import { validateMatch, validateQuery } from "./bounds.ts";
import { HttpError, getManifest } from "./data.ts";
import { tools as toolNames } from "./discovery.ts";
import { cachedServe, execMatch, execQuery, guard, paused, point, send, type C, type Served } from "./gate.ts";
import { normClientName, trafficClass, type Point } from "./metrics.ts";
import type { Bucket } from "./quota.ts";

let TOKEN = "";
export const internalToken = () => TOKEN;

const TOOL_DEFS: Record<string, { description: string; inputSchema: object; route: string; price: PriceKey }> = {
  query_specs: { route: "/v1/query", price: "query",
    description: "Filtered spec query over one category with per-value provenance (free preview; quotas may change).",
    inputSchema: { type: "object", additionalProperties: false, required: ["category"], properties: {
      category: { type: "string" }, filters: { type: "string", description: "key<op>value comma list, e.g. cpu.cores>=8,brand=ASUS (ops >= <= > < != = ~)" },
      q: { type: "string", maxLength: BOUNDS.q }, fields: { type: "string", description: "comma list of spec keys" },
      limit: { type: "integer", minimum: 1, maximum: BOUNDS.limitMax }, offset: { type: "integer", minimum: 0, maximum: BOUNDS.offsetMax } } } },
  match_product: { route: "/v1/match", price: "match",
    description: "Resolve a retail listing title to a product id. Precision first: returns no candidates rather than a wrong one.",
    inputSchema: { type: "object", additionalProperties: false, required: ["title"], properties: { title: { type: "string", maxLength: BOUNDS.title }, category: { type: "string" } } } },
};

const rpc = (id: unknown, result: unknown) => ({ jsonrpc: "2.0", id, result });
const rpcErr = (id: unknown, code: number, message: string, data?: unknown) => ({ jsonrpc: "2.0", id, error: { code, message, ...(data ? { data } : {}) } });

export async function handleMcp(c: C, app: Hono<any>) {
  const rq = c.get("rq"), env = c.env;
  rq.kind = "mcp"; rq.route = "/mcp";
  TOKEN ||= crypto.randomUUID();
  const len = Number(c.req.header("content-length") ?? 0);
  if (len > BOUNDS.mcpBody) { rq.outcome = "bad_input"; return send(c, 413, { ...rpcErr(null, -32600, "body larger than 16 KB") }); }
  const text = await c.req.text();
  if (text.length > BOUNDS.mcpBody) { rq.outcome = "bad_input"; return send(c, 413, { ...rpcErr(null, -32600, "body larger than 16 KB") }); }
  let msg: any;
  try { msg = JSON.parse(text); } catch { rq.outcome = "bad_input"; await guard(c, []); return send(c, 400, rpcErr(null, -32700, "parse error")); }
  const batch = Array.isArray(msg);
  const msgs: any[] = batch ? msg : [msg];
  if (batch && (msgs.length === 0 || msgs.length > BOUNDS.mcpBatch)) { rq.outcome = "bad_input"; await guard(c, []); return send(c, 400, rpcErr(null, -32600, `batch must hold 1 to ${BOUNDS.mcpBatch} messages`)); }
  const man = await getManifest(env);
  const surf = { mode: rq.mode, match: !!man.match?.catalogue, release: man.release, categories: man.categories.map((x) => x.id), site: "" };
  const offered = toolNames(surf);
  const calls = msgs.filter((m) => m && m.method === "tools/call" && m.id !== undefined);
  const lim = limits(env);
  let allowOk: Record<string, boolean> = {};
  if (calls.length && rq.mode !== "on-bad") {
    if (!previewOn(env)) return paused(c);
    const per: Record<string, number> = {};
    for (const m of calls) { const t = TOOL_DEFS[m.params?.name]; if (t) per[t.price] = (per[t.price] ?? 0) + 1; }
    const buckets: Bucket[] = [{ kind: "day", n: calls.length, limit: rq.mode === "on" ? Number.MAX_SAFE_INTEGER : lim.daily, data: true },
      ...Object.entries(per).map(([k, n]) => ({ kind: `r:${k}`, n, limit: rq.mode === "on" ? lim.allowance[k] ?? 0 : Number.MAX_SAFE_INTEGER }))];
    const g = await guard(c, buckets, rq.mode === "on");
    if (g instanceof Response) return g;
    Object.keys(per).forEach((k, i) => { allowOk[k] = g.ok[i + 1] === true; });
  } else {
    const g = await guard(c, []);
    if (g instanceof Response) return g;
  }
  const out: unknown[] = [];
  for (const m of msgs) {
    const id = m?.id, method = m?.method, params = m?.params;
    if (!m || typeof m !== "object" || m.jsonrpc !== "2.0" || typeof method !== "string") { out.push(rpcErr(id ?? null, -32600, "invalid request")); continue; }
    if (id === undefined) continue; // notification
    const t0 = Date.now();
    const mpoint = (route: string, status: number, o: Partial<Point> = {}) =>
      point(env, rq, status, { kind: "mcp", route, traffic: trafficClass(c.req.raw, rq.uaFamily, rq.cid, ""), wallMs: Date.now() - t0, ...o });
    switch (method) {
      case "initialize":
        rq.mcpClient = normClientName(params?.clientInfo?.name);
        out.push(rpc(id, { protocolVersion: typeof params?.protocolVersion === "string" ? params.protocolVersion.slice(0, 20) : "2025-06-18",
          capabilities: { tools: {} }, serverInfo: { name: "specsheet", version: "0.2.0" },
          instructions: `Release ${man.release}. Free preview, quotas may change, paid tier not enabled. Quota is shared per client network with the REST API.` }));
        mpoint("/mcp:initialize", 200, { mcpClient: rq.mcpClient, outcome: "ok" });
        break;
      case "ping": out.push(rpc(id, {})); mpoint("/mcp:ping", 200, { outcome: "ok" }); break;
      case "tools/list":
        out.push(rpc(id, { tools: offered.map((n) => ({ name: n, description: TOOL_DEFS[n].description, inputSchema: TOOL_DEFS[n].inputSchema })) }));
        mpoint("/mcp:tools/list", 200, { outcome: "ok" });
        break;
      case "tools/call": {
        const name = params?.name;
        const def = offered.includes(name) ? TOOL_DEFS[name] : undefined;
        if (rq.mode === "on-bad") { out.push(rpcErr(id, -32000, "payments_not_configured")); mpoint(`/mcp:${name}`, 503, { outcome: "error" }); break; }
        if (!def) { out.push(rpcErr(id, -32602, `unknown tool ${String(name).slice(0, 40)}`)); mpoint("/mcp:unknown", 400, { outcome: "bad_input" }); break; }
        const r = await runTool(c, app, def, name, params, allowOk[def.price] === true);
        out.push({ jsonrpc: "2.0", id, ...(r.msg as object) });
        mpoint(`/mcp:${name}`, r.status, { outcome: r.outcome, category: r.category, results: r.results, bytes: r.bytes, detail: r.detail,
          traffic: trafficClass(c.req.raw, rq.uaFamily, rq.cid, r.canonical), mode: wouldPay(rq.mode, def.price, lim.allowance[def.price] ?? 0) });
        break;
      }
      default: out.push(rpcErr(id, -32601, `method not found: ${String(method).slice(0, 40)}`)); mpoint("/mcp:other", 400, { outcome: "bad_input" });
    }
  }
  if (!out.length) return new Response(null, { status: 202, headers: { "x-specsheet-release": rq.release } });
  const body = JSON.stringify(batch ? out : out[0]);
  rq.bytes = body.length;
  return new Response(body, { headers: { "content-type": "application/json; charset=utf-8", "x-specsheet-release": rq.release } });
}

// off: would-be-paid marker only once the D3.3 allowance would be spent is unknown per call here, so mark routes with no allowance.
const wouldPay = (mode: string, price: string, free: number) => (mode === "on-bad" ? "on" : mode) + (free === 0 ? `:${price}` : "");

async function runTool(c: C, app: Hono<any>, def: (typeof TOOL_DEFS)[string], name: string, params: any, within: boolean) {
  const env = c.env, rq = c.get("rq");
  const args = params?.arguments ?? {};
  const res = (status: number, msg: unknown, o: Partial<{ outcome: any; category: string; results: number; bytes: number; detail: string; canonical: string }> = {}) =>
    ({ status, msg, outcome: o.outcome ?? "ok_results", category: o.category ?? "", results: o.results ?? 0, bytes: o.bytes ?? 0, detail: o.detail ?? "", canonical: o.canonical ?? "" });
  if (typeof args !== "object" || Array.isArray(args)) return res(400, { error: { code: -32602, message: "arguments must be an object" } }, { outcome: "bad_input" });
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(args as Record<string, unknown>)) {
    if (v === undefined || v === null) continue;
    if (typeof v === "object") return res(400, { result: errResult("bad_input", `argument ${k.slice(0, 40)} must be a string or number`) }, { outcome: "bad_input" });
    sp.set(k, String(v));
  }
  const man = await getManifest(env);
  let v: { params: any; canonical: string; filterKeys: string[] };
  try { v = name === "query_specs" ? validateQuery(man, sp) : validateMatch(man, sp); }
  catch (e) { if (!(e instanceof HttpError)) throw e; return res(e.status, { result: errResult(e.code, e.message) }, { outcome: "bad_input" }); }
  const category = v.params.category ?? "";
  const meta = { category, detail: v.filterKeys.join(","), canonical: `${def.route}?${v.canonical}` };
  if (rq.mode === "on" && !within) {
    // beyond the free allowance: the REST route's x402 middleware decides (402 requirements or verify+settle)
    const url = new URL(def.route, c.req.url); url.search = sp.toString();
    const h = new Headers({ accept: "application/json", "x-specsheet-internal": TOKEN });
    const pay = params?._meta?.["x402/payment"];
    if (pay) h.set("PAYMENT-SIGNATURE", typeof pay === "string" ? pay : btoa(JSON.stringify(pay)));
    const r = await app.fetch(new Request(url, { headers: h }), env, c.executionCtx);
    const text = await r.text();
    let json: any; try { json = JSON.parse(text); } catch { json = undefined; }
    if (r.status === 402) {
      let req: unknown = json; const hdr = r.headers.get("PAYMENT-REQUIRED");
      try { if (hdr) req = JSON.parse(atob(hdr)); } catch { /* body */ }
      return res(402, { result: { isError: true, structuredContent: req, content: [{ type: "text", text: JSON.stringify(req) }], _meta: { "x402/error": { code: 402 } } } }, { ...meta, outcome: "quota" });
    }
    const pr = r.headers.get("PAYMENT-RESPONSE");
    return res(r.status, { result: { isError: r.status >= 400, structuredContent: json, content: [{ type: "text", text }], _meta: pr ? { "x402/payment-response": pr } : {} } },
      { ...meta, outcome: r.status < 400 ? "ok_results" : "error", results: json?.count ?? json?.candidates?.length ?? 0, bytes: text.length });
  }
  let s: Served;
  try {
    s = await cachedServe(c, def.route, v.canonical, () => (name === "query_specs" ? execQuery(env, man.release, v.params) : execMatch(env, man, v.params)));
  } catch (e) { if (!(e instanceof HttpError)) throw e; return res(e.status, { result: errResult(e.code, e.message) }, { ...meta, outcome: "error" }); }
  return res(s.status, { result: { isError: s.status >= 400, structuredContent: JSON.parse(s.text), content: [{ type: "text", text: s.text }] } },
    { ...meta, outcome: s.outcome, results: s.results, bytes: s.text.length });
}

const errResult = (code: string, detail: string) => ({ isError: true, structuredContent: { error: code, detail }, content: [{ type: "text", text: `${code}: ${detail}` }] });
