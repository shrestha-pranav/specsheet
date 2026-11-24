// Parity: src/match.ts (on the pack catalogue, api-worker/pack/match/catalogue.json) must return exactly what scripts/match.py returns.
// Python runs ONCE over every title. It reports two results per title: `full` (docs/api/v1, what release.sh tests) and `pack` (the same
// Catalogue with products restricted to the ids in the pack catalogue, which is what the Worker sees). TS must equal `pack` for every
// title; any title where `full` != `pack` is a difference caused SOLELY by the pack restriction and is listed, not hidden.
//   cd api-worker && node --test test/match-parity.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";
import { Matcher, loadMatcher, tokens, cleanTitle, type CatalogueDoc, type MatchCandidate } from "../src/match.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const CATALOGUE = join(HERE, "..", "pack", "match", "catalogue.json");
const API = join(ROOT, "docs", "api", "v1");
const FIXTURES = ["match_titles.jsonl", "match_titles_heldout.jsonl"];
const skip = !existsSync(CATALOGUE) ? "pack/match/catalogue.json not built" : !existsSync(join(API, "categories.json")) ? "docs/api/v1 not built" : false;

interface Case { title: string; category?: string; expect?: string | null; fixture?: string }

function cases(): Case[] {
  const out: Case[] = [];
  for (const f of FIXTURES) {
    for (const ln of readFileSync(join(ROOT, "tests", "fixtures", f), "utf8").split("\n")) {
      if (!ln.trim()) continue;
      const x = JSON.parse(ln);
      out.push({ title: x.title, expect: x.expect ?? null, fixture: f });
    }
  }
  // tests/test_match.py lookalikes
  for (const t of ["Anker 735 Charger (Nano II 65W)", "Anker 737 Charger (GaNPrime 120W)", "Anker Nano II 65W Charger", "Anker 711 Charger (Nano II 30W)",
    "Anker 511 Charger (Nano 3) 30W", "Belkin BoostCharge Pro 108W WCH010 GaN charger $49 at Amazon", "Anker 30W Nano USB-C Charger, 2 Pack",
    "Anker 735 Charger (Nano II 65W) GaN 3-port $25.99 at Amazon"]) out.push({ title: t });
  out.push({ title: "Belkin BoostCharge Pro 108W WCH010", category: "tvs" });
  // adversarial
  out.push(
    { title: "" }, { title: "$19.99" }, { title: "  $1,299.00 40% off save $300 " },
    { title: ("Anker 735 Charger (Nano II 65W) GaN 3-port fast charger for iPhone MacBook iPad Galaxy, foldable plug, compact travel " +
      "adapter with PowerIQ 3.0, black, lowest price deal, free shipping, prime members").slice(0, 200) },
    { title: "Anker 735 Charger (Nano II 65W)", category: "chargers" }, { title: "Belkin BoostCharge Pro 108W WCH010", category: "chargers" },
    { title: "Anker 511 Charger (Nano 3) 30W", category: "power-banks" },
    { title: "Samsung 990 PRO 2TB NVMe SSD – 40% off at Best Buy\n" }, { title: "Anker Nano II 65W charger at Amazon\nsecond line" },
    { title: "Anker 735 Charger (Nano II 65W)" }, { title: "Anker ٧٣٥ Charger (Nano II ٦٥W)" }, { title: "Anker 735 Charger (Nano Ⅱ 65W)" },
    { title: "2-Pack Anker 511 Charger (Nano 3) 30W" }, { title: "Anker 10K power bank" }, { title: "Anker 20K mAh portable charger 22.5W" },
    { title: "UGREEN 15202 charger" }, { title: "15202" }, { title: "Samsung 65\" Class QLED 4K Q80C" }, { title: "LG 27GP850-B 27″ monitor" },
    { title: "ASUS RT-AX88U Pro router" }, { title: "TP-Link Archer AX55 Pro" }, { title: "Ankér Charger 735" }, { title: "ANKER A2667" },
  );
  return out;
}

const PY = String.raw`
import copy, json, sys
sys.path.insert(0, 'scripts')
import match as M
req = json.load(sys.stdin)
full = M.Catalogue(req["api"])
pack = copy.copy(full)
keep = set(req["pack_ids"])
pack.products = {i: p for i, p in full.products.items() if i in keep}
cur = [full]
M.catalogue = lambda api=None: cur[0]
def run(c):
    d = {}
    r = M.match(c["title"], c.get("category"), None, d)
    return {"cands": r, "ambiguous": "ambiguous" in d, "brands": d.get("brands"), "title_category": d.get("title_category")}
out = []
for c in req["cases"]:
    cur[0] = full; f = run(c)
    cur[0] = pack; p = run(c)
    out.append({"full": f, "pack": p, "tokens": M.tokens(M.clean_title(c["title"]))})
print(json.dumps(out, default=sorted))
`;

interface PyRes { cands: MatchCandidate[]; ambiguous: boolean; brands: string[]; title_category: string | null }

