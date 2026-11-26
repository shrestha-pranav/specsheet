"""A3-impl r8: certification-only rows + air-purifier identity follow-ups, each coordinator decision as a fixture.

1. Certification-only rows (profile index_rows, scripts/catmeta.py + v1_publish.py): an entity whose trusted values are all certification keys
   is not a default index row, but keeps its detail file, id and lookup entries and is a row of the compact index-certonly shard; a category
   without index_rows is unchanged; the two key lists must partition the profile.
2. Crosswalks (scripts/xwalk.py, feature model_crosswalks): a reviewed pair whose quote names both strings links same_model without a merge;
   unevidenced / one-string / market / contradictory / disagreeing pairs are rejected; proposals are possible_match only.
3. Declared same hardware (feature same_hardware_relations): an ES declared alias that is another entity's key gets same_hardware_as, no merge;
   over an approved edge only eff.energy_star (dated) transfers; conflict, market, undated, several-bases and model_variant cases transfer nothing.
4. Policies: the new r8 ids are pending (or human-approved), allowlists explicit, transfer keys are certification keys; production
   crosswalks hold no pair.
  python3 -I tests/test_r8.py
"""
import copy, hashlib, json, os, shutil, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

import yaml

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "scripts"))
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
import catmeta  # noqa: E402
import decisions as D  # noqa: E402
import xwalk as XW  # noqa: E402

NEW = ("claim/air-purifiers-es-same-hardware@1", "rel/air-purifiers-es-same-hardware@1", "rel/air-purifiers-crosswalk@1")


class Partition(unittest.TestCase):
    PROF = {"specs": [{"key": "a.x"}, {"key": "a.y"}, {"key": "c.z"}]}

    def test_absent_rule_is_none(self):
        self.assertIsNone(catmeta.substantive_keys("t", self.PROF))

    def test_exact_partition(self):
        p = dict(self.PROF, index_rows={"substantive_keys": ["a.x", "a.y"], "certification_keys": ["c.z"]})
        self.assertEqual(catmeta.substantive_keys("t", p), {"a.x", "a.y"})

    def test_missing_overlap_or_unknown_key_fails(self):
        for sub, cert in ((["a.x"], ["c.z"]), (["a.x", "a.y"], ["a.y", "c.z"]), (["a.x", "a.y", "q.q"], ["c.z"])):
            with self.assertRaises(SystemExit):
                catmeta.substantive_keys("t", dict(self.PROF, index_rows={"substantive_keys": sub, "certification_keys": cert}))

    def test_air_purifiers_declare_carb_and_es_membership_as_certification(self):
        m = catmeta.load("air-purifiers")
        cert = set(m["profile"]["index_rows"]["certification_keys"])
        self.assertEqual(cert, {"ozone.carb_certified", "ozone.carb_type", "ozone.carb_date", "ozone.carb_eo", "eff.energy_star",
                                "eff.most_efficient", "cert.maker_listed"})
        self.assertTrue({"cadr.smoke_cfm", "ozone.es_emissions_ppb", "pwr.annual_kwh"} <= m["substantive"], "measured values are substantive")
        self.assertTrue(set(m["same_hardware"]["transfer_keys"]) <= cert)


