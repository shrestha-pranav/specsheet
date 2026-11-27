"""r11 A2-chg (team/reports/2026-11-26-a2-chg-r11.md): the KUXIU store adapter kuxiu_chargers (a port '+' is not a bundle, printed Model
row identity, non-US-plug listings dropped, AVS lines never read as PPS) and its policy; shopify_chargers stays at @3. Stored-snapshot checks skip when raw/ is absent.

  python3 -m unittest tests.test_a2_chg_r11
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import yaml  # noqa: E402
import _contract as C  # noqa: E402
import kuxiu_chargers as K  # noqa: E402
import registry as R  # noqa: E402


class Kuxiu(unittest.TestCase):
    k = K.KuxiuChargers()

    def test_keep(self):
        self.assertTrue(self.k.keep({"title": "KUXIU 60W GaN Power Adapter", "variants": [{"sku": "US-60W-AVS-WHITE"}, {"sku": "EU-60W-AVS-WHITE"}]}))
        self.assertTrue(self.k.keep({"title": "KUXIU 100W Universal Travel Adapter with Built-in Retractable Cable", "variants": []}))
        self.assertFalse(self.k.keep({"title": "KUXIU 45W Adapter", "variants": [{"sku": "45W-AU-Orange"}, {"sku": "45W-mini-EU-Orange"}]}), "other-market listing")
        self.assertFalse(self.k.keep({"title": "KUXIU 45W Charger + EU & UK Plug Adapter Set", "variants": []}), "plug-adapter bundle")
        self.assertFalse(self.k.keep({"title": "KUXIU M30 Smart Connector Charger for iPad", "variants": []}))
        self.assertFalse(self.k.keep({"title": "KUXIU S2 Power Bank Charger", "variants": []}), "power banks stay in kuxiu-us-powerbanks")
        self.assertTrue(self.k.keep({"title": "KUXIU 45W GaN Charger 1C + 1A", "variants": []}), "a port '+' is a layout, not a bundle")
        self.assertFalse(self.k.keep({"title": "KUXIU 45W GaN Charger + 6ft Cable", "variants": []}), "a real bundle")

    def test_model_row(self):
        self.assertEqual(self.k.model_of({"Model": "RY-C40C-C"}, [], "", "")[0], "RY-C40C-C")
        self.assertEqual(self.k.model_of({"Model": "DP-A127G45"}, [], "", "")[0], "DP-A127G45")
        self.assertEqual(self.k.model_of({"Product Model": "GS-45W0993"}, [], "", "")[0], "GS-45W0993")
        self.assertIsNone(self.k.model_of({}, ["45W-US-ORANGE"], "", "")[0], "a SKU is not a model")

    def test_stored_avs_not_pps(self):
        latest = self.k.store.latest()
        if not latest:
            self.skipTest("no stored kuxiu snapshots")
        seen = {}
        for key, s in latest.items():
            snap = C.Snapshot(s["snapshot"], C.Ref(self.k.source_id, key, s["url"]), 200, s["fetched_at"], s["final_url"], {})
            pr = self.k.parse(snap, self.k.store, None)
            m = next((i["value"] for i in pr.identifiers if i["scheme"] == "mfr_model"), None)
            seen[m] = {c["key"]: c.get("value") for c in pr.claims}
        self.assertIn("RY-C40C-C", seen)
        self.assertNotIn("pd.pps", seen["RY-C40C-C"], "an AVS range is not PPS")
        if "OL-H02-PD45" in seen:
            self.assertIs(seen["OL-H02-PD45"].get("pd.pps"), True, "a protocol row naming PPS still reads as PPS")


    def test_policy_pins_and_allowlist(self):
        d = yaml.safe_load((ROOT / "data" / "decisions" / "policies.yaml").read_text())
        act = {x["id"]: x for x in d["claim_policies"]}
        p = act["claim/mfr-chargers-kuxiu@1"]
        self.assertEqual(p["audit"]["parsers"]["kuxiu_chargers@1"], R.parser_fingerprint("kuxiu_chargers"))
        self.assertFalse({"gen.gan", "gen.form_factor", "gen.product_line", "pd.protocols", "id.msrp_us", "in.rating", "out.ports"} & set(p["match"]["keys"]))
        old = act["claim/mfr-chargers-structured@4"]["audit"]["parsers"]
        self.assertEqual(old["ugreen_chargers@3"], R.parser_fingerprint("shopify_chargers"), "shopify_chargers unchanged: approved @4 still holds")
        self.assertEqual(R.SOURCES["kuxiu-us-chargers"]["module"], "kuxiu_chargers")


if __name__ == "__main__":
    unittest.main()
