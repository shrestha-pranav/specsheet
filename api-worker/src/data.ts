import type { Env } from "./config.ts";
import { matches, parseFilters, type Row } from "./filters.ts";

export interface CatMeta { id: string; count: number; legacy: boolean; bulk: string; bulk_bytes: number }
export interface DataManifest { release: string; built_at: string | null; categories: CatMeta[] }

export class HttpError extends Error { constructor(public status: number, msg: string, public extra: Record<string, unknown> = {}) { super(msg); } }

let manifestCache: { at: number; m: DataManifest } | null = null;
const indexCache = new Map<string, { release: string; rows: Row[] }>();

export async function getManifest(env: Env): Promise<DataManifest> {
  if (manifestCache && Date.now() - manifestCache.at < 60_000) return manifestCache.m;
  const o = await env.DATA.get("meta/manifest.json");
  if (!o) throw new HttpError(503, "dataset not loaded into R2 (run scripts/build_r2.py and seed; see README)");
  const m = (await o.json()) as DataManifest;
  manifestCache = { at: Date.now(), m };
  return m;
}

async function getIndex(env: Env, cat: string, release: string): Promise<Row[]> {
  const hit = indexCache.get(cat);
  if (hit && hit.release === release) return hit.rows;
  const o = await env.DATA.get(`index/${cat}.json`);
  if (!o) throw new HttpError(404, `no index for category ${cat}`);
  const rows = (await o.json()) as Row[];
  indexCache.set(cat, { release, rows });
  return rows;
}

async function shardOf(id: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(id));
  return [...new Uint8Array(d).slice(0, 1)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

interface Spec { value: unknown; unit?: string | null; sources?: string[]; kind?: string | null; status?: string }

export async function runQuery(env: Env, p: { category: string; filters: string[]; q?: string; fields?: string[]; limit: number; offset: number }) {
  const man = await getManifest(env);
  if (!man.categories.some((c) => c.id === p.category))
    throw new HttpError(404, `unknown category '${p.category}'`, { categories: man.categories.map((c) => c.id) });
  const { filters, error } = parseFilters(p.filters);
  if (error) throw new HttpError(400, error);
  const rows = await getIndex(env, p.category, man.release);
  const q = p.q?.toLowerCase();
  const hits = rows.filter((r) => matches(r, filters) && (!q || `${r.brand} ${r.name} ${r.variant_label ?? ""} ${(r.ids ?? []).join(" ")}`.toLowerCase().includes(q)));
  const page = hits.slice(p.offset, p.offset + p.limit);
  // provenance: pull record shards for just this page
  const shards = new Map<string, Record<string, any>>();
  for (const r of page) {
    const xx = await shardOf(r.id);
    if (!shards.has(xx)) {
      const o = await env.DATA.get(`records/${p.category}/${xx}.json`);
      shards.set(xx, o ? ((await o.json()) as Record<string, any>) : {});
    }
  }
  const results = [];
  for (const r of page) {
    const rec = shards.get(await shardOf(r.id))?.[r.id];
    const srcById = new Map<string, any>((rec?.sources ?? []).map((s: any) => [s.id, s]));
    const specs: Record<string, unknown> = {};
    for (const [k, sp] of Object.entries((rec?.specs ?? {}) as Record<string, Spec>)) {
      if (sp.status !== "known") continue;
      if (p.fields?.length && !p.fields.includes(k)) continue;
      specs[k] = { value: sp.value, unit: sp.unit ?? null, kind: sp.kind ?? null, sources: (sp.sources ?? []).map((id) => srcById.get(id) ?? { id }) };
    }
    results.push({ id: r.id, kind: r.kind, brand: r.brand, name: r.name, variant_label: r.variant_label, ids: r.ids, lifecycle: r.lifecycle, specs, sources: rec?.sources ?? [] });
  }
  return { category: p.category, release: man.release, total: hits.length, offset: p.offset, count: results.length, results };
}

function compact(s: string): string {
  // accepts a release id (20261123T233625Z-9e307181), a compact stamp, or ISO 8601 (2026-11-23T23:36:25Z / 2026-11-23)
  const iso = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}):?(\d{2})?)?/.exec(s);
  if (iso) return `${iso[1]}${iso[2]}${iso[3]}T${iso[4] ?? "00"}${iso[5] ?? "00"}${iso[6] ?? "00"}Z`;
  return s;
}

export async function runChanges(env: Env, p: { since: string; category?: string; limit: number }) {
  const o = await env.DATA.get("changes/index.json");
  if (!o) throw new HttpError(503, "changes history not loaded into R2");
  const hist = (await o.json()) as { release: string; created_at: string | null; baseline: boolean; counts: Record<string, unknown> }[];
  const since = compact(p.since);
  if (!/^\d{8}T\d{6}Z/.test(since)) throw new HttpError(400, "since must be a release id or an ISO date/time");
  const newer = hist.filter((h) => h.release > since && !h.baseline);
  const out: Record<string, { added: string[]; removed: string[]; changed: unknown[] }> = {};
  let truncated = false, budget = p.limit;
  for (const h of newer) {
    const f = await env.DATA.get(`changes/${h.release}.json`);
    if (!f) continue;
    const d = (await f.json()) as { categories: Record<string, any> };
    for (const [cat, c] of Object.entries(d.categories)) {
      if (p.category && cat !== p.category) continue;
      const t = (out[cat] ??= { added: [], removed: [], changed: [] });
      for (const k of ["added", "removed", "changed"] as const) {
        for (const x of c[k]) { if (budget-- > 0) (t[k] as unknown[]).push(x); else truncated = true; }
      }
    }
  }
  return {
    since: p.since, latest_release: hist.at(-1)?.release ?? null,
    releases: newer.map((h) => ({ release: h.release, created_at: h.created_at })),
    note: "Multi-release ranges are concatenated in release order (a record may appear in several releases). History starts at the first export build.",
    truncated, categories: out,
  };
}

export async function bulkObject(env: Env, file: string) {
  const m = /^([a-z0-9-]+)\.jsonl\.gz$/.exec(file);
  if (!m) throw new HttpError(404, "expected /v1/bulk/<category>.jsonl.gz");
  const man = await getManifest(env);
  if (!man.categories.some((c) => c.id === m[1])) throw new HttpError(404, `unknown category '${m[1]}'`, { categories: man.categories.map((c) => c.id) });
  const o = await env.DATA.get(`bulk/${m[1]}.jsonl.gz`);
  if (!o) throw new HttpError(404, "bulk file missing");
  return { body: o.body, release: man.release, size: o.size };
}