class Pure(unittest.TestCase):
    class E:
        def __init__(self, claims=()):
            self.claims = [({"key": k, "status": "known", "value": v}, None) for k, v in claims]
            self.extra = {}

    def setUp(self):
        self.a, self.b = self.E([("ozone.carb_type", "mechanical")]), self.E([("ozone.carb_type", "mechanical")])
        self.models = {("lv", "CORE 40"): (self.a, "US"), ("lv", "LAP-40-US"): (self.b, "US")}

    def pair(self, **kw):
        p = {"brand": "lv", "a": "Core 40", "b": "LAP-40-US", "market": "US", "by": "human", "at": "2026-11-24",
             "evidence": {"url": "https://example.invalid/p", "quote": "Model: Core 40 (label LAP-40-US)"}}
        p.update(kw)
        return p

    def check(self, p, others=()):
        import collections
        partner = collections.defaultdict(set)
        for q in (p,) + tuple(others):
            partner[(q["brand"], XW._sq(q["a"]))].add(XW._sq(q["b"])); partner[(q["brand"], XW._sq(q["b"]))].add(XW._sq(q["a"]))
        return XW.check_pair(p, self.models, partner, ["ozone.carb_type"])[0]

    def test_good_pair(self):
        self.assertIsNone(self.check(self.pair()))

    def test_fail_closed(self):
        self.assertIn("human", self.check(self.pair(by=None)))
        self.assertIn("human", self.check(self.pair(at=None)))
        self.assertIn("both exact strings", self.check(self.pair(evidence={"url": "https://x.invalid", "quote": "Core 40 only"})))
        self.assertIn("must exist", self.check(self.pair(b="LAP-41-US", evidence={"url": "u", "quote": "Core 40 LAP-41-US"})))
        self.assertIn("market", self.check(self.pair(market=None)))
        self.assertIn("contradictory", self.check(self.pair(), [self.pair(b="LAP-40-CA")]))
        self.b.claims = [({"key": "ozone.carb_type", "status": "known", "value": "electronic"}, None)]
        self.assertIn("disagree", self.check(self.pair()))

    def test_declaration_wording(self):
        ok = ["4312112000 is same as 4312111000, except for color.", "Identical except model number and color",
              "ModelKJ600F-LM1-SH and SAP5682SAW are identical except for the model name"]
        bad = ["C610 identical in performance, only difference is the colour", "X2 is a derivative of X1", "X2 is not the same as X1",
               "X2 is the same as X1 except for the filter"]
        for c in ok:
            self.assertTrue(XW.AFFIRM.search(c) and not XW.NEGATE.search(c), c)
        for c in bad:
            self.assertFalse(XW.AFFIRM.search(c) and not XW.NEGATE.search(c), c)

    def test_transfer_keys_must_be_certification(self):
        class W:
            category = "t"
            meta = {"features": ["same_hardware_relations"], "same_hardware": {"source": "s", "transfer_keys": ["cadr.smoke_cfm"]},
                    "profile": {"index_rows": {"certification_keys": ["eff.energy_star"]}}}
        with self.assertRaises(SystemExit):
            XW.apply(W(), {}, {})


class Policies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dec = D.Decisions(CODE / "data")
        cls.pol = {p["id"]: p for p in cls.dec.claim_policies + cls.dec.relation_policies + cls.dec.retired_policies}

    def test_new_policies_pending_or_human_approved(self):
        for i in NEW:
            a = self.pol[i]["approval"]
            self.assertTrue(a["state"] == "pending" and a["by"] is None and a["at"] is None or a["state"] == "approved" and a.get("by") and a.get("at"), i)

    def test_allowlists_explicit_and_pinned(self):
        c = self.pol["claim/air-purifiers-es-same-hardware@1"]["match"]
        self.assertEqual((c["extractors"], c["keys"]), (["energystar_airpurifiers_same_hardware@1"], {"energystar-airpurifiers": ["eff.energy_star"]}))
        self.assertNotIn("energystar_airpurifiers_same_hardware@1", self.pol["claim/air-purifiers-structured@1"]["match"]["extractors"])
        r = self.pol["rel/air-purifiers-es-same-hardware@1"]["rules"]
        self.assertEqual(r, [{"method": "es-declared:exact", "types": ["same_hardware_as"], "parsers": ["energystar_airpurifiers@1+xwalk@1"]}])
        self.assertEqual(self.pol["rel/air-purifiers-crosswalk@1"]["rules"][0]["parsers"], ["xwalk@1"])
        for i in NEW:
            self.assertEqual(self.pol[i]["audit"]["parsers"]["xwalk@1"], XW.fingerprint(), f"{i}: xwalk.py changed since the audit")

    def test_production_crosswalks_hold_no_pair(self):
        doc = yaml.safe_load((CODE / "data" / "decisions" / "air-purifier-crosswalks.yaml").read_text())
        self.assertEqual(doc["pairs"], [], "no source prints both namespaces: proposals only")
        self.assertTrue(all(not p.get("by") for p in doc["proposals"]))


