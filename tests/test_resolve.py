"""Normalisation (P1-5) + condition-aware resolution (P0-2) + publisher end-to-end fixture (P0-1, P0-2, P1-4)."""
import json, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import normalize as N  # noqa: E402
import resolve as R  # noqa: E402
import _cpu  # noqa: E402

U = N.units({"specs": [{"key": "x", "unit": "nits"}]})
num = lambda key, unit, t="number", label="": {"key": key, "type": t, "unit": unit, "label": label}
known = lambda v, unit=None, raw=None: {"status": "known", "value": v, "unit": unit, "raw": raw}


class NormaliseTest(unittest.TestCase):
    def test_review_probes(self):
        self.assertEqual(N.normalise(num("phys.weight", "kg"), known(1000, "g"), U)[:2], (True, 1))
        self.assertEqual(N.normalise(num("port.usba_count", None, "integer"), known(2.9), U)[0], False)
        ok, v, x = N.normalise(num("phys.weight", "kg"), known("starting at 1.2 kg"), U)
        self.assertEqual((ok, v, x.get("qualifier")), (True, 1.2, "from"), "qualifier preserved, never an exact value")

    def test_affine_and_precision(self):
        self.assertAlmostEqual(N.convert(25, "degC", "degC", N.units()), 25)
        self.assertEqual(N.normalise(num("phys.weight", "kg"), known("3.5 lb"), U)[1], 1.59)

    def test_storage_display_and_multi(self):
        st = num("stor.size", "GB")
        self.assertEqual(N.normalise(st, known("1000GB SSD"), U)[2].get("display"), "1 TB")
        self.assertEqual(N.normalise(st, known("1024GB SSD"), U)[2], {})
        self.assertEqual(N.normalise(st, known("2x 1TB SSD"), U)[1], 2000)
        self.assertFalse(N.normalise(st, known("1TB SSD + 1TB SSD"), U)[0])
        self.assertFalse(N.normalise(num("surge.amps", "A"), known("3-25A"), U)[0])

    def test_up_to_only_on_max_specs(self):
        self.assertEqual(N.normalise(num("cpu.boost_clock", "GHz", label="Max boost clock"), known("up to 4.8 GHz"), U)[2], {})
        self.assertEqual(N.normalise(num("disp.nits", "nits"), known("up to 500 nits"), U)[2].get("qualifier"), "up_to")

    def test_range_validation(self):
        self.assertFalse(N.normalise({"key": "r", "type": "range", "unit": "W"}, known({"min": 30, "max": 10}), U)[0])
        self.assertTrue(N.normalise({"key": "r", "type": "range", "unit": "W"}, known({"min": 10, "max": 30}), U)[0])


class CpuSplitTest(unittest.TestCase):
    def test_psref_amd(self):
        self.assertEqual(_cpu.parse("AMD Ryzen AI 5 430 (4C / 8T, 2.0 / 4.5GHz, 4MB L2 / 8MB L3)"),
                         {"model": "AMD Ryzen AI 5 430", "cores": 4, "threads": 8, "cores_threads": "4C / 8T", "base_clock": 2, "boost_clock": 4.5, "cache": "4MB L2 / 8MB L3"})

    def test_psref_intel_hybrid(self):
        p = _cpu.parse("Intel Core 5 210H, 8C (4P + 4E) / 12T, P-core 2.2 / 4.8GHz, E-core 1.6 / 3.6GHz, 12MB Intel Smart Cache")
        self.assertEqual((p["model"], p["cores"], p["threads"], p["base_clock"], p["boost_clock"], p["cache"]), ("Intel Core 5 210H", 8, 12, 2.2, 4.8, "12MB"))

    def test_apple(self):
        self.assertEqual(_cpu.parse(["Apple M2 chip", "8-core CPU with 4 performance cores and 4 efficiency cores", "10-core GPU"]), {"model": "Apple M2", "cores": 8})
        self.assertNotIn("cores", _cpu.parse(["Apple M2 Pro chip", "10-core CPU", "12-core CPU", "Apple M2 Max chip"]), "configurable chips: no single core count")

    def test_gpu_cores_not_cpu_cores(self):
        self.assertEqual(_cpu.parse("NVIDIA RTX Spark N1X with 6144-core GPU and 20-core CPU")["cores"], 20)


def c(id, value, kind="official", cond=None, mmode=None, supersedes=None, src="s1", ok=True, review="accepted"):
    return {"id": id, "status": "known", "kind": kind, "cond": cond or {}, "mmode": mmode, "ok": ok, "value": value, "raw": str(value),
            "nx": {}, "source": src, "review": review, "supersedes": supersedes}


