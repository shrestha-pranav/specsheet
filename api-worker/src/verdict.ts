// Per-filter status for /v1/query and the MCP tools: the API honours "explicit unknown + source" (coordinator ruling 2026-11-25).
// Same semantics as scripts/presets.py _verdict (test/verdict-parity.test.ts runs both on the same rows):
//   match      the known value satisfies the filter
//   no         the known value rules the row out
//   unknown    no published value (absent, not_published, not_applicable): might match, never ruled out
//   conflicted sources conflict, no headline value: might match (presets.py calls it disagree)
//   disagree   a disagreeing alternative (index `a`) of the headline value: might match (rules in verdict())
// Enum keys compare exactly (enum values are canonical slugs, as in presets.py); text keys and top-level fields case-insensitively.
// Unknown/conflicted/disagree reveal no licensed value, so they are reported on every tier.
import { TOP, type Filter } from "./filters.ts";
// Rows carry JSON-serialisable values only (index rows), so JSON equality is value equality (presets.py _same).

export type Verdict = "match" | "no" | "unknown" | "conflicted" | "disagree";
export interface VRow { id: string; v: Record<string, unknown>; s?: Record<string, string>; a?: Record<string, unknown[]>; [k: string]: unknown }
export interface FieldMeta { key: string; label?: string | null; group?: string | null; type?: string | null; unit?: string | null; enum?: unknown;
  tier?: string | null; facet?: boolean; facet_kind?: string | null; fill?: number }

const NUMERIC = new Set(["number", "integer", "range"]);
const YES = new Set(["yes", "true", "1"]), NO = new Set(["no", "false", "0"]);

function cmp1(actual: unknown, f: Filter, field?: FieldMeta): boolean {
  if (Array.isArray(actual)) return f.op === "!=" ? !actual.some((a) => cmp1(a, { ...f, op: "=" }, field)) : actual.some((a) => cmp1(a, f, field));
  if (actual === null || actual === undefined) return false;
  if (typeof actual === "object") {
    // range values {min,max} (presets.py: min filter tests lo, max filter tests hi)
    const o = actual as { min?: unknown; max?: unknown };
    const lo = Number(o.min), hi = Number(o.max);
    if (f.num === null || Number.isNaN(lo) || Number.isNaN(hi)) return false;
    switch (f.op) { case ">=": return lo >= f.num; case ">": return lo > f.num; case "<=": return hi <= f.num; case "<": return hi < f.num; default: return false; }
  }
  if (typeof actual === "boolean") {
    const b = f.value.toLowerCase();
    const want = YES.has(b) ? true : NO.has(b) ? false : null;
    if (want === null) return false;
    return f.op === "=" ? actual === want : f.op === "!=" ? actual !== want : false;
  }
  if (typeof actual === "number" && f.num !== null) {
    switch (f.op) {
      case ">=": return actual >= f.num; case "<=": return actual <= f.num; case ">": return actual > f.num; case "<": return actual < f.num;
      case "=": return actual === f.num; case "!=": return actual !== f.num; case "~": return String(actual).includes(f.value);
    }
  }
  if (field && NUMERIC.has(field.type ?? "") && field.facet_kind !== "enum" && ">=<=".includes(f.op)) {
    return false; // presets.py: a non-numeric value under a numeric filter is "no"
  }
  if (field?.type === "enum" && (f.op === "=" || f.op === "!=")) return (String(actual) === f.value) === (f.op === "=");
  const a = String(actual).toLowerCase(), b = f.value.toLowerCase();
  switch (f.op) {
    case "=": return a === b; case "!=": return a !== b; case "~": return a.includes(b);
    default: return false;
  }
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** Verdict of one filter on one index row. Top-level fields (brand, name, ...) are always known: match or no. D10 alternatives (index `a`):
 *  headline matches and an alternative fails or differs -> disagree; headline fails and an alternative matches -> disagree; no headline:
 *  all alternatives fail -> no, else disagree; no headline, no alternatives, conflicted -> conflicted (presets.py: disagree). */
export function verdict(row: VRow, f: Filter, field?: FieldMeta): Verdict {
  if (TOP.has(f.key)) return cmp1((row as Record<string, unknown>)[f.key], f) ? "match" : "no";
  const alts = row.a?.[f.key];
  if (!alts?.length) {  // hot path: no alternatives (nearly every row)
    if (f.key in row.v) return cmp1(row.v[f.key], f, field) ? "match" : "no";
    return row.s?.[f.key] === "conflicted" ? "conflicted" : "unknown";
  }
  const av = alts.map((x) => cmp1(x, f, field));
  if (!(f.key in row.v)) {
    return av.every((x) => !x) ? "no" : "disagree";
  }
  const hv = row.v[f.key];
  const ok = cmp1(hv, f, field);
  if (ok && (av.some((x) => !x) || alts.some((x) => !same(x, hv)))) return "disagree";
  if (!ok && av.some((x) => x)) return "disagree";
  return ok ? "match" : "no";
}

export type RowStatus = "match" | "unknown" | "conflicted" | "disagree" | "no";
/** Disjoint row bucket (presets.py measure, review-7): no > disagree > conflicted > unknown > match. maybe = unknown + conflicted + disagree
 *  (presets.py: maybe = unknown + disagree, its disagree = our conflicted + disagree). */
export function rowStatus(vs: Verdict[]): RowStatus {
  for (const s of ["no", "disagree", "conflicted", "unknown"] as const) if (vs.includes(s)) return s;
  return "match";
}

/** presets.py _parse_filters + _verdict1 branch choice -> the Worker filter grammar, so list_presets hands agents a query_specs filter
 *  string with the same semantics as the site's preset counts. Returns null for a key the pack schema lacks. */
export function presetFilter(appKey: string, value: string, fields: Map<string, FieldMeta>): string | null {
  const m = /^f_(.+)_(min|max|value)$/.exec(appKey);
  if (!m) return null;
  const field = fields.get(m[1]);
  if (!field) return null;
  const k = m[1], suffix = m[2], t = field.type ?? "";
  if (NUMERIC.has(t) && field.facet_kind !== "enum") return `${k}${suffix === "min" ? ">=" : "<="}${value}`;
  if (t === "bool") return `${k}=${value === "yes" ? "yes" : "no"}`;
  if (t === "enum") return `${k}=${value}`;
  return `${k}~${value}`;
}
