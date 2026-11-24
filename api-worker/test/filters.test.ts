import { test } from "node:test";
import assert from "node:assert/strict";
import { parseFilters, matches } from "../src/filters.ts";

const row = { id: "a", brand: "ASUS", name: "Zenbook 14", v: { "cpu.cores": 8, "mem.size": 16, "ports": ["usb-c", "hdmi"] } };
test("parse", () => {
  assert.equal(parseFilters("cpu.cores>=8,brand=asus,name~zen").filters.length, 3);
  assert.ok(parseFilters("junk").error);
});
test("match", () => {
  const m = (s: string) => matches(row, parseFilters(s).filters);
  assert.ok(m("cpu.cores>=8")); assert.ok(!m("cpu.cores>8")); assert.ok(m("brand=asus")); assert.ok(m("ports=hdmi"));
  assert.ok(!m("gpu.vram>=4")); assert.ok(!m("gpu.vram!=4")); assert.ok(m("name~book"));
});
