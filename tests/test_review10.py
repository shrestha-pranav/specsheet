#!/usr/bin/env python3
"""A3-fix (2026-11-26): Codex review-10 counterexamples (reviews/2026-11-26-astra-review-10.md), one class per finding.
P1-1 approval cannot be bypassed through dependencies: a psref-split value publishes only when its parent literal is accepted, or is a candidate
     SOLELY because it does not normalise (import.parent_supports); the TV per-port completeness proof uses only a TRUSTED hdmi.count
     (docspec_r7tv.inventory + import.trusted_probe). The end-to-end case (pending parent policy, approved claim/psref-split@1, real PSREF store:
     trusted docs, R2 pack, preset counts) is EndToEnd below; it needs state/raw and is skipped when raw/lenovo-psref is absent.
P1-2 SFC 2.0 -> PPS: modal / contraction negation and exact normalised model identity (pb_pps_r7@8).
P1-3 UPS switchover: alternatives after the figure and trailing lower bounds never exact, rows and prose (_powerstation, stations @9).
P1-4 zero trace for free:false hosts: tests/test_zero_trace.py (scripts/zero_trace.py)."""
import collections, gzip, importlib, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "crawler"), str(ROOT / "crawler" / "adapters")]
import _contract as C  # noqa: E402
import decisions as D  # noqa: E402
import docspec_r7tv as R7TV  # noqa: E402
import pb_pps_r7 as PPS  # noqa: E402
import _powerstation as PS  # noqa: E402

APPROVED = {"state": "approved", "by": "fixture-approver", "at": "2026-11-26"}
HALF = {"state": "approved", "by": "fixture-approver", "at": None}
PENDING = {"state": "pending"}
PARENT = {"source_id": "lenovo-psref", "extractor": "lenovo_psref@5", "key": "mem.slots", "spec_type": "object", "kind": "official",
          "tier": "manufacturer", "status": "known", "normalized": False}


SLOTS_PENDING = {"id": "claim/slots@1", "since": "2026-11-26", "rationale": "fixture", "approval": PENDING,
                 "match": {"extractors": ["lenovo_psref@5"], "source_ids": ["lenovo-psref"], "kinds": ["official"], "statuses": ["known"],
                           "require_normalized": True, "keys": {"lenovo-psref": ["mem.slots"]}}}


def decs(approval, keys=("mem.slots", "disp.size"), extra=()):
    d = Path(tempfile.mkdtemp())
    (d / "decisions").mkdir()
    pol = {"id": "claim/parent@1", "since": "2026-11-26", "rationale": "fixture", "approval": approval,
           "match": {"extractors": ["lenovo_psref@5", "maker-tvs@1"], "source_ids": ["lenovo-psref", "maker-tvs"], "kinds": ["official"],
                     "statuses": ["known"], "require_normalized": True, "keys": {"lenovo-psref": list(keys), "maker-tvs": ["hdmi.count"]}}}
    (d / "decisions" / "policies.yaml").write_text(yaml.safe_dump({"format": "specsheet.policies/2", "claim_policies": [pol, *extra],
                                                                   "relation_policies": []}, sort_keys=False))
    return D.Decisions(d)


