"""Air purifiers: review-3/4 rules on the four adapters (affirmative-only flags, bases in conditions, conflict-aware grouping, exact-match
certification). Pure fixtures, no network.

  python3 -I tests/test_air_purifiers.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import _airpurifier as A  # noqa: E402
import energystar_airpurifiers as ES  # noqa: E402
import carb_airpurifiers as CB  # noqa: E402
import levoit_airpurifiers as LV  # noqa: E402
import winix_airpurifiers as WX  # noqa: E402

OBS = "2026-11-23T00:00:00Z"


def snap(hints=None, key="x", url="https://example.test/p"):
    return C.Snapshot("sha256:fixture", C.Ref("fixture", key, url, hints or {}), 200, OBS, url, {})


def by_key(pr):
    out = {}
    for c in pr.claims:
        out.setdefault(c["key"], []).append(c)
    return out


def known(pr, key):
    return [c.get("value") for c in by_key(pr).get(key, []) if c["status"] == "known"]


ESROW = {"pd_id": "1", "brand_name": "Coway Airmega", "model_number": "AP-1512HH", "markets": "United States, Canada", "date_certified": "2024-01-02T00:00:00.000",
         "smoke_free_clean_air_delivery": "233.0", "dust_free_clean_air_delivery": "246.0", "pollen_free_clean_air_delivery": "240.0", "pm25_cadr": "240.0",
         "room_size_sq_ft": "361", "filter_1_type": "HEPA-Type", "connected_capable": "No", "automatic_mode": "None", "meets_most_efficient_criteria": "No"}


class EnergyStar(unittest.TestCase):
    def run_es(self, rows, model="AP-1512HH"):
        return ES.parse_rows(snap({"brand": "coway", "model": model, "pd_ids": [r["pd_id"] for r in rows]}), {"brand": "coway", "model": model}, rows)

    def test_cadr_and_room_carry_basis(self):
        pr = self.run_es([ESROW])
        c = by_key(pr)["cadr.smoke_cfm"][0]
        self.assertEqual((c["value"], c["conditions"]), (233, {"cadr_basis": "energy_star_certified"}))
        self.assertEqual(by_key(pr)["room.size_sqft"][0]["conditions"], {"room_basis": "energy_star_formula"})

    def test_hepa_type_is_never_true_hepa_nor_false(self):
        pr = self.run_es([ESROW])
        self.assertEqual(known(pr, "filter.true_hepa"), [])
        self.assertEqual(known(pr, "filter.hepa_class"), ["hepa_type"])
        pr = self.run_es([dict(ESROW, filter_1_type="HEPA")])
        self.assertEqual(known(pr, "filter.true_hepa"), [True])

    def test_no_watts_derived(self):
        pr = self.run_es([dict(ESROW, smoke_free_clean_air_delivery_rate_cfm_w="3.9")])
        self.assertFalse(any(k.startswith("pwr.") and k != "pwr.annual_kwh" for k in by_key(pr)))

    def test_disagreeing_rows_are_unresolved_not_picked(self):
        pr = self.run_es([ESROW, dict(ESROW, pd_id="2", smoke_free_clean_air_delivery="250.0")])
        cs = by_key(pr)["cadr.smoke_cfm"]
        self.assertEqual([c["status"] for c in cs], ["unknown"])
        self.assertIn("233.0", cs[0]["raw"]); self.assertIn("250.0", cs[0]["raw"])
        self.assertEqual(known(pr, "cadr.dust_cfm"), [246])

    def test_wildcard_and_junk_cells(self):
        self.assertEqual(ES.model_cells("HPA120***"), [("HPA120***", True)])
        self.assertEqual(ES.model_cells("W"), [])
        self.assertEqual(ES.model_cells("Kilo"), [])
        self.assertEqual([m for m, _ in ES.model_cells("Airmega 350(W);Airmega 350(BG)")], ["Airmega 350(W)", "Airmega 350(BG)"])

    def test_declarations(self):
        toks, ph = ES.split_additional("4312112000,4312112000,4312112000 is same as 4312111000, except for color.", "4312111000")
        self.assertEqual(toks, [("4312112000", "declared_same_hardware")])
        toks, _ = ES.split_additional("C710,C710 is a derivative model of C610. C710 is identical in performance to C610, only difference is inlet", "C610")
        self.assertTrue(all(k != "declared_same_hardware" for _, k in toks))
        toks, _ = ES.split_additional("LAP-C401S-KUSR; LAP-C401S-may be followed up to four characters", "LAP-C401S-WUSR")
        self.assertEqual(toks, [("LAP-C401S-KUSR", "model_variant")])

    def test_canada_only_gives_nothing(self):
        pr = ES.parse_rows(snap({"brand": "coway", "model": "X1"}), {"brand": "coway", "model": "X1"}, [])
        self.assertEqual(pr.claims, [])

    def test_brand_folding_is_owner_only(self):
        self.assertEqual(A.brand_id("Coway Airmega"), "coway")
        self.assertEqual(A.brand_id("Honeywell™ by Kaz"), "honeywell")
        self.assertNotEqual(A.brand_id("AROEVE"), A.brand_id("BREEZOME"))


CARBROWS = [{"brand": "Levoit", "name": "Air Purifier", "model": "LAP-C511S-WUS", "type": "Mechanical", "date": "2026-09-09", "eo": "G-26-209"},
            {"brand": "LEVOIT", "name": "Air Purifier", "model": "LAP-C511S-WUS", "type": "Electronic", "date": "2025-01-01", "eo": "G-25-001"}]


class Carb(unittest.TestCase):
    def test_dated_affirmative_and_type_conflict(self):
        pr = CB.parse_rows(snap(), {"brand": "levoit", "model": "LAP-C511S-WUS"}, CARBROWS)
        self.assertEqual(known(pr, "ozone.carb_certified"), [True])
        self.assertIn("G-26-209", by_key(pr)["ozone.carb_certified"][0]["quote"])
        self.assertEqual(known(pr, "ozone.carb_type"), [])          # disagreeing rows -> unresolved
        self.assertEqual(known(pr, "ozone.carb_date"), ["2025-01-01"])

    def test_exact_match_only_and_exclusions(self):
        rows = CARBROWS[:1] + [{"brand": "Acme", "name": "Air Purifier", "model": "AP-1", "type": "Mechanical", "date": "2026-01-01", "eo": "G-1"},
                               {"brand": "Acme", "name": "Air Purifier", "model": "AP-100", "type": "Mechanical", "date": "2026-01-01", "eo": "G-1"},
                               {"brand": "Dyson", "name": "Hand Dryer", "model": "HU02", "type": "Electronic", "date": "2026-01-01", "eo": "G-2"},
                               {"brand": "Dyson", "name": "Air Purifier", "model": "TP07, TP09", "type": "Electronic", "date": "2026-01-01", "eo": "G-2"}]
        refs, st = CB.group(rows, {"acme|AP-100"})
        self.assertEqual(sorted(refs), ["acme|AP-100", "levoit|LAP-C511S-WUS"])   # Acme AP-1 is no exact peer; no stem / prefix match
        self.assertEqual((st["not_purifier"], st["multi_or_bad_model"]), (1, 1))


LEVOIT = """<h2 class="text-lg font-light">Features</h2><ul><li>Smart Control</li><li>Wi-Fi Indicator </li><li>Sleep Mode</li></ul></details>
<h2 class="text-lg font-light">Product Specifications</h2><ul><li><strong>Rated Power</strong>: 38W</li>
<li><strong>Ideal Room Size</strong>: 1718 ft2 (1 ACH) / 358 ft2 (4.8 ACH)</li><li><strong>Dimensions</strong>: 10.8 x 10.8 x 20.5 in</li>
<li><strong>Noise Level</strong>: 22–52dB </li><li><strong>CADR</strong>: 231 CFM</li><li><strong>Standby Power</strong>: &lt; 2W</li>
<li><strong>Model</strong>: Core 400S</li></ul></details>"""


class Levoit(unittest.TestCase):
    def test_rows(self):
        pr = LV.parse_html(snap({"title": "Levoit Core 400S-P"}), LEVOIT)
        self.assertEqual(pr.identifiers[0]["value"], "Core 400S")
        self.assertEqual(known(pr, "cadr.smoke_cfm"), [])                     # unlabelled CADR is never smoke
        self.assertEqual(known(pr, "cadr.unspecified_cfm"), [231])
        rs = by_key(pr)["room.size_sqft"][0]
        self.assertEqual((rs["value"], rs["conditions"]), (358, {"room_basis": "maker_stated_ach", "ach": 4.8}))
        self.assertEqual(by_key(pr)["room.coverage_sqft"][0]["conditions"], {"ach": 1})
        self.assertEqual(sorted((c["value"], c["conditions"]["fan_speed"]) for c in by_key(pr)["noise.db"]), [(22, "range_min"), (52, "range_max")])
        self.assertEqual(known(pr, "pwr.standby_w"), [])                     # '< 2W' is a bound
        self.assertEqual(known(pr, "phys.width_in"), [])                     # no axis order printed
        self.assertEqual(known(pr, "smart.wifi"), [True])

    def test_aham_cadr_only_when_stated(self):
        h = LEVOIT.replace("<li><strong>CADR</strong>: 231 CFM</li>", "<li><strong>CADR*</strong>: Smoke: 85 CFM / 144 m³/h Dust: 90 CFM</li>"
                           "<li><strong>Certified</strong>: Aham Verifide</li>")
        pr = LV.parse_html(snap(), h)
        self.assertEqual(by_key(pr)["cadr.smoke_cfm"][0]["conditions"], {"cadr_basis": "aham_verified_maker_stated"})
        pr = LV.parse_html(snap(), h.replace("Aham Verifide", "Not AHAM Verifide"))
        self.assertEqual(by_key(pr)["cadr.smoke_cfm"][0]["conditions"], {"cadr_basis": "maker_claimed"})

    def test_no_model_row_no_entity(self):
        pr = LV.parse_html(snap(), LEVOIT.replace("<li><strong>Model</strong>: Core 400S</li>", ""))
        self.assertEqual((pr.identifiers, pr.claims), ([], []))


def wrow(label, value):
    return (f'<th class="woocommerce-product-attributes-item__label" scope="row">{label}</th>'
            f'<td class="woocommerce-product-attributes-item__value"><p>{value}</p></td>')


class Winix(unittest.TestCase):
    def page(self, extra=()):
        rows = [("Model Name", "C545"), ("CADR (Dust / Pollen / Smoke)", "243 / 246 / 232"), ("HEPA Filter (Filter Life)", "99.99% True HEPA (12M)"),
                ("Timer", "No"), ("Smart Feature(s)", "WiFi / Alexa"), ("Product Dimensions (W&#8221; x D&#8221; x H&#8221;)", "13.7 x 8.4 x 20.5")] + list(extra)
        return "".join(wrow(*r) for r in rows)

    def test_cadr_order_from_label_and_basis(self):
        pr = WX.parse_html(snap(), self.page())
        self.assertEqual((known(pr, "cadr.dust_cfm"), known(pr, "cadr.smoke_cfm")), ([243], [232]))
        self.assertEqual(by_key(pr)["cadr.smoke_cfm"][0]["conditions"], {"cadr_basis": "maker_claimed"})
        pr = WX.parse_html(snap(), self.page([("AHAM Verified Room Size", "360 sq. ft.")]))
        self.assertEqual(by_key(pr)["cadr.smoke_cfm"][0]["conditions"], {"cadr_basis": "aham_verified_maker_stated"})
        self.assertEqual(known(pr, "room.size_sqft"), [360])

    def test_flags(self):
        pr = WX.parse_html(snap(), self.page())
        self.assertEqual(known(pr, "filter.true_hepa"), [True])
        self.assertEqual(known(pr, "feat.timer"), [False])                  # own row, bare No
        self.assertEqual((known(pr, "smart.wifi"), known(pr, "smart.voice")), ([True], [["alexa"]]))
        self.assertEqual((known(pr, "phys.width_in"), known(pr, "phys.height_in")), ([13.7], [20.5]))
        pr = WX.parse_html(snap(), self.page().replace("99.99% True HEPA", "HEPA-type"))
        self.assertEqual(known(pr, "filter.true_hepa"), [])

    def test_pollen_bound_and_humidifier(self):
        pr = WX.parse_html(snap(), self.page().replace("243 / 246 / 232", "482 / >450 / 461"))
        self.assertEqual((known(pr, "cadr.pollen_cfm"), known(pr, "cadr.dust_cfm")), ([], [482]))
        self.assertEqual(by_key(pr)["cadr.pollen_cfm"][0]["status"], "unknown")
        pr = WX.parse_html(snap(), wrow("Model Name", "L201") + wrow("Humidification Type", "Ultrasonic"))
        self.assertEqual(pr.identifiers, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
