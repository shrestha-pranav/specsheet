// D3.6 input bounds. Everything here runs before any data load (the manifest and the release list are metadata). Errors are 400/414,
// are never charged, and count once against the daily quota (the caller spends before validating).
import { BOUNDS } from "./config.ts";
import { compactStamp, HttpError, type PackManifest } from "./data.ts";
import { parseFilters, TOP, type Filter } from "./filters.ts";

const bad = (detail: string, extra: Record<string, unknown> = {}) => new HttpError(400, "bad_input", detail, extra);

/** Reject unknown and repeated parameters (query-string cache-busting). Returns a plain map. */
export function strictParams(sp: URLSearchParams, allowed: readonly string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of sp) {
    if (!allowed.includes(k)) throw bad(`unknown parameter '${k.slice(0, 40)}'`, { allowed });
    if (k in out) throw bad(`parameter '${k}' given twice`);
    out[k] = v;
  }
  return out;
}

function intParam(v: string | undefined, name: string, d: number, min: number, max: number): number {
  if (v === undefined) return d;
  if (!/^\d{1,6}$/.test(v)) throw bad(`${name} must be an integer`);
  const n = Number(v);
  if (n < min || n > max) throw bad(`${name} must be between ${min} and ${max}`);
  return n;
}

function category(man: PackManifest, v: string | undefined, required: boolean) {
  if (v === undefined || v === "") { if (required) throw bad("category is required", { categories: man.categories.map((c) => c.id) }); return undefined; }
  const c = man.categories.find((x) => x.id === v);
  if (!c) throw bad(`unknown category`, { categories: man.categories.map((x) => x.id) });
  return c;
}

export const QUERY_PARAMS = ["category", "filters", "q", "fields", "limit", "offset"] as const;
export const CHANGES_PARAMS = ["since", "category", "limit"] as const;
export const MATCH_PARAMS = ["title", "category"] as const;

export interface Validated<T> { params: T; canonical: string; filterKeys: string[] }

export function validateQuery(man: PackManifest, sp: URLSearchParams) {
  const p = strictParams(sp, QUERY_PARAMS);
  const cat = category(man, p.category, true)!;
  const keys = new Set([...(cat.keys ?? []), ...TOP]);
  let filters: Filter[] = [];
  if (p.filters !== undefined) {
    if (p.filters.length > BOUNDS.filtersChars) throw bad(`filters longer than ${BOUNDS.filtersChars} chars`);
    const r = parseFilters(p.filters);
    if (r.error) throw bad(r.error);
    filters = r.filters;
    if (filters.length > BOUNDS.filterClauses) throw bad(`more than ${BOUNDS.filterClauses} filter clauses`);
    for (const f of filters) {
      if (!keys.has(f.key)) throw bad(`unknown filter key '${f.key.slice(0, 64)}' for ${cat.id}`);
      if (f.value.length > BOUNDS.filterValue) throw bad(`filter value longer than ${BOUNDS.filterValue} chars`);
    }
  }
  if (p.q !== undefined && p.q.length > BOUNDS.q) throw bad(`q longer than ${BOUNDS.q} chars`);
  let fields: string[] | undefined;
  if (p.fields !== undefined) {
    fields = [...new Set(p.fields.split(",").map((s) => s.trim()).filter(Boolean))];
    if (fields.length > BOUNDS.fields) throw bad(`more than ${BOUNDS.fields} fields`);
    for (const f of fields) if (!keys.has(f)) throw bad(`unknown field '${f.slice(0, 64)}' for ${cat.id}`);
    fields.sort();
  }
  const limit = intParam(p.limit, "limit", BOUNDS.limitDefault, 1, BOUNDS.limitMax);
  const offset = intParam(p.offset, "offset", 0, 0, BOUNDS.offsetMax);
  const q = p.q?.trim() || undefined;
  const fstr = filters.map((f) => `${f.key}${f.op}${f.value}`).sort().join(",");
  const canonical = new URLSearchParams([["category", cat.id], ["fields", fields?.join(",") ?? ""], ["filters", fstr], ["limit", String(limit)],
    ["offset", String(offset)], ["q", q?.toLowerCase() ?? ""]]).toString();
  return { params: { category: cat.id, filters, q, fields, limit, offset }, canonical, filterKeys: [...new Set(filters.map((f) => f.key))].sort() };
}

export function validateChanges(man: PackManifest, sp: URLSearchParams, retained: string[], now = Date.now()) {
  const p = strictParams(sp, CHANGES_PARAMS);
  const since = p.since;
  if (!since) throw bad("since is required (a retained release id or an ISO date within 90 days)", { releases: retained });
  if (since.length > 40) throw bad("since too long");
  if (!retained.includes(since)) {
    const st = compactStamp(since);
    const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(st);
    const t = m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) : NaN;
    if (!/^\d{4}-\d{2}-\d{2}/.test(since) || Number.isNaN(t)) throw bad("since must be a retained release id or an ISO date", { releases: retained });
    if (t < now - BOUNDS.changesDays * 86400_000 || t > now + 86400_000) throw bad(`since must be within the last ${BOUNDS.changesDays} days`);
  }
  const cat = category(man, p.category, false);
  const limit = intParam(p.limit, "limit", BOUNDS.changesLimitDefault, 1, BOUNDS.changesLimitMax);
  const canonical = new URLSearchParams([["category", cat?.id ?? ""], ["limit", String(limit)], ["since", since]]).toString();
  return { params: { since, category: cat?.id, limit }, canonical, filterKeys: [] as string[] };
}

export function validateMatch(man: PackManifest, sp: URLSearchParams) {
  const p = strictParams(sp, MATCH_PARAMS);
  const title = p.title?.trim();
  if (!title) throw bad("title is required");
  if (p.title.length > BOUNDS.title) throw bad(`title longer than ${BOUNDS.title} chars`);
  const cat = category(man, p.category, false);
  const canonical = new URLSearchParams([["category", cat?.id ?? ""], ["title", title.toLowerCase()]]).toString();
  return { params: { title, category: cat?.id }, canonical, filterKeys: [] as string[] };
}