# ----------------------------------------------------------------------------- fixture data root
PROFILE = """
profile_format: specsheet.category-profile/1
category: apx
version: 0.1.0
label: Purifiers
identity: {levels: [family, model], primary_key: manufacturer model number}
index_rows:
  substantive_keys: [cadr.smoke_cfm]
  certification_keys: [ozone.carb_certified, ozone.carb_type, eff.energy_star]
groups: [{id: general, label: General}]
specs:
  - {key: cadr.smoke_cfm, label: Smoke CADR, group: general, type: number, unit: cfm, tier: core, level: model, facet: {kind: range, bins: [100]}, sources: [x]}
  - {key: ozone.carb_certified, label: CARB, group: general, type: bool, tier: core, level: model, facet: {kind: bool}, sources: [x]}
  - {key: ozone.carb_type, label: CARB type, group: general, type: enum, enum: [mechanical, electronic], tier: important, level: model, facet: {kind: enum}, sources: [x]}
  - {key: eff.energy_star, label: ENERGY STAR, group: general, type: bool, tier: important, level: model, facet: {kind: bool}, sources: [x]}
"""
NOX_PROFILE = """
profile_format: specsheet.category-profile/1
category: nox
version: 0.1.0
label: No rule
identity: {levels: [family, model], primary_key: manufacturer model number}
groups: [{id: general, label: General}]
specs:
  - {key: ozone.carb_certified, label: CARB, group: general, type: bool, tier: core, level: model, facet: {kind: bool}, sources: [x]}
"""
CAT = """
name: Purifiers
description: Fixture.
columns: [cadr.smoke_cfm, eff.energy_star]
features: [model_crosswalks, same_hardware_relations]
crosswalks: {file: apx-crosswalks.yaml, compare_keys: [ozone.carb_type, cadr.smoke_cfm]}
same_hardware: {source: es-apx, extractor: esa_same_hardware@1, transfer_keys: [eff.energy_star], compare_keys: [ozone.carb_type, cadr.smoke_cfm]}
identity_scope: {cross_market_brands: "*", market_scoped_brands: []}
"""
NOX_CAT = """
name: No rule
description: Fixture.
columns: [ozone.carb_certified]
identity_scope: {cross_market_brands: "*", market_scoped_brands: []}
"""
CROSSWALKS = """
format: specsheet.model-crosswalks/1
pairs:
  - {brand: bx, a: Core 40, b: LAP-40-US, market: US, by: fixture-human, at: '2026-11-24',
     evidence: {url: 'https://example.invalid/core40', quote: 'Model: Core 40 / label code LAP-40-US'}}
  - {brand: bx, a: Core 50, b: LAP-50-US, market: US, by: fixture-human, at: '2026-11-24', evidence: {url: 'https://example.invalid/x', quote: 'Core 50 only'}}
proposals:
  - {brand: bx, a: Core 60, b: LAP-60-US, why: fixture}
"""


def claim(key, value, ex, loc=None, unit=None):
    return {"key": key, "status": "known", "kind": "official", "unit": unit, "raw": f"{key}={value}", "source": "s1",
            "method": {"stage": "table", "extractor": ex}, "observed_at": "2026-11-23T00:00:00Z", "value": value, "locator": loc or {}}


def page(model, claims, aliases=(), tier="manufacturer", pd=None, market="US"):
    ids = [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "bx", "market": market, "package_level": "model", "role": "key", "sources": ["s1"]}]
    if pd:
        ids.append({"scheme": "x_energystar_pd_id", "value": pd, "value_raw": pd, "issuer": "energystar", "sources": ["s1"]})
    return {"identifiers": ids, "aliases": [{"text": t, "kind": k} for t, k in aliases], "claims": claims, "media": [], "documents": [],
            "absences": [], "links": [], "fingerprints": {}, "sources": [{"id": "s1", "url": f"https://example.invalid/{model}", "label": "page", "tier": tier}]}


def es(model, pd, ami, aliases, markets="United States", dated=True, cadr=200):
    loc = {"energystar_pd_id": pd, "date_certified": "2025-06-23" if dated else ""}
    cl = [claim("cadr.smoke_cfm", cadr, "esa@1", loc, "cfm"), claim("eff.energy_star", True, "esa@1", loc), claim("ozone.carb_type", "mechanical", "esa@1", loc)]
    return page(model, cl, aliases, "regulatory", pd), {"pd_id": pd, "model_number": model, "additional_model_information": ami, "markets": markets}