class DependentGate(unittest.TestCase):
    """import.parent_supports(dec, (parent state, parent decision, parent ctx))."""

    def setUp(self):
        self.imp = importlib.import_module("import")

    def test_unnormalisable_parent_under_approved_policy_supports(self):
        self.assertTrue(self.imp.parent_supports(decs(APPROVED), ("candidate", None, PARENT)))
        self.assertTrue(self.imp.parent_supports(decs(PENDING), ("accepted", "d_1", PARENT)), "a ledger-accepted parent supports")

    def test_withheld_parent_never_supports(self):
        for app in (PENDING, HALF, {"state": "approved", "by": None, "at": "2026-11-26"}, None):
            self.assertFalse(self.imp.parent_supports(decs(app), ("candidate", None, PARENT)), app)
        self.assertTrue(self.imp.parent_supports(decs(APPROVED, keys=("disp.size",)), ("candidate", None, PARENT)),
                        "no policy at all covers the literal's key (Memory Slots): the derivative's own approved policy decides")
        self.assertFalse(self.imp.parent_supports(decs(APPROVED, keys=("disp.size",), extra=[SLOTS_PENDING]), ("candidate", None, PARENT)),
                         "a pending policy that would cover the normalised literal withholds it")
        self.assertFalse(self.imp.parent_supports(decs(APPROVED), ("candidate", None, dict(PARENT, normalized=True))),
                         "a parent that normalised and is still a candidate is withheld, not 'failed normalisation'")
        self.assertFalse(self.imp.parent_supports(decs(APPROVED), ("rejected", "d_2", PARENT)))
        self.assertFalse(self.imp.parent_supports(decs(APPROVED), ("candidate", "d_3", PARENT)), "a parent with a decision on it")
        self.assertFalse(self.imp.parent_supports(decs(APPROVED), None), "no parent seen")

    def test_probe_has_no_side_effects(self):
        dec = decs(PENDING)
        self.assertEqual(dec.claim_state("c1", dict(PARENT, normalized=True), record=False), ("candidate", None))
        self.assertEqual(dec.held, {})
        self.assertEqual(dec.claim_state("c1", dict(PARENT, normalized=True)), ("candidate", None))
        self.assertEqual(dec.held, {"claim/parent@1": {"claims": 1, "relations": 0}})


class TrustedInventory(unittest.TestCase):
    """docspec_r7tv: the complete-inventory proof (hdmi.count) must be trusted; import.trusted_probe decides it like the write loop."""

    def setUp(self):
        self.imp = importlib.import_module("import")
        sys.path.insert(0, str(ROOT / "tests"))
        import test_review9 as R9
        self.R9 = R9.TvPortsTransform
        self.helper = self.R9("test_complete_inventory_emits")
        self.helper.imp = self.imp

    def probe(self, approval):
        cats = ["tvs"]
        profiles = {c: self.imp.load_profile(c) for c in cats}
        unitsets = {c: self.imp.N.units(profiles[c][0]) for c in cats}
        psref = {c: self.imp.load_psref(c, profiles[c][1]) for c in cats}
        return self.imp.trusted_probe(decs(approval), profiles, unitsets, psref)

    def run_guide(self, trusted, counts=(4,)):
        w, ents = self.helper.world(["85QM7K"], {"85QM7K": list(counts)})
        for c, ob in ents["85QM7K"].claims:
            c.setdefault("method", {"extractor": "maker-tvs@1"})
        R7TV.apply({"tvs": w}, [], {}, trusted=trusted, root=self.helper.store(self.R9_doc(), ["85qm7k"]))
        return self.helper.got(ents["85QM7K"])

    @staticmethod
    def R9_doc():
        import test_review9 as R9
        return R9.tdoc("85QM7K\n" + R9.FOUR)

    def test_approved_count_proves_inventory(self):
        self.assertEqual(self.run_guide(self.probe(APPROVED)), {"hdmi.ports_4k120": 2, "hdmi.has_4k120": True})

    def test_pending_or_half_approved_count_proves_nothing(self):
        for app in (PENDING, HALF):
            self.assertEqual(self.run_guide(self.probe(app)), {}, app)
        self.assertEqual(self.run_guide(None), {}, "no probe -> nothing")

    def test_untrusted_disagreeing_count_voids(self):
        only_four = lambda cat, e, c, ob: c.get("value") == 4
        self.assertEqual(self.run_guide(only_four, counts=(4, 3)), {})
        self.assertEqual(self.run_guide(only_four, counts=(4,)), {"hdmi.ports_4k120": 2, "hdmi.has_4k120": True})


