// Unit tests: D3.6 bounds at limit and limit+1, redaction, client keys, UA families, metrics field order, naming/price hygiene.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { BOUNDS, PRICES } from "../src/config.ts";
import { strictParams, validateChanges, validateMatch, validateQuery } from "../src/bounds.ts";
import { HttpError, type PackManifest } from "../src/data.ts";
import { normClientName, redactMiss, toDataPoint, uaFamily } from "../src/metrics.ts";
import { clientKey, nextOneAm as nextOneAmFor, secondsToReset } from "../src/keys.ts";

const man = { release: "20261124T000000Z-aaaa", tier: "free", built_at: null, categories: [{ id: "laptops", count: 1, keys: Array.from({ length: 50 }, (_, i) => `k.${i}`), bulk: "", bulk_bytes: 0 }] } as PackManifest;
const sp = (o: Record<string, string>) => new URLSearchParams(o);
const rejects = (f: () => unknown, status = 400) => assert.throws(f, (e: unknown) => e instanceof HttpError && e.status === status);
const q = (o: Record<string, string>) => validateQuery(man, sp({ category: "laptops", ...o }));

test("query bounds: at limit ok, limit+1 rejected", () => {
  q({ q: "a".repeat(BOUNDS.q) }); rejects(() => q({ q: "a".repeat(BOUNDS.q + 1) }));
  q({ limit: String(BOUNDS.limitMax) }); rejects(() => q({ limit: String(BOUNDS.limitMax + 1) })); rejects(() => q({ limit: "0" })); rejects(() => q({ limit: "5x" }));
  assert.equal(q({}).params.limit, BOUNDS.limitDefault);
  q({ offset: String(BOUNDS.offsetMax) }); rejects(() => q({ offset: String(BOUNDS.offsetMax + 1) }));
  const clauses = (n: number) => Array.from({ length: n }, (_, i) => `k.${i}>=1`).join(",");
  q({ filters: clauses(BOUNDS.filterClauses) }); rejects(() => q({ filters: clauses(BOUNDS.filterClauses + 1) }));
  q({ filters: `k.1=${"v".repeat(BOUNDS.filterValue)}` }); rejects(() => q({ filters: `k.1=${"v".repeat(BOUNDS.filterValue + 1)}` }));
  const eight = Array.from({ length: 8 }, (_, i) => `k.${i}=${"v".repeat(59)}`).join(",") + "v"; // 8 clauses, exactly 512 chars
  assert.equal(eight.length, BOUNDS.filtersChars);
  q({ filters: eight }); rejects(() => q({ filters: eight + "v" }));
  const fields = (n: number) => Array.from({ length: n }, (_, i) => `k.${i}`).join(",");
  q({ fields: fields(BOUNDS.fields) }); rejects(() => q({ fields: fields(BOUNDS.fields + 1) }));
  rejects(() => q({ filters: "nope.key=1" })); rejects(() => q({ fields: "nope.key" }));
  rejects(() => validateQuery(man, sp({ category: "tvs" }))); rejects(() => validateQuery(man, sp({})));
  rejects(() => q({ cachebust: "1" })); rejects(() => strictParams(new URLSearchParams("a=1&a=2"), ["a"]));
});

test("canonical key: sorted, validated params only", () => {
  assert.equal(q({ filters: "k.2=b,k.1=a", limit: "10" }).canonical, q({ limit: "10", filters: "k.1=a,k.2=b" }).canonical);
  assert.deepEqual(q({ filters: "k.2=b,k.1>=3" }).filterKeys, ["k.1", "k.2"]);
});

test("match and changes bounds", () => {
  validateMatch(man, sp({ title: "t".repeat(BOUNDS.title) })); rejects(() => validateMatch(man, sp({ title: "t".repeat(BOUNDS.title + 1) })));
  rejects(() => validateMatch(man, sp({ title: "" })));
  const now = Date.UTC(2026, 10, 24);
  const ch = (o: Record<string, string>) => validateChanges(man, sp(o), ["20261101T000000Z-x"], now);
  ch({ since: "20261101T000000Z-x" }); ch({ since: "2026-08-26" }); rejects(() => ch({ since: "2026-08-25" })); // 90 days
  rejects(() => ch({ since: "garbage" })); rejects(() => ch({}));
  ch({ since: "2026-11-01", limit: String(BOUNDS.changesLimitMax) }); rejects(() => ch({ since: "2026-11-01", limit: String(BOUNDS.changesLimitMax + 1) }));
});

test("miss redaction: emails, URLs, phone-like runs, length", () => {
  assert.equal(redactMiss("Anker 735 Charger"), "anker 735 charger");
  assert.equal(redactMiss("mail me at Bob.Smith+x@Example.co.uk please"), "mail me at · please");
  assert.equal(redactMiss("see https://evil.example/a?b=c and www.x.org/p"), "see · and ·");
  assert.equal(redactMiss("spam.example.com/promo"), "·");
  assert.equal(redactMiss("call (555) 123-4567 now"), "call · now");
  assert.equal(redactMiss("call +1 555 123 4567"), "call ·");
  assert.equal(redactMiss("ssd 2tb 7450 mb/s"), "ssd 2tb 7450 mb/s", "short numbers stay");
  assert.equal(redactMiss("model 21SK0092US"), "model 21sk0092us", "model numbers stay");
  assert.equal(redactMiss("1234567890123"), "·", "long bare digit runs");
  assert.equal(redactMiss("x".repeat(200)).length, 80);
  assert.equal([...redactMiss("é".repeat(100))].length, 80);
});

