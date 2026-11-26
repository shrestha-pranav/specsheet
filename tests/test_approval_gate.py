"""A3-gov 2026-11-26: policy approval is ENFORCED, not metadata (incident: pending claim/mfr-monitor-aoc@3 auto-accepted for ~1h).

Only a policy whose approval is {state: approved, by, at} auto-accepts claims / approves relations. A pending (or missing, or
half-filled) approval leaves its claims candidates (preview only, never in the trusted index) and its relations proposed, and the import
output lists it under governance.held_by_pending with the claim/relation counts that approval would publish. Approving it (filling
`approval` only; the lock hash is unchanged) makes the same claims accepted on the next build.

Unit level (decisions.Decisions) plus one throwaway data root reusing the tests/test_new_category.py fixture, imported + published twice:
first with every policy pending, then after approving them.

  python3 -I tests/test_approval_gate.py
"""
import json, os, shutil, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

import yaml

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "scripts"))
sys.path.insert(0, str(CODE / "tests"))
import decisions as D  # noqa: E402
import test_new_category as NC  # noqa: E402    fixture profile/category/rows only

APPROVED = {"state": "approved", "by": "fixture-approver", "at": "2026-11-26"}
CPOL = {"id": "claim/g@1", "since": "2026-11-26", "rationale": "fixture", "approval": {"state": "pending", "by": None, "at": None},
        "match": {"extractors": ["xa@1"], "source_ids": ["xs"], "kinds": ["official"], "statuses": ["known"], "keys": {"xs": ["gen.a"]}}}
RPOL = {"id": "rel/g@1", "since": "2026-11-26", "rationale": "fixture", "approval": {"state": "pending", "by": None, "at": None},
        "rules": [{"method": "adapter:xs", "types": ["configuration_of"], "parsers": ["xa@1"]}]}
CTX = {"source_id": "xs", "extractor": "xa@1", "key": "gen.a", "kind": "official", "status": "known", "normalized": True}


class Unit(unittest.TestCase):
    def dec(self, capp, rapp):
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True)
        (d / "decisions").mkdir()
        doc = {"format": "specsheet.policies/2", "claim_policies": [dict(CPOL, approval=capp)], "relation_policies": [dict(RPOL, approval=rapp)]}
        (d / "decisions" / "policies.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
        return D.Decisions(d)

    def test_pending_holds_back_and_counts(self):
        dec = self.dec(CPOL["approval"], RPOL["approval"])
        self.assertEqual(dec.claim_state("c1", CTX), ("candidate", None))
        self.assertEqual(dec.claim_state("c2", CTX), ("candidate", None))
        self.assertEqual(dec.relation_state("a", "configuration_of", "b", "adapter:xs", "xa@1"), ("proposed", None))
        self.assertEqual(dec.held, {"claim/g@1": {"claims": 2, "relations": 0}, "rel/g@1": {"claims": 0, "relations": 1}})

    def test_approved_accepts(self):
        dec = self.dec(APPROVED, APPROVED)
        self.assertEqual(dec.claim_state("c1", CTX), ("accepted", "claim/g@1"))
        self.assertEqual(dec.relation_state("a", "configuration_of", "b", "adapter:xs", "xa@1"), ("approved", "rel/g@1"))
        self.assertEqual(dec.held, {})

    def test_half_filled_or_missing_approval_is_not_approval(self):
        for app in ({"state": "approved", "by": "x", "at": None}, {"state": "approved", "by": None, "at": "2026-11-26"},
                    {"state": "approved"}, {"state": "pending", "by": "x", "at": "2026-11-26"}, None, {}):
            dec = self.dec(app, app)
            self.assertEqual(dec.claim_state("c1", CTX)[0], "candidate", app)
            self.assertEqual(dec.relation_state("a", "configuration_of", "b", "adapter:xs", "xa@1")[0], "proposed", app)

    def test_pending_policy_still_validated(self):
        glob = dict(RPOL, rules=[{"method": "adapter:*", "types": ["configuration_of"], "parsers": ["xa@1"]}])
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True); (d / "decisions").mkdir()
        (d / "decisions" / "policies.yaml").write_text(yaml.safe_dump({"claim_policies": [], "relation_policies": [glob]}))
        with self.assertRaises(SystemExit):
            D.Decisions(d)

    def test_approved_later_policy_wins_and_is_not_counted_as_held(self):
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True); (d / "decisions").mkdir()
        doc = {"claim_policies": [CPOL, dict(CPOL, id="claim/g@2", approval=APPROVED)], "relation_policies": []}
        (d / "decisions" / "policies.yaml").write_text(yaml.safe_dump(doc))
        dec = D.Decisions(d)
        self.assertEqual(dec.claim_state("c1", CTX), ("accepted", "claim/g@2"))
        self.assertEqual(dec.held, {})

    def test_incomplete_approval_reported(self):
        dec = self.dec({"state": "approved", "by": "x", "at": None}, APPROVED)
        self.assertEqual(dec.approvals(), {"claim/g@1": "approved-incomplete", "rel/g@1": "approved"})

    def test_ledger_decision_unaffected(self):
        dec = self.dec(CPOL["approval"], RPOL["approval"])
        dec.claims["c9"] = {"id": "d_1", "action": "accept_claim", "claim": "c9", "by": "pranav"}
        self.assertEqual(dec.claim_state("c9", CTX), ("accepted", "d_1"))


