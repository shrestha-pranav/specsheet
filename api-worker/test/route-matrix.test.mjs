// E2E: every row of test/route-matrix.json in every mode, each mode on its own `wrangler dev --local` (workerd, real Durable Objects
// with SQLite, rate-limit binding, ASSETS = the built pack). Off mode runs against a recording mock facilitator and must make ZERO calls
// and return no 402 even with payment headers. Also: no-PII inspection of every metrics point, and the x402 paid flow in on mode.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { MATRIX, runMode, call } from "./matrix-runner.mjs";
import { startMockFacilitator } from "./mock-facilitator.mjs";
import { startWorker } from "./wrangler-dev.mjs";
import { x402Client } from "@x402/core/client";
import { ExactEvmScheme } from "@x402/evm";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

const root = resolve(import.meta.dirname, "..");
const HAVE_PACK = existsSync(resolve(root, "pack/meta/manifest.json"));
const SITE = "https://site.example";
const PAY_TO = "0x00000000000000000000000000000000000000B2";
const DAILY = 3, ALLOW = 2;
const common = ["SITE_ORIGIN:" + SITE, "METRICS_ECHO:on", "QUOTA_DAILY:" + DAILY];
const MODES = {
  "off": { port: 8811, fport: 8821, vars: [...common, "PAY_TO:" + PAY_TO] },
  "on": { port: 8812, fport: 8822, vars: [...common, "PAYMENTS:on", "PAY_TO:" + PAY_TO, "ALLOWANCE_QUERY:" + ALLOW, "ALLOWANCE_MATCH:" + ALLOW] },
  "on-bad": { port: 8813, fport: 8823, vars: [...common, "PAYMENTS:on"] },
  "preview-off": { port: 8814, fport: 8824, vars: [...common, "PREVIEW:off"] },
  "breaker": { port: 8815, fport: 8825, vars: [...common, "BREAKER_DAILY:2"] },
};
const W = {}, F = {}, seen = {};

before(async () => {
  if (!HAVE_PACK) return;
  await Promise.all(Object.entries(MODES).map(async ([m, c]) => {
    F[m] = await startMockFacilitator(c.fport);
    W[m] = await startWorker(c.port, [...c.vars, `FACILITATOR_URL:http://127.0.0.1:${c.fport}`]);
  }));
  // trip the breaker instance (BREAKER_DAILY=2) with data-route requests from several client keys
  const b = `http://127.0.0.1:${MODES.breaker.port}`;
  for (let i = 0; i < 4; i++) await fetch(`${b}/v1/query?category=chargers&limit=1`, { headers: { "cf-connecting-ip": `192.0.2.${i}` } });
});
after(() => { for (const w of Object.values(W)) w.stop(); for (const f of Object.values(F)) f.server.close(); });

for (const [i, mode] of MATRIX.modes.entries()) {
  test(`route matrix: ${mode}`, { skip: !HAVE_PACK && "pack not built" }, async () => {
    seen[mode] = [];
    const res = await runMode(`http://127.0.0.1:${MODES[mode].port}`, mode, { site: SITE, spoofIp: true, ipBlock: 10 + i, daily: DAILY, allowance: ALLOW, seen: seen[mode] });
    const bad = res.filter((r) => !r.ok);
    assert.deepEqual(bad, [], JSON.stringify(bad, null, 1));
    assert.equal(res.length, MATRIX.rows.filter((r) => r.expect[mode]).length);
    if (mode === "off") {
      assert.deepEqual(F.off.calls, { verify: 0, settle: 0, supported: 0, other: 0 }, "PAYMENTS=off must never contact the facilitator");
      assert.ok(seen.off.every((s) => s.status !== 402));
    }
  });
}

test("the matrix covers every D3.5 route", () => {
  for (const r of MATRIX.rows) for (const m of Object.keys(r.expect)) assert.ok(MATRIX.modes.includes(m), `${r.id}: ${m}`);
  const covered = new Set(MATRIX.rows.map((r) => `${r.method} ${r.path}`));
  for (const k of ["GET /", "GET /health", "GET /openapi.json", "GET /llms.txt", "GET /robots.txt", "GET /v1/query", "GET /v1/changes", "GET /v1/match",
    "GET /v1/bulk/chargers.jsonl.gz", "GET /v1/bulk/all.jsonl.gz", "POST /mcp", "GET /mcp", "POST /v1/miss", "POST /v1/event"]) assert.ok(covered.has(k), k);
  for (const r of MATRIX.rows.filter((x) => ["query", "changes", "match", "bulk-category", "mcp-query", "health"].includes(x.id)))
    for (const m of MATRIX.modes) assert.ok(r.expect[m], `${r.id} lacks mode ${m}`);
});

