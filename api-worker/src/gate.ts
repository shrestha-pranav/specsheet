// Shared request plumbing: per-request record (rq) -> one metrics point, JSON responses that always carry `release`, the quota guard,
// the canonical-key cache, and the data executors used by both REST and MCP (so MCP never re-enters the REST quota).
import type { Context } from "hono";
import { limits, type Env, type Mode } from "./config.ts";
import { HttpError, Lru, cachedJson, getManifest, runChanges, runQuery, type PackManifest, type QueryParams } from "./data.ts";
import { loadMatcher } from "./match.ts";
import { writePoint, type Kind, type Outcome, type Point } from "./metrics.ts";
import { clientKey, secondsToReset, shardName } from "./keys.ts";
import type { Bucket } from "./quota.ts";

export interface Rq {
  t0: number; key: string; uaFamily: string; cid: string; mode: Mode; release: string; kind: Kind; route: string; category: string;
  outcome: Outcome; results: number; bytes: number; cacheHit: boolean; detail: string; mcpClient: string; canonical: string;
  wouldPay: string; traffic: string; skip: boolean; points: AnalyticsEngineDataPoint[];
}
export type C = Context<{ Bindings: Env; Variables: { rq: Rq } }>;

export function newRq(env: Env, req: Request, mode: Mode, uaFamily: string): Rq {
  return { t0: Date.now(), key: clientKey(req.headers.get("cf-connecting-ip")), uaFamily, cid: "none", mode, release: "none", kind: "api",
    route: new URL(req.url).pathname.slice(0, 64), category: "", outcome: "ok", results: 0, bytes: 0, cacheHit: false, detail: "", mcpClient: "",
    canonical: "", wouldPay: "", traffic: "real", skip: false, points: [] };
}

export function point(env: Env, rq: Rq, status: number, over: Partial<Point> = {}) {
  const p: Point = { kind: rq.kind, route: rq.route, category: rq.category, status, outcome: rq.outcome, ua: rq.uaFamily,
    mode: rq.wouldPay ? `${rq.mode === "on-bad" ? "on" : rq.mode}:${rq.wouldPay}` : rq.mode === "on-bad" ? "on" : rq.mode, traffic: rq.traffic,
    release: rq.release, mcpClient: rq.mcpClient, cid: rq.cid, detail: rq.detail, results: rq.results, bytes: rq.bytes,
    wallMs: Date.now() - rq.t0, cacheHit: rq.cacheHit, ...over };
  rq.points.push(writePoint(env, p));
}

export const JSON_CT = "application/json; charset=utf-8";
export function send(c: C, status: number, body: Record<string, unknown>, headers: Record<string, string> = {}) {
  const rq = c.get("rq");
  const text = JSON.stringify({ release: rq.release, ...body });
  rq.bytes = text.length;
  return new Response(text, { status, headers: { "content-type": JSON_CT, "x-specsheet-release": rq.release, ...headers } });
}
export function fail(c: C, e: HttpError, headers: Record<string, string> = {}) {
  const rq = c.get("rq");
  if (rq.outcome === "ok") rq.outcome = e.status === 429 ? "quota" : e.status === 503 && e.code.startsWith("preview") ? "breaker" : e.status >= 500 ? "error" : "bad_input";
  return send(c, e.status, { error: e.code, detail: e.message, ...e.extra }, headers);
}

// ---------------------------------------------------------------- quota guard
let trippedUntil = 0; // per-isolate copy of the breaker state (30 s), so a tripped breaker costs no DO request

export type GuardResult = { ok: boolean[]; counts: number[]; degraded: boolean };
/** Minute limit (binding), then the daily buckets in one DO call. buckets[0] decides 429. Returns a Response to send on refusal. */
export async function guard(c: C, buckets: Bucket[], failClosed = false): Promise<Response | GuardResult> {
  const rq = c.get("rq"), env = c.env, now = Date.now();
  if (env.RATE_LIMITER) {
    const r = await env.RATE_LIMITER.limit({ key: rq.key });
    if (!r.success) { rq.outcome = "quota"; return send(c, 429, { error: "rate_limited", detail: "60 requests per minute per client network" }, { "retry-after": "60" }); }
  }
  if (!buckets.length) return { ok: [], counts: [], degraded: false };
  if (buckets.some((b) => b.data) && trippedUntil > now) return capacity(c);
  try {
    const ns = env.BUDGET;
    const stub = ns.get(ns.idFromName(await shardName(rq.key)));
    const r = await stub.spend(rq.key, rq.uaFamily, buckets, limits(env).breaker);
    rq.cid = r.cid;
    if (r.tripped) { trippedUntil = now + 30_000; if (buckets.some((b) => b.data)) return capacity(c); } else trippedUntil = 0;
    if (!r.ok[0]) {
      rq.outcome = "quota";
      return send(c, 429, { error: "quota_exceeded", detail: `daily budget spent (${buckets[0].limit}/day per client network, resets 00:00 UTC). Use the static files for volume.` },
        { "retry-after": String(secondsToReset()) });
    }
    return { ok: r.ok, counts: r.counts, degraded: false };
  } catch (e) {
    // DO unavailable: fail open on binding-only limits (free routes), fail closed for paid routes in PAYMENTS=on.
    point(env, rq, 0, { kind: "ops", route: "quota_degraded", outcome: "error", detail: String((e as Error)?.message ?? e).slice(0, 60).replace(/[0-9a-f]{8,}/g, "·") });
    if (failClosed) return send(c, 503, { error: "quota_unavailable", detail: "quota service unavailable; paid routes fail closed" }, { "retry-after": "60" });
    return { ok: buckets.map(() => true), counts: buckets.map(() => 0), degraded: true };
  }
}
function capacity(c: C) {
  c.get("rq").outcome = "breaker";
  return send(c, 503, { error: "preview_capacity", detail: "the free preview reached its daily capacity; the static dataset on GitHub Pages is unaffected" },
    { "retry-after": String(secondsToReset()) });
}
export function paused(c: C) {
  c.get("rq").outcome = "breaker";
  return send(c, 503, { error: "preview_paused", detail: "the free preview is paused by the operator; the static dataset on GitHub Pages is unaffected" }, { "retry-after": "3600" });
}

