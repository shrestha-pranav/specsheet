"""A2-bulb r12: light-bulbs category, ENERGY STAR Connected Light Bulbs (crawler/adapters/energystar_bulbs.py). Pure fixtures, no network.

  python3 -m unittest tests.test_a2_bulb_r12
"""
import json, sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import _contract as C  # noqa: E402
import energystar_bulbs as B  # noqa: E402
import yaml  # noqa: E402

ROW = {"pd_id": "2298692", "brand_name": "Philips Hue", "model_name": "9290011998B", "model_number": "9290011998B",
       "additional_model_information": ",9290011998B,929001199871 (461004);929001199872 (466706)", "bulb_type": "A19", "base_type": "E26 (Medium)",
       "lamp_category": "Omnidirectional", "technology": "LED", "warranty_years": "2", "wattage_equivalency_watts": "60", "maximum_overall_length_mm": "110",
       "maximum_overall_diameter_mm": "60", "brightness_lumens": "800", "energy_used_watts": "10", "efficacy_lumens_watt": "80", "three_way": "No",
       "life_hrs": "25000", "light_appearance_kelvin": "4000", "color_quality_cri": "84", "r9": "-2", "power_factor": "0.6", "dimmable": "Dimmable",
       "dims_down_to": "1", "lamp_rated_for_enclosed_fixtures": "No", "connected_lamp": "Yes", "communication_method_connected_protocol": "Bluetooth,Zigbee",
       "special_features": "Use With Timers,Full-Color-Tunable,Damp Location Rated,White-Tunable", "standby_power_consumption_w": "0.3",
       "markets": "United States, Canada", "date_qualified": "2019-05-01T00:00:00.000"}


def parse(rows, model=None, pattern=False):
    model = model or rows[0]["model_number"]
    h = {"brand": B.brand_id(rows[0]["brand_name"]), "model": model, "pattern": pattern, "pd_ids": [r["pd_id"] for r in rows]}
    s = C.Snapshot("sha256:" + "0" * 64, C.Ref("energystar-light-bulbs", f"{h['brand']}|{model}", "https://data.energystar.gov/resource/msj5-kqfv.json", h),
                   200, "2026-11-26T00:00:00Z", "https://data.energystar.gov/resource/msj5-kqfv.json", {})
    return B.EnergyStarBulbs().parse_rows(s, h, rows)


def by_key(pr):
    return {c["key"]: c for c in pr.claims}


