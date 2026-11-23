"""A3-impl r6: bundle packages (scripts/bundles.py), the claim basis in the index `x` map, and the repeated-port-row fix (_powerbank).

Pure parser fixtures plus one throwaway data root (SPECSHEET_ROOT, same pattern as tests/test_new_category.py): a `kits` category is imported
once WITHOUT the bundle_packages feature and once WITH it, then published. Checks: existing ids survive and only package ids are minted;
packages carry no specs, link to their member model with `contains`, are listed under the model (`bundles`) and are never index rows; an
uncorroborated SKU is not minted and is reviewable; index rows carry x[k].basis for claim_basis / power_mode fields.

  python3 -I tests/test_r6.py
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "scripts"))
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
import bundles as B  # noqa: E402
import _powerbank as P  # noqa: E402
import decisions as D  # noqa: E402
import registry  # noqa: E402


def mem(title, names, key="K-1", sku="SKU1", opt=False, pw=(), brand=""):
    """r7 (bundles@2): key / sku / opt no longer matter (no SKU-digit inference); kept so the r6 call sites read unchanged."""
    return B.members(title, {B.norm(n) for n in names}, pw, brand)


class Parser(unittest.TestCase):
    def test_explicit_members_and_quantities(self):
        m, _ = mem("AC180P+200W Solar | 1800W,1440Wh,200W Solar Kit", ["AC180P"], "AC180P", "AC180P-2-62-SPFUS-00")
        self.assertEqual((m["model"], m["parts"]), (1, [("200W Solar", 1)]))
        m, _ = mem("(Members-only) 2 x DELTA 3 Plus", ["DELTA 3 Plus Portable Power Station"], "EFDELTA3P", "EFDELTA3P-US-2")
        self.assertEqual((m["model"], m["parts"]), (2, []))
        m, _ = mem("Black / Explorer 1000 v2 + SolarSaga 200W x 2", ["Explorer 1000 v2"], "Explorer 1000 v2", "60-1")
        self.assertEqual(m["parts"], [("SolarSaga 200W", 2)])
        m, _ = B.members("DELTA 3 Max Plus (2048Wh) + 400W Solar Panel", {B.norm("DELTA 3 Max Plus")}, caps={2048.0})
        self.assertEqual(m["model"], 1, "a capacity note does not hide the model (r7: when it equals the page's own capacity)")

    def test_free_promotions_are_not_contents(self):
        m, why = mem("(Flash Sale) DELTA 3 Plus + Free DELTA 3 Series Waterproof Bag", ["DELTA 3 Plus"], "EFDELTA3P", "EFDELTA3P-US-BAG")
        self.assertIsNone(m); self.assertIn("single item", why)
        m, _ = mem("DELTA 2 Max + 2 x 160W Solar Panel + Free Bag", ["DELTA 2 Max"], "EFDELTA2MAX", "D2M-160WSP-2")
        self.assertEqual(m["parts"], [("160W Solar Panel", 2)])

    def test_member_must_be_explicit(self):
        self.assertIsNone(mem("Explorer 2000 v2 Extreme Kit", ["Explorer 2000 v2"], "Explorer 2000 v2", "60-2000-USD1A1", opt=True)[0],
                          "a kit name is not a member list, and a spaced name key never licenses the add-on-only rule")
        self.assertIsNone(mem("DELTA 3 Max (Detachable Wheels) (2048Wh) + 220W Solar Panel", ["DELTA 3 Max"], "EFD3M", "X")[0], "hardware note = other unit")
        self.assertIsNone(mem("Freo 20 Robot Vacuum & Mop", ["Freo 20"], "Freo 20", "CP-ZD-A00314-00-00")[0], "a product-type phrase is one item")
        self.assertIsNone(mem("Handsfree 2 | 60L Storage, 700W, 512Wh", ["Handsfree 2"], "HF2", "HF2-2-01")[0])

    def test_addon_option_needs_the_model_number_in_the_sku(self):
        """r7 (review 4): the SKU-digit rule is gone; an add-on-only title never names the model, whatever the SKU embeds."""
        self.assertIsNone(mem("2× 100W Bifacial Solar Panel", ["C1000 Gen 2"], "A1763", "G17631A5", opt=True)[0])
        self.assertIsNone(mem("100W Bifacial Solar Panel", ["C1000 Gen 2"], "A1763", "B19990A9", opt=True)[0])

    def test_pack_word_and_brand_prefix(self):
        m, why = mem("X50 Ultra Complete / White", ["X50 Ultra"], "X50 Ultra", "010204AA000863", pw=["Complete"])
        self.assertIsNone(m, "r7: a pack word fabricates no component (one item)"); self.assertIn("not itemised", why)
        m, _ = mem("Narwal Freo Z10 Turbo & Advanced Kit", ["Freo Z10 Turbo"], "Freo Z10 Turbo", "CP-1-AC01", brand="Narwal")
        self.assertEqual(m["parts"], [("Advanced Kit", 1)])
        self.assertIsNone(mem("White", ["X50 Ultra"], "X50 Ultra", "010204AA000703", pw=["Complete"])[0], "a colour option stays an alias")

    def test_member_signature_ignores_wording_not_designation(self):
        """r7: the lossy number-only signature is gone; full descriptions are compared (plural folding only)."""
        self.assertNotEqual(B.canon_desc("220W Solar Panel"), B.canon_desc("220W Portable Solar Panel"))
        self.assertNotEqual(B.canon_desc("160W Solar Panel"), B.canon_desc("220W Solar Panel"))


class RepeatedPortRow(unittest.TestCase):
    def test_iniu_p73_output_cell_lists_out1_out2_once(self):
        t = ("Wireless OUT: (Qi2)15W/10W/7.5W/5W OUT1/ OUT2: 5V⎓3A 9V⎓3A 12V⎓3A 15V⎓3A 45W (Max); OUT1/ OUT2 : 5V⎓3A 9V⎓3A 12V⎓3A 15V⎓3A 45W (Max); "
             "OUT1+OUT2 : 15W(Max); OUT1+Wireless OUT: 15W(Max); OUT2+Wireless OUT : 15W(Max); Total (OUT1+OUT2+Wireless OUT) : 15W(Max)")
        ports, _, total, toks = P.ports_from(t)
        self.assertEqual([p["name"] for p in ports], ["Wireless OUT", "OUT1/ OUT2"])
        self.assertEqual((total, toks), (15, ["OUT1", "OUT2", "W"]))

    def test_different_rows_with_one_name_are_kept(self):
        ports = P.ports_from("USB-C1: 5V3A 9V3A 30W(Max); USB-C1: 5V3A 9V3A 12V2.5A 30W(Max)")[0]
        self.assertEqual(len(ports), 2, "only exact repeats collapse; a disagreement stays visible")


class Policies(unittest.TestCase):
    def test_r6_policies_pending_and_old_ones_inert(self):
        dec = D.Decisions(CODE / "data")
        pol = {p["id"]: p for p in dec.claim_policies + dec.relation_policies + dec.retired_policies}
        cur = {registry.parser_info(s)["parser"] for s in registry.SOURCES}
        for i in ("claim/mfr-power-banks-structured@5", "claim/mfr-power-stations-structured@2", "rel/bundle-contents@1"):
            a = pol[i]["approval"]; self.assertIn(a["state"], ("pending", "approved"), i); self.assertTrue(a["state"] == "pending" or (a.get("by") and a.get("at")), i)  # human-approved 2026-11-23
        for i in ("claim/mfr-power-banks-structured@4", "claim/mfr-power-stations-structured@1"):
            self.assertFalse(set(pol[i]["match"]["extractors"]) & cur, f"{i} still matches a live extractor")
        st = {registry.parser_info(s)["parser"] for s, m in registry.SOURCES.items() if m["category"] == "power-stations"}
        self.assertEqual(set(pol["claim/mfr-power-stations-structured@2"]["match"]["extractors"]), st)
        self.assertEqual(pol["claim/mfr-power-stations-structured@2"]["match"]["keys"], pol["claim/mfr-power-stations-structured@1"]["match"]["keys"])
        self.assertEqual(pol["claim/mfr-power-banks-structured@5"]["match"]["keys"], pol["claim/mfr-power-banks-structured@4"]["match"]["keys"])
        self.assertEqual({t for r in pol["rel/bundle-contents@1"]["rules"] for t in r["types"]}, {"contains"})


PROFILE = """
profile_format: specsheet.category-profile/1
category: kits
version: 0.1.0
label: Kits
identity:
  levels: [family, model, configuration, package]
  primary_key: manufacturer model number
