"""A2 r5 (2026-11-25): (1) import.py names each configuration from its OWN marketing alias (bound by its gen.capacity claim), never the
model's first alias; (2) lg_us@3 flk.pwm none only from a named UL flicker-free certificate in the page's own CMS copy; (3) benq_monitors@3
flk.pwm none from 'TUV Certificate: Flicker-free'. Pure fixtures.

  python3 -I tests/test_a2_r5.py
"""
import importlib.util, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
sys.path.insert(0, str(ROOT / "scripts"))
import _contract as C  # noqa: E402
import benq_monitors as BQ  # noqa: E402
import lg_us as LG  # noqa: E402

_spec = importlib.util.spec_from_file_location("specsheet_import", ROOT / "scripts" / "import.py")
IMP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IMP)


def cap(sku, gb):
    return {"key": "gen.capacity", "value": gb, "locator": {"sku": sku, "label": "Capacity"}}


def mk(aliases, claims):
    return {"aliases": [{"text": t, "kind": k} for t, k in aliases], "claims": claims}


class OwnAlias(unittest.TestCase):
    def test_team_row_aliases(self):            # one 'Model Capacity' alias per table row, model's first alias is the 4TB row
        pr = mk([("G50 EVO 4TB", "marketing_name"), ("G50 EVO 2TB", "marketing_name"), ("G50 EVO 512GB", "marketing_name")],
                [cap("TM8FGQ004T0C129", 4000), cap("TM8FGQ512G0C129", 512)])
        self.assertEqual(IMP.own_alias(pr, "TM8FGQ512G0C129"), "G50 EVO 512GB")
        self.assertEqual(IMP.own_alias(pr, "TM8FGQ004T0C129"), "G50 EVO 4TB")

    def test_sandisk_title_plus_line(self):     # per-sku title then the line name (no capacity): the titled one wins
        pr = mk([("WD_BLACK SN850X NVMe SSD 1TB", "marketing_name"), ("WD_BLACK SN850X", "marketing_name"),
                 ("WD_BLACK SN850X NVMe SSD 2TB", "marketing_name"), ("WD_BLACK SN850X", "marketing_name")], [cap("WDS200T2X0E", 2000)])
        self.assertEqual(IMP.own_alias(pr, "WDS200T2X0E"), "WD_BLACK SN850X NVMe SSD 2TB")

    def test_kingston_model_name_first(self):   # capacity-free model name first (v4 workaround) stays harmless
        pr = mk([("NV2 PCIe 4.0 NVMe SSD", "marketing_name"), ("NV2 PCIe 4.0 NVMe SSD 250GB", "marketing_name"),
                 ("NV2 PCIe 4.0 NVMe SSD 4000GB", "marketing_name")], [cap("SNV2S/4000G", 4000)])
        self.assertEqual(IMP.own_alias(pr, "SNV2S/4000G"), "NV2 PCIe 4.0 NVMe SSD 4000GB")

    def test_tb_gb_equivalence_and_tolerance(self):
        pr = mk([("X 1TB", "marketing_name")], [cap("A", 1000)])
        self.assertEqual(IMP.own_alias(pr, "A"), "X 1TB")
        pr = mk([("X 960GB", "marketing_name")], [cap("A", 1000)])
        self.assertIsNone(IMP.own_alias(pr, "A"))

    def test_no_binding_keeps_model_name(self):
        self.assertIsNone(IMP.own_alias(mk([("Laptop 15", "marketing_name")], []), "A"))            # no capacity claim (laptops)
        self.assertIsNone(IMP.own_alias(mk([("Range 500GB-4TB", "marketing_name")], [cap("A", 500)]), "A"))   # range alias: two capacities
        self.assertIsNone(IMP.own_alias(mk([("slug-1tb", "retail_slug")], [cap("A", 1000)]), "A"))   # only marketing names bind
        self.assertIsNone(IMP.own_alias(mk([("X 1TB", "marketing_name")], [cap("B", 1000)]), "A"))   # another sku's capacity


def nd(foot=None, feature=None, alt=None):
    cms = {"legal_footnote": [{"legal_text_copy": foot}] if foot else [],
           "overview_feature_tab": [{"feature_tab": [{"body": {"children": [{"children": [{"text": feature}]}]} if feature else {},
                                                      "media": [{"textMetaproperties": [{"name": "AltText", "value": alt}]}] if alt else []}]}]}
    return {"props": {"pageProps": {"cmsProductData": cms}}}


class LgFlicker(unittest.TestCase):
    FOOT = ("  1 Requires graphics card.   5 LG 4th Gen Tandem OLED has been verified as Flicker-Free, Discomfort Glare Free by UL. Certificate "
            "Number: Flicker-Free Display (OLED) - A196009, Discomfort Glare Free - V563481.   6 Software installation required. ")

    def test_numbered_certificate_footnote(self):
        t, q = LG.lg_flicker_free(nd(foot=self.FOOT))
        self.assertEqual(t, "legal footnote")
        self.assertTrue(q.startswith("5 LG 4th Gen Tandem OLED") and "A196009" in q and "Software" not in q)

    def test_ul_verified_feature_copy(self):
        self.assertEqual(LG.lg_flicker_free(nd(feature="UL-verified “Flicker-free Display”, “Discomfort Glare Free”"))[0], "overview feature")

    def test_never_maps(self):
        for f in (dict(alt="Flicker-Free\r\nDiscomfort Glare Free\r\nLow Blue Light Platinum"),       # image alt / badge list
                  dict(feature="Together, these technologies help reduce screen flicker."),
                  dict(feature="Reader Mode and Flicker Safe help reduce eye strain."),
                  dict(foot="  1 certified as Flicker-Free by UL.   2 Other. ")):                           # no numbered certificate
            self.assertIsNone(LG.lg_flicker_free(nd(**f)), f)


def benq_page(rows):
    items = "".join(f'<li class="item"><div class="name">{n}</div><div class="detail">{d}</div></li>' for n, d in rows)
    return ('<p>localNavigation.type = g6-product-spec-page</p><p>SW242Q</p>'
            f'<div class="spec-container"><p class="category">Eye Care</p><ul>{items}</ul></div>')


def bsnap():
    return C.Snapshot("sha256:x", C.Ref("benq-us-monitors", "sw242q", "https://example.invalid/sw242q", {"line": "photographer"}), 200, "t", "u", {})


class BenqTuv(unittest.TestCase):
    def pwm(self, rows):
        return [c for c in BQ.parse_html(bsnap(), benq_page(rows)).claims if c["key"] == "flk.pwm"]

    def test_tuv_flicker_free(self):
        c = self.pwm([("TUV Certificate", "Flicker-free")])
        self.assertEqual([(x["value"], x["quote"]) for x in c], [("none", "TUV Certificate: Flicker-free")])

    def test_yes_row_wins_once(self):
        c = self.pwm([("Flicker-free Technology", "Yes"), ("TUV Certificate", "Flicker-free, Low Blue Light")])
        self.assertEqual(len(c), 1)
        self.assertIn("Flicker-free Technology", c[0]["quote"])

    def test_other_tuv_marks_never_map(self):
        self.assertEqual(self.pwm([("TUV Certificate", "Low Blue Light, Eye Comfort")]), [])
        self.assertEqual(self.pwm([("Flicker-free Technology", "No")]), [])


if __name__ == "__main__":
    unittest.main()
