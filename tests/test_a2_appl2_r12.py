"""A2-appl2 r12: ENERGY STAR freezers / clothes washers / clothes dryers (crawler/adapters/energystar_siblings.py). Pure fixtures, no network.

  python3 -m unittest tests.test_a2_appl2_r12
"""
import json, sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import energystar_appliances as E  # noqa: E402
import energystar_siblings as S  # noqa: E402
import registry as R  # noqa: E402
import yaml  # noqa: E402


def snap(h, src):
    return C.Snapshot("sha256:" + "0" * 64, C.Ref(src, f"{h['brand']}|{h['model']}", "https://data.energystar.gov/resource/x.json", h), 200,
                      "2026-11-26T00:00:00Z", "https://data.energystar.gov/resource/x.json", {})


FREEZER = {"pd_id": "2365353", "brand_name": "ALPHA", "model_number": "RDVC138WE", "type": "Upright Freezer",
           "product_class": "9 - Upright freezers with automatic defrost without an automatic ice maker", "defrost_type": "Automatic",
           "compact": "No", "built_in": "No", "thru_the_door_dispenser": "No", "ice_maker": "No", "capacity_total_volume_ft3": "13.8",
           "adjusted_volume_ft3": "24.4", "annual_energy_use_kwh_yr": "394", "us_federal_standard_kwh_yr": "439",
           "percent_less_energy_use_than_us_federal_standard": "10", "connected_functionality": "No", "date_qualified": "2020-07-01T00:00:00.000",
           "markets": "United States, Canada", "meets_most_efficient_criteria": "No"}
WASHER = {"pd_id": "2545602", "brand_name": "Samsung", "model_number": "WF45B6300A*", "upc": "887276000001", "load_configuration": "Front Load",
          "additional_washer_features": "Steam Cycle,Sanitize Option,Drum Clean", "intended_market": "Residential", "volume_cubic_feet": "4.50",
          "width_inches": "27.0", "integrated_modified_energy_factor_imef": "2.92", "us_federal_standard_imef": "1.84",
          "annual_energy_use_kwh_year": "90", "integrated_water_factor_iwf": "2.9", "us_federal_standard_iwf": "4.7",
          "annual_water_use_gallons_year": "3841", "connected": "Yes", "connects_using": "Wi-Fi", "date_qualified": "2023-07-04T00:00:00.000",
          "markets": "United States", "meets_most_efficient_criteria": "Yes"}
DRYER = {"pd_id": "2216961", "brand_name": "LG", "model_name": "DLHC1455*B", "model_number": "DLHC1455*B", "product_type": "Electric Compact Ventless 240V",
         "type": "Electric", "drum_capacity_cu_ft": "4.2", "height_inches": "33.5", "width_inches": "24", "depth_inches": "25.25",
         "combined_energy_factor_cef": "6.4", "estimated_annual_energy_use_kwh_yr": "133", "estimated_energy_test_cycle_time_min": "70",
         "additional_dryer_features": "None", "vented_or_ventless": "Ventless", "connected": "No", "date_qualified": "2022-01-13T00:00:00.000",
         "markets": "United States, Canada", "meets_most_efficient_criteria": "No", "refrigerant_type": "R-290", "refrigerant_with_gwp": "R-290 (GWP:3 | Lower GWP)"}


def claims(pr):
    return {c["key"]: c for c in pr.claims}


def parse(cls, rows, model, pattern):
    h = {"brand": E.brand_id(rows[0]["brand_name"]), "model": model, "pattern": pattern, "pd_ids": [r["pd_id"] for r in rows]}
    return cls().parse_rows(snap(h, cls.source_id), h, rows)


def profile_keys(cat):
    return {s["key"] for s in yaml.safe_load((CODE / "research" / cat / "spec-profile.yaml").read_text())["specs"]}


