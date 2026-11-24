"""Licensing gate (scripts/source_policy.py over data/source-policy.yaml): fixtures F1-F16 of team/briefs/pm-2026-11-24-licensing-gate.md.

An end-to-end fixture (throwaway SPECSHEET_ROOT, real scripts/import.py + v1_publish.publish + build.policy_outputs + build_r2.py for both
tiers) plus unit cases on the gate. Fixture policies: tests/fixtures/source-policy/.

  python3 -I tests/test_source_policy.py
"""
import gzip, json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
FX = CODE / "tests" / "fixtures" / "source-policy"
sys.path.insert(0, str(CODE / "scripts"))
import source_policy as SP  # noqa: E402

PROFILE = """
profile_format: specsheet.category-profile/1
category: widgets
version: 0.1.0
label: Widgets
identity: {levels: [family, model, revision, package], primary_key: manufacturer model number}
groups: [{id: general, label: General}]
index_rows: {substantive_keys: [gen.size, gen.kind, gen.color, gen.note], certification_keys: [cert.tier]}
specs:
  - {key: gen.size, label: Size, group: general, type: number, unit: in, tier: core, level: model, facet: {kind: range, bins: [20]}, sources: [x]}
  - {key: gen.kind, label: Kind, group: general, type: enum, enum: [alpha, beta], tier: core, level: model, facet: true, sources: [x]}
  - {key: gen.color, label: Colour, group: general, type: enum, enum: [teal, red], tier: core, level: model, facet: true, sources: [x]}
  - {key: gen.note, label: Note, group: general, type: text, tier: detail, level: model, sources: [x]}
  - {key: cert.tier, label: Certification tier, group: general, type: enum, enum: [gold, silver], tier: core, level: model, facet: true, sources: [x]}
"""
CATEGORY = "name: Widgets\ndescription: Fixture.\ncolumns: [gen.size, gen.kind, gen.color, cert.tier]\nidentity_scope: {cross_market_brands: \"*\", market_scoped_brands: []}\n"
# source id -> (url base, tier, extractor, keys)
SRC = {"maker-us": ("https://www.maker.example/p/", "manufacturer", "maker@1", ["gen.size", "gen.kind", "gen.note"]),
       "shop": ("https://www.shop.example/item/", "retailer", "shop@1", ["gen.size", "gen.color", "cert.tier"]),
       "cert": ("https://data.cert.example/r/", "certifier", "cert@1", ["cert.tier", "gen.size"]),
       "ref": ("https://ref.maker.example/", "manufacturer", "ref@1", ["gen.size", "gen.kind"]),
       "unk": ("https://unknown.example/", "manufacturer", "unk@1", ["gen.size"]),
       "hold": ("https://www.hold.example/", "manufacturer", "hold@1", ["gen.size", "gen.kind"])}
NOTE = 'See <a href="https://www.maker.example/docks">docks</a>'
ITEMS = {   # source -> [(model, {key: value})]
    "maker-us": [("W-100", {"gen.size": 12, "gen.kind": "alpha", "gen.note": NOTE})],
    "shop": [("W-100", {"gen.size": 12, "gen.color": "teal"}),      # F2 same value as maker; F1 gen.color only from a free:false domain
             ("W-200", {"gen.size": 22, "gen.color": "teal"}),      # F8 identity only from the free:false domain
             ("W-800", {"cert.tier": "gold"})],                     # F14 would be a certification-only row
    "cert": [("W-100", {"cert.tier": "gold", "gen.size": 12}),      # F5 granted source beside the maker
             ("W-700", {"cert.tier": "silver"})],                   # F14 granted certification-only row
    "ref": [("W-300", {"gen.size": 30, "gen.kind": "beta"})],       # F4 free but not paid
    "unk": [("W-400", {"gen.size": 40})],                           # F6 unlisted domain
    "hold": [("W-500", {"gen.size": 50, "gen.kind": "beta"})],      # F9 withhold_keys [gen.kind]
}


def run(args, env=None, ok=True):
    e = {k: v for k, v in os.environ.items() if k != "RELEASE"}
    e.update(env or {})
    r = subprocess.run([sys.executable, "-I"] + [str(a) for a in args], env=e, capture_output=True, text=True)
    if ok:
        assert r.returncode == 0, r.stderr[-3000:]
    return r


