"""Chargers category (team/reports/2026-11-24-a12-chargers-matcher.md): review-3 rules applied to the charger parsers from the start, identity
rules per brand, and the v0 gan-chargers migration. Pure-parser fixtures first; the last class reads the release store and the built dataset.

  python3 -m unittest tests.test_chargers
"""
import json, sqlite3, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import yaml  # noqa: E402
import _contract as C  # noqa: E402
import _charger as G  # noqa: E402
import _powerbank as P  # noqa: E402
import shopify_chargers as S  # noqa: E402

SNAP = C.Snapshot("sha256:x", C.Ref("fx", "k", "https://example.test/p", {}), 200, "2026-11-24T00:00:00Z", "https://example.test/p", {})


def run(rows, title="Fixture Charger (100W)", kind="wall", model="X1"):
    pr = C.ParseResult()
    G.read_rows(pr, "fixture@1", SNAP, model, title, kind, rows)
    return {c["key"]: (c.get("value") if c["status"] == "known" else ("UNRESOLVED", c.get("quote"))) for c in pr.claims}, pr


class Totals(unittest.TestCase):
    def test_labelled_total_and_all_ports_by_count(self):
        v, _ = run([("Total number of ports", [("USB-C", "2"), ("USB-A", "1")]),
                    ("Total Output", [("Total Output", "100W Max (Top Port USB-C1)"), ("1 Port in Use", "USB-C1 / C2- 5V⎓3A / 9V⎓3A / 15V⎓3A / 20V⎓5A (100W Max)"),
                                      ("1 Port in Use", "USB-A-5V⎓3A / 9V⎓2A (22.5W Max)"), ("2 Ports in Use", "100W Max"), ("3 Ports in Use", "89W Max")])])
        self.assertEqual(v["out.max_total_w"], 100)
        self.assertEqual(v["out.all_ports_w"], 89, "3 ports in use with 3 printed ports = all ports")
        self.assertEqual(v["out.max_single_port_w"], 100)
        self.assertEqual(v["out.port_count"], 3)

    def test_additive_split_is_never_a_total(self):
        v, _ = run([("USB-C1 Output", ["5V⎓3A / 20V⎓3.5A (70W Max)"]), ("USB-C2 Output", ["5V⎓3A / 20V⎓3.5A (70W Max)"]), ("USB-A1 Output", ["5V⎓3A (15W Max)"]),
                    ("Three-Port Output", ["USB-C1 + USB-C2 + USB-A1: 45W + 7.5W + 7.5W"])], title="Fixture Charger (70W)")
        self.assertEqual(v["out.all_ports_w"][0], "UNRESOLVED")
        self.assertNotIn("out.max_total_w", v, "no labelled total row -> no total, never a sum or the largest port")

    def test_paren_allocation_row_with_max_words_is_additive(self):
        v, _ = run([("Single Port Output", ["USB-C 1 (65W Max) / USB-C 2 (65W Max) / USB-A (22.5W Max)"]),
                    ("Triple Port Output", ["USB-C 1 (40W Max), USB-C 2 (12W Max), USB-A (12W Max)"])], title="Fixture Charger (65W)")
        self.assertNotEqual(v.get("out.all_ports_w"), 40, "'40W Max + 12W Max + 12W Max' is not a 40 W total")

    def test_subset_combination_is_not_all_ports(self):
        v, _ = run([("Total number of ports", [("USB-C", "2"), ("USB-A", "1")]), ("USB-C1 Output", ["20V⎓3A (60W Max)"]), ("USB-C2 Output", ["20V⎓3A (60W Max)"]),
                    ("USB-A Output", ["5V⎓3A (15W Max)"]), ("Dual Port Output", ["USB-C1 + USB-C2: 65W Max"])], title="Fixture Charger (65W)")
        self.assertEqual(v["out.all_ports_w"][0], "UNRESOLVED")

    def test_unlabelled_wattage_is_rated_only_and_checked_against_the_title(self):
        v, _ = run([("Wattage", ["108W"]), ("Number of USB-C Ports", ["2"]), ("Number of USB-A ports", ["2"])], title="BoostCharge Pro 108W 4-Port GaN")
        self.assertEqual(v["out.rated_w"], 108)
        self.assertNotIn("out.max_total_w", v); self.assertNotIn("out.max_single_port_w", v)
        v, _ = run([("Wattage", ["20W"])], title="BoostCharge 65W Compact USB-C Wall Charger")
        self.assertEqual(v["out.rated_w"][0], "UNRESOLVED", "title 65W vs Wattage 20W contradicts itself")
        v, _ = run([("Output", ["140W"])], title="Speedport 140W Wall Charger")
        self.assertEqual(v["out.rated_w"], 140)
        self.assertNotIn("out.max_total_w", v)


