// Default config (PAID_ENABLED unset/false): paid routes are 503 "coming soon", discovery omits them.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, ".."), BASE = "http://127.0.0.1:8796";
let wd;
before(async () => {
  wd = spawn("npx", ["wrangler", "dev", "--local", "--port", "8796", "--var", "PAY_TO:0x00000000000000000000000000000000000000B2"], { cwd: root, stdio: "pipe", detached: true, env: { ...process.env, WRANGLER_SEND_METRICS: "false" } });
  for (let i = 0; i < 60; i++) { try { if ((await fetch(BASE + "/")).ok) return; } catch {} await new Promise((r) => setTimeout(r, 500)); }
  throw new Error("wrangler dev did not start");
});
after(() => wd && process.kill(-wd.pid, "SIGKILL"));
test("paid disabled by default", async () => {
  for (const p of ["/v1/query?category=x", "/v1/changes?since=2026-01-01", "/v1/match?title=x", "/v1/bulk/x.jsonl.gz"]) {
    const r = await fetch(BASE + p); assert.equal(r.status, 503); assert.equal((await r.json()).error, "coming_soon");
  }
  const o = await (await fetch(BASE + "/openapi.json")).json();
  assert.equal(o.paths["/v1/query"], undefined); assert.ok(o.paths["/v1/{path}"]);
  assert.equal((await fetch(BASE + "/v1/x.json", { redirect: "manual" })).status, 302);
});
