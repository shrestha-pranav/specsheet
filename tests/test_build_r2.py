import json, os, subprocess, sys, tempfile, unittest, gzip
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def w(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(o, open(p, "w"))

class BuildR2(unittest.TestCase):
    def test_policy_gate_and_diff(self):
        with tempfile.TemporaryDirectory() as t:
            docs, rel, out, snap = (os.path.join(t, x) for x in ("docs", "rel", "out", "snap"))
            cfg = os.path.join(ROOT, "tests/fixtures/source-policy/policy.yaml")   # www.maker.example free; shop.example (+subdomains) free: false
            def mk(w_val):
                rec = {"id": "a", "kind": "model", "brand": {"name": "Acme"}, "name": "A", "media": [1],
                       "sources": [{"id": "s1", "url": "https://www.maker.example/a"}, {"id": "s2", "url": "https://x.shop.example/a"}],
                       "specs": {"p.w": {"value": w_val, "status": "known", "sources": ["s1"]},
                                 "only.bad": {"value": 1, "status": "known", "sources": ["s2"]},
                                 "unk": {"value": None, "status": "unknown", "sources": []}}}
                w(os.path.join(docs, "c/products/a.json"), rec)
                w(os.path.join(docs, "manifest.json"), {"categories": [{"id": "c", "index": [], "count": 1}], "build": "x"})
            def run(rid):
                subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts/build_r2.py"), "--docs", docs, "--releases", rel, "--out", out, "--tier", "free",
                                "--policy", cfg, "--snapshots", snap, "--release", rid], check=True, capture_output=True, env={k: v for k, v in os.environ.items() if k != "RELEASE"})
            mk(60); run("20261124T000000Z-a")
            idx = json.load(open(os.path.join(out, "index/c.json")))
            self.assertEqual(idx[0]["v"], {"p.w": 60})  # excluded + unknown values gone
            line = json.loads(gzip.open(os.path.join(out, "bulk/c.jsonl.gz")).readline())
            self.assertNotIn("media", line); self.assertEqual(len(line["sources"]), 1)
            mk(65); run("20261124T010000Z-b")
            hist = json.load(open(os.path.join(out, "changes/index.json")))
            self.assertTrue(hist[0]["baseline"]); self.assertFalse(hist[1]["baseline"])
            d = json.load(open(os.path.join(out, "changes/20261124T010000Z-b.json")))
            self.assertEqual(d["categories"]["c"]["changed"][0]["fields"]["p.w"], [60, 65])

    def test_alternatives_only_from_gated_records(self):
        """review-8 P1: pack `a` comes from the policy-gated record, never the docs index x[*].alt. A restricted-only alternative
        (shop.example, free: false) neither appears nor changes the pack index; an authorized one still yields 'disagree'."""
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import presets as P
        cfg = os.path.join(ROOT, "tests/fixtures/source-policy/policy.yaml")
        def build(t, restricted):
            docs, out = os.path.join(t, "docs"), os.path.join(t, "out")
            bad = [{"value": 20, "kind": "measured", "sources": ["s2"], "claims": []}] if restricted else []
            rec = {"id": "a", "kind": "model", "brand": {"name": "Acme"}, "name": "A",
                   "sources": [{"id": "s1", "url": "https://www.maker.example/a"}, {"id": "s2", "url": "https://x.shop.example/a"}],
                   "specs": {"p.w": {"value": 60, "status": "known", "kind": "official", "sources": ["s1"], "alternatives": bad},
                             "p.v": {"value": 20, "status": "known", "kind": "official", "sources": ["s1"],
                                     "alternatives": [{"value": 9, "kind": "measured", "sources": ["s1"], "claims": []}]}}}
            x = {"p.v": {"alt": [{"v": 9, "k": "measured"}]}}
            if restricted:
                x["p.w"] = {"alt": [{"v": 20, "k": "measured"}]}   # an ungated index carrying the restricted value
            w(os.path.join(docs, "c/products/a.json"), rec)
            w(os.path.join(docs, "c/index.json"), [{"id": "a", "kind": "model", "ids": [], "v": {"p.w": 60, "p.v": 20}, "x": x}])
            w(os.path.join(docs, "manifest.json"), {"categories": [{"id": "c", "index": ["c/index.json"], "count": 1}], "build": "x"})
            subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts/build_r2.py"), "--docs", docs, "--releases", os.path.join(t, "rel"),
                            "--out", out, "--tier", "free", "--policy", cfg, "--snapshots", os.path.join(t, "snap"), "--release", "20261126T000000Z-a"],
                           check=True, capture_output=True, env={k: v for k, v in os.environ.items() if k != "RELEASE"})
            return json.load(open(os.path.join(out, "index/c.json")))
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            with_bad, without = build(t1, True), build(t2, False)
        self.assertEqual(with_bad, without)                       # membership/values/statuses identical
        self.assertEqual(with_bad[0]["a"], {"p.v": [9]})           # restricted p.w alt absent, authorized p.v alt kept
        fld = {"key": "p.w", "type": "number", "facet": {"kind": "range"}}
        row = {"v": with_bad[0]["v"], "x": {k: {"alt": [{"v": v} for v in vs]} for k, vs in with_bad[0]["a"].items()}}
        self.assertEqual(P._verdict(row, fld, "max", "30"), "no")  # a restricted 20 W alt would have made this 'disagree'
        self.assertEqual(P._verdict(row, dict(fld, key="p.v"), "min", "15"), "disagree")

if __name__ == "__main__":
    unittest.main()
