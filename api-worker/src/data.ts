// Query pack access (api-worker/pack, built by scripts/build_r2.py --tier free) through the ASSETS binding, plus /v1/query and
// /v1/changes. Assets are only reachable through this module (run_worker_first: true), so nothing is served ungated or unmetered.
import type { Env } from "./config.ts";
import { matches, type Filter, type Row } from "./filters.ts";

export interface CatMeta { id: string; count: number; keys?: string[]; bulk: string; bulk_bytes: number; sha256?: Record<string, string> }
export interface PackManifest {
  release: string; tier: string; built_at: string | null; policy_version?: string; policy_sha256?: string; shard_hex?: number;
  categories: CatMeta[]; match?: { catalogue: string; sha256: string } | null; [k: string]: unknown;
}

export class HttpError extends Error {
  status: number; code: string; extra: Record<string, unknown>;
  constructor(status: number, code: string, detail: string, extra: Record<string, unknown> = {}) {
    super(detail); this.status = status; this.code = code; this.extra = extra;
  }
}

// One Worker version = one release, so per-isolate caches never need invalidation. Bounded LRUs keep memory under the 128 MB isolate cap.
export class Lru<V> {
  m = new Map<string, V>();
  max: number;
  constructor(max: number) { this.max = max; }
  delete(k: string) { this.m.delete(k); }
  get(k: string) { const v = this.m.get(k); if (v !== undefined) { this.m.delete(k); this.m.set(k, v); } return v; }
  set(k: string, v: V) { this.m.delete(k); this.m.set(k, v); if (this.m.size > this.max) this.m.delete(this.m.keys().next().value as string); }
}

let manifest: Promise<PackManifest> | null = null;
const indexes = new Lru<Promise<Row[]>>(4);
const shards = new Lru<Promise<Record<string, any>>>(512);
const jsonCache = new Lru<Promise<unknown>>(16);

async function asset(env: Env, path: string): Promise<Response | null> {
  const r = await env.ASSETS.fetch(new Request(`https://pack.internal/${path}`));
  return r.ok ? r : null;
}
async function assetJson<T>(env: Env, path: string): Promise<T | null> {
  const r = await asset(env, path);
  return r ? ((await r.json()) as T) : null;
}

export function getManifest(env: Env): Promise<PackManifest> {
  manifest ??= assetJson<PackManifest>(env, "meta/manifest.json").then((m) => {
    if (!m) throw new HttpError(503, "pack_missing", "query pack not built (python3 -I scripts/build_r2.py --tier free --shard-hex 3)");
    return m;
  });
  manifest.catch(() => { manifest = null; });
  return manifest;
}

export async function categoryMeta(env: Env, id: string) {
  return (await getManifest(env)).categories.find((c) => c.id === id);
}

function getIndex(env: Env, cat: string): Promise<Row[]> {
  let p = indexes.get(cat);
  if (!p) {
    p = assetJson<Row[]>(env, `index/${cat}.json`).then((rows) => { if (!rows) throw new HttpError(503, "pack_missing", `no index for ${cat}`); return rows; });
    p.catch(() => indexes.delete(cat));
    indexes.set(cat, p);
  }
  return p;
}

export function cachedJson<T>(env: Env, path: string): Promise<T | null> {
  let p = jsonCache.get(path) as Promise<T | null> | undefined;
  if (!p) { p = assetJson<T>(env, path); jsonCache.set(path, p); }
  return p;
}

const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
async function shardOf(id: string, width: number) {
  return hex(await crypto.subtle.digest("SHA-1", new TextEncoder().encode(id))).slice(0, width);
}
function getShard(env: Env, cat: string, xx: string) {
  const k = `${cat}/${xx}`;
  let p = shards.get(k);
  if (!p) { p = assetJson<Record<string, any>>(env, `records/${k}.json`).then((d) => d ?? {}); shards.set(k, p); }
  return p;
}

export interface QueryParams { category: string; filters: Filter[]; q?: string; fields?: string[]; limit: number; offset: number }
interface Spec { value: unknown; unit?: string | null; sources?: string[]; kind?: string | null; status?: string }