PPS = {"key": "pps.max_a", "type": "number", "unit": "A", "conditions": ["port", "active_ports"], "headline_condition": {"active_ports": ["C1"], "port": "C1"}}


class ResolveTest(unittest.TestCase):
    def test_two_active_port_combinations_and_official_vs_measured(self):
        claims = [c("c_1", 5, cond={"port": "C1", "active_ports": ["C1"]}),
                  c("c_2", 3, cond={"port": "C1", "active_ports": ["C2", "C1"]}),
                  c("c_3", 5, kind="measured", mmode="negotiated", cond={"port": "C1", "active_ports": ["C1"]}, src="s2"),
                  c("c_4", 2.9, kind="measured", mmode="sustained", cond={"port": "C1", "active_ports": ["C1", "C2"]}, src="s2")]
        r = R.resolve_spec(PPS, claims, [])
        self.assertEqual((r["status"], r["value"], r["kind"]), ("known", 5, "official"), "headline = profile headline_condition, official")
        self.assertEqual(r["alternatives"], [{"value": 5, "kind": "measured", "sources": ["s2"], "measurement_mode": "negotiated"}],
                         "equal measured value is NOT collapsed into the official one")
        self.assertEqual(len(r["conditional"]), 1, "C1+C2 condition (order-insensitive set) is one conditional row")
        row = r["conditional"][0]
        self.assertEqual((row["conditions"], row["value"], row["status"]), ({"active_ports": ["C1", "C2"], "port": "C1"}, 3, "known"))
        self.assertEqual(row["alternatives"][0]["value"], 2.9, "measured stays an alternative, never a conflict")

    def test_no_headline_evidence_is_unknown_not_first_condition(self):
        r = R.resolve_spec(PPS, [c("c_2", 3, cond={"port": "C1", "active_ports": ["C1", "C2"]})], [])
        self.assertEqual((r["status"], r["value"]), ("unknown", None))
        self.assertEqual(r["conditional"][0]["value"], 3)

    def test_supersession_first_and_conflicts(self):
        spec = {"key": "k", "type": "number", "unit": "W"}
        r = R.resolve_spec(spec, [c("c_1", 65), c("c_2", 60, supersedes="c_1")], [])
        self.assertEqual((r["status"], r["value"]), ("known", 60))
        r = R.resolve_spec(spec, [c("c_1", 65), c("c_2", 60)], [])
        self.assertEqual(r["status"], "conflicted"); self.assertEqual(len(r["alternatives"]), 2)

    def test_inheritance_rules(self):
        self.assertTrue(R.inheritable({"key": "cpu.model", "level": "model"}, "model", "configuration"))
        self.assertFalse(R.inheritable({"key": "mem.size", "level": "configuration"}, "model", "configuration"), "varies below the parent")
        self.assertFalse(R.inheritable({"key": "phys.weight_lb"}, "model", "package"), "package physical facts never inherit")
        self.assertFalse(R.inheritable({"key": "x"}, "family", "model"))
        order, cyc = R.topo({"a": 1, "b": 1, "c": 1}, {"c": "b", "b": "a"})
        self.assertLess(order.index("a"), order.index("b")); self.assertLess(order.index("b"), order.index("c"))