test("client key: IPv4 /32, IPv6 /64", () => {
  assert.equal(clientKey("203.0.113.9"), "203.0.113.9");
  assert.equal(clientKey("2001:db8:aa:bb:1:2:3:4"), clientKey("2001:db8:aa:bb:ffff::1"));
  assert.equal(clientKey("2001:0db8:00aa:00bb::1"), "2001:db8:aa:bb::/64");
  assert.notEqual(clientKey("2001:db8:aa:bc::1"), clientKey("2001:db8:aa:bb::1"));
  assert.equal(clientKey("::ffff:198.51.100.2"), "198.51.100.2");
  assert.equal(clientKey(""), "none"); assert.equal(clientKey("junk"), "invalid");
});

test("day reset and salt deletion times", () => {
  assert.equal(secondsToReset(Date.UTC(2026, 10, 24, 23, 59, 0)), 60);
  assert.equal(nextOneAmFor(Date.UTC(2026, 10, 24, 0, 30)), Date.UTC(2026, 10, 24, 1));
  assert.equal(nextOneAmFor(Date.UTC(2026, 10, 24, 1, 0)), Date.UTC(2026, 10, 25, 1));
});

test("UA family and MCP client names", () => {
  assert.equal(uaFamily("curl/8.5.0"), "curl-like"); assert.equal(uaFamily("python-requests/2.31"), "python");
  assert.equal(uaFamily("Mozilla/5.0 (X11; Linux) Chrome/120"), "browser"); assert.equal(uaFamily("Mozilla/5.0 (compatible; GPTBot/1.1)"), "bot:openai");
  assert.equal(uaFamily("node"), "node"); assert.equal(uaFamily("anything", "/mcp"), "mcp"); assert.equal(uaFamily(""), "other");
  assert.equal(normClientName("Claude Desktop"), "claude-desktop"); assert.equal(normClientName("x".repeat(40)), "other"); assert.equal(normClientName(3), "other");
});

test("metrics point: contract field order", () => {
  const dp = toDataPoint({ kind: "api", route: "/v1/query", category: "laptops", status: 200, outcome: "ok_results", ua: "curl-like", mode: "off", traffic: "real",
    release: "r", mcpClient: "", cid: "0123456789abcdef", detail: "cpu.cores", results: 3, bytes: 100, wallMs: 4, cacheHit: true });
  assert.deepEqual(dp, { indexes: ["api"], blobs: ["/v1/query", "laptops", "200", "ok_results", "curl-like", "off", "real", "r", "", "0123456789abcdef", "cpu.cores"], doubles: [3, 100, 4, 1] });
});

// ---------------------------------------------------------------- repo hygiene (brief item 1)
const ROOT = resolve(import.meta.dirname, "..", "..");
const SKIP = new Set(["node_modules", ".git", "raw", "state", "pack", "r2-data", ".wrangler", "releases", "api", "data", "team", "reviews", "product", "__pycache__"]);
function* files(dir: string): Generator<string> {
  for (const n of readdirSync(dir)) {
    if (SKIP.has(n)) continue;
    const p = join(dir, n);
    const st = statSync(p);
    if (st.isDirectory()) yield* files(p); else if (/\.(ts|mjs|js|jsonc|json|md|py|sh|sql|example)$/.test(n) && st.size < 2_000_000) yield p;
  }
}
test("no legacy paid-mode flag anywhere in code/config/docs; every price string in api-worker is a PRICES value", () => {
  const OLD = "PAID" + "_ENABLED", OLDFN = "paid" + "Enabled(";
  const hits: string[] = [];
  for (const f of files(ROOT)) { const t = readFileSync(f, "utf8"); if (t.includes(OLD) || t.includes(OLDFN)) hits.push(f); }
  assert.deepEqual(hits, []);
  const allowed = new Set(Object.values(PRICES));
  const bad: string[] = [];
  const aw = resolve(import.meta.dirname, "..");
  for (const f of [...files(join(aw, "src")), ...files(join(aw, "scripts")), join(aw, "README.md"), join(aw, "wrangler.jsonc")]) {
    for (const m of readFileSync(f, "utf8").matchAll(/\$\d+\.\d{2,3}\b/g)) if (!allowed.has(m[0] as never)) bad.push(`${f}: ${m[0]}`);
  }
  assert.deepEqual(bad, []);
});

test("README route table matches test/route-matrix.json", () => {
  const readme = readFileSync(resolve(import.meta.dirname, "../README.md"), "utf8");
  const start = readme.indexOf("<!-- route-table:start -->"), end = readme.indexOf("<!-- route-table:end -->");
  assert.ok(start > 0 && end > start, "README has the generated route table markers");
  const gen = execTable();
  assert.equal(readme.slice(start, end + "<!-- route-table:end -->".length), gen, "run: node scripts/route-table.mjs --write");
});
import { routeTable as execTable } from "../scripts/route-table.mjs";
