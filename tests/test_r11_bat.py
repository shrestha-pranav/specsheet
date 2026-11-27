"""r11 A2-bat (2026-11-26): NITECORE power banks (nitecore_powerbanks@1) and PECRON power stations (pecron_stations@1).
Pure fixtures trimmed from stored maker pages (raw/nitecore-us-powerbanks, raw/pecron-us-stations)."""
import gzip, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "crawler" / "adapters"), str(ROOT / "crawler"), str(ROOT / "scripts")]
import _contract as C  # noqa: E402
import nitecore_powerbanks as N  # noqa: E402
import pecron_stations as PE  # noqa: E402


def snap(src, key):
    return C.Snapshot("sha256:x", C.Ref(src, key, "https://example.invalid/" + key, {}), 200, "t", "u", {})


class Blob:
    def __init__(self, body):
        self.b = gzip.compress(body)

    def read(self, snapshot, ext):
        return self.b


def row(k, v):
    return (f'<div class="spec-row" data-v-8><div class="spec-key" data-v-8><span data-v-8>{k}</span></div>'
            f'<div class="spec-value" data-v-8><span data-v-8>{v} </span></div></div>')


NB10000 = ('<meta property="og:title" content="NITECORE NB10000 Ultra Lightweight Carbon Fiber Energy Brick">' + "".join([
    row("Weight", "150g (5.29 oz)"), row("Cell", "Li-ion"), row("Capacity", "10,000mAh 3.85V (38.5Wh)"),
    row("Rated Energy", "6,400mAh 5V (TYP 1A)"), row("Input", "USB-C: 5V⎓2.4A / 9V⎓2A (18W MAX)"),
    row("Output", "USB-C: 5V⎓3A / 9V⎓2.22A / 12V⎓1.68A (20W MAX)\nUSB-A: 5V⎓3A / 9V⎓2A / 12V⎓1.5A (18W MAX)"),
    row("Total Output", "5V⎓3A (15W MAX)")]))


def nite(page, key="nb10000"):
    ad = N.NitecorePowerbanks()
    return ad.parse(snap(N.SOURCE, key), Blob(page.encode()), None)


def vals(pr):
    return {c["key"]: c.get("value") for c in pr.claims if c["status"] == "known"}


class Nitecore(unittest.TestCase):
    def test_identity_and_rows(self):
        pr = nite(NB10000)
        self.assertEqual([i["value"] for i in pr.identifiers if i["scheme"] == "mfr_model"], ["NB10000"])
        v = vals(pr)
        self.assertEqual((v["cap.cell_mah"], v["cap.energy_wh"], v["cap.cell_voltage"]), (10000, 38.5, 3.85))
        self.assertEqual(v["bat.chemistry"], "li_ion")
        self.assertEqual(v["phys.weight"], 150)
        self.assertEqual(v["in.max_w"], 18)
        self.assertEqual(v["out.max_total_w"], 15)
        self.assertEqual(pr.claims[0]["method"]["extractor"], "nitecore_powerbanks@2")

    def test_one_port_per_line(self):
        v = vals(nite(NB10000))
        self.assertEqual([(p["type"], p["max_w"]) for p in v["out.ports"]], [("usb_c", 20), ("usb_a", 18)])
        self.assertEqual(v["out.max_single_port_w"], 20)        # not the USB-A PDOs merged into the USB-C port

    def test_wireless_line_is_not_a_wired_single_port_max(self):
        page = NB10000.replace("USB-C: 5V⎓3A / 9V⎓2.22A / 12V⎓1.68A (20W MAX)\nUSB-A: 5V⎓3A / 9V⎓2A / 12V⎓1.5A (18W MAX)",
                               "USB-C: 5V⎓2.4A / 9V⎓2.22A / 12V⎓1.67A\nWireless:5W / 7.5W / 10W / 15W")
        v = vals(nite(page))
        self.assertNotIn("out.max_single_port_w", v)
        self.assertEqual(v["out.wireless_w"], 15)

    def test_rated_energy_without_clean_basis_is_unresolved(self):
        c = [c for c in nite(NB10000).claims if c["key"] == "cap.rated_mah"]
        self.assertEqual([x["status"] for x in c], ["unknown"])

    def test_name_must_equal_slug(self):
        pr = nite(NB10000, key="Carbon_Battery_6K_Kit")
        self.assertEqual(pr.identifiers, [])
        self.assertEqual(pr.claims, [])
        self.assertIn("slug", pr.absences[0]["reason"])

    def test_no_output_row_is_not_a_bank(self):
        page = '<meta property="og:title" content="NITECORE NBP68HD Battery Pack">' + row("Capacity", "3.7V 98Wh") + row("Weight", "587g")
        pr = nite(page, key="nbp68hd")
        self.assertEqual((pr.identifiers, pr.claims), ([], []))

    def test_discover_filter(self):
        self.assertTrue(N.BANK_SLUG.match("nb20000Gen3") and N.BANK_SLUG.match("carbon_battery_6k") and N.BANK_SLUG.match("summitair"))
        self.assertFalse(N.BANK_SLUG.match("nl2160hp") or N.BANK_SLUG.match("edc37") or N.BANK_SLUG.match("nu25"))


