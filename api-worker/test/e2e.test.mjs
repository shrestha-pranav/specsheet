// End-to-end: real `wrangler dev` (local workerd, simulated R2) + mock facilitator + real x402 client signing.
// run: npm test   (no accounts, no network beyond localhost; throwaway key generated in-process)
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { gzipSync, gunzipSync } from "node:zlib";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { Miniflare } from "miniflare";
import { x402Client } from "@x402/core/client";
import { ExactEvmScheme } from "@x402/evm";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { startMockFacilitator } from "./mock-facilitator.mjs";

const root = resolve(import.meta.dirname, "..");
const PORT = 8797, FPORT = 8798, BASE = `http://127.0.0.1:${PORT}`;
const TEST_PAY_TO = "0x00000000000000000000000000000000000000B2"; // test-only placeholder passed via --var
let wd, fac, state;

before(async () => {
  state = mkdtempSync(join(tmpdir(), "specsheet-r2-"));
  const mf = new Miniflare({ modules: true, script: "export default{fetch(){return new Response('')}}", compatibilityDate: "2026-08-01", r2Buckets: { DATA: "specsheet-data" }, r2Persist: join(state, "v3/r2") });
  const b = await mf.getR2Bucket("DATA");
  const put = (k, v) => b.put(k, v);
  const rec = { id: "w-1", category: "widgets", sources: [{ id: "s1", url: "https://example.com/w1", label: "Maker", tier: "manufacturer" }],
    specs: { "power.w": { value: 65, unit: "W", status: "known", sources: ["s1"], kind: "official" }, "port.count": { value: 2, status: "unknown", sources: [] } } };
  const xx = createHash("sha1").update("w-1").digest("hex").slice(0, 2);
  await put("meta/manifest.json", JSON.stringify({ release: "20261124T000000Z-aaaa", built_at: "2026-11-24T00:00:00Z", categories: [{ id: "widgets", count: 2, legacy: false, bulk: "bulk/widgets.jsonl.gz", bulk_bytes: 1 }] }));
  await put("index/widgets.json", JSON.stringify([
    { id: "w-1", kind: "model", brand: "Acme", name: "Widget One", variant_label: null, ids: ["mfr_model:W1"], lifecycle: "current", v: { "power.w": 65 } },
    { id: "w-2", kind: "model", brand: "Acme", name: "Widget Two", variant_label: null, ids: [], lifecycle: "current", v: { "power.w": 30 } }]));
  await put(`records/widgets/${xx}.json`, JSON.stringify({ "w-1": rec }));
  await put("bulk/widgets.jsonl.gz", gzipSync(JSON.stringify(rec) + "\n"));
  await put("changes/index.json", JSON.stringify([
    { release: "20261123T000000Z-0000", created_at: "2026-11-23T00:00:00Z", baseline: true, counts: {} },
    { release: "20261124T000000Z-aaaa", created_at: "2026-11-24T00:00:00Z", baseline: false, counts: { widgets: { added: 1, removed: 0, changed: 1 } } }]));
  await put("changes/20261124T000000Z-aaaa.json", JSON.stringify({ release: "20261124T000000Z-aaaa", categories: { widgets: { added: ["w-2"], removed: [], changed: [{ id: "w-1", fields: { "power.w": [60, 65] } }] } } }));
  await mf.dispose();
  fac = await startMockFacilitator(FPORT);
  wd = spawn("npx", ["wrangler", "dev", "--local", "--port", String(PORT), "--persist-to", state, "--var", "PAID_ENABLED:true", "--var", `PAY_TO:${TEST_PAY_TO}`, "--var", `FACILITATOR_URL:http://127.0.0.1:${FPORT}`, "--var", "STATIC_ORIGIN:https://static.example"], { cwd: root, stdio: "pipe", detached: true, env: { ...process.env, WRANGLER_SEND_METRICS: "false" } });
  for (let i = 0; i < 60; i++) { try { if ((await fetch(BASE + "/")).ok) return; } catch {} await new Promise((r) => setTimeout(r, 500)); }
  throw new Error("wrangler dev did not start");
});
after(() => { wd && process.kill(-wd.pid, "SIGKILL"); fac?.server.close(); });