class Adapter(unittest.TestCase):
    def test_values_and_cct_basis(self):
        c = by_key(parse([ROW]))
        self.assertEqual(c["light.lumens"]["value"], 800)
        self.assertEqual(c["light.lumens"]["conditions"], {"cct_k": 4000}, "lumens carry the tested CCT")
        self.assertEqual(c["power.watts"]["conditions"], {"cct_k": 4000})
        self.assertEqual(c["power.equiv_watts"]["value"], 60)
        self.assertNotIn("conditions", c["power.equiv_watts"])
        self.assertEqual((c["form.shape"]["value"], c["form.base"]["value"]), ("a19", "e26"))
        self.assertEqual(c["smart.protocols"]["value"], ["bluetooth", "zigbee"])
        self.assertEqual(c["smart.color"]["value"], "full_color", "Full-Color-Tunable wins over White-Tunable")
        self.assertEqual(c["light.r9"]["value"], -2)
        self.assertIs(c["ctl.dimmable"]["value"], True)
        self.assertIs(c["cert.energy_star"]["value"], True)
        self.assertNotIn("light.lumens_color_max", c, "ENERGY STAR tests in white: never a full-colour figure")

    def test_absence_is_unknown_not_false(self):
        r = dict(ROW, special_features="Damp Location Rated", dimmable="", connected_lamp="No")
        c = by_key(parse([r]))
        self.assertNotIn("smart.color", c, "no tunable flag says nothing (some colour rows omit it)")
        self.assertNotIn("ctl.dimmable", c)
        self.assertNotIn("smart.connected", c, "only true is written")
        self.assertIs(by_key(parse([dict(ROW, dimmable="Non-Dimmable")]))["ctl.dimmable"]["value"], False)

    def test_refilings_disagree_unknown_and_canada_dropped(self):
        r2 = dict(ROW, pd_id="2", brightness_lumens="806", light_appearance_kelvin="2700")
        ca = dict(ROW, pd_id="3", brightness_lumens="1600", markets="Canada")
        c = by_key(parse([ROW, r2, ca]))
        self.assertEqual(c["light.lumens"]["status"], "unknown")
        self.assertEqual(c["light.lumens"]["conditions"], {"cct_k": [2700, 4000]})
        self.assertNotIn("1600", c["light.lumens"]["raw"], "Canada-only filing ignored")
        self.assertFalse(parse([ca]).claims)

    def test_pattern_and_split_cells_mint_nothing(self):
        pr = parse([dict(ROW, model_number="34208*")], "34208*", pattern=True)
        self.assertTrue(pr.fingerprints.get("wildcard_pattern"))
        self.assertFalse(pr.claims)
        self.assertFalse(parse([ROW], "CL-SMRT-A19-10W-2757(WIFI").claims)

    def test_identity_brand_folding_and_pack_aliases(self):
        pr = parse([ROW])
        key = next(i for i in pr.identifiers if i["role"] == "key")
        self.assertEqual((key["scheme"], key["value"], key["issuer"]), ("mfr_model", "9290011998B", "philips_hue"))
        self.assertIn("929001199871", {a["text"] for a in pr.aliases if a["kind"] == "model_variant"})
        self.assertEqual(B.brand_id("Feit Electroc"), "feit_electric")
        self.assertEqual(B.brand_id("Phillips"), "philips")
        cat = yaml.safe_load((CODE / "research" / "light-bulbs" / "category.yaml").read_text())
        self.assertEqual(cat["brand_aliases"]["philips_hue"], "philips")


class Wiring(unittest.TestCase):
    def test_registry_policy_profile(self):
        import registry
        self.assertEqual(registry.SOURCES["energystar-light-bulbs"]["category"], "light-bulbs")
        prof = yaml.safe_load((CODE / "research" / "light-bulbs" / "spec-profile.yaml").read_text())
        keys = {s["key"] for s in prof["specs"]}
        lum = next(s for s in prof["specs"] if s["key"] == "light.lumens")
        self.assertIn("cct_k", lum["basis_conditions"])
        pol = next(p for p in yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())["claim_policies"]
                   if p["id"] == "claim/light-bulbs-energystar@1")
        allowed = set(pol["match"]["keys"]["energystar-light-bulbs"])
        self.assertTrue(allowed <= keys)
        self.assertNotIn("light.lumens_color_max", allowed)
        ap = pol["approval"]
        self.assertTrue(ap["state"] == "pending" or (ap.get("by") and ap.get("at")))
        self.assertEqual(pol["audit"]["parsers"]["energystar_bulbs@1"], registry.parser_info("energystar-light-bulbs")["fingerprint"])

    def test_presets_use_profile_keys_and_never_equiv_watts(self):
        prof = yaml.safe_load((CODE / "research" / "light-bulbs" / "spec-profile.yaml").read_text())
        keys = {s["key"] for s in prof["specs"]}
        ps = [p for p in json.loads((CODE / "docs" / "presets.json").read_text())["presets"] if p["category"] == "light-bulbs"]
        self.assertGreaterEqual(len(ps), 3)
        for p in ps:
            gate = {k[2:].rsplit("_", 1)[0] for k in p["filters"]} | set(p.get("require") or [])
            self.assertTrue(gate <= keys, p["id"])
            self.assertNotIn("power.equiv_watts", gate, "equivalent watts is never a brightness gate")


if __name__ == "__main__":
    unittest.main()