class Sfc2Identity(unittest.TestCase):
    def test_review_probes_emit_nothing(self):
        self.assertIsNone(PPS.sfc2("It cannot support Samsung Super Fast Charging 2.0.", "P73"))
        self.assertIsNone(PPS.sfc2("The P730 supports Samsung Super Fast Charging 2.0.", "P73"))

    def test_modal_and_contraction_negation(self):
        for neg in ("can't", "can’t", "can not", "won't", "will not", "isn't", "doesn't", "does not", "is unable to", "never", "is incompatible with",
                    "lacks"):
            s = f"It {neg} support Samsung Super Fast Charging 2.0."
            self.assertIsNone(PPS.sfc2(s, "P73"), s)
        self.assertIsNone(PPS.sfc2("Samsung Super Fast Charging 2.0 is not supported?", "P73"))
        self.assertIsNone(PPS.sfc2("Can it support Samsung Super Fast Charging 2.0", "P73"))

    def test_exact_model_identity(self):
        self.assertIsNone(PPS.sfc2("The P73 supports Samsung Super Fast Charging 2.0.", "P730"))
        self.assertIsNone(PPS.sfc2("The P73-PRO supports Samsung Super Fast Charging 2.0.", "P73"))
        self.assertTrue(PPS.sfc2("The P73 supports Samsung Super Fast Charging 2.0.", "P73"))
        self.assertTrue(PPS.sfc2("The B61 supports Samsung Super Fast Charging 2.0.", "INIU B61"), "a model token printed inside the own model")
        self.assertTrue(PPS.sfc2("The BI-B61 supports Samsung Super Fast Charging 2.0.", "B61", ("BI-B61",)), "an explicit alias (mfr_sku)")
        self.assertTrue(PPS.sfc2("It supports Samsung Super Fast Charging 2.0 for Galaxy S25.", "P73"), "target phones are not products")


def ups_row(v):
    pr = C.ParseResult()
    snap = C.Snapshot("sha256:x", C.Ref("x", "r", "https://x", {}), 200, "2026-11-26T00:00:00Z", "https://x", {})
    PS.emit_rows(pr, "x@1", snap, "Explorer 1000", {"UPS Switchover Time": v}, "spec")
    return [(c.get("value"), c["status"]) for c in pr.claims if c["key"] == "ups.switchover_ms"]


def ups_prose(sent):
    return PS.ups_prose(f"<p>UPS switchover {sent}.</p>", ("Explorer 1000",))[0]


class UpsAlternativesAndLowerBounds(unittest.TestCase):
    NEVER_EXACT = ("10 ms or 20 ms", "10ms or 20ms", "10 or 20 ms", "10 ms / 20 ms", "10 ms, 20 ms", "10 ms and 20 ms", "<10 ms or 20 ms",
                   "10-20 ms", "10 ms - 20 ms", "10 ms ~ 20 ms", "10 to 20 ms", "between 10 and 20 ms",
                   "20 ms or over", "20 ms or above", "20 ms and over", "20 ms or more", "20 ms or longer", "20 ms and higher", "20 ms+",
                   ">=20ms", ">= 20 ms", "=>20 ms", "≥20ms", "&gt;=20ms", "at least 20 ms", "over 20 ms", "min. 20 ms")

    def test_rows_never_exact(self):
        for v in self.NEVER_EXACT:
            got = ups_row(v)
            self.assertTrue(all(st != "known" for _, st in got), (v, got))
            self.assertFalse([x for x, _ in got if x in (10, 20, "up to 10", "up to 20")], (v, got))

    def test_prose_never_exact(self):
        for v in self.NEVER_EXACT:
            self.assertIsNone(ups_prose(v), v)

    def test_labelled_modes_and_upper_bounds_kept(self):
        self.assertEqual(ups_row("Backup UPS: <20ms, Online UPS: 0ms"), [("up to 20", "known")])
        for v in ("up to 20 ms", "<=20ms", "20 ms or less", "20 ms maximum", "within 20 ms"):
            self.assertEqual(ups_row(v), [("up to 20", "known")], v)
            self.assertEqual(ups_prose(v), "up to 20", v)
        self.assertEqual(ups_row("20ms"), [(20, "known")])
        self.assertEqual(ups_prose("in 20 ms"), 20)