conditions:
  - {id: claim_basis, label: Claim basis, type: enum, enum: [mfr_in_house_lab, mfr_unstated]}
groups:
  - {id: general, label: General}
specs:
  - {key: gen.power, label: Power, group: general, type: number, unit: W, tier: core, level: model, facet: {kind: range, bins: [100]},
     conditions: [claim_basis], basis_conditions: [claim_basis], sources: [spec page]}
  - {key: phys.weight, label: Weight, group: general, type: number, unit: kg, tier: core, level: model, facet: {kind: range, bins: [5]}, sources: [spec page]}
"""
CATEGORY = """
name: Kits
description: Fixture category.
columns: [gen.power, phys.weight]
features: [%s]
bundles: {pack_words: [Complete]}
identity_scope: {cross_market_brands: "*", market_scoped_brands: []}
"""
POLICIES = """
format: specsheet.policies/1
claim_policies:
  - id: claim/kitco-spec@1
    since: "2026-11-23"
    rationale: fixture
    match: {extractors: [kitco@1], source_ids: [kitco-us], kinds: [official], tiers: [manufacturer], statuses: [known], require_normalized: true,
            keys: [gen.power, phys.weight]}
relation_policies:
  - {id: rel/fixture-bundle@1, since: "2026-11-23", rationale: fixture, rules: [{method: "bundle:kitco-us", types: [contains], parsers: [kitco@1]}]}
  - {id: rel/fixture-bundle@2, since: "2026-11-23", rationale: "r7: the bundles@2 transform", rules: [{method: "bundle:kitco-us", types: [contains], parsers: ["kitco@1+bundles@2"]}]}
