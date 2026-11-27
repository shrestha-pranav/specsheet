"""A2-appl r11: ENERGY STAR refrigerators + dishwashers (crawler/adapters/energystar_appliances.py, scripts/escover.py). Pure fixtures, no network.

  python3 -m unittest tests.test_a2_appl_r11
"""
import collections, sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import _contract as C  # noqa: E402
import energystar_appliances as E  # noqa: E402
import escover as EC  # noqa: E402
import yaml  # noqa: E402


def snap(h, src="energystar-refrigerators"):
    return C.Snapshot("sha256:" + "0" * 64, C.Ref(src, f"{h['brand']}|{h['model']}", "https://data.energystar.gov/resource/x.json", h), 200,
                      "2026-11-26T00:00:00Z", "https://data.energystar.gov/resource/x.json", {})


FRIDGE = {"pd_id": "1", "brand_name": "Samsung", "model_number": "BRB106003**", "type": "Bottom Freezer", "product_class": "5 - Refrigerator-freezers",
          "standard_or_counter_depth": "Yes", "compact": "No", "built_in": "No", "defrost_type": "Automatic", "width_in": "35.75", "height_in": "70.1",
          "capacity_total_volume_ft3": "4.8", "adjusted_volume_ft3": "5.8", "annual_energy_use_kwh_yr": "640", "us_federal_standard_kwh_yr": "711",
          "percent_less_energy_use_than_us_federal_standard": "10", "meets_most_efficient_criteria": "No", "ice_maker": "Yes",
          "thru_the_door_dispenser": "No", "connected_functionality": "No", "refrigerant_type": "R-600a,R600a/20g(0.705 ounces)",
          "refrigerant_with_gwp": "R-600a (GWP:3 | Lower GWP)", "markets": "United States, Canada", "date_qualified": "2025-04-15T00:00:00.000",
          "upc": "887276123456", "additional_model_information": "BRB10600300, BRB106003WW"}
DW = {"pd_id": "9", "brand_name": "Beko", "model_number": "DDT25401X", "type": "Standard", "width_inches": "59.8", "depth_inches": "22",
      "capacity_maximum_number_of_place_settings": "14", "soil_sensing_capability": "Yes", "tub_material": "Stainless Steel",
      "drying_method": "Automatic Door Release,Condensation Dry", "annual_energy_use_kwh_year": "234", "better_than_us_federal_standard_kwh_year": "24",
      "water_use_gallons_cycle": "3.2", "connected_capable": "No", "meets_most_efficient_criteria": "No", "markets": "United States",
      "date_certified": "2024-06-10T00:00:00.000"}


def claims(pr):
    return {c["key"]: c for c in pr.claims}


class Adapter(unittest.TestCase):
    def parse(self, cls, rows, model, pattern):
        h = {"brand": E.brand_id(rows[0]["brand_name"]), "model": model, "pattern": pattern, "pd_ids": [r["pd_id"] for r in rows]}
        return cls().parse_rows(snap(h, cls.source_id), h, rows)

    def test_pattern_detection_and_cells(self):
        self.assertTrue(E.is_pattern("BRB106003**") and E.is_pattern("ARD484F*10R/L") and E.is_pattern("FA490Uxxx") and E.is_pattern("SHE53CE#"))
        self.assertFalse(E.is_pattern("DW80B7070US/AA") or E.is_pattern("G 7106 SCU") or E.is_pattern("BCD-740WP/HC"))
        self.assertEqual(E.model_cells("NS-OCF55xxxxxx (x = a-z, A-Z, 0-9, -, blank)"), [("NS-OCF55xxxxxx", True)])
        self.assertEqual(E.model_cells("SHX78CC5UC, SHE78D7***"), [("SHX78CC5UC", False), ("SHE78D7***", True)])
        self.assertEqual(E.brand_id("Café"), "cafe")

    def test_pattern_row_is_own_entity_with_pattern_extractor(self):
        pr = self.parse(E.EnergyStarRefrigerators, [FRIDGE], "BRB106003**", True)
        key = next(i for i in pr.identifiers if i["role"] == "key")
        self.assertEqual(key["scheme"], "x_energystar_model_pattern")
        self.assertFalse(any(i["scheme"] in ("mfr_model", "gtin") for i in pr.identifiers), "no SKU key, no GTIN identifier on a pattern")
        self.assertIn(("887276123456", "covered_upc"), {(a["text"], a["kind"]) for a in pr.aliases})
        self.assertEqual({c["method"]["extractor"] for c in pr.claims}, {E.PATTERN_EXTRACTOR})
        c = claims(pr)
        self.assertIs(c["gen.is_pattern"]["value"], True)
        self.assertIn("dims.width_in", set(pr.fingerprints["non_transfer_keys"]))

    def test_policy_allowlist_matches_a1_transfer_lists(self):
        pol = {p["id"]: p for p in yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())["claim_policies"]}
        keys = pol["claim/appliances-es-pattern@2"]["match"]["keys"]
        self.assertEqual(set(keys["energystar-refrigerators"]), set(E.FRIDGE_PATTERN_KEYS))
        self.assertEqual(set(keys["energystar-dishwashers"]), set(E.DW_PATTERN_KEYS))
        for k in ("dims.width_in", "dims.height_in", "dims.depth_in", "config.counter_depth", "conn.connected", "features.tub_material"):
            self.assertNotIn(k, keys["energystar-refrigerators"] + keys["energystar-dishwashers"])

    def test_values_volume_percent_refrigerant_procedure(self):
        c = claims(self.parse(E.EnergyStarRefrigerators, [dict(FRIDGE, model_number="BRB10600300")], "BRB10600300", False))
        self.assertEqual((c["capacity.total_ft3"]["value"], c["capacity.adjusted_ft3"]["value"]), (4.8, 5.8), "adjusted volume is its own key")
        self.assertEqual(c["capacity.total_ft3"]["conditions"], {"test_procedure": "appendix_a"})
        self.assertEqual((c["energy.pct_below_federal"]["value"], c["energy.pct_below_federal"]["unit"]), (10, "%"))
        self.assertEqual((c["refrigerant.type"]["value"], c["refrigerant.gwp"]["value"]), ("r600a", 3))
        self.assertEqual(c["features.dispenser"]["value"], "none")
        self.assertIs(c["cert.energy_star"]["value"], True)
        self.assertEqual(c["cert.es_date"]["value"], "2025-04-15")
        self.assertEqual(c["gen.is_pattern"]["method"]["extractor"], E.ADAPTER)

    def test_beko_width_quarantined_and_dw_lists(self):
        c = claims(self.parse(E.EnergyStarDishwashers, [DW], "DDT25401X", False))
        self.assertEqual(c["dims.width_in"]["status"], "unknown")
        self.assertIn("quarantined", c["dims.width_in"]["raw"])
        self.assertEqual(c["features.drying_method"]["value"], ["auto_door_open", "condensation"])
        self.assertEqual(c["water.gal_per_cycle"]["conditions"], {"test_procedure": "appendix_c1"})
        self.assertEqual(c["energy.pct_below_federal"]["unit"], "%")

    def test_market_freezer_and_refiling_conflicts(self):
        pr = self.parse(E.EnergyStarRefrigerators, [dict(FRIDGE, markets="Canada")], "X1", False)
        self.assertEqual(pr.claims, [])
        pr = self.parse(E.EnergyStarRefrigerators, [dict(FRIDGE, type="Upright Freezer")], "X1", False)
        self.assertEqual(pr.claims, [])
        two = [dict(FRIDGE, model_number="X100"), dict(FRIDGE, pd_id="2", model_number="X100", annual_energy_use_kwh_yr="700")]
        c = claims(self.parse(E.EnergyStarRefrigerators, two, "X100", False))
        self.assertEqual(c["energy.annual_kwh"]["status"], "unknown")
        self.assertNotIn("value", c["energy.annual_kwh"])
        self.assertFalse(any(x["key"] == "cert.energy_star" and x.get("value") is False for x in c.values()))