ES = [
    es("B-100", "1001", "B-100C,B-100C,B-100C is same as B-100, except for color.; B-100D,B-100D,B-100D is same as B-100, except for color.; B-100E",
       [("B-100C", "declared_same_hardware"), ("B-100D", "declared_same_hardware"), ("B-100E", "model_variant")]),
    es("B-200", "1002", "B-200C, identical except model number", [("B-200C", "declared_same_hardware")], markets="Canada"),
    es("B-300", "1003", "B-3C, identical except model number", [("B-3C", "declared_same_hardware")]),
    es("B-301", "1004", "B-3C, identical except model number", [("B-3C", "declared_same_hardware")]),
    es("B-400", "1005", "B-400C, identical except model number", [("B-400C", "declared_same_hardware")], dated=False),
    es("B-500", "1006", "B-500C performs identical in performance, only difference is the colour", [("B-500C", "declared_same_hardware")]),
]
CARB = [(m, t) for m, t in (("B-100", "mechanical"), ("B-100C", "mechanical"), ("B-100D", "electronic"), ("B-100E", "mechanical"), ("B-200C", "mechanical"),
                            ("B-3C", "mechanical"), ("B-400C", "mechanical"), ("B-500C", "mechanical"), ("Z-9", "mechanical"), ("LAP-40-US", "mechanical"),
                            ("LAP-50-US", "mechanical"), ("LAP-60-US", "mechanical"))]
MFR = [("Core 40", 150), ("Core 50", 160), ("Core 60", 170)]


FIXTURE_APPROVAL = {"state": "approved", "by": "fixture-approver", "at": "2026-11-26"}   # 2026-11-26 gate: only approved policies auto-accept


def policies():
    real = {p["id"]: p for p in (lambda d: d["claim_policies"] + d["relation_policies"])(yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text()))}
    shc, shr, xw = (copy.deepcopy(real[i]) for i in NEW)        # the REAL allowlists / rules, re-pointed at the fixture source ids
    shc["match"].update(extractors=["esa_same_hardware@1"], source_ids=["es-apx"], keys={"es-apx": shc["match"]["keys"]["energystar-airpurifiers"]})
    shr["rules"][0]["parsers"] = ["esa@1+xwalk@1"]
    fx = lambda i, ex, sid, tier, keys: {"id": i, "since": "2026-11-24", "rationale": "fixture", "approval": FIXTURE_APPROVAL, "match": {
        "extractors": [ex], "source_ids": [sid], "kinds": ["official"], "tiers": [tier], "statuses": ["known"], "require_normalized": False, "keys": keys}}
    return {"format": "specsheet.policies/2", "claim_policies": [
        fx("claim/fx-es@1", "esa@1", "es-apx", "regulatory", ["cadr.smoke_cfm", "eff.energy_star", "ozone.carb_type"]),
        fx("claim/fx-carb@1", "carba@1", "carb-apx", "regulatory", ["ozone.carb_certified", "ozone.carb_type"]),
        fx("claim/fx-mfr@1", "mfra@1", "mfr-apx", "manufacturer", ["cadr.smoke_cfm"]),
        fx("claim/fx-nox@1", "noxa@1", "nox-src", "regulatory", ["ozone.carb_certified"]), shc],
        "relation_policies": [shr, xw]}