class Build(unittest.TestCase):
    """The NC fixture with every policy pending, then approved (approval fields only)."""

    @classmethod
    def run_build(cls, tag):
        env = dict(os.environ, SPECSHEET_ROOT=str(cls.tmp))
        r = subprocess.run([sys.executable, "-I", str(CODE / "scripts" / "import.py"), "--data", str(cls.tmp / "data")], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        imp = json.loads(r.stdout[r.stdout.index("{"):])
        api = cls.tmp / f"api-{tag}"
        code = ("import sys, json; sys.path.insert(0, %r); import v1_publish as P; from pathlib import Path; P.publish(Path(%r), {})"
                % (str(CODE / "scripts"), str(api)))
        r = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        con = sqlite3.connect(cls.tmp / "state" / "specsheet.sqlite")
        rels = {(e, t, x, s) for e, t, x, s in con.execute("SELECT entity_id, type, target_id, status FROM relations")}
        con.close()
        return imp, api, rels

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="specsheet-gate-"))
        t = cls.tmp
        os.symlink(CODE / "schemas", t / "schemas")
        (t / "research" / "widgets").mkdir(parents=True)
        (t / "research" / "widgets" / "spec-profile.yaml").write_text(NC.PROFILE)
        (t / "research" / "widgets" / "category.yaml").write_text(NC.CATEGORY)
        (t / "data" / "decisions").mkdir(parents=True)
        pol = yaml.safe_load(NC.POLICIES)
        for p in pol["claim_policies"] + pol["relation_policies"]:
            p["approval"] = {"state": "pending", "by": None, "at": None}
        pp = t / "data" / "decisions" / "policies.yaml"
        pp.write_text(yaml.safe_dump(pol, sort_keys=False))
        (t / "data" / "decisions" / "ledger.jsonl").write_text("")
        (t / "sources.extra.json").write_text(json.dumps({
            "widgetco-us": {"brand": "widgetco", "brand_name": "WidgetCo", "category": "widgets", "module": "none", "importer": "model", "parser": "widgetco@1"},
            "widget-cert": {"brand": "certbody", "brand_name": "Cert Body", "category": "widgets", "module": "none", "importer": "model", "parser": "widgetcert@1"}}))
        rev = {"scheme": "hw_rev", "value": "B", "value_raw": "B", "issuer": "widgetco", "package_level": "revision", "role": "key", "sources": ["s1"]}
        v = lambda lab: {"scheme": "hw_version", "value": f"W-500 {lab}", "value_raw": f"W-500 {lab}", "issuer": "widgetco", "package_level": "revision",
                         "role": "key", "sources": ["s1"], "revision_label": lab}
        rows = {"widgetco-us": [NC.parsed("W-500", "US", "manufacturer", [("gen.size", 12, "in"), ("gen.kind", "alpha", None)], "widgetco@1", extra_ids=[v("V1"), v("V2")]),
                                NC.parsed("W-100", "US", "manufacturer", [("gen.size", 12, "in"), ("gen.kind", "alpha", None)], "widgetco@1"),
                                NC.parsed("W-200-B", "US", "manufacturer", [("gen.size", 24, "in")], "widgetco@1", extra_ids=[rev])],
                "widget-cert": [NC.parsed("w-100", None, "certifier", [("cert.tier", "gold", None)], "widgetcert@1")]}
        for src, items in rows.items():
            d = t / "raw" / src
            (d / "parsed").mkdir(parents=True)
            log = []
            for n, pr in enumerate(items):
                (d / "parsed" / f"r{n}.json").write_text(json.dumps(pr))
                log.append({"snapshot": f"sha256:{n + (0 if src == 'widgetco-us' else 100):064x}", "ref": f"r{n}", "url": pr["sources"][0]["url"],
                            "final_url": pr["sources"][0]["url"], "status": 200, "fetched_at": "2026-11-23T00:00:00Z", "etag": None,
                            "last_modified": None, "adapter": "fixture@1", "blob": f"blobs/{n:064x}.json"})
            (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
        cls.imp1, cls.api1, cls.rels1 = cls.run_build("pending")
        lock_before = (t / "data" / "decisions" / "policy-lock.jsonl").read_text()
        for p in pol["claim_policies"] + pol["relation_policies"]:
            p["approval"] = dict(APPROVED)
        pp.write_text(yaml.safe_dump(pol, sort_keys=False))
        cls.imp2, cls.api2, cls.rels2 = cls.run_build("approved")
        cls.lock_unchanged = lock_before == (t / "data" / "decisions" / "policy-lock.jsonl").read_text()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def idx(self, api, preview=False):
        return {r["id"]: r for r in json.loads((api / ("preview/widgets" if preview else "widgets") / "index.json").read_text())}

    def test_pending_claims_are_candidates_preview_only(self):
        rv = self.imp1["claims_review"]["widgets"]
        self.assertEqual(rv.get("accepted", 0), 0, rv)
        self.assertGreater(rv.get("candidate", 0), 0)
        self.assertEqual(self.idx(self.api1), {}, "nothing from a pending policy reaches the trusted index")
        prev = self.idx(self.api1, preview=True)
        self.assertEqual(prev["widgetco-w-100"]["v"].get("gen.size"), 12, "pending claims are visible in preview")

    def test_approving_accepts_next_build(self):
        self.assertTrue(self.lock_unchanged, "approval does not change the policy hash")
        self.assertEqual(self.imp2["claims_review"]["widgets"].get("candidate", 0), 0)
        self.assertEqual(self.imp2["claims_review"]["widgets"]["accepted"], self.imp1["claims_review"]["widgets"]["candidate"])
        rows = self.idx(self.api2)
        self.assertEqual(rows["widgetco-w-100"]["v"], {"gen.size": 12, "gen.kind": "alpha", "cert.tier": "gold"})

    def test_pending_relation_policy_stays_proposed(self):
        adapter = lambda rels, st: {(e, t, x) for e, t, x, s in rels if s == st and t == "variant_of"}
        self.assertEqual(adapter(self.rels1, "approved"), set())
        self.assertEqual(adapter(self.rels1, "proposed"), adapter(self.rels2, "approved"))
        self.assertTrue(adapter(self.rels2, "approved"))
        m = json.loads((self.api2 / "widgets" / "products" / "widgetco-w-500.json").read_text())
        self.assertEqual(m["children"], ["widgetco-w-500-v1", "widgetco-w-500-v2"])

    def test_governance_lists_held_policies(self):
        g1, g2 = self.imp1["governance"], self.imp2["governance"]
        held = g1["held_by_pending"]
        self.assertEqual(sorted(held), ["claim/widget-cert@1", "claim/widgetco-spec@1", "rel/fixture-adapter@1"])
        self.assertEqual(held["claim/widgetco-spec@1"]["claims"] + held["claim/widget-cert@1"]["claims"], self.imp1["claims_review"]["widgets"]["candidate"])
        self.assertGreater(held["rel/fixture-adapter@1"]["relations"], 0)
        self.assertEqual(held["claim/widgetco-spec@1"]["approval"], "pending")
        self.assertEqual(g2["held_by_pending"], {})
        self.assertEqual(g2["pending_approval"], [])


if __name__ == "__main__":
    unittest.main()
