// specsheet-api Worker: L1 free preview (PAYMENTS=off) per product/decisions.md D3.4-D3.7. Route matrix: test/route-matrix.json.
import { Hono } from "hono";
import { BOUNDS, limits, paymentsMode, previewOn, resolveX402, type Env, type PriceKey } from "./config.ts";
import { validateChanges, validateMatch, validateQuery } from "./bounds.ts";
import { HttpError, bulkBody, changeHistory, getManifest, type PackManifest } from "./data.ts";
import { llmsTxt, openapi, type Surface } from "./discovery.ts";
import { cachedServe, point, execChanges, execMatch, execQuery, fail, guard, matcherFor, newRq, paused, send, JSON_CT, type C, type Rq, type Served } from "./gate.ts";
import { handleMcp, internalToken } from "./mcp.ts";
import { handleBeacon, preflight } from "./beacons.ts";
import { trafficClass, uaFamily } from "./metrics.ts";
import { getPaymentMiddleware } from "./x402.ts";
import type { Bucket } from "./quota.ts";

export { Budget, Breaker } from "./quota.ts";

const app = new Hono<{ Bindings: Env; Variables: { rq: Rq } }>();

app.use("*", async (c, next) => {
  const ua = uaFamily(c.req.header("user-agent"), new URL(c.req.url).pathname);
  const rq = newRq(c.env, c.req.raw, paymentsMode(c.env), ua);
  c.set("rq", rq);
  try { rq.release = (await getManifest(c.env)).release; } catch { rq.release = "none"; }
  await next();
  if (!rq.skip) {
    rq.traffic = trafficClass(c.req.raw, rq.uaFamily, rq.cid, rq.canonical);
    if (rq.kind !== "mcp" || !rq.points.some((p) => p.indexes?.[0] === "mcp")) point(c.env, rq, c.res.status);
  }
  if (c.env.METRICS_ECHO === "on" && c.req.header("x-specsheet-test") === "1") {
    c.res = new Response(c.res.body, c.res);
    c.res.headers.set("x-specsheet-points", btoa(unescape(encodeURIComponent(JSON.stringify(rq.points)))));
  }
});

app.onError((e, c) => {
  if (e instanceof HttpError) return fail(c as C, e);
  console.error(e);
  c.get("rq").outcome = "error";
  return send(c as C, 500, { error: "internal_error", detail: "unexpected error" });
});

export async function surface(env: Env): Promise<Surface> {
  const man = await getManifest(env);
  const site = (env.STATIC_ORIGIN || "").replace(/\/$/, "");
  return { mode: paymentsMode(env), match: !!man.match?.catalogue, release: man.release, categories: man.categories.map((x) => x.id), site };
}

let breakerCache: { at: number; state: string } | null = null;
async function breakerState(env: Env): Promise<string> {
  if (breakerCache && Date.now() - breakerCache.at < 30_000) return breakerCache.state;
  let state = "unknown";
  try { const s = await env.BREAKER.get(env.BREAKER.idFromName("global")).status(limits(env).breaker); state = s.tripped ? "open" : "closed"; } catch { /* unknown */ }
  breakerCache = { at: Date.now(), state };
  return state;
}

async function health(c: C) {
  const man = await getManifest(c.env);
  const mode = paymentsMode(c.env);
  return send(c, 200, {
    name: "specsheet-api", tier: man.tier, built_at: man.built_at, policy_version: man.policy_version ?? null, policy_sha256: man.policy_sha256 ?? null,
    payments: mode === "on-bad" ? "not_configured" : mode, preview: previewOn(c.env) ? "on" : "off", breaker: await breakerState(c.env),
    match: man.match?.catalogue ? "available" : "not_available", retained_releases: (await changeHistory(c.env)).map((h) => h.release),
    checksums: { categories: Object.fromEntries(man.categories.map((x) => [x.id, x.sha256 ?? null])), match: man.match?.sha256 ?? null },
    docs: { openapi: "/openapi.json", llms: "/llms.txt", mcp: "/mcp" },
    note: "Free preview, quotas may change, paid tier not enabled.",
  }, { "cache-control": "no-store" });
}
app.get("/", (c) => health(c as C));
app.get("/health", (c) => health(c as C));
app.get("/openapi.json", async (c) => send(c as C, 200, openapi(c.env, new URL(c.req.url).origin, await surface(c.env))));
app.get("/llms.txt", async (c) => new Response(llmsTxt(new URL(c.req.url).origin, await surface(c.env)), { headers: { "content-type": "text/plain; charset=utf-8", "x-specsheet-release": c.get("rq").release } }));
app.get("/robots.txt", (c) => new Response("User-agent: *\nDisallow: /\n", { headers: { "content-type": "text/plain", "x-specsheet-release": c.get("rq").release } }));