const view = (r: { cands: MatchCandidate[]; ambiguous: boolean }) =>
  ({ ids: r.cands.map((c) => c.id), basis: r.cands.map((c) => c.basis), confidence: r.cands.map((c) => c.confidence),
     evidence: r.cands.map((c) => c.evidence), ambiguous: r.ambiguous });

const pct = (xs: number[], q: number) => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; };

test("match.ts == scripts/match.py", { skip }, (t) => {
  const text = readFileSync(CATALOGUE, "utf8");
  let t0 = performance.now();
  const doc = JSON.parse(text) as CatalogueDoc;
  const parseMs = performance.now() - t0;
  t0 = performance.now();
  const m = new Matcher(doc);
  const ctorMs = performance.now() - t0;
  assert.equal(loadMatcher(doc), loadMatcher(doc));

  const cs = cases();
  const py = spawnSync("python3", ["-I", "-c", PY], {
    cwd: ROOT, encoding: "utf8", maxBuffer: 64 << 20,
    input: JSON.stringify({ api: API, pack_ids: doc.products.map((p) => p[0]), cases: cs.map(({ title, category }) => ({ title, category })) }),
  });
  assert.equal(py.status, 0, py.stderr);
  const pr = JSON.parse(py.stdout) as { full: PyRes; pack: PyRes; tokens: string[] }[];
  assert.equal(pr.length, cs.length);

  const restricted: string[] = [];
  let same = 0;
  const ts: MatchCandidate[][] = [];
  cs.forEach((c, k) => {
    const d: Record<string, unknown> = {};
    const r = m.match(c.title, c.category, d);
    ts.push(r);
    const mine = { cands: r, ambiguous: "ambiguous" in d };
    const label = JSON.stringify(c);
    assert.deepEqual(view(mine), view(pr[k].pack), `result differs: ${label}`);
    assert.deepEqual([d.brands, d.title_category], [pr[k].pack.brands, pr[k].pack.title_category], `diagnostics differ: ${label}`);
    assert.deepEqual(r.map((x) => [x.category, x.brand, x.name]), pr[k].pack.cands.map((x) => [x.category, x.brand, x.name]), label);
    if (JSON.stringify(view(pr[k].full)) === JSON.stringify(view(pr[k].pack))) same++;
    else restricted.push(`${label}: python(docs) ${JSON.stringify(view(pr[k].full))} vs python(pack) ${JSON.stringify(view(pr[k].pack))}`);
  });
  t.diagnostic(`parity: ${cs.length}/${cs.length} titles identical to match.py on the pack catalogue; ${same}/${cs.length} also identical to match.py on docs/api/v1`);
  for (const r of restricted) t.diagnostic(`differs ONLY because the pack omits products: ${r}`);

  // tokens(): also checked directly (the matcher-level parity above would hide a tokenisation drift that happens not to change the result)
  cs.forEach((c, k) => assert.deepEqual(tokens(cleanTitle(c.title)), pr[k].tokens, `tokens differ: ${JSON.stringify(c.title)}`));

  // fixture precision / recall (tests/test_match.py thresholds), scored on the TS results
  for (const [f, minP, minR, minN] of [["match_titles.jsonl", 0.97, 0.85, 60], ["match_titles_heldout.jsonl", 0.9, 0.8, 0]] as [string, number, number, number][]) {
    let tp = 0, fp = 0, fn = 0, tn = 0;
    cs.forEach((c, k) => {
      if (c.fixture !== f) return;
      const got = ts[k][0]?.id ?? null;
      if (c.expect && got === c.expect) tp++; else if (got) fp++; else if (c.expect) fn++; else tn++;
    });
    const precision = tp / Math.max(1, tp + fp), recall = tp / Math.max(1, tp + fn);
    t.diagnostic(`${f}: tp=${tp} fp=${fp} fn=${fn} tn=${tn} precision=${precision.toFixed(3)} recall=${recall.toFixed(3)}`);
    assert.ok(tp + fp + fn + tn >= minN, `${f}: ${tp + fp + fn + tn} titles`);
    assert.ok(precision >= minP, `${f} precision ${precision}`);
    assert.ok(recall >= minR, `${f} recall ${recall}`);
  }

  // per-call cost on a warm matcher, fixture titles
  const fx = cs.filter((c) => c.fixture);
  for (let i = 0; i < 3; i++) for (const c of fx) m.match(c.title);
  const times: number[] = [];
  for (let i = 0; i < 20; i++) for (const c of fx) { const s = performance.now(); m.match(c.title); times.push(performance.now() - s); }
  t.diagnostic(`catalogue JSON.parse ${parseMs.toFixed(1)} ms (${(text.length / 1e6).toFixed(2)} MB); new Matcher ${ctorMs.toFixed(1)} ms; ` +
    `match() median ${pct(times, 0.5).toFixed(3)} ms, p95 ${pct(times, 0.95).toFixed(3)} ms, max ${Math.max(...times).toFixed(3)} ms over ${times.length} calls`);
  assert.ok(pct(times, 0.5) < 2, "median per-call time should stay well under 2 ms");
});
