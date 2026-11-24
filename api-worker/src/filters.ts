// Filter grammar for /v1/query:  filters=cpu.cores>=8,mem.size>=16,brand=ASUS,name~zenbook   (also repeatable: &filter=...)
// Operators: >= <= > < != = ~ (substring, case-insensitive). Top-level fields: brand, name, kind, lifecycle, id; all
// other keys are spec keys matched against known values only (unknown/unpublished values never match).
export type Op = ">=" | "<=" | ">" | "<" | "!=" | "=" | "~";
export interface Filter { key: string; op: Op; value: string }

const RE = /^\s*([A-Za-z0-9_.\-]+)\s*(>=|<=|!=|=|>|<|~)\s*(.*?)\s*$/;

export function parseFilters(raw: string[]): { filters: Filter[]; error?: string } {
  const filters: Filter[] = [];
  for (const chunk of raw) {
    for (const part of chunk.split(",")) {
      if (!part.trim()) continue;
      const m = RE.exec(part);
      if (!m) return { filters, error: `bad filter '${part}' (expected key<op>value, ops: >= <= > < != = ~)` };
      filters.push({ key: m[1], op: m[2] as Op, value: m[3] });
    }
  }
  return { filters };
}

const TOP = new Set(["brand", "name", "kind", "lifecycle", "id", "variant_label"]);

function cmp(actual: unknown, f: Filter): boolean {
  if (Array.isArray(actual)) {
    const hit = actual.some((a) => cmp(a, f));
    return f.op === "!=" ? !actual.some((a) => cmp(a, { ...f, op: "=" })) : hit;
  }
  if (actual === null || actual === undefined || typeof actual === "object") return false;
  const nf = Number(f.value);
  if (typeof actual === "number" && f.value !== "" && !Number.isNaN(nf)) {
    switch (f.op) {
      case ">=": return actual >= nf; case "<=": return actual <= nf; case ">": return actual > nf; case "<": return actual < nf;
      case "=": return actual === nf; case "!=": return actual !== nf; case "~": return String(actual).includes(f.value);
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
    const actual = TOP.has(f.key) ? (row as unknown as Record<string, unknown>)[f.key] : row.v[f.key];
    if (actual === undefined && f.op === "!=" && !TOP.has(f.key)) return false; // unknown never satisfies a filter
    if (!cmp(actual, f)) return false;
  }
  return true;
}