export async function runQuery(env: Env, p: QueryParams) {
  const man = await getManifest(env);
  const rows = await getIndex(env, p.category);
  const q = p.q?.toLowerCase();
  const hits: Row[] = [];
  for (const r of rows) {
    if (!matches(r, p.filters)) continue;
    if (q && !`${r.brand} ${r.name} ${r.variant_label ?? ""} ${(r.ids ?? []).join(" ")}`.toLowerCase().includes(q)) continue;
    hits.push(r);
  }
  const page = hits.slice(p.offset, p.offset + p.limit);
  const width = man.shard_hex ?? 2;
  const xs = await Promise.all(page.map((r) => shardOf(r.id, width)));
  const recs = await Promise.all(page.map((r, i) => getShard(env, p.category, xs[i]).then((s) => s[r.id])));
  const fields = p.fields?.length ? new Set(p.fields) : null;
  const results = page.map((r, i) => {
    const rec = recs[i] ?? {};
    const specs: Record<string, unknown> = {};
    const used = new Set<string>();
    for (const [k, sp] of Object.entries((rec.specs ?? {}) as Record<string, Spec>)) {
      if (sp.status !== "known" || (fields && !fields.has(k))) continue;
      specs[k] = { value: sp.value, unit: sp.unit ?? null, kind: sp.kind ?? null, sources: sp.sources ?? [] };
      for (const s of sp.sources ?? []) used.add(s);
    }
    const sources = ((rec.sources ?? []) as { id: string }[]).filter((s) => !fields || used.has(s.id));
    return { id: r.id, kind: r.kind, brand: r.brand, name: r.name, variant_label: r.variant_label ?? null, ids: r.ids ?? [], lifecycle: r.lifecycle ?? null, specs, sources };
  });
  return { category: p.category, total: hits.length, offset: p.offset, count: results.length, results };
}

export interface ChangeEntry { release: string; created_at: string | null; baseline: boolean; counts: Record<string, unknown> }
export const changeHistory = (env: Env) => cachedJson<ChangeEntry[]>(env, "changes/index.json").then((h) => h ?? []);

export function compactStamp(s: string): string {
  const iso = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?Z?)?$/.exec(s);
  return iso ? `${iso[1]}${iso[2]}${iso[3]}T${iso[4] ?? "00"}${iso[5] ?? "00"}${iso[6] ?? "00"}Z` : s;
}

export async function runChanges(env: Env, p: { since: string; category?: string; limit: number }) {
  const hist = await changeHistory(env);
  const since = compactStamp(p.since);
  const newer = hist.filter((h) => h.release > since && !h.baseline);
  const out: Record<string, { added: string[]; removed: string[]; changed: unknown[] }> = {};
  let truncated = false, budget = p.limit;
  for (const h of newer) {
    const d = await cachedJson<{ categories: Record<string, any> }>(env, `changes/${h.release}.json`);
    if (!d) continue;
    for (const [cat, c] of Object.entries(d.categories)) {
      if (p.category && cat !== p.category) continue;
      const t = (out[cat] ??= { added: [], removed: [], changed: [] });
      for (const k of ["added", "removed", "changed"] as const) for (const x of c[k] ?? []) { if (budget-- > 0) (t[k] as unknown[]).push(x); else truncated = true; }
    }
  }
  return {
    since: p.since, latest_release: hist.at(-1)?.release ?? null,
    releases: newer.map((h) => ({ release: h.release, created_at: h.created_at })),
    note: "Multi-release ranges are concatenated in release order (a record may appear in several releases). History starts at the first pack build.",
    truncated, categories: out,
  };
}

/** Paid mode only (L2). <cat>.jsonl.gz from the pack; all.jsonl.gz = the category files concatenated (valid multi-member gzip). */
export async function bulkBody(env: Env, file: string): Promise<{ body: ReadableStream; size: number }> {
  const man = await getManifest(env);
  const cats = file === "all.jsonl.gz" ? man.categories : man.categories.filter((c) => `${c.id}.jsonl.gz` === file);
  if (!cats.length) throw new HttpError(404, "not_found", "unknown bulk file");
  const { readable, writable } = new TransformStream();
  (async () => {
    for (const c of cats) { const r = await asset(env, c.bulk); if (r?.body) await r.body.pipeTo(writable, { preventClose: true }); }
    await writable.close();
  })();
  return { body: readable, size: cats.reduce((n, c) => n + c.bulk_bytes, 0) };
}
