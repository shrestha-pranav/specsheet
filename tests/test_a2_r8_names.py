"""A2-lap r8 (2026-11-26): per-adapter variant labels for SSD configuration names. A marketing_name alias carrying sku = the configuration
(sandisk_ssd@7 data-sku-title, samsung_ssd@4 one-SKU page name) names that configuration via import.py bound_label(), so a fallback name
never inherits a sibling's words (My Passport 'Gold', SN850X 'without Heatsink', SN7100S 'M.2 2280'). Pure fixtures.

  python3 -I tests/test_a2_r8_names.py
"""
import importlib.util, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
_spec = importlib.util.spec_from_file_location("specsheet_import_a2r8", ROOT / "scripts" / "import.py")
IMP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IMP)
import sandisk_ssd as SD  # noqa: E402
import _contract as C  # noqa: E402


def cap(sku, gb):
    return {"key": "gen.capacity", "value": gb, "locator": {"sku": sku, "label": "Capacity"}}


def pr(aliases, claims):
    """aliases: (text, sku-or-None)."""
    return {"aliases": [dict({"text": t, "kind": "marketing_name"}, **({"sku": s} if s else {})) for t, s in aliases], "claims": claims,
            "identifiers": []}


class BoundLabel(unittest.TestCase):
    def test_colour_from_own_title(self):
        p = pr([("WD My Passport SSD - 1TB - Gold", "WDBAGF0010BGD"), ("WD My Passport SSD - 1TB - Blue", "WDBAGF0010BBL")],
               [cap("WDBAGF0010BGD", 1000), cap("WDBAGF0010BBL", 1000)])
        self.assertEqual(IMP.own_alias(p, "WDBAGF0010BBL"), "WD My Passport SSD - 1TB - Blue")
        self.assertEqual(IMP.own_alias(p, "WDBAGF0010BGD"), "WD My Passport SSD - 1TB - Gold")

    def test_heatsink_sibling_words_never_inherited(self):
        p = pr([("SN850X 1TB Internal NVMe SSD without Heatsink", "WDS100T2X0E"), ("SN850X 1TB Internal NVMe SSD with Heatsink", "WDS100T2XHE")],
               [cap("WDS100T2X0E", 1000), cap("WDS100T2XHE", 1000)])
        self.assertEqual(IMP.own_alias(p, "WDS100T2XHE"), "SN850X 1TB Internal NVMe SSD with Heatsink")

    def test_wrong_capacity_in_own_title_removed(self):     # SN7100S SDFPTSL-512G block title says 2TB, its Capacity row 512GB
        p = pr([("SN7100S NVMe SSD - M.2 2230 - 2TB", "SDFPTSL-512G")], [cap("SDFPTSL-512G", 512)])
        self.assertEqual(IMP.own_alias(p, "SDFPTSL-512G"), "SN7100S NVMe SSD - M.2 2230")

    def test_no_capacity_claim_keeps_title(self):           # Samsung T9 page with no Capacity row: its own name stands
        p = pr([("Portable SSD T9 USB 3.2 Gen2x2 2TB (Black)", "MU-PG2T0B/AM")], [])
        self.assertEqual(IMP.own_alias(p, "MU-PG2T0B/AM"), "Portable SSD T9 USB 3.2 Gen2x2 2TB (Black)")

    def test_one_part_several_titles(self):                 # one Model Number under several capacities: capacity-free forms
        p = pr([("SN5000S - 512GB, M.2 2280, Pyrite", "SDEPNSJ"), ("SN5000S - 1TB, M.2 2280, Pyrite", "SDEPNSJ")], [cap("SDEPNSJ", 512)])
        self.assertEqual(IMP.own_alias(p, "SDEPNSJ"), "SN5000S, M.2 2280, Pyrite")
        p = pr([("SN8050S - 1TB", "SDFPNJK"), ("SN8050S - 1TB SED", "SDFPNJK")], [cap("SDFPNJK", 1000)])
        self.assertEqual(IMP.own_alias(p, "SDFPNJK"), "SN8050S")   # disagreeing descriptors: only the shared leading words

    def test_sibling_bound_alias_never_used(self):
        p = pr([("X 1TB Gold", "A")], [cap("A", 1000), cap("B", 2000)])
        self.assertIsNone(IMP.own_alias(p, "B"))            # B has no label of its own: caller falls back (neutral_name)
        self.assertIsNone(IMP.bound_label(p, "B"))

    def test_unbound_behaviour_unchanged(self):              # review-8 rules still apply to adapters that bind nothing
        p = pr([("SN850X 1TB", None), ("SN850X 1TB with Heatsink", None)], [cap("A", 1000), cap("B", 1000)])
        self.assertIsNone(IMP.own_alias(p, "A"))


class SandiskAdapter(unittest.TestCase):
    def test_title_alias_bound_to_model_number(self):
        h = ('<h1 class="pdp-product-title">Line<span></span></h1>'
             '<div class="product-title" data-sku="WDBAGF0010BBL-WESN" data-sku-title="WD My Passport SSD - 1TB - Blue"></div>'
             '<div class="product-title" data-sku="WDBAGF0010BGD-WESN" data-sku-title="WD My Passport SSD - 1TB - Gold"></div>'
             '<div id="product-specifications">'
             '<div class="active" data-sku="WDBAGF0010BBL-WESN"><div class="font-bold inheritPara">Model Number</div>'
             '<div class="inheritPara text-grey-4">WDBAGF0010BBL</div></div>'
             '<div class="hidden" data-sku="WDBAGF0010BGD-WESN"><div class="font-bold inheritPara">Model Number</div>'
             '<div class="inheritPara text-grey-4">WDBAGF0010BGD</div></div></div>')
        snap = C.Snapshot("sha256:x", C.Ref("sandisk-us-ssd", "wd-my-passport", "https://www.sandisk.com/x", {"kind": "external-ssd"}),
                          200, "2026-11-26T00:00:00Z", "https://www.sandisk.com/x", {})
        r = SD.parse_html(snap, h)
        bound = {a["sku"]: a["text"] for a in r.aliases if a.get("sku")}
        self.assertEqual(bound, {"WDBAGF0010BBL": "WD My Passport SSD - 1TB - Blue", "WDBAGF0010BGD": "WD My Passport SSD - 1TB - Gold"})


if __name__ == "__main__":
    unittest.main()