@unittest.skipUnless((ROOT / "raw" / "lenovo-psref").exists() and os.environ.get("SPECSHEET_E2E", "1") != "0", "needs the PSREF raw store")
class EndToEnd(unittest.TestCase):
    """Real PSREF store (import --source lenovo-psref into a throwaway root, data/ copied), built twice:
      control  every policy as in the repo (parents accepted by claim/mfr-structured-datasheet@5, claim/psref-split@1 approved);
      pending  the PARENT policy pending (approval fields only: lock hash unchanged), a pending fixture policy over the Memory Slots
               literal (mem.slots), an approved fixture policy over every other PSREF key so laptops still publish, and claim/psref-split@1
               still approved.
    In 'pending' no psref-split value may reach the trusted store, trusted docs (index, products), the R2 pack (records / bulk / index:
    what /v1/query and the MCP tools serve) or preset counts; the preview keeps them. The control proves each artifact carries them."""
    PARENT_POLICY = "claim/mfr-structured-datasheet@5"
    PARENT_KEYS = {"disp.size", "mem.size", "mem.slots"}           # the literals psref_split derives from (Display, Memory, Memory Slots)
    SPLIT_KEYS = ("disp.panel_type", "disp.nits_sdr", "disp.refresh", "disp.resolution", "mem.soldered", "mem.type")

    @classmethod
    def build(cls, tag, parent_pending):
        t = cls.tmp / tag
        t.mkdir()
        for d in ("research", "raw", "schemas"):
            os.symlink(ROOT / d, t / d)
        (t / "docs").mkdir(); (t / "state").mkdir()
        for f in ("site.json", "presets.json"):
            os.symlink(ROOT / "docs" / f, t / "docs" / f)
        shutil.copytree(ROOT / "data", t / "data")
        pp = t / "data" / "decisions" / "policies.yaml"
        if parent_pending:
            s = pp.read_text()
            i = s.index(f"- id: {cls.PARENT_POLICY}\n"); j = s.index("\n- id:", i + 5)
            blk = re.sub(r"(?m)^  approval: .*$", "  approval: {state: pending}", s[i:j], count=1)
            parent = next(p for p in yaml.safe_load(s)["claim_policies"] if p["id"] == cls.PARENT_POLICY)
            keys = [k for k in parent["match"]["keys"]["lenovo-psref"] if k not in cls.PARENT_KEYS]
            fx = {"id": "claim/e2e-fixture-nonparent@1", "since": "2026-11-26", "rationale": "test fixture: every PSREF key except the split parents",
                  "audit": {"by": "fixture", "at": "2026-11-26", "evidence": "tests/test_review10.py", "parsers": {}}, "approval": APPROVED,
                  "match": dict(parent["match"], source_ids=["lenovo-psref"], keys={"lenovo-psref": keys})}
            slots = {"id": "claim/e2e-fixture-slots@1", "since": "2026-11-26", "rationale": "test fixture: a PENDING policy over the Memory Slots literal",
                     "audit": {"by": "fixture", "at": "2026-11-26", "evidence": "tests/test_review10.py", "parsers": {}}, "approval": {"state": "pending"},
                     "match": dict(parent["match"], source_ids=["lenovo-psref"], keys={"lenovo-psref": ["mem.slots"]})}
            s = s[:i] + blk + s[j:]
            s = s.replace("claim_policies:\n", "claim_policies:\n" + yaml.safe_dump([fx, slots], sort_keys=False), 1)
            pp.write_text(s)
        env = dict(os.environ, SPECSHEET_ROOT=str(t))
        r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "import.py"), "--source", "lenovo-psref", "--data", str(t / "data"),
                            "--db", str(t / "scratch.sqlite")], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        con = sqlite3.connect(t / "scratch.sqlite")
        con.execute("UPDATE meta SET v='full' WHERE k='scope'")      # fixture root: publish the PSREF-only store (v1_publish refuses 'partial')
        con.commit(); con.close()
        (t / "scratch.sqlite").replace(t / "state" / "specsheet.sqlite")
        api = t / "api"
        code = ("import sys, json; sys.path.insert(0, %r); import v1_publish as P, presets; from pathlib import Path; api = Path(%r); "
                "c, m, rel = P.publish(api, {}); (api / 'categories.json').write_text(json.dumps(c)); "
                "json.dump({'categories': m, 'generated_at': '2026-11-26T00:00:00Z'}, open(api / 'manifest.json', 'w')); "
                "src = json.loads(open(%r).read()); src['presets'] = [p for p in src['presets'] if p['category'] == 'laptops']; "
                "(api / 'presets.json').write_text(json.dumps(presets.build(api, c, source=src)))"
                % (str(ROOT / "scripts"), str(api), str(ROOT / "docs" / "presets.json")))
        r = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "build_r2.py"), "--docs", str(api), "--tier", "free", "--out", str(t / "pack"),
                            "--snapshots", str(t / "snaps"), "--releases", str(t / "releases"), "--release", "r10-e2e", "--categories", "laptops",
                            "--no-match"], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        return t

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="specsheet-r10-"))
        cls.ctl = cls.build("control", False)
        cls.pen = cls.build("pending", True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def store(self, t):
        con = sqlite3.connect(t / "state" / "specsheet.sqlite")
        q = lambda w: con.execute("SELECT review, COUNT(*) FROM claims WHERE " + w + " GROUP BY 1").fetchall()
        out = dict(q("extractor='import.py+psref-split@1'")), dict(q("source_id='lenovo-psref' AND mapped_key IN ('disp.size','mem.size','mem.slots') "
                                                                      "AND extractor NOT LIKE 'import.py+%'"))
        con.close()
        return out

    def test_store(self):
        split, parent = self.store(self.ctl)
        self.assertGreater(split.get("accepted", 0), 1000)
        split, parent = self.store(self.pen)
        self.assertEqual(parent.get("accepted", 0), 0, "parents withheld by the pending policy")
        self.assertEqual(split.get("accepted", 0), 0, "every dependent withheld with its parent")
        self.assertGreater(split.get("candidate", 0), 1000, "the dependents exist, as candidates (preview)")

    def found(self, t, preview=False):
        """-> {split key: n} values carried by trusted (or preview) docs and the pack."""
        api, hits = t / "api", collections.Counter()
        base = api / "preview" / "laptops" if preview else api / "laptops"
        for f in sorted(base.glob("index*.json")):
            for r in json.loads(f.read_text()):
                hits.update(("index", k) for k in self.SPLIT_KEYS if (r.get("v") or {}).get(k) is not None)
        for f in (base / "products").glob("*.json"):
            sp = json.loads(f.read_text()).get("specs") or {}
            hits.update(("products", k) for k in self.SPLIT_KEYS if isinstance(sp.get(k), dict) and sp[k].get("value") is not None)
        if not preview:
            for f in (t / "pack").rglob("*"):
                if not f.is_file() or "laptops" not in f.name and "laptops" not in f.parts:
                    continue
                txt = gzip.decompress(f.read_bytes()).decode() if f.suffix == ".gz" else f.read_text()
                docs = [json.loads(x) for x in txt.splitlines() if x.strip()] if ".jsonl" in f.name else [json.loads(txt)]
                for d in docs:
                    for r in (d.values() if isinstance(d, dict) and "specs" not in d and "id" not in d else d if isinstance(d, list) else [d]):
                        if not isinstance(r, dict):
                            continue
                        sp, v = r.get("specs") or {}, r.get("v") or {}
                        hits.update(("pack", k) for k in self.SPLIT_KEYS
                                    if (isinstance(sp.get(k), dict) and sp[k].get("value") is not None) or v.get(k) is not None)
        return hits

    def test_trusted_docs_and_pack(self):
        ctl = self.found(self.ctl)
        self.assertTrue(all(ctl[(w, "mem.soldered")] > 0 for w in ("index", "products", "pack")), ctl)
        self.assertEqual(self.found(self.pen), collections.Counter(), "no dependent value in trusted docs or the pack (MCP / v1 query)")
        self.assertGreater(self.found(self.pen, preview=True)[("products", "mem.soldered")], 0, "preview still shows the candidates")

    def test_preset_counts(self):
        cnt = lambda t: next(p for p in json.loads((t / "api" / "presets.json").read_text())["presets"] if p["id"] == "ram-upgradable")["count"]
        c, p = cnt(self.ctl), cnt(self.pen)
        self.assertGreater(c["matches"], 0, c)
        self.assertGreater(p["total"], 0, "laptops still publish in scope")
        self.assertEqual(p["matches"], 0, p)
        for f in (self.pen / "pack").rglob("presets.json"):
            pr = next((x for x in json.loads(f.read_text()).get("presets", []) if x.get("id") == "ram-upgradable"), None)
            if pr and isinstance(pr.get("count"), dict):
                self.assertEqual(pr["count"].get("matches", 0), 0, f)


if __name__ == "__main__":
    unittest.main()