// ---------------------------------------------------------------- data routes
interface Spec<V> {
  route: string; price: PriceKey | null; available: (man: PackManifest, c: C) => boolean | Promise<boolean>;
  validate: (man: PackManifest, sp: URLSearchParams) => Promise<{ params: V; canonical: string; filterKeys: string[]; category?: string }> | { params: V; canonical: string; filterKeys: string[] };
  serve: (c: C, man: PackManifest, v: V) => Promise<Served | Response>;
  cache: boolean;
}

async function dataRoute<V>(c: C, s: Spec<V>): Promise<Response> {
  const rq = c.get("rq"), env = c.env, mode = rq.mode;
  rq.kind = "api"; rq.route = s.route;
  const internal = !!internalToken() && c.req.header("x-specsheet-internal") === internalToken();
  if (internal) rq.skip = true; // MCP already counted and metered this logical call
  if (mode === "on-bad") { rq.outcome = "error"; return send(c, 503, { error: "payments_not_configured", detail: "PAYMENTS=on without a valid payment config: paid routes fail closed" }); }
  if (!previewOn(env)) return paused(c);
  const man = await getManifest(env);
  const url = new URL(c.req.url);
  let v: Awaited<ReturnType<Spec<V>["validate"]>> | null = null, verr: HttpError | null = null;
  try {
    if (c.req.url.length > BOUNDS.url) throw new HttpError(414, "uri_too_long", `URL longer than ${BOUNDS.url} characters`);
    if (!(await s.available(man, c))) throw new HttpError(404, "not_available", `${s.route} is not offered in this mode`);
    v = await s.validate(man, url.searchParams);
    rq.canonical = `${s.route}?${v.canonical}`;
    rq.category = (v.params as { category?: string }).category ?? "";
    rq.detail = v.filterKeys.join(",");
  } catch (e) { if (e instanceof HttpError) verr = e; else throw e; }
  const lim = limits(env);
  const allow = s.price ? (mode === "on" ? (lim.allowance[s.price] ?? 0) : Number.MAX_SAFE_INTEGER) : 0;
  // PAYMENTS=on: the day limit is the per-route allowance (then 402), not a 429 (D3.5 "over budget" row)
  const buckets: Bucket[] = [{ kind: "day", n: 1, limit: mode === "on" ? Number.MAX_SAFE_INTEGER : lim.daily, data: true }];
  if (s.price && v) buckets.push({ kind: `r:${s.price}`, n: 1, limit: allow });
  let g: Awaited<ReturnType<typeof guard>> | null = null;
  if (!internal) {
    g = await guard(c, buckets, mode === "on");
    if (g instanceof Response) return g;
  }
  if (verr) return fail(c, verr);
  const withinAllowance = !internal && g?.ok[1] === true;
  if (s.price && v) {
    const free = lim.allowance[s.price] ?? 0, cnt = g && !g.degraded ? g.counts[1] ?? 0 : -1;
    rq.wouldPay = cnt >= 0 && (free === 0 || cnt > free) ? s.price : ""; // what D3.3 would bill; usage, not willingness to pay
  }
  const run = async (): Promise<Response> => {
    const out = s.cache ? await cachedServe(c, s.route, v!.canonical, async () => (await s.serve(c, man, v!.params)) as Served) : await s.serve(c, man, v!.params);
    if (out instanceof Response) return out;
    rq.results = out.results; rq.outcome = out.outcome; rq.bytes = out.text.length;
    return new Response(out.text, { status: out.status, headers: { "content-type": out.contentType ?? JSON_CT, "x-specsheet-release": rq.release, "cache-control": "public, max-age=300" } });
  };
  if (mode === "off" || withinAllowance) return run(); // payment headers are ignored and never forwarded
  // PAYMENTS=on and the allowance is spent (or the route has none): x402. Never reached in PAYMENTS=off.
  const x = resolveX402(env);
  if (!x.ok) return send(c, 503, { error: "payments_not_configured", detail: x.reason });
  const mw = getPaymentMiddleware(env, x);
  const r = ((await mw(c as never, async () => { c.res = await run(); })) as Response | undefined) ?? c.res;
  if (r.headers.get("x-specsheet-release")) return r;
  const text = await r.text(); // x402's 402 / facilitator errors: add `release` like every other JSON response
  let j: unknown; try { j = JSON.parse(text); } catch { j = undefined; }
  const out = new Response(j && typeof j === "object" && !Array.isArray(j) ? JSON.stringify({ release: rq.release, ...(j as object) }) : text, r);
  out.headers.set("x-specsheet-release", rq.release); out.headers.delete("content-length");
  return out;
}

