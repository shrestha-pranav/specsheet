// Parity: src/verdict.ts (per-filter status in /v1/query) must give the verdict scripts/presets.py _verdict gives, on the same rows, for
// (1) the hand-written fixtures (test/fixtures/verdict-rows.json) and (2) every built docs preset over its category's docs index rows.
// TS "conflicted" == presets.py "disagree" (a conflict with no headline value). Preset app filters are translated with presetFilter, so
// this also proves list_presets hands agents filter strings with the site's semantics. Python runs once per case set.
//   cd api-worker && node --test test/verdict-parity.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseFilters } from "../src/filters.ts";
import { presetFilter, rowStatus, verdict, type FieldMeta, type Verdict, type VRow } from "../src/verdict.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const API = join(ROOT, "docs", "api", "v1");

const PY = `
import sys, json
sys.path.insert(0, ${JSON.stringify(join(ROOT, "scripts"))})
import presets as P
d = json.load(sys.stdin)
F = {f["key"]: f for f in d["fields"]}
out = []
for r in d["rows"]:
    out.append([P._verdict(r, F[P.KEY.match(k).group(1)], P.KEY.match(k).group(2), v) for k, v in d["filters"]])
print(json.dumps(out))
`;
function py(fields: unknown[], rows: unknown[], filters: [string, string][]): string[][] {
  const r = spawnSync("python3", ["-I", "-c", PY], { input: JSON.stringify({ fields, rows, filters }), maxBuffer: 1 << 28, encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
}

/** docs index row -> pack index row (what scripts/build_r2.py writes): s = conflicted/not_applicable statuses, a = alternative values. */
function packRow(r: any): VRow {
  const s = Object.fromEntries(Object.entries(r.s ?? {}).filter(([, v]) => v === "conflicted" || v === "not_applicable")) as Record<string, string>;
  const a: Record<string, unknown[]> = {};
  for (const [k, x] of Object.entries((r.x ?? {}) as Record<string, any>)) if (x?.alt?.length) a[k] = x.alt.map((y: any) => y.v);
  return { ...r, v: r.v ?? {}, s, a };
}
const toPy = (v: Verdict) => (v === "conflicted" ? "disagree" : v);
const metaOf = (f: any): FieldMeta => ({ key: f.key, type: f.type, facet: !!f.facet, facet_kind: typeof f.facet === "object" && f.facet ? f.facet.kind : null });

function tsVerdicts(fields: any[], rows: any[], filters: [string, string][]): Verdict[][] {
  const fm = new Map(fields.map((f) => [f.key, metaOf(f)]));
  const fs = filters.map(([k, v]) => {
    const s = presetFilter(k, v, fm);
    assert.ok(s, `preset filter ${k} not translatable`);
    const p = parseFilters(s!);
    assert.equal(p.filters.length, 1, s!);
    return { f: p.filters[0], meta: fm.get(p.filters[0].key) };
  });
  return rows.map((r) => fs.map(({ f, meta }) => verdict(packRow(r), f, meta)));
}

test("fixtures: TS verdicts == presets.py verdicts, and pinned", () => {
  const d = JSON.parse(readFileSync(join(HERE, "fixtures", "verdict-rows.json"), "utf8"));
  const p = py(d.fields, d.rows, d.filters);
  const t = tsVerdicts(d.fields, d.rows, d.filters);
  d.rows.forEach((r: any, i: number) => {
    assert.deepEqual(t[i].map(toPy), p[i], `row ${r.id}`);
    assert.deepEqual(t[i], r.expect, `row ${r.id} pinned`);
  });
});

const skip = !existsSync(join(API, "presets.json")) ? "docs/api/v1 not built" : false;
test("docs presets: every row x filter verdict and row bucket equals presets.py", { skip }, () => {
  const cats = JSON.parse(readFileSync(join(API, "categories.json"), "utf8"));
  const presets = JSON.parse(readFileSync(join(API, "presets.json"), "utf8")).presets;
  let cells = 0, buckets = 0;
  for (const pr of presets) {
    const filters = Object.entries(pr.filters ?? {}).map(([k, v]) => [k, String(v)]) as [string, string][];
    if (!filters.length) continue;
    const cat = cats.find((c: any) => c.id === pr.category);
    const fields = JSON.parse(readFileSync(join(API, cat.schema), "utf8")).fields;
    let rows: any[] = [];
    for (const sh of cat.index) rows = rows.concat(JSON.parse(readFileSync(join(API, sh), "utf8")));
    rows = rows.filter((r) => r.kind !== "revision");
    const p = py(fields, rows, filters);
    const t = tsVerdicts(fields, rows, filters);
    rows.forEach((r, i) => {
      assert.deepEqual(t[i].map(toPy), p[i], `${pr.id} ${r.id}`);
      const pb = p[i].includes("no") ? "no" : p[i].includes("disagree") ? "disagree" : p[i].includes("unknown") ? "unknown" : "match";
      const tb = rowStatus(t[i]);
      assert.equal(tb === "conflicted" ? "disagree" : tb, pb, `${pr.id} ${r.id} bucket`);
      cells += filters.length; buckets++;
    });
  }
  assert.ok(buckets > 1000, `only ${buckets} rows compared`);
  console.log(`verdict parity: ${cells} row x filter cells, ${buckets} row buckets, ${presets.length} presets`);
});