"""


def claim(key, value, unit, cond=None):
    c = {"id": f"c_{key}_{value}", "key": key, "status": "known", "kind": "official", "unit": unit, "raw": f"{key}={value}", "source": "s1",
         "method": {"stage": "table", "extractor": "kitco@1"}, "observed_at": "2026-11-23T00:00:00Z", "value": value, "locator": {}}
    if cond:
        c["conditions"] = cond
    return c


def page(model, claims, packages=(), skus=()):
    ids = [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "kitco", "market": "US", "package_level": "model", "role": "key", "sources": ["s1"]}]
    ids += [{"scheme": "mfr_sku", "value": s, "value_raw": s, "issuer": "kitco", "market": "US", "package_level": "configuration", "role": "alias", "sources": ["s1"],
             "option": o} for s, o in skus]
    return {"identifiers": ids, "aliases": [{"text": f"{model} Power Station", "kind": "marketing_name"}], "claims": claims, "media": [], "documents": [],
            "absences": [], "links": [], "fingerprints": {"packages": [{"sku": s, "title": t} for s, t in packages]},
            "sources": [{"id": "s1", "url": f"https://example.invalid/{model}", "label": "page", "tier": "manufacturer"}]}


ROWS = [
    page("K-1", [claim("gen.power", 500, "W", {"claim_basis": "mfr_in_house_lab"}), claim("phys.weight", 9, "kg")],
         packages=[("K1-PV", "K-1 + 200W Panel"), ("K1-X2", "(Members-only) 2 x K-1"), ("K1-C", "K-1 + 100W Panel"), ("K1-US", "K-1 + Free Bag"),
                   ("K1-ALT", "K-1 + K-2")],
         skus=[("K1-US", "White"), ("K1-CP", "K-1 Complete + 100W Panel / White")]),
    page("K-1", [], packages=[("K1-C", "K-1 + 200W Panel"), ("K1-PV", "K-1 + 200W Panel + Free Bag")]),       # second page of K-1 (r7: exact multiset)
    page("K-2", [claim("gen.power", 300, "W"), claim("phys.weight", 4, "kg")]),
    page("K-3", [claim("gen.power", 400, "W", {"claim_basis": "mfr_unstated"})]),
]


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = t = Path(tempfile.mkdtemp(prefix="specsheet-r6-"))
        os.symlink(CODE / "schemas", t / "schemas")
        (t / "research" / "kits").mkdir(parents=True)
        (t / "research" / "kits" / "spec-profile.yaml").write_text(PROFILE)
        (t / "data" / "decisions").mkdir(parents=True)
        (t / "data" / "decisions" / "policies.yaml").write_text(POLICIES)
        (t / "data" / "decisions" / "ledger.jsonl").write_text("")
        (t / "sources.extra.json").write_text(json.dumps({"kitco-us": {"brand": "kitco", "brand_name": "KitCo", "category": "kits", "module": "none",
                                                                       "importer": "model", "parser": "kitco@1"}}))
        d = t / "raw" / "kitco-us"
        (d / "parsed").mkdir(parents=True)
        log = []
        for n, pr in enumerate(ROWS):
            (d / "parsed" / f"r{n}.json").write_text(json.dumps(pr))
            log.append({"snapshot": f"sha256:{n:064x}", "ref": f"r{n}", "url": pr["sources"][0]["url"], "final_url": pr["sources"][0]["url"], "status": 200,
                        "fetched_at": "2026-11-23T00:00:00Z", "etag": None, "last_modified": None, "adapter": "fixture@1", "blob": f"blobs/{n:064x}.json"})
        (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
        env = dict(os.environ, SPECSHEET_ROOT=str(t))
        imp = lambda: subprocess.run([sys.executable, "-I", str(CODE / "scripts" / "import.py"), "--data", str(t / "data")], env=env, capture_output=True, text=True)
        (t / "research" / "kits" / "category.yaml").write_text(CATEGORY % "")
        r = imp(); assert r.returncode == 0, r.stderr[-2000:]
        cls.before = [json.loads(x) for x in (t / "data" / "_ids" / "registry.jsonl").read_text().splitlines() if x.strip()]
        (t / "research" / "kits" / "category.yaml").write_text(CATEGORY % "bundle_packages")
        r = imp(); assert r.returncode == 0, r.stderr[-2000:]
        cls.imp = json.loads(r.stdout[r.stdout.index("{"):])
        cls.after = [json.loads(x) for x in (t / "data" / "_ids" / "registry.jsonl").read_text().splitlines() if x.strip()]
        code = ("import sys, json; sys.path.insert(0, %r); import v1_publish as P; from pathlib import Path; st = {}; P.publish(Path(%r), st); print(json.dumps(st))"
                % (str(CODE / "scripts"), str(t / "api")))
        r = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        cls.stats = json.loads(r.stdout.splitlines()[-1])
        cls.api = t / "api" / "kits"
        cls.rows = {x["id"]: x for x in json.loads((cls.api / "index.json").read_text())}
        cls.det = lambda self, i: json.loads((self.api / "products" / f"{i}.json").read_text())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_existing_ids_survive_only_packages_minted(self):
        self.assertEqual(self.after[:len(self.before)], self.before, "registry is append-only and earlier ids keep their anchors")
        new = self.after[len(self.before):]
        self.assertEqual(sorted(x["id"] for x in new), ["kitco-k1-alt", "kitco-k1-cp", "kitco-k1-pv", "kitco-k1-x2"])
        self.assertEqual({x["kind"] for x in new}, {"package"})
        self.assertEqual(self.imp["ids"]["reused"], len(self.before))

    def test_packages_are_not_rows_and_inherit_nothing(self):
        self.assertEqual(set(self.rows), {"kitco-k-1", "kitco-k-2", "kitco-k-3"})
        d = self.det("kitco-k1-pv")
        self.assertEqual((d["kind"], d["specs"], d["name"]), ("package", {}, "K-1 + 200W Panel"))
        self.assertEqual(d["contents"], [{"entity": "kitco-k-1", "qty": 1}, {"description": "200W Panel", "qty": 1}], "free bag is a promotion, not content")
        self.assertEqual([(r["type"], r["target"], r["status"]) for r in d["relations"]], [("contains", "kitco-k-1", "approved")])
        self.assertEqual(len(d["sources"]), 2, "both pages that list the SKU are cited")
        self.assertEqual(self.det("kitco-k1-x2")["contents"], [{"entity": "kitco-k-1", "qty": 2}])

    def test_member_models_list_their_bundles(self):
        m = self.det("kitco-k-1")
        self.assertEqual([(b["id"], b["sku"], b["qty"]) for b in m["bundles"]],
                         [("kitco-k1-x2", "K1-X2", 2), ("kitco-k1-pv", "K1-PV", 1), ("kitco-k1-alt", "K1-ALT", 1), ("kitco-k1-cp", "K1-CP", 1)])
        self.assertEqual([b["id"] for b in self.det("kitco-k-2")["bundles"]], ["kitco-k1-alt"], "a second named model is a member too")
        self.assertNotIn("K1-CP", {i["value"] for i in m["identifiers"]}, "a pack SKU is the package's key, not a configuration alias")
        self.assertIn("K1-US", {i["value"] for i in m["identifiers"]})

    def test_uncorroborated_skus_not_minted(self):
        ids = {x["id"] for x in self.after}
        self.assertNotIn("kitco-k1-c", ids, "K1-C: two pages, different panels")
        self.assertNotIn("kitco-k1-us", ids, "unit SKU with a free gift")
        self.assertEqual(self.imp["stem_proposals"]["kits"].get("bundle_disputed"), 1)
        self.assertEqual(self.imp["identity"]["page_identity_review"], 1)

    def test_index_carries_claim_basis(self):
        self.assertEqual(self.rows["kitco-k-1"]["x"]["gen.power"], {"basis": {"claim_basis": "mfr_in_house_lab"}})
        self.assertNotIn("x", self.rows["kitco-k-2"], "no stated basis -> nothing (the shell defaults to unstated)")
        self.assertNotIn("x", self.rows["kitco-k-3"], "the 'unstated' default is omitted: absent == mfr_unstated")
        self.assertEqual(self.det("kitco-k-3")["specs"]["gen.power"]["basis"], {"claim_basis": "mfr_unstated"}, "the detail keeps it explicit")
        self.assertEqual(self.det("kitco-k-1")["specs"]["gen.power"]["basis"], self.rows["kitco-k-1"]["x"]["gen.power"]["basis"])


if __name__ == "__main__":
    unittest.main()
