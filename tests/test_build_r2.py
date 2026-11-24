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

if __name__ == "__main__":
    unittest.main()
