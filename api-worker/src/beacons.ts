// POST /v1/miss and POST /v1/event (D4, measurement-plan §2): CORS for the site origin only, size-capped, one event each, separate
// daily budgets (miss 30, event 200 per client network). Event names and fields come from an allowlist; miss text is redacted before
// it is written. Neither body is stored anywhere else. Content-Type text/plain is accepted so navigator.sendBeacon needs no preflight.
import { BOUNDS, QUOTA, type Env } from "./config.ts";
import { getManifest } from "./data.ts";
import { guard, send, type C } from "./gate.ts";
import { redactMiss } from "./metrics.ts";

const siteOrigin = (env: Env) => (env.SITE_ORIGIN || "").replace(/\/$/, "");
const cors = (env: Env): Record<string, string> => ({ "access-control-allow-origin": siteOrigin(env), vary: "Origin" });

export function preflight(c: C) {
  const o = c.req.header("origin");
  c.get("rq").skip = true;
  if (!o || o !== siteOrigin(c.env)) return new Response(null, { status: 403 });
  return new Response(null, { status: 204, headers: { ...cors(c.env), "access-control-allow-methods": "POST", "access-control-allow-headers": "content-type", "access-control-max-age": "86400" } });
}

const ID = /^[a-z0-9][a-z0-9_.-]{0,63}$/;
const HOST = /^(?=.{1,100}$)[a-z0-9-]+(\.[a-z0-9-]+)+$/;
type Check = (v: unknown, keys: Set<string>) => boolean;
const EVENTS: Record<string, { fields: Record<string, Check>; detail?: string; count?: string }> = {
  killer_query: { fields: { preset: (v) => typeof v === "string" && ID.test(v), results: (v) => Number.isInteger(v) && (v as number) >= 0 && (v as number) <= 1e6 }, detail: "preset", count: "results" },
  source_click: { fields: { domain: (v) => typeof v === "string" && HOST.test(v) }, detail: "domain" },
  request_click: { fields: {} },
  spec_unknown_shown: { fields: { key: (v, keys) => typeof v === "string" && keys.has(v) }, detail: "key" },
  product_view: { fields: { brand: (v) => typeof v === "string" && ID.test(v) }, detail: "brand" },
};
const OPTIONAL_CATEGORY = new Set(["killer_query"]);

export async function handleBeacon(c: C, which: "miss" | "event") {
  const rq = c.get("rq"), env = c.env;
  rq.kind = "beacon"; rq.route = `/v1/${which}`;
  const o = c.req.header("origin");
  const h = o === siteOrigin(env) ? cors(env) : {};
  const bad = (status: number, code: string, detail: string) => { rq.outcome = "bad_input"; return send(c, status, { error: code, detail }, h); };
  if (o && o !== siteOrigin(env)) return bad(403, "origin_not_allowed", "beacons accept the site origin only");
  const cap = which === "miss" ? BOUNDS.missBody : BOUNDS.eventBody;
  if (Number(c.req.header("content-length") ?? 0) > cap) return bad(413, "too_large", `body larger than ${cap} bytes`);
  const text = await c.req.text();
  if (text.length > cap) return bad(413, "too_large", `body larger than ${cap} bytes`);
  const g = await guard(c, [{ kind: which, n: 1, limit: which === "miss" ? QUOTA.miss : QUOTA.event }]);
  if (g instanceof Response) { const r = new Response(g.body, g); for (const [k, v] of Object.entries(h)) r.headers.set(k, v); return r; }
  let body: any;
  try { body = JSON.parse(text); } catch { return bad(400, "bad_input", "body must be one JSON object"); }
  if (!body || typeof body !== "object" || Array.isArray(body)) return bad(400, "bad_input", "body must be one JSON object (one event)");
  const man = await getManifest(env);
  const catOk = (v: unknown) => typeof v === "string" && man.categories.some((x) => x.id === v);
  if (which === "miss") {
    for (const k of Object.keys(body)) if (k !== "category" && k !== "q") return bad(400, "bad_input", `unknown field ${k.slice(0, 32)}`);
    if (typeof body.q !== "string" || !body.q.trim()) return bad(400, "bad_input", "q (string) is required");
    if (body.category !== undefined && !catOk(body.category)) return bad(400, "bad_input", "unknown category");
    rq.category = body.category ?? "";
    rq.detail = redactMiss(body.q);
    rq.outcome = "ok";
    return new Response(null, { status: 204, headers: { ...h, "x-specsheet-release": rq.release } });
  }
  const ev = EVENTS[body.event];
  if (!ev) return bad(400, "bad_input", `event must be one of ${Object.keys(EVENTS).join(", ")}`);
  const cat = man.categories.find((x) => x.id === body.category);
  if (body.category === undefined ? !OPTIONAL_CATEGORY.has(body.event) : !cat) return bad(400, "bad_input", "unknown or missing category");
  const keys = new Set(cat?.keys ?? []);
  for (const k of Object.keys(body)) {
    if (k === "event" || k === "category") continue;
    const chk = ev.fields[k];
    if (!chk || !chk(body[k], keys)) return bad(400, "bad_input", `field ${k.slice(0, 32)} not allowed or invalid for ${body.event}`);
  }
  for (const k of Object.keys(ev.fields)) if (body[k] === undefined) return bad(400, "bad_input", `field ${k} required for ${body.event}`);
  rq.category = cat?.id ?? "";
  rq.detail = ev.detail ? `${body.event}:${body[ev.detail]}` : body.event;
  if (ev.count) rq.results = body[ev.count];
  rq.outcome = "ok";
  return new Response(null, { status: 204, headers: { ...h, "x-specsheet-release": rq.release } });
}
