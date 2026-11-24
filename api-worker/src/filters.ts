// Filter grammar for /v1/query:  filters=cpu.cores>=8,mem.size>=16,brand=ASUS,name~zenbook
// Operators: >= <= > < != = ~ (substring, case-insensitive). Top-level fields: brand, name, kind, lifecycle, id, variant_label; all
// other keys are spec keys matched against known values only (unknown/unpublished values never match).
export type Op = ">=" | "<=" | ">" | "<" | "!=" | "=" | "~";
export interface Filter { key: string; op: Op; value: string; num: number | null }

const RE = /^\s*([A-Za-z0-9_.\-]+)\s*(>=|<=|!=|=|>|<|~)\s*(.*?)\s*$/;
export const TOP = new Set(["brand", "name", "kind", "lifecycle", "id", "variant_label"]);

export function parseFilters(raw: string): { filters: Filter[]; error?: string } {
  const filters: Filter[] = [];
  for (const part of raw.split(",")) {
    if (!part.trim()) continue;
    const m = RE.exec(part);
    if (!m) return { filters, error: `bad filter '${part.slice(0, 80)}' (expected key<op>value, ops: >= <= > < != = ~)` };
    const n = m[3] !== "" ? Number(m[3]) : NaN;
    filters.push({ key: m[1], op: m[2] as Op, value: m[3], num: Number.isNaN(n) ? null : n });
  }
  return { filters };
}

function cmp(actual: unknown, f: Filter): boolean {
  if (Array.isArray(actual)) {
    return f.op === "!=" ? !actual.some((a) => cmp(a, { ...f, op: "=" })) : actual.some((a) => cmp(a, f));
  }
  if (actual === null || actual === undefined || typeof actual === "object") return false;
  if (typeof actual === "number" && f.num !== null) {
    switch (f.op) {
      case ">=": return actual >= f.num; case "<=": return actual <= f.num; case ">": return actual > f.num; case "<": return actual < f.num;
      case "=": return actual === f.num; case "!=": return actual !== f.num; case "~": return String(actual).includes(f.value);
    }
  }
  const a = String(actual).toLowerCase(), b = f.value.toLowerCase();
  switch (f.op) {
    case "=": return a === b; case "!=": return a !== b; case "~": return a.includes(b);
    default: return false; // ordering operators need numbers
  }
}

export interface Row { id: string; kind?: string; brand?: string; name?: string; variant_label?: string | null; lifecycle?: string; ids?: string[]; v: Record<string, unknown> }

export function matches(row: Row, filters: Filter[]): boolean {
  for (const f of filters) {
    const top = TOP.has(f.key);
    const actual = top ? (row as unknown as Record<string, unknown>)[f.key] : row.v[f.key];
    if (actual === undefined && !top) return false; // unknown never satisfies a filter, not even !=
    if (!cmp(actual, f)) return false;
  }
  return true;
}