class PublishFixtureTest(unittest.TestCase):
    """End to end through v1_publish.publish() on a synthetic store: accepted-only trusted set, preview delta, inheritance
    provenance pointing at the ancestor's real URL, two active-port combinations, official vs measured."""
    def test_publish(self):
        import importlib
        imp = importlib.import_module("import"); vp = importlib.import_module("v1_publish")
        tmp = Path(tempfile.mkdtemp())
        db = tmp / "s.sqlite"; con = sqlite3.connect(db); imp.schema(con)
        con.execute("INSERT INTO meta VALUES ('scope','full')")
        ent = lambda i, kind, parent: con.execute("INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?)", (i, "fx", kind, "acme", "Acme", i, parent, None, "current", "US", "{}"))
        ent("acme-m1", "model", None); ent("acme-m1-blk", "configuration", "acme-m1")
        con.execute("INSERT INTO identifiers VALUES (?,?,?,?,?,?,?,?,?,?)", ("acme-m1", "mfr_model", "M1", "M1", "acme", "US", "model", "key", 1, 0))
        con.execute("INSERT INTO identifiers VALUES (?,?,?,?,?,?,?,?,?,?)", ("acme-m1-blk", "mfr_sku", "M1-BLK", "M1-BLK", "acme", "US", "configuration", "key", 1, 0))
        con.execute("INSERT INTO relations VALUES (?,?,?,?,?,?)", ("acme-m1-blk", "configuration_of", "acme-m1", "approved", "adapter:fx", "rel/source-stated-hierarchy@1"))
        con.execute("INSERT INTO entity_sources VALUES (?,?,?,?,?,?,?)", ("acme-m1", "s1", "https://acme.example/m1", "manufacturer", None, "sha256:a", "2026-11-22T00:00:00Z"))
        con.execute("INSERT INTO entity_sources VALUES (?,?,?,?,?,?,?)", ("acme-m1", "s2", "https://lab.example/m1", "measurement", None, "sha256:b", "2026-11-22T00:00:00Z"))
        con.execute("INSERT INTO entity_sources VALUES (?,?,?,?,?,?,?)", ("acme-m1-blk", "s1", "https://acme.example/m1-blk", "manufacturer", None, "sha256:c", "2026-11-22T00:00:00Z"))
        def claim(eid, cid, key, val, review="accepted", kind="official", cond=None, mmode=None, src="s1"):
            con.execute("INSERT INTO claims (id, entity_id, key, mapped_key, status, kind, cond, mmode, value, norm_ok, norm_value, source, review) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, eid, key, key, "known", kind, json.dumps(cond or {}), mmode, json.dumps(val), 1, json.dumps(val), src, review))
        claim("acme-m1", "c_1", "pps.max_a", 5, cond={"port": "C1", "active_ports": ["C1"]})
        claim("acme-m1", "c_2", "pps.max_a", 3, cond={"port": "C1", "active_ports": ["C1", "C2"]})
        claim("acme-m1", "c_3", "pps.max_a", 5, kind="measured", mmode="negotiated", cond={"port": "C1", "active_ports": ["C1"]}, src="s2")
        claim("acme-m1", "c_4", "outlets", 6)
        claim("acme-m1", "c_5", "joules", 1080, review="candidate")
        claim("acme-m1-blk", "c_6", "color", "black")
        con.commit(); con.close()
        prof = {"version": 1, "groups": [{"id": "g", "label": "G"}], "specs": [dict(PPS, label="PPS", group="g", facet=True),
                {"key": "outlets", "label": "Outlets", "group": "g", "type": "integer", "facet": True},
                {"key": "joules", "label": "Joules", "group": "g", "type": "number", "unit": "J", "facet": True},
                {"key": "color", "label": "Colour", "group": "g", "type": "text", "level": "configuration"}]}
        old = (vp.DB, vp.CATEGORIES, vp.load_profile)
        vp.DB, vp.CATEGORIES, vp.load_profile = db, {"fx": {"name": "Fixture", "description": "", "columns": ["outlets"], "us_only": False}}, lambda cat: prof
        try:
            cats, mcats, rel = vp.publish(tmp / "api", {})
        finally:
            vp.DB, vp.CATEGORIES, vp.load_profile = old
        api = tmp / "api"
        idx = json.loads((api / "fx" / "index.json").read_text())
        self.assertEqual({r["id"] for r in idx}, {"acme-m1", "acme-m1-blk"})
        m1 = json.loads((api / "fx" / "products" / "acme-m1.json").read_text())
        self.assertNotIn("joules", m1["specs"], "candidate claim never in the trusted record")
        self.assertNotIn("joules", json.loads((api / "fx" / "facets.json").read_text())["joules"].get("counts", {}) or {})
        pps = m1["specs"]["pps.max_a"]
        self.assertEqual((pps["value"], pps["kind"], pps["alternatives"][0]["kind"], len(pps["conditional"])), (5, "official", "measured", 1))
        blk = json.loads((api / "fx" / "products" / "acme-m1-blk.json").read_text())
        out = blk["specs"]["outlets"]
        self.assertEqual(out["inherited_from"], "acme-m1")
        src = {s["id"]: s for s in blk["sources"]}
        self.assertEqual(src[out["sources"][0]]["url"], "https://acme.example/m1", "inherited provenance = the ancestor's real URL")
        self.assertEqual(blk["specs"]["color"]["sources"], ["s1"]); self.assertEqual(src["s1"]["url"], "https://acme.example/m1-blk")
        prev = json.loads((api / "preview" / "fx" / "products" / "acme-m1.json").read_text())
        self.assertEqual(set(prev["specs"]), {"joules"}, "preview detail is a delta over the trusted record")
        self.assertEqual(prev["review_scope"], "preview")


if __name__ == "__main__":
    unittest.main()