class Siblings(unittest.TestCase):
    def test_own_parser_ids_and_untouched_r11_fingerprint(self):
        """Claims and snapshots name energystar_siblings; the approved r11 parser module is not edited by this lane (its fingerprint is a
        dependency of ours, so a later shared-code edit drifts both)."""
        pr = parse(S.EnergyStarFreezers, [FREEZER], "RDVC138WE", False)
        self.assertEqual({c["method"]["extractor"] for c in pr.claims}, {S.ADAPTER})
        pr = parse(S.EnergyStarClothesDryers, [DRYER], "DLHC1455*B", True)
        self.assertEqual({c["method"]["extractor"] for c in pr.claims}, {S.PATTERN_EXTRACTOR})
        self.assertEqual(E.ADAPTER, "energystar_appliances@1", "the shared module's own ids are unchanged by the rebind")
        for sid in ("energystar-freezers", "energystar-clothes-washers", "energystar-clothes-dryers"):
            self.assertEqual(R.parser_info(sid)["parser"], S.ADAPTER)
            self.assertEqual(R.SOURCES[sid]["category"], sid.removeprefix("energystar-"))
        self.assertNotEqual(R.parser_info("energystar-freezers")["fingerprint"], R.parser_info("energystar-refrigerators")["fingerprint"])

    def test_freezer_values_procedure_and_compact_type(self):
        c = claims(parse(S.EnergyStarFreezers, [FREEZER], "RDVC138WE", False))
        self.assertEqual((c["capacity.total_ft3"]["value"], c["capacity.adjusted_ft3"]["value"]), (13.8, 24.4))
        self.assertEqual(c["energy.annual_kwh"]["conditions"], {"test_procedure": "appendix_b"})
        self.assertEqual(c["config.es_type"]["value"], "upright")
        self.assertNotIn("features.dispenser", c, "through-door column mirrors ice_maker in this dataset: not mapped")
        c = claims(parse(S.EnergyStarFreezers, [dict(FREEZER, type="Compact")], "X1", False))
        self.assertEqual(c["config.es_type"]["value"], "compact")

    def test_washer_doe_capacity_j2_and_pattern_transfer(self):
        pr = parse(S.EnergyStarClothesWashers, [WASHER], "WF45B6300A*", True)
        c = claims(pr)
        self.assertEqual(c["capacity.doe_ft3"]["value"], 4.5)
        self.assertNotIn("capacity.iec_ft3", c, "ES never fills the IEC figure")
        for k in ("capacity.doe_ft3", "energy.imef", "water.iwf", "energy.annual_kwh"):
            self.assertEqual(c[k]["conditions"], {"test_procedure": "appendix_j2"}, k)
        self.assertEqual(c["config.load"]["value"], "front")
        self.assertEqual(c["features.washer"]["value"], ["drum_clean", "sanitize", "steam"])
        self.assertIn(("887276000001", "covered_upc"), {(a["text"], a["kind"]) for a in pr.aliases})
        self.assertIn("dims.width_in", pr.fingerprints["non_transfer_keys"])

    def test_dryer_d2_heat_pump_blank_is_unknown(self):
        c = claims(parse(S.EnergyStarClothesDryers, [DRYER], "DLHC1455*B", True))
        self.assertEqual(c["energy.cef"]["conditions"], {"test_procedure": "appendix_d2"})
        self.assertIs(c["config.ventless"]["value"], True)
        self.assertNotIn("config.heat_pump", c, "blank heat_pump_technology = no claim (unknown), never none")
        self.assertEqual(c["features.dryer"]["value"], [], "'None' = explicit empty list")
        self.assertEqual((c["refrigerant.type"]["value"], c["refrigerant.gwp"]["value"]), ("r290", 3))
        c = claims(parse(S.EnergyStarClothesDryers, [dict(DRYER, heat_pump_technology="Hybrid Heat Pump", voltage="240")], "DLHC1455AB", False))
        self.assertEqual((c["config.heat_pump"]["value"], c["elec.voltage"]["value"]), ("hybrid_heat_pump", 240))
        self.assertFalse(any(x.get("value") is False for k, x in c.items() if k == "cert.energy_star"))

    def test_keys_in_profiles_and_policy_allowlists(self):
        for cls, cat in ((S.EnergyStarFreezers, "freezers"), (S.EnergyStarClothesWashers, "clothes-washers"), (S.EnergyStarClothesDryers, "clothes-dryers")):
            keys = profile_keys(cat)
            emitted = {f[1] for f in cls.fields} | {"gen.is_pattern", "cert.es_date", "cert.energy_star"}
            self.assertLessEqual(emitted, keys, cat)
            self.assertLessEqual(set(cls.pattern_keys), emitted, cat)
            for k in ("dims.width_in", "dims.height_in", "dims.depth_in", "elec.voltage", "conn.connected", "conn.protocols"):
                self.assertNotIn(k, cls.pattern_keys, f"{cat}: {k} never transfers from a pattern")
        pol = {p["id"]: p for p in yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())["claim_policies"]}
        pat = pol.get("claim/appliances-siblings-es-pattern@1")
        if pat is None:
            self.skipTest("policies not added yet")
        for cls in (S.EnergyStarFreezers, S.EnergyStarClothesWashers, S.EnergyStarClothesDryers):
            self.assertEqual(set(pat["match"]["keys"][cls.source_id]), set(cls.pattern_keys))
        for pid in ("claim/appliances-siblings-energystar@1", "claim/appliances-siblings-es-pattern@1"):
            ap = pol[pid].get("approval") or {}
            self.assertTrue(ap.get("state") == "pending" or (ap.get("state") == "approved" and ap.get("by") and ap.get("at")), pid)

    def test_presets_p3_p4_name_profile_facets(self):
        pre = {p["id"]: p for p in json.loads((CODE / "docs" / "presets.json").read_text())["presets"]}
        for pid, cat in (("dryer-ventless-heat-pump-4cuft", "clothes-dryers"), ("washer-front-4p5-iwf32", "clothes-washers")):
            if pid not in pre:
                self.skipTest("presets not added yet")
            p = pre[pid]
            self.assertEqual(p["category"], cat)
            keys = profile_keys(cat)
            for f in p["filters"]:
                self.assertIn(f[2:].rsplit("_", 1)[0], keys, f)
            self.assertNotIn("f_gen.is_pattern_value", p["filters"], "every gate key is a pattern-transferable key: patterns are in scope")


if __name__ == "__main__":
    unittest.main()