const client = () => { const acct = privateKeyToAccount(generatePrivateKey()); return new x402Client().register("eip155:84532", new ExactEvmScheme(acct)); };
const reqsOf = (r) => JSON.parse(Buffer.from(r.headers.get("payment-required"), "base64").toString());
async function paid(path) {
  const r1 = await fetch(BASE + path);
  assert.equal(r1.status, 402);
  const payload = await client().createPaymentPayload(reqsOf(r1));
  return fetch(BASE + path, { headers: { "PAYMENT-SIGNATURE": Buffer.from(JSON.stringify(payload)).toString("base64") } });
}

test("free: redirects to the static dataset, preview/ is not exposed", async () => {
  const r = await fetch(BASE + "/v1/laptops/facets.json", { redirect: "manual" });
  assert.equal(r.status, 302); assert.equal(r.headers.get("location"), "https://static.example/api/v1/laptops/facets.json");
  assert.equal((await fetch(BASE + "/v1/preview/x.json", { redirect: "manual" })).status, 404);
});

test("discovery: openapi 3.1, llms.txt, mcp tools/list", async () => {
  const o = await (await fetch(BASE + "/openapi.json")).json();
  assert.equal(o.openapi, "3.1.0"); assert.ok(o.paths["/v1/query"]);
  assert.match(await (await fetch(BASE + "/llms.txt")).text(), /Base Sepolia/);
  const t = await (await fetch(BASE + "/mcp", { method: "POST", body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }) })).json();
  assert.deepEqual(t.result.tools.map((x) => x.name), ["query_specs", "match_product"]);
});

for (const [path, amount] of [["/v1/query?category=widgets", "1000"], ["/v1/changes?since=2026-01-01", "2000"], ["/v1/match?title=x", "2000"], ["/v1/bulk/widgets.jsonl.gz", "50000"]]) {
  test(`paid ${path.split("?")[0]}: 402 with correct x402 requirements`, async () => {
    const r = await fetch(BASE + path);
    assert.equal(r.status, 402);
    const q = reqsOf(r);
    assert.equal(q.x402Version, 2);
    const a = q.accepts[0];
    assert.equal(a.scheme, "exact"); assert.equal(a.network, "eip155:84532"); assert.equal(a.amount, amount);
    assert.equal(a.payTo, TEST_PAY_TO); assert.equal(a.asset.toLowerCase(), "0x036cbd53842c5426634e7929541ec2318f3dcf7e");
  });
}

test("paid query: filters + provenance (mock facilitator, signed testnet payload)", async () => {
  const r = await paid("/v1/query?category=widgets&filters=" + encodeURIComponent("power.w>=60"));
  assert.equal(r.status, 200);
  assert.ok(r.headers.get("payment-response"));
  const j = await r.json();
  assert.equal(j.total, 1); assert.equal(j.results[0].id, "w-1");
  assert.equal(j.results[0].specs["power.w"].sources[0].url, "https://example.com/w1");
  assert.equal(j.results[0].specs["port.count"], undefined); // unknown values are not served as facts
});

test("paid changes + bulk", async () => {
  const c = await (await paid("/v1/changes?since=20261123T000000Z-0000")).json();
  assert.deepEqual(c.categories.widgets.added, ["w-2"]); assert.deepEqual(c.categories.widgets.changed[0].fields["power.w"], [60, 65]);
  const b = await paid("/v1/bulk/widgets.jsonl.gz");
  assert.equal(b.status, 200); assert.equal(JSON.parse(gunzipSync(Buffer.from(await b.arrayBuffer())).toString().trim()).id, "w-1");
});

test("errors are not charged (400 / 501 never settle)", async () => {
  const before = fac.calls.settle;
  assert.equal((await paid("/v1/query?category=widgets&filters=garbage")).status, 400);
  assert.equal((await paid("/v1/match?title=anker 65w")).status, 501);
  assert.equal(fac.calls.settle, before);
});

test("mcp: unpaid tools/call returns x402 requirements; paid call returns data", async () => {
  const call = (meta) => fetch(BASE + "/mcp", { method: "POST", body: JSON.stringify({ jsonrpc: "2.0", id: 7, method: "tools/call", params: { name: "query_specs", arguments: { category: "widgets", filters: "power.w>=60" }, ...(meta && { _meta: meta }) } }) }).then((r) => r.json());
  const u = await call();
  assert.equal(u.result.isError, true); const q = u.result.structuredContent; assert.equal(q.accepts[0].amount, "1000");
  const payload = await client().createPaymentPayload(q);
  const p = await call({ "x402/payment": payload });
  assert.equal(p.result.isError, false); assert.equal(p.result.structuredContent.results[0].id, "w-1");
  assert.ok(p.result._meta["x402/payment-response"]);
});