class Ent:
    def __init__(self, brand, scheme, value, aliases=None):
        self.kind, self.brand, self.aliases, self.extra, self.claims = "model", brand, aliases or {}, {}, []
        self.idents = {(scheme, value.upper()): {"value": value.upper(), "value_raw": value, "role": "key"}}
        self.id = f"{brand}-{value}"


class World:
    def __init__(self, ents):
        self.ents, self.meta = ents, {}


class Dec:
    def relation_state(self, frm, typ, to, method, parser):
        return ("approved", "fixture") if method in EC.METHODS_APPROVABLE else ("proposed", None)


class Coverage(unittest.TestCase):
    def run_world(self, ents):
        w, st = World(ents), collections.Counter()
        EC.apply(w, st, "energystar_appliances@1")
        EC.finalize(w, Dec())
        return {e.id: e.extra.get("certifications") for e in ents}, st

    def test_unique_listed_ambiguous_undocumented(self):
        P = EC.PATTERN_SCHEME
        p1 = Ent("samsung", P, "BRB106003**", {"BRB10600300": "model_variant"})
        p2 = Ent("absocold", P, "ARD484F*10R/L")
        p3, p4 = Ent("lg", P, "LR*A2"), Ent("lg", P, "L*BA2")
        p5 = Ent("frigidaire", P, "FA490Uxxx")
        c = {n: Ent(b, "mfr_model", n) for b, n in (("samsung", "BRB10600300"), ("samsung", "BRB106003WWX"), ("absocold", "ARD484FW10L"),
                                                     ("lg", "LRBA2"), ("frigidaire", "FA490UABC"), ("lg", "BRB10600301"))}
        out, st = self.run_world([p1, p2, p3, p4, p5] + list(c.values()))
        m = lambda n: [(x["record"], x["method"], x["status"]) for x in out[c[n].id] or []]
        self.assertEqual(m("BRB10600300"), [(p1.id, "es-pattern:listed", "approved")])
        self.assertEqual(m("BRB106003WWX"), [], "length mismatch: no edge")
        self.assertEqual(m("ARD484FW10L"), [(p2.id, "es-pattern:unique-match", "approved")])
        self.assertEqual(sorted(x[1] for x in m("LRBA2")), ["es-pattern:ambiguous"] * 2)
        self.assertTrue(all(x[2] == "proposed" for x in m("LRBA2")))
        self.assertEqual(m("FA490UABC"), [(p5.id, "es-pattern:undocumented-token", "proposed")])
        self.assertEqual(m("BRB10600301"), [], "other brand: no edge")
        self.assertIsNone(out[p1.id], "patterns themselves get no edge")
        self.assertTrue(all(not e.claims for e in c.values()), "no claim transfers in escover@1")


if __name__ == "__main__":
    unittest.main()