PECRON_TABLE = ('<table class="pf-inner-table"><tbody><tr><th class="A1"><span>Model</span></th><th class="B1"><span>E1000LFP</span></th></tr>'
                '<tr><th><span>Rated Power</span></th><td><span>1800W</span></td></tr><tr><th><span>Peak Power</span></th><td><span>3000W (10MS)</span></td></tr>'
                '<tr><th><span>Capacity</span></th><td><span>1024Wh </span></td></tr><tr><th><span>Output Volts</span></th><td><span>100V~120V Pure Sine Wave</span></td></tr>'
                '<tr><th><span>Battery Type</span></th><td><span>LiFePo4</span></td></tr><tr><th><span>Weight</span></th><td><span>29lbs(13.5Kg)</span></td></tr>'
                '<tr><th><span>Solar Input</span></th><td><span>XT60: Voc 11V~60V / 600W Max / 20A Max</span></td></tr></tbody></table>')
PECRON_PROD = {"title": "PECRON E1000LFP Portable Power Station 1800W 1024Wh", "body_html": "",
               "variants": [{"sku": "E1000LFP", "title": "E1000LFP"}, {"sku": "E1000LFP-200W", "title": "E1000LFP-200W"},
                            {"sku": "E1000LFP+EP3800-48V", "title": "E1000LFP+EP3800-48V"}]}


def pec(page, prod):
    body = json.dumps({"page": page, "product": prod}).encode()
    return PE.PecronStations().parse(snap(PE.SOURCE, "pecron-e1000lfp"), Blob(body), None)


class Pecron(unittest.TestCase):
    def test_table_rows(self):
        pr = pec(PECRON_TABLE, PECRON_PROD)
        self.assertEqual([i["value"] for i in pr.identifiers if i["scheme"] == "mfr_model"], ["E1000LFP"])
        v = vals(pr)
        self.assertEqual((v["out.ac_continuous_w"], v["out.ac_surge_w"], v["cap.energy_wh"]), (1800, 3000, 1024))
        self.assertEqual((v["bat.chemistry"], v["out.ac_waveform"], v["phys.weight"], v["in.solar_w"]), ("lfp", "pure_sine", 13.5, 600))
        self.assertEqual(pr.claims[0]["method"]["extractor"], "pecron_stations@2")
        self.assertNotIn("E1000LFP-200W", [i["value"] for i in pr.identifiers])       # bundle SKUs are packages, not aliases

    def test_other_models_table_skipped(self):
        pr = pec(PECRON_TABLE.replace('<th class="B1"><span>E1000LFP', '<th class="B1"><span>E2400LFP'), PECRON_PROD)
        self.assertEqual(vals(pr), {})

    def test_without_cart_variant_is_the_unit(self):
        prod = dict(PECRON_PROD, title="PECRON F3000LFP Portable Power Station 3600W 3072Wh",
                    variants=[{"sku": "F3000LFP", "title": "F3000LFP / Without Cart"}, {"sku": "F3000LFP+Cart", "title": "F3000LFP / With Cart"}])
        m, why, unit, pkg = PE.PecronStations().identity(prod, "", [])
        self.assertEqual((m, [v["sku"] for v in unit]), ("F3000LFP", ["F3000LFP"]))

    def test_approximate_weight_dropped(self):
        v = vals(pec(PECRON_TABLE.replace("29lbs(13.5Kg)", "Around 28.7kg / 63.3lb"), PECRON_PROD))
        self.assertNotIn("phys.weight", v)

    def test_keep(self):
        k = PE.PecronStations().keep
        self.assertTrue(k({"title": "PECRON E500LFP Portable Power Station 600W 576Wh"}))
        self.assertFalse(k({"title": "PECRON E1000LFP Solar Generator Kit"}) or k({"title": "PECRON EP3800-48V Expansion Battery 3840Wh"}))


class Policies(unittest.TestCase):
    def test_pending_and_pinned(self):
        import yaml
        import registry as R
        pol = {p["id"]: p for p in yaml.safe_load((ROOT / "data/decisions/policies.yaml").read_text())["claim_policies"]}
        for pid, src in (("claim/mfr-power-banks-nitecore@2", "nitecore-us-powerbanks"), ("claim/mfr-power-stations-pecron@2", "pecron-us-stations")):
            p = pol[pid]
            a = p["approval"]                                        # invariant, not a snapshot: pending, or approved with by + at
            self.assertIn(a["state"], ("pending", "approved"))
            if a["state"] == "approved":
                self.assertTrue(a.get("by") and a.get("at"))
            info = R.parser_info(src)
            self.assertEqual(p["audit"]["parsers"], {info["parser"]: info["fingerprint"]})
            self.assertEqual(p["match"]["source_ids"], [src])


if __name__ == "__main__":
    unittest.main()