def write_source(t, sid, rows, raw=None):
    d = t / "raw" / sid
    (d / "parsed").mkdir(parents=True)
    (d / "blobs").mkdir()
    log = []
    for n, pr in enumerate(rows):
        (d / "parsed" / f"r{n}.json").write_text(json.dumps(pr))
        h = hashlib.sha256(f"{sid}|{n}".encode()).hexdigest()
        if raw:
            (d / "blobs" / f"{h}.json").write_text(json.dumps([raw[n]]))
        log.append({"snapshot": f"sha256:{h}", "ref": f"r{n}", "url": pr["sources"][0]["url"], "final_url": pr["sources"][0]["url"], "status": 200,
                    "fetched_at": "2026-11-23T00:00:00Z", "etag": None, "last_modified": None, "adapter": "fixture@1", "blob": f"blobs/{h}.json"})
    (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = t = Path(tempfile.mkdtemp(prefix="specsheet-r8-"))
        os.symlink(CODE / "schemas", t / "schemas")
        for cat, prof, cm in (("apx", PROFILE, CAT), ("nox", NOX_PROFILE, NOX_CAT)):
            (t / "research" / cat).mkdir(parents=True)
            (t / "research" / cat / "spec-profile.yaml").write_text(prof)
            (t / "research" / cat / "category.yaml").write_text(cm)
        dd = t / "data" / "decisions"
        dd.mkdir(parents=True)
        (dd / "policies.yaml").write_text(yaml.safe_dump(policies(), sort_keys=False))
        (dd / "ledger.jsonl").write_text("")
        (dd / "apx-crosswalks.yaml").write_text(CROSSWALKS)
        src = lambda cat, p: {"brand": "bx", "brand_name": "BX", "category": cat, "module": "none", "importer": "model", "parser": p}
        (t / "sources.extra.json").write_text(json.dumps({"es-apx": src("apx", "esa@1"), "carb-apx": src("apx", "carba@1"), "mfr-apx": src("apx", "mfra@1"),
                                                          "nox-src": src("nox", "noxa@1")}))
        write_source(t, "es-apx", [p for p, _ in ES], [r for _, r in ES])
        write_source(t, "carb-apx", [page(m, [claim("ozone.carb_certified", True, "carba@1"), claim("ozone.carb_type", ty, "carba@1")], tier="regulatory")
                                     for m, ty in CARB])
        write_source(t, "mfr-apx", [page(m, [claim("cadr.smoke_cfm", v, "mfra@1", unit="cfm")]) for m, v in MFR])
        write_source(t, "nox-src", [page("N-1", [claim("ozone.carb_certified", True, "noxa@1")], tier="regulatory")])
        env = dict(os.environ, SPECSHEET_ROOT=str(t))
        imp = lambda *a: subprocess.run([sys.executable, "-I", str(CODE / "scripts" / "import.py"), "--data", str(t / "data"), *a],
                                        env=env, capture_output=True, text=True)
        r = imp(); assert r.returncode == 0, r.stderr[-3000:]
        cls.reg1 = (t / "data" / "_ids" / "registry.jsonl").read_text()
        r = imp("--no-mint"); assert r.returncode == 0, r.stderr[-3000:]
        cls.con = sqlite3.connect(t / "state" / "specsheet.sqlite"); cls.con.row_factory = sqlite3.Row
        code = ("import sys, json; sys.path.insert(0, %r); import v1_publish as P; from pathlib import Path; st = {}; "
                "c, m, _ = P.publish(Path(%r), st); print(json.dumps({'stats': st, 'cats': c}))" % (str(CODE / "scripts"), str(t / "api")))
        r = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        cls.pub = json.loads(r.stdout)
        cls.api = t / "api"
        cls.ids = {r["value_raw"]: r["entity_id"] for r in cls.con.execute("SELECT * FROM identifiers WHERE scheme='mfr_model' AND role='key'")}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def j(self, *p):
        return json.loads((self.api.joinpath(*p)).read_text())

    def ex(self, model):
        return json.loads(self.con.execute("SELECT extra FROM entities WHERE id=?", (self.ids[model],)).fetchone()[0] or "{}")

    def rel(self, model, typ):
        return [dict(r) for r in self.con.execute("SELECT * FROM relations WHERE entity_id=? AND type=?", (self.ids[model], typ))]

    def accepted(self, model, key):
        return [dict(r) for r in self.con.execute("SELECT * FROM claims WHERE entity_id=? AND mapped_key=? AND review='accepted'", (self.ids[model], key))]

    # --------------------------------------------------------------- 1 certification-only rows
    def test_certonly_not_a_default_row_but_published(self):
        cat = next(c for c in self.pub["cats"] if c["id"] == "apx")
        rows = {r["id"] for p in cat["index"] for r in self.j(p)}
        crows = [r for p in cat["certification_only"]["index"] for r in self.j(p)]
        cids = {r["id"] for r in crows}
        self.assertEqual(cat["certification_only"]["count"], len(crows))
        self.assertEqual(cat["count"], len(rows))
        z = self.ids["Z-9"]
        self.assertNotIn(z, rows); self.assertIn(z, cids)
        self.assertFalse(rows & cids)
        self.assertIn(self.ids["B-100"], rows); self.assertIn(self.ids["Core 40"], rows)
        d = self.j("apx", "products", f"{z}.json")
        self.assertEqual(d["index_scope"], "certification_only")
        self.assertNotIn("index_scope", self.j("apx", "products", f"{self.ids['B-100']}.json"))
        lookup = self.j("lookup", "identifiers.json")
        self.assertIn(z, lookup["mfr_model:Z9"], "certonly entities stay in the identifier lookup")
        for r in crows:
            self.assertEqual(r["scope"], "certification_only")
            self.assertTrue(set(r["v"]) <= {"ozone.carb_certified", "ozone.carb_type", "eff.energy_star"})
            self.assertNotIn("s", r)
        f = self.j("apx", "facets.json")
        self.assertEqual(sum(f["ozone.carb_certified"]["counts"].values()) + f["ozone.carb_certified"]["not_yet_extracted"], len(rows), "facets over default rows")
        self.assertEqual(self.pub["stats"]["apx"]["certonly_rows"], len(crows))

    def test_category_without_rule_unchanged(self):
        cat = next(c for c in self.pub["cats"] if c["id"] == "nox")
        self.assertNotIn("certification_only", cat)
        self.assertEqual([r["id"] for p in cat["index"] for r in self.j(p)], [self.ids["N-1"]])

    def test_ids_stable_on_replay(self):
        self.assertEqual((self.tmp / "data" / "_ids" / "registry.jsonl").read_text(), self.reg1)

    # --------------------------------------------------------------- 2 crosswalks
    def test_reviewed_pair_links_without_merge(self):
        r = self.rel("Core 40", "same_model")
        self.assertEqual([(x["target_id"], x["status"], x["method"]) for x in r], [(self.ids["LAP-40-US"], "approved", "crosswalk:reviewed")])
        self.assertNotEqual(self.ids["Core 40"], self.ids["LAP-40-US"])
        self.assertEqual([x["status"] for x in self.ex("LAP-40-US")["crosswalks"]], ["linked"])
        self.assertFalse(self.accepted("LAP-40-US", "cadr.smoke_cfm"), "nothing transfers over same_model")
        rel = [x for x in self.j("apx", "products", f"{self.ids['Core 40']}.json")["relations"] if x["type"] == "same_model"]
        self.assertEqual(rel[0]["target"], self.ids["LAP-40-US"])

    def test_unevidenced_pair_rejected_and_proposal_only_possible_match(self):
        self.assertFalse(self.rel("Core 50", "same_model"))
        self.assertIn("both exact strings", self.ex("Core 50")["crosswalks"][0]["reason"])
        p = self.rel("Core 60", "possible_match")
        self.assertEqual([(x["target_id"], x["status"], x["method"]) for x in p], [(self.ids["LAP-60-US"], "proposed", "crosswalk:proposal")])

    # --------------------------------------------------------------- 3 declared same hardware
    def test_exact_declaration_transfers_only_dated_certification(self):
        r = self.rel("B-100C", "same_hardware_as")
        self.assertEqual([(x["target_id"], x["status"], x["method"]) for x in r], [(self.ids["B-100"], "approved", "es-declared:exact")])
        self.assertNotEqual(self.ids["B-100C"], self.ids["B-100"], "no merge")
        es = self.accepted("B-100C", "eff.energy_star")
        self.assertEqual(len(es), 1)
        self.assertEqual(es[0]["extractor"], "esa_same_hardware@1")
        self.assertEqual(json.loads(es[0]["locator"])["same_hardware_of"], "B-100")
        self.assertIn("2025-06-23", es[0]["raw"])
        self.assertFalse(self.accepted("B-100C", "cadr.smoke_cfm"), "measured CADR never transfers")
        d = self.j("apx", "products", f"{self.ids['B-100C']}.json")
        self.assertEqual(d["same_hardware"][0]["transferred"], ["eff.energy_star"])
        self.assertEqual(d["index_scope"], "certification_only", "a transferred certification is still not substantive")
        base = self.j("apx", "products", f"{self.ids['B-100']}.json")
        self.assertIn(("certified_base", self.ids["B-100C"], "approved"), [(x["role"], x.get("alias_id"), x["status"]) for x in base["same_hardware"]])

    def test_fail_closed_cases_transfer_nothing(self):
        for model, method in (("B-100D", "es-declared:conflict"), ("B-200C", "es-declared:market"), ("B-3C", "es-declared:several-bases"),
                              ("B-400C", "es-declared:undated"), ("B-500C", "es-declared:not-exact")):
            r = self.rel(model, "same_hardware_as")
            self.assertTrue(r and all(x["status"] == "proposed" and x["method"] == method for x in r), (model, r))
            self.assertFalse(self.accepted(model, "eff.energy_star"), model)
            d = self.j("apx", "products", f"{self.ids[model]}.json")
            self.assertNotIn("same_hardware", d, "trusted details list approved edges only")
        self.assertFalse(self.rel("B-100E", "same_hardware_as"), "model_variant aliases get no edge")
        self.assertTrue(self.con.execute("SELECT 1 FROM identity_conflicts WHERE value='B-100D'").fetchone(), "conflict listed for review")


if __name__ == "__main__":
    unittest.main(verbosity=1)
