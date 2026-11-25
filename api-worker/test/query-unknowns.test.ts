// /v1/query explicit-unknown semantics on the real pack (api-worker/pack), in Node with ASSETS served from disk.
//   cd api-worker && node --test test/query-unknowns.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { runQuery } from "../src/data.ts";
import { parseFilters } from "../src/filters.ts";
import { rowStatus, verdict } from "../src/verdict.ts";

const PACK = join(dirname(fileURLToPath(import.meta.url)), "..", "pack");
const skip = existsSync(join(PACK, "meta", "manifest.json")) ? false : "pack not built";
const env = { ASSETS: { fetch: async (r: Request) => {
  const f = join(PACK, new URL(r.url).pathname.slice(1));
  return existsSync(f) ? new Response(readFileSync(f)) : new Response(null, { status: 404 });
} } } as any;
const q = (filters: string, include?: "maybe", limit = 25) => runQuery(env, { category: "laptops", filters: parseFilters(filters).filters, limit, offset: 0, include });

test("maybe counts are always reported, rows listed only with include=maybe", { skip }, async () => {
  const a = await q("mem.soldered=socketed,mem.max>=32");
  const b = await q("mem.soldered=socketed,mem.max>=32", "maybe");
  assert.equal(a.include, "matches");
  assert.ok(a.maybe.total > 0, "laptops has unknown mem.soldered rows");
  assert.equal(a.maybe.total, a.maybe.unknown + a.maybe.conflicted + a.maybe.disagree);
  assert.deepEqual(a.maybe, b.maybe);
  assert.ok(a.results.every((r) => r.status === "match"));
  const all = await q("mem.soldered=socketed,mem.max>=32", "maybe", 25);
  assert.equal(b.total, a.total);
  // with include=maybe the matches come first, then maybe rows with their per-filter status
  const tail = await runQuery(env, { category: "laptops", filters: parseFilters("mem.soldered=socketed,mem.max>=32").filters, limit: 25, offset: a.total, include: "maybe" });
  assert.ok(tail.results.length > 0 && tail.results.every((r) => r.status === "maybe" && r.maybe_reason));
  assert.ok(tail.results.some((r) => Object.values(r.filter_status).includes("unknown")));
  assert.ok(all.count <= 25);
});

test("buckets partition the category (match + maybe + ruled out = rows)", { skip }, async () => {
  const fs = parseFilters("mem.soldered=socketed,mem.max>=32").filters;
  const rows = JSON.parse(readFileSync(join(PACK, "index", "laptops.json"), "utf8"));
  const schema = JSON.parse(readFileSync(join(PACK, "schema", "laptops.json"), "utf8"));
  const fm = new Map(schema.fields.map((f: any) => [f.key, f]));
  const n = { match: 0, maybe: 0, no: 0 };
  for (const r of rows) { const s = rowStatus(fs.map((f) => verdict(r, f, fm.get(f.key) as any))); n[s === "match" ? "match" : s === "no" ? "no" : "maybe"]++; }
  const a = await q("mem.soldered=socketed,mem.max>=32");
  assert.equal(a.total, n.match); assert.equal(a.maybe.total, n.maybe);
  assert.equal(n.match + n.maybe + n.no, rows.length);
});

test("results list unknown core keys explicitly and never a value for them", { skip }, async () => {
  const man = JSON.parse(readFileSync(join(PACK, "meta", "manifest.json"), "utf8"));
  const core = man.categories.find((c: any) => c.id === "laptops").core;
  assert.ok(core.length > 0);
  const a = await q("brand=Lenovo");
  for (const r of a.results) for (const k of Object.keys(r.unknown_core)) { assert.ok(core.includes(k)); assert.ok(!(k in r.specs)); }
  assert.ok(a.results.some((r) => Object.keys(r.unknown_core).length > 0));
});