def tree_text(*dirs):
    out = []
    for d in dirs:
        for p in ([Path(d)] if Path(d).is_file() else Path(d).rglob("*")):
            if p.is_file():
                b = p.read_bytes()
                out.append(gzip.decompress(b).decode() if p.suffix == ".gz" else b.decode())
    return "\n".join(out)


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = t = Path(tempfile.mkdtemp(prefix="specsheet-policy-"))
        os.symlink(CODE / "schemas", t / "schemas")
        (t / "research" / "widgets").mkdir(parents=True)
        (t / "research" / "widgets" / "spec-profile.yaml").write_text(PROFILE)
        (t / "research" / "widgets" / "category.yaml").write_text(CATEGORY)
        (t / "data" / "decisions").mkdir(parents=True)
        pols = ["format: specsheet.policies/1", "claim_policies:"]
        for sid, (_, tier, ext, keys) in SRC.items():
            pols += [f"  - id: claim/{sid}@1", '    since: "2026-11-24"', "    rationale: fixture",
                     f"    match: {{extractors: [{ext}], source_ids: [{sid}], kinds: [official], tiers: [{tier}], statuses: [known], keys: [{', '.join(keys)}]}}"]
        pols += ["relation_policies: []"]
        (t / "data" / "decisions" / "policies.yaml").write_text("\n".join(pols) + "\n")
        (t / "data" / "decisions" / "ledger.jsonl").write_text("")
        (t / "sources.extra.json").write_text(json.dumps({sid: {"brand": "widgetco", "brand_name": "WidgetCo", "category": "widgets", "module": "none",
                                                               "importer": "model", "parser": ext} for sid, (_, _, ext, _) in SRC.items()}))
        n = 0
        for sid, items in ITEMS.items():
            base, tier, ext, _ = SRC[sid]
            d = t / "raw" / sid
            (d / "parsed").mkdir(parents=True)
            log = []
            for model, vals in items:
                n += 1
                url = base + model
                pr = {"identifiers": [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "widgetco", "market": "US", "package_level": "model",
                                       "role": "key", "sources": ["s1"]}],
                      "aliases": [], "media": [], "documents": [], "absences": [], "links": [], "fingerprints": {},
                      "claims": [{"id": f"c_{sid}_{model}_{k}", "key": k, "status": "known", "kind": "official", "unit": "in" if k == "gen.size" else None,
                                  "raw": f"{k}={v}", "source": "s1", "method": {"stage": "table", "extractor": ext}, "observed_at": "2026-11-24T00:00:00Z",
                                  "value": v, "locator": {}} for k, v in vals.items()],
                      "sources": [{"id": "s1", "url": url, "label": "page", "tier": tier}]}
                (d / "parsed" / f"r{n}.json").write_text(json.dumps(pr))
                log.append({"snapshot": f"sha256:{n:064x}", "ref": f"r{n}", "url": url, "final_url": url, "status": 200, "fetched_at": "2026-11-24T00:00:00Z",
                            "etag": None, "last_modified": None, "adapter": "fixture@1", "blob": f"blobs/{n:064x}.json"})
            (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
        env = {"SPECSHEET_ROOT": str(t)}
        r = run([CODE / "scripts" / "import.py", "--data", t / "data"], env)
        cls.import_out = r.stdout
        cls.api, cls.api2 = t / "api", t / "api2"
        code = ("import sys, json; sys.path.insert(0, %r); import v1_publish as P, build as B; from pathlib import Path; api = Path(sys.argv[1]); g = {}; "
                "cats, man, rel = P.publish(api, {}, g); pol, cov, stamp = B.policy_outputs(api, g, 'specsheet'); "
                "B.dump(api / 'categories.json', cats); B.dump(api / 'manifest.json', dict(stamp, categories=man, release=rel)); "
                "pol.check_unlisted(release=False); print(json.dumps(cats))") % str(CODE / "scripts")
        r = run(["-c", code, cls.api], dict(env, SPECSHEET_SOURCE_POLICY=str(FX / "policy.yaml")))
        cls.cats = json.loads(r.stdout.splitlines()[-1])
        cls.build_err = r.stderr
        run(["-c", code, cls.api2], dict(env, SPECSHEET_SOURCE_POLICY=str(FX / "policy-v2.yaml")))
        cls.pack, cls.paid, cls.snap = t / "pack", t / "paid", t / "snap"
        r2 = CODE / "scripts" / "build_r2.py"
        cls.r2 = r2
        cls.pack_err = run([r2, "--tier", "free", "--docs", cls.api, "--out", cls.pack, "--snapshots", t / "snap-free", "--releases", t / "rel",
                            "--policy", FX / "policy.yaml", "--release", "20261124T000000Z-a"]).stderr
        run([r2, "--tier", "paid", "--docs", cls.api, "--out", cls.paid, "--snapshots", t / "snap-paid", "--releases", t / "rel",
             "--policy", FX / "policy.yaml", "--release", "20261124T000000Z-a"])
        # F10: a second release built with policy v2 (gen.kind withheld for www.maker.example), same free-pack history
        run([r2, "--tier", "free", "--docs", cls.api2, "--out", cls.pack, "--snapshots", t / "snap-free", "--releases", t / "rel",
             "--policy", FX / "policy-v2.yaml", "--release", "20261124T010000Z-b"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def detail(self, api, mid):
        p = api / "widgets" / "products" / f"widgetco-{mid.lower()}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def rows(self, d, cert=False):
        return {r["id"]: r for r in json.loads((d / "widgets" / ("index-certonly.json" if cert else "index.json")).read_text())}

    def bulk(self, d):
        return {r["id"]: r for r in map(json.loads, gzip.open(d / "bulk" / "widgets.jsonl.gz", "rt"))}

    def test_f1_free_false_value_gone_everywhere(self):
        d = self.detail(self.api, "W-100")
        self.assertEqual((d["specs"]["gen.color"]["status"], d["specs"]["gen.color"]["value"], d["specs"]["gen.color"]["sources"]), ("not_published", None, []))
        self.assertNotIn("gen.color", self.rows(self.api)["widgetco-w-100"]["v"])
        facets = json.loads((self.api / "widgets" / "facets.json").read_text())
        self.assertEqual(facets["gen.color"]["counts"], {})
        slim = {r["id"]: r for r in json.loads((self.api / "widgets" / "products.json").read_text())}
        self.assertIsNone(slim["widgetco-w-100"]["specs"]["gen.color"]["value"])
        self.assertNotIn("gen.color", json.loads((self.pack / "index" / "widgets.json").read_text())[0]["v"])
        self.assertNotIn("gen.color", self.bulk(self.paid).get("widgetco-w-100", {}).get("specs", {}).get("gen.color", {}).get("value") or {})
        text = tree_text(self.api, self.api2, self.pack, self.paid)
        self.assertNotIn("shop.example", text, "a free:false domain appears nowhere in any tier's output")
        text = tree_text(*[p for d in (self.api, self.api2, self.pack, self.paid) for p in Path(d).rglob("*") if p.is_file() and p.name != "schema.json"])
        self.assertNotIn("teal", text, "its value appears nowhere (index, facets, lookup, products.json, pack, bulk, diffs)")

    def test_f2_mixed_sources_same_value_cites_allowed_only(self):
        d = self.detail(self.api, "W-100")
        by = {s["id"]: s["url"] for s in d["sources"]}
        self.assertEqual(d["specs"]["gen.size"]["value"], 12)
        self.assertTrue(all("shop.example" not in by[s] for s in d["specs"]["gen.size"]["sources"]))
        self.assertEqual({SP.host_of(by[s]) for s in d["specs"]["gen.size"]["sources"]}, {"www.maker.example", "data.cert.example"})

    def test_f3_no_borrowed_provenance(self):
        pol = SP.load(FX / "policy.yaml")
        rec = {"id": "x", "category": "widgets", "sources": [{"id": "s1", "url": "https://www.shop.example/x"}, {"id": "s2", "url": "https://www.maker.example/x"}],
               "specs": {"k": {"value": 12, "status": "known", "sources": ["s1", "s2"], "claims": ["ca", "cb"]}}}
        claimed = {("https://www.shop.example/x", "ca"): 12, ("https://www.maker.example/x", "cb"): 14}     # B claimed a different value
        sup = lambda rid, k, url, v, cids: any(claimed.get((url, c)) == v for c in cids)
        self.assertEqual(pol.gate(rec, "free", support=sup)["specs"]["k"]["status"], "not_published")
        claimed[("https://www.maker.example/x", "cb")] = 12
        self.assertEqual(pol.gate(rec, "free", support=sup)["specs"]["k"]["sources"], ["s2"])
        # the same rule in v1_publish (owner sids + accepted claims of the scope), unit-level
        import v1_publish as P
        from collections import defaultdict
        ents = {"e": {}}
        srcs = {"e": [{"sid": "s1", "url": "https://www.shop.example/x"}, {"sid": "s2", "url": "https://www.maker.example/x"}]}
        cl = defaultdict(lambda: defaultdict(list))
        cl["e"]["k"] = [{"id": "ca", "source": "s1", "value": 12, "review": "accepted"}, {"id": "cb", "source": "s2", "value": 14, "review": "accepted"}]
        view = {"e": {"k": {"value": 12, "status": "known", "sources": ["s1", "s2"], "claims": ["ca", "cb"]}}}
        self.assertEqual(P.gate_view(pol, view, ents, srcs, cl, {"accepted"}, set()), 1)
        self.assertEqual(view["e"]["k"]["status"], "not_published")

    def test_f4_paid_false_source(self):
        self.assertEqual(self.rows(self.api)["widgetco-w-300"]["v"]["gen.size"], 30)
        self.assertIsNone(self.detail(self.api, "W-300")["specs"].get("gen.size", {}).get("note"))
        self.assertNotIn("widgetco-w-300", json.dumps(json.loads((self.paid / "index" / "widgets.json").read_text())))
        self.assertNotIn("widgetco-w-300", self.bulk(self.paid))
        self.assertNotIn("ref.maker.example", tree_text(self.paid))

    def test_f5_grant_flags(self):
        d = self.detail(self.api, "W-100")
        flags = {SP.host_of(s["url"]): s["licence_grant"] for s in d["sources"]}
        self.assertEqual(flags, {"www.maker.example": False, "data.cert.example": True})
        by = {s["id"]: s for s in d["sources"]}
        self.assertTrue(any(by[s]["licence_grant"] for s in d["specs"]["cert.tier"]["sources"]))
        self.assertFalse(any(by[s]["licence_grant"] for s in d["specs"]["gen.kind"]["sources"]), "maker-only value has no granted source")
        paid = self.bulk(self.paid)["widgetco-w-100"]
        self.assertEqual({k for k, v in paid["specs"].items() if v["status"] == "known"}, {"cert.tier", "gen.size"})
        self.assertTrue(all(s["licence_grant"] for s in paid["sources"]))

    def test_f6_unlisted_domain(self):
        self.assertRegex(self.build_err, r"unlisted domain unknown\.example: .*1 values")
        self.assertIn("unknown.example", self.pack_err)
        self.assertEqual(self.rows(self.api)["widgetco-w-400"]["v"]["gen.size"], 40)
        self.assertNotIn("widgetco-w-400", self.bulk(self.paid))
        r = run([self.r2, "--tier", "free", "--docs", self.api, "--out", self.tmp / "pack-rel", "--snapshots", self.tmp / "snap-rel",
                 "--releases", self.tmp / "rel", "--policy", FX / "policy.yaml", "--release", "20261124T020000Z-c"], {"RELEASE": "1"}, ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown.example", r.stderr.splitlines()[-1])

    def test_f7_host_matching(self):
        pol = SP.load()
        self.assertFalse(pol.disposition("https://psrefstuff.lenovo.com/x")["listed"])
        self.assertTrue(pol.disposition("https://psref.lenovo.com/x")["listed"])
        for u in ("https://amazon.com/x", "https://www.amazon.com/x", "https://smile.amazon.com/x", "https://WWW.AMAZON.COM./x", "https://www.amazon.com:443/x"):
            self.assertEqual(pol.disposition(u)["domain"], "amazon.com", u)
        self.assertIsNone(pol.disposition("https://notamazon.com/x")["domain"])
        self.assertEqual(pol.disposition("https://PSREF.Lenovo.COM.:443/p")["domain"], "psref.lenovo.com")
        d = pol.disposition("https://psref.lenovo.com@evil.example/")
        self.assertEqual((d["host"], d["listed"]), ("evil.example", False))

    def test_f8_identity_only_from_dropped_source(self):
        for d in (self.api, self.pack, self.paid):
            self.assertNotIn("w-200", tree_text(d).lower(), d)
        self.assertIsNone(self.detail(self.api, "W-200"))
        self.assertEqual([c["count"] for c in self.cats if c["id"] == "widgets"], [len(self.rows(self.api))])

    def test_f9_withhold_keys(self):
        d = self.detail(self.api, "W-500")
        self.assertEqual((d["specs"]["gen.size"]["value"], d["specs"]["gen.kind"]["status"]), (50, "not_published"))
        self.assertEqual(SP.host_of(d["sources"][0]["url"]), "www.hold.example")

    def test_f10_withdrawn_diff(self):
        ch = json.loads((self.pack / "changes" / "20261124T010000Z-b.json").read_text())
        row = next(c for c in ch["categories"]["widgets"]["changed"] if c["id"] == "widgetco-w-100")
        self.assertEqual(row["withdrawn"], [{"key": "gen.kind", "change": "withdrawn"}])
        self.assertNotIn("gen.kind", row["fields"])
        self.assertNotIn("alpha", json.dumps(ch), "no previous value printed")

    def test_f11_invalid_policies(self):
        base = (FX / "policy.yaml").read_text()
        good = '{domain: www.maker.example, match: exact, kind: maker, credit: "WidgetCo pages", free: true, paid: false, licence_grant: false, evidence: {level: none, checked: null}}'
        cases = {"paid without grant": good.replace("paid: false, licence_grant: false", "paid: true, licence_grant: false"),
                 "grant without free": good.replace("free: true, paid: false, licence_grant: false", "free: false, paid: false, licence_grant: true"),
                 "grant with search evidence": good.replace("licence_grant: false, evidence: {level: none, checked: null}",
                                                            "licence_grant: true, evidence: {level: search, checked: null, refs: [x]}"),
                 "duplicate domain": good + "\n  - " + good,
                 "unknown key": good.replace("kind: maker,", "kind: maker, public_domain: true,")}
        self.assertIn(good, base)
        for name, rep in cases.items():
            with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
                f.write(base.replace(good, rep)); f.flush()
                with self.assertRaises(SystemExit, msg=name):
                    SP.load(f.name)

    def test_f12_policy_stamped_in_all_manifests(self):
        pol = SP.load(FX / "policy.yaml")
        pol2 = SP.load(FX / "policy-v2.yaml")
        ms = [json.loads((self.api / "manifest.json").read_text()), json.loads((self.pack / "meta" / "manifest.json").read_text()),
              json.loads((self.paid / "meta" / "manifest.json").read_text()), json.loads((self.api2 / "manifest.json").read_text())]
        self.assertEqual({(m["policy_version"], m["policy_sha256"]) for m in [ms[0], ms[2]]}, {(pol.version, pol.sha256)})
        self.assertEqual({(m["policy_version"], m["policy_sha256"]) for m in [ms[1], ms[3]]}, {(pol2.version, pol2.sha256)},
                         "the pack was last rebuilt from the v2 docs (F10): pack and its free manifest agree")
        for m in ms:
            self.assertEqual((m["license"], m["license_scope"]), ("ODbL-1.0", SP.LICENSE["license_scope"]))
            self.assertTrue(m["attribution"]["dataset"].startswith("Data: "))
        cov = json.loads((self.api / "coverage.json").read_text())
        self.assertEqual(cov["categories"]["widgets"], ms[2]["coverage"]["categories"]["widgets"], "free coverage.json == paid manifest block")
        self.assertEqual(cov["categories"]["widgets"]["paid"]["records"], 2)   # W-100 + W-700 (cert source)
        # a docs tree built with another policy is refused
        r = run([self.r2, "--tier", "paid", "--docs", self.api2, "--out", self.tmp / "x", "--snapshots", self.tmp / "sx", "--releases", self.tmp / "rel",
                 "--policy", FX / "policy.yaml"], ok=False)
        self.assertNotEqual(r.returncode, 0)

    def test_f13_sources_json_from_policy(self):
        import site_meta
        doc = site_meta.sources()
        self.assertEqual(doc["generated_from"], "data/source-policy.yaml")
        self.assertEqual({s["domain"] for s in doc["granted"]}, {"data.energystar.gov"})
        self.assertIn("psref.lenovo.com", {s["domain"] for s in doc["facts_only"]})
        self.assertNotIn("public_domain", json.dumps(doc))
        self.assertFalse({s["domain"] for s in doc["facts_only"]} & {"amazon.com"}, "free:false domains are not listed")
        p = CODE / "docs" / "sources.json"
        if p.exists():
            self.assertNotIn("public_domain", p.read_text())

    def test_f14_certonly_and_preview_gated_identically(self):
        cert = self.rows(self.api, cert=True)
        self.assertIn("widgetco-w-700", cert)
        self.assertNotIn("widgetco-w-800", cert)
        self.assertNotIn("widgetco-w-800", json.loads((self.api / "lookup" / "identifiers.json").read_text()).get("mfr_model:W800", []))
        text = tree_text(self.api / "preview")
        self.assertNotIn("w-800", tree_text(self.api).lower())
        self.assertNotIn("shop.example", text)
        self.assertIn("widgetco-w-700", self.bulk(self.paid), "certification-only rows reach the paid export through the same gate")

    def test_f15_expression_guard(self):
        d = self.detail(self.api, "W-100")
        self.assertEqual(d["specs"]["gen.note"]["status"], "not_published")
        pol = SP.load(FX / "policy.yaml")
        g = pol.gate({"id": "x", "category": "widgets", "name": "Portable SSD<br>", "sources": [{"id": "s1", "url": "https://www.maker.example/x"}],
                      "specs": {"t": {"value": "a <b>bold</b> claim", "status": "known", "sources": ["s1"]}}}, "free")
        self.assertEqual((g["name"], g["specs"]["t"]["status"]), ("Portable SSD", "not_published"))
        ok = re.compile(r"^(https?://\S+)$")
        for api in (self.api, self.paid):
            for p in api.rglob("*.json"):
                obj = json.loads(p.read_text())
                stack = [(obj, "")]
                while stack:
                    o, path = stack.pop()
                    if isinstance(o, dict):
                        stack += [(v, k) for k, v in o.items() if k not in ("refs", "url", "license_url")]
                    elif isinstance(o, list):
                        stack += [(v, path) for v in o]
                    elif isinstance(o, str) and SP.is_expression(o) and not ok.match(o):
                        self.fail(f"{p}: {path}: {o[:80]}")

    def test_f16_one_policy_reader(self):
        for f in ("build.py", "build_r2.py", "v1_publish.py", "site_meta.py"):
            self.assertRegex((CODE / "scripts" / f).read_text(), r"(?m)^\s*import source_policy", f)
        readers = sorted(p.name for p in list((CODE / "scripts").glob("*.py")) + list((CODE / "scripts").glob("*.mjs")) + list((CODE / "api-worker" / "src").glob("*.ts"))
                         if "source-policy" in p.read_text() and re.search(r"(?m)^\s*(import yaml|from yaml)|readFile|fs\.", p.read_text()))
        self.assertEqual(readers, ["source_policy.py"])
        bad = [str(p) for p in CODE.rglob("*exclusions*") if "node_modules" not in p.parts and ".git" not in p.parts]
        self.assertEqual(bad, [])
        for p in (CODE / "api-worker" / "src").glob("*.ts"):
            self.assertNotIn("licensing-exclusions", p.read_text())

    def test_real_policy_valid(self):
        pol = SP.load()
        self.assertEqual(SP.validate(pol.doc), [])
        self.assertTrue(pol.disposition("https://data.energystar.gov/x")["paid"])


if __name__ == "__main__":
    unittest.main()