class PortTable(unittest.TestCase):
    def test_protocol_lists_are_not_pdos(self):
        v, _ = run([("USB-C2/C3", ["QC3.0 / PD2.0 / PD3.0 / PPS / Apple5V/2.4A / BC1.2 / AFC / FCP"]), ("USB-A", ["QC3.0 / AFC / FCP / Apple 5V/2.4A"])])
        self.assertNotIn("out.ports", v)

    def test_normalisations_and_flags(self):
        v, _ = run([("Output", ["5.0V==3.0A /9.0V==3.0A / 15.0V==3.0A / 20.0V==3.25A (65W Max)"])], title="Fixture (65W)")
        self.assertEqual(v["out.ports"][0]["fixed_pdos"], "5V3A 9V3A 15V3A 20V3.25A")
        v, _ = run([("Total Output", [("USB-C Output", "5V⎓3A /9V⎓3A /15V⎓2A /20V⎓1.5A (30W Max)"), ("PPS 3.3", "11V⎓3A Max (30W Max)"), ("PPS 3.3", "3.3-16V⎓2A Max (30W Max)")])],
                   title="Nano Charger (30W)")
        self.assertEqual(v["out.ports"][0]["pps"], "3.3-11V 3A; 3.3-16V 2A")
        self.assertIs(v["pd.pps"], True); self.assertEqual(v["pd.pps_max_current_a"], 3)
        v, _ = run([("USB-C1", ["5V⎓3A / 20V⎓5A / 28V⎓5A (140W Max)"])], title="Fixture (140W)")
        self.assertIs(v["pd.epr"], True)
        v, _ = run([("USB-C", ["5V/9V/12V/15V⎓3A, 20V⎓3.35A (67W Max)"])], title="Fixture (67W)")
        self.assertEqual(v["out.ports"][0]["fixed_pdos"], "5V3A 9V3A 12V3A 15V3A 20V3.35A")

    def test_flags_are_affirmative_only(self):
        _, pr = run([("Technology", ["Silicon"]), ("Plug", ["Fixed"]), ("Output", ["5V⎓3A (15W Max)"])], title="Plain Charger (15W)")
        for c in pr.claims:
            self.assertFalse(c["key"] in ("gen.gan", "pd.pps", "pd.epr", "phys.foldable_plug") and c.get("value") is False, c)

    def test_amazon_attribute_voltage_is_not_an_input_rating(self):
        v, _ = run([("Input Voltage", ["240 volts"])])
        self.assertNotIn("in.rating", v)