app.get("/v1/query", (c) => dataRoute(c as C, {
  route: "/v1/query", price: "query", available: () => true, cache: true,
  validate: (man, sp) => validateQuery(man, sp), serve: (c, man, p) => execQuery(c.env, man.release, p),
}));
app.get("/v1/changes", (c) => dataRoute(c as C, {
  route: "/v1/changes", price: "changes", available: () => true, cache: true,
  validate: async (man, sp) => validateChanges(man, sp, (await changeHistory(c.env)).map((h) => h.release)),
  serve: (c, _man, p) => execChanges(c.env, _man.release, p),
}));
app.get("/v1/match", (c) => dataRoute(c as C, {
  route: "/v1/match", price: "match", available: (man) => !!man.match?.catalogue, cache: true,
  validate: (man, sp) => validateMatch(man, sp), serve: (c, man, p) => execMatch(c.env, man, p),
}));
app.get("/v1/bulk/:file", (c) => {
  const file = c.req.param("file");
  return dataRoute(c as C, {
    route: file === "all.jsonl.gz" ? "/v1/bulk/all" : "/v1/bulk/category", price: file === "all.jsonl.gz" ? "bulk_all" : "bulk_category",
    available: () => (c as C).get("rq").mode === "on", cache: false,
    validate: (man, sp) => {
      if ([...sp.keys()].length) throw new HttpError(400, "bad_input", "bulk takes no parameters");
      if (file !== "all.jsonl.gz" && !man.categories.some((x) => `${x.id}.jsonl.gz` === file)) throw new HttpError(404, "not_found", "unknown bulk file");
      return { params: file, canonical: file, filterKeys: [], category: file.replace(".jsonl.gz", "") };
    },
    serve: async (c, _m, f) => {
      const b = await bulkBody(c.env, f as string);
      return new Response(b.body, { headers: { "content-type": "application/gzip", "content-disposition": `attachment; filename="${f}"`, "x-specsheet-release": c.get("rq").release } });
    },
  });
});

app.post("/mcp", (c) => handleMcp(c as C, app));
app.get("/mcp", (c) => send(c as C, 405, { error: "method_not_allowed", detail: "Use POST (stateless Streamable HTTP, JSON responses only)" }, { allow: "POST" }));
app.on("OPTIONS", ["/v1/miss", "/v1/event"], (c) => preflight(c as C));
app.post("/v1/miss", (c) => handleBeacon(c as C, "miss"));
app.post("/v1/event", (c) => handleBeacon(c as C, "event"));

app.notFound((c) => {
  const rq = c.get("rq");
  if (rq) { rq.route = "other"; rq.outcome = "bad_input"; }
  return send(c as C, 404, { error: "not_found", detail: "no such route; see /openapi.json" }, { "cache-control": "public, max-age=300" });
});

export { matcherFor };
export default app;