test("no PII in any metrics point written during the off-mode matrix", { skip: !HAVE_PACK && "pack not built" }, () => {
  const pts = (seen.off ?? []).flatMap((s) => (s.headers["x-specsheet-points"] ? JSON.parse(Buffer.from(s.headers["x-specsheet-points"], "base64").toString()) : []));
  assert.ok(pts.length > 40, `points captured: ${pts.length}`);
  const blob = JSON.stringify(pts);
  for (const banned of ["198.51.", "198.52.", "192.0.2.", "specsheet-matrix/1", "brand=Anker", "=Anker", "Anker 735", "bob@example.com", "555-123-4567", "Matrix Test Client"])
    assert.ok(!blob.includes(banned), `a point contains ${banned}`);
  for (const p of pts) {
    assert.equal(p.indexes.length, 1); assert.equal(p.blobs.length, 11); assert.equal(p.doubles.length, 4);
    assert.ok(["api", "mcp", "beacon", "ops"].includes(p.indexes[0]));
    assert.ok(p.blobs[9] === "none" || /^[0-9a-f]{16}$/.test(p.blobs[9]), `cid ${p.blobs[9]}`);
    assert.equal(p.blobs[6], "test", "X-Specsheet-Test traffic is classed test");
    assert.match(p.blobs[4], /^(browser|mcp|curl-like|python|node|other|bot:[a-z]+)$/);
  }
  assert.ok(pts.some((p) => p.blobs[0] === "/v1/miss" && p.blobs[10] === "anker 999 charger · ·"), "miss text is redacted before writing");
  assert.ok(pts.some((p) => p.blobs[10] === "spec_unknown_shown:out.max_total_w"));
  assert.ok(pts.some((p) => p.blobs[8] === "matrix-test-client"));
  assert.ok(pts.some((p) => p.blobs[0] === "/v1/query" && p.blobs[10] === "brand"), "filter keys, not values");
});

test("on mode: x402 paid flow beyond the allowance (mock facilitator, signed testnet payload), REST and MCP", { skip: !HAVE_PACK && "pack not built" }, async () => {
  const base = `http://127.0.0.1:${MODES.on.port}`, ip = "203.0.113.77";
  const q = { method: "GET", path: "/v1/query", query: { category: "chargers", limit: "1" } };
  const ctx = { spoofIp: true, site: SITE, release: "" };
  for (let i = 0; i < ALLOW; i++) assert.equal((await call(base, q, ctx, ip)).r.status, 200);
  const r1 = await call(base, q, ctx, ip);
  assert.equal(r1.r.status, 402);
  const reqs = JSON.parse(Buffer.from(r1.r.headers.get("payment-required"), "base64").toString());
  assert.equal(reqs.accepts[0].amount, "2000"); // $0.002 = PRICES.query
  const client = new x402Client().register("eip155:84532", new ExactEvmScheme(privateKeyToAccount(generatePrivateKey())));
  const r2 = await call(base, { ...q, headers: { "PAYMENT-SIGNATURE": Buffer.from(JSON.stringify(await client.createPaymentPayload(reqs))).toString("base64") } }, ctx, ip);
  assert.equal(r2.r.status, 200); assert.ok(r2.r.headers.get("payment-response")); assert.equal(F.on.calls.settle, 1);
  const mcp = (meta) => call(base, { method: "POST", path: "/mcp", body: { jsonrpc: "2.0", id: 9, method: "tools/call", params: { name: "query_specs", arguments: { category: "chargers", limit: 1 }, ...(meta && { _meta: meta }) } } }, ctx, "203.0.113.79");
  for (let i = 0; i < ALLOW; i++) assert.equal((await mcp()).json.result.isError, false);
  const u = await mcp();
  assert.equal(u.json.result.isError, true); assert.equal(u.json.result.structuredContent.accepts[0].amount, "2000");
  const p = await mcp({ "x402/payment": await client.createPaymentPayload(u.json.result.structuredContent) });
  assert.equal(p.json.result.isError, false, JSON.stringify(p.json).slice(0, 300)); assert.ok(p.json.result._meta["x402/payment-response"]);
});