class Identity(unittest.TestCase):
    def test_page_kind(self):
        for t in ("Anker 313 Wireless Charger (Pad)", "OntheGo 3-in-1 Charger", "Anker 511 Charger (Nano Pro) with Cable (2-Pack)"):
            self.assertIsNone(G.charger_kind(t), t)
        self.assertFalse(S.UgreenChargers().keep({"title": "UGREEN Portable Charger 10000mAh", "handle": "pb"}), "power-bank hybrids are dropped at discovery")
        self.assertEqual(G.charger_kind("Anker Nano Charger (45W) with USB-C to USB-C Cable"), "wall")
        self.assertEqual(G.charger_kind("BoostCharge 30W USB-C Car Charger"), "car")

    def test_brand_rules(self):
        self.assertEqual(S.SatechiChargers().model_of({}, ["ST-COTG45Y-US", "ST-COTG45P-US", "ST-COTG45B-US"], "", "")[0], "ST-COTG45")
        self.assertEqual(S.SatechiChargers().model_of({}, ["ST-UC165GM", "ST-UC165GM-EU", "ST-UC165GM-UK"], "", "")[0], "ST-UC165GM")
        self.assertEqual(S.HyperChargers().model_of({}, ["HJ1202BUNA", "HJ1202OGNA"], "", "")[0], "HJ1202")
        self.assertEqual(S.NativeUnionChargers().model_of({}, ["FAST-PD67-BLK-2CA", "FAST-PD67-WHT-2CA"], "", "")[0], "FAST-PD67-2CA")
        self.assertEqual(S.IniuChargers().model_of({}, ["D01-A11-E1-US-BK", "D01-A11-2P-BK-US"], "", "")[0], "A11-E1", "2-pack SKU is not a model stem")
        self.assertIsNone(S.IniuChargers().model_of({}, ["D01-1847"], "", "")[0], "a bare number is not an INIU model")
        self.assertIsNone(S.AukeyChargers().model_of({}, [], "Aivyo Swift GaN Wall Charger PA-B14 PA-B15 PA-B16", "")[0], "one page, several models")
        self.assertIsNone(S.UgreenChargers().model_of({}, ["35478", "75813", "45090"], "", "")[0], "several item numbers -> no model")


class Published(unittest.TestCase):
    DB = ROOT / "state" / "specsheet.sqlite"
    API = ROOT / "docs" / "api" / "v1"

    @unittest.skipUnless((ROOT / "state" / "specsheet.sqlite").exists(), "release store not built")
    def test_store_and_migration(self):
        con = sqlite3.connect(self.DB)
        n = con.execute("SELECT COUNT(*) FROM entities WHERE category='chargers' AND kind='model'").fetchone()[0]
        self.assertGreaterEqual(n, 150)
        ids = {r[0] for r in con.execute("SELECT id FROM entities WHERE category='chargers'")}
        for keep in ("anker-a2147", "anker-a2667", "anker-a2692", "anker-a120f", "anker-a2688"):
            self.assertIn(keep, ids, f"v0 public id {keep} kept")
        tomb = [json.loads(x) for x in (ROOT / "data" / "_ids" / "tombstones.jsonl").read_text().splitlines() if x.strip()]
        t = {x["id"]: x for x in tomb}
        self.assertEqual(t["category:gan-chargers"]["replaced_by"], ["chargers"])
        self.assertEqual(t["belkin-wch010dqwh"]["replaced_by"], ["belkin-wch010"])
        self.assertTrue(set(t) & ids == set(), "no live id is tombstoned")

    @unittest.skipUnless((ROOT / "docs" / "api" / "v1" / "categories.json").exists(), "dataset not built")
    def test_dataset(self):
        cats = {c["id"]: c for c in json.loads((self.API / "categories.json").read_text())}
        self.assertNotIn("gan-chargers", cats, "v0 category retired")
        self.assertGreaterEqual(cats["chargers"]["count"], 120)
        red = json.loads((self.API / "redirects.json").read_text())
        self.assertIn("category:gan-chargers", red)
        al = self.API / "lookup" / "aliases.json"
        self.assertTrue(al.exists()); self.assertLess(al.stat().st_size, 250_000, "aliases.json stays compact")

    def test_policy_pending_and_allowlisted(self):
        d = yaml.safe_load((ROOT / "data" / "decisions" / "policies.yaml").read_text())
        p = next(x for x in d["claim_policies"] if x["id"] == "claim/mfr-chargers-structured@4")   # r9 (cleanup): @2 retired, same rules
        self.assertIsInstance(p["match"]["keys"], dict)
        for src, keys in p["match"]["keys"].items():
            self.assertFalse({"gen.gan", "gen.form_factor", "gen.product_line", "pd.protocols", "id.msrp_us"} & set(keys), src)


if __name__ == "__main__":
    unittest.main()