// ---------------------------------------------------------------- cache (D3.7: release + route + category + sorted validated params)
export interface Served { status: number; text: string; results: number; outcome: Outcome; contentType?: string }
const micro = new Lru<Served>(256);
const TTL = 300;

export async function cachedServe(c: C, route: string, canonical: string, compute: () => Promise<Served>): Promise<Served> {
  const rq = c.get("rq");
  const key = `https://cache.specsheet.internal/${rq.release}${route}?${canonical}`;
  const m = micro.get(key);
  if (m && (m as Served & { at?: number }).at! > Date.now() - TTL * 1000) { rq.cacheHit = true; return m; }
  let edge: Cache | null = null;
  try { edge = (globalThis as unknown as { caches?: { default: Cache } }).caches?.default ?? null; } catch { edge = null; }
  if (edge) {
    const hit = await edge.match(key).catch(() => undefined);
    if (hit) {
      rq.cacheHit = true;
      const s: Served = { status: hit.status, text: await hit.text(), results: Number(hit.headers.get("x-specsheet-results") ?? 0), outcome: (hit.headers.get("x-specsheet-outcome") ?? "ok_results") as Outcome };
      micro.set(key, Object.assign(s, { at: Date.now() }));
      return s;
    }
  }
  const s = await compute();
  if (s.status === 200 || (s.status === 404 && s.outcome !== "error")) {
    micro.set(key, Object.assign({ ...s }, { at: Date.now() }));
    if (edge) {
      const put = edge.put(key, new Response(s.text, { status: s.status, headers: { "content-type": JSON_CT, "cache-control": `public, max-age=${TTL}`, "x-specsheet-results": String(s.results), "x-specsheet-outcome": s.outcome } })).catch(() => {});
      try { c.executionCtx.waitUntil(put); } catch { /* no ctx in unit harness */ }
    }
  }
  return s;
}

// ---------------------------------------------------------------- executors (no quota, no metrics: callers own those)
const ser = (release: string, body: Record<string, unknown>) => JSON.stringify({ release, ...body });

export async function execQuery(env: Env, release: string, p: QueryParams): Promise<Served> {
  const r = await runQuery(env, p);
  return { status: 200, text: ser(release, r), results: r.count, outcome: r.total ? "ok_results" : "ok_empty" };
}
export async function execChanges(env: Env, release: string, p: { since: string; category?: string; limit: number }): Promise<Served> {
  const r = await runChanges(env, p);
  const n = Object.values(r.categories).reduce((a, x) => a + x.added.length + x.removed.length + x.changed.length, 0);
  return { status: 200, text: ser(release, r), results: n, outcome: n ? "ok_results" : "ok_empty" };
}
export async function matcherFor(env: Env, man: PackManifest) {
  if (!man.match?.catalogue) return null;
  const doc = await cachedJson<unknown>(env, man.match.catalogue);
  return doc ? loadMatcher(doc as never) : null;
}
export async function execMatch(env: Env, man: PackManifest, p: { title: string; category?: string }): Promise<Served> {
  const m = await matcherFor(env, man);
  if (!m) throw new HttpError(404, "not_available", "match is not available in this release");
  const diag: Record<string, unknown> = {};
  const candidates = m.match(p.title, p.category, diag);
  const body: Record<string, unknown> = { title: p.title, category: p.category ?? null, candidates };
  if (!candidates.length) body.reason = typeof diag.ambiguous === "string" ? diag.ambiguous : "no safe match";
  return { status: 200, text: ser(man.release, body), results: candidates.length, outcome: candidates.length ? "ok_results" : "match_fail" };
}

export const manifestOf = (env: Env) => getManifest(env);
