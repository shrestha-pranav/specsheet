"""A2 preset fill (2026-11-24), power banks: pd.pps from protocol rows, pd.pps false only by complete enumeration (A1 ruling 1),
out.max_single_port_w only from labelled single-port figures / complete per-port lists. Pure fixtures."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import belkin_powerbanks as B  # noqa: E402
import shopify_powerbanks as S  # noqa: E402
import shopify_powerbanks2 as S2  # noqa: E402


def snap(src, key):
    return C.Snapshot("sha256:x", C.Ref(src, key, "https://example.invalid/" + key, {}), 200, "t", "u", {})


def ugreen(block, sku="25188"):
    page = f"<html><body><div>Specs SKU {sku} {block} Learn More</div></body></html>"
    pr = S.parse_shop(S.UgreenPowerbanks(), snap("ugreen-us-powerbanks", sku), page, {"title": "UGREEN power bank"})
    return {c["key"]: c for c in pr.claims if c.get("status") != "unknown"}


class UgreenPPS(unittest.TestCase):
    def test_positive_port_lists_pps(self):
        c = ugreen("Output USB-C1 : 100W Max USB-C2 : 30W Max USB-A:22.5W Max Ports USB-A*1 USB-C*2 Support Protocol Input:USB-C1:PD3.0/PD2.0 "
                   "Output:USB-C1:PD3.0/PD2.0/PPS/QC3.0 USB-C2:PD3.0/PD2.0/QC3.0 USB-A:SCP/QC3.0")
        self.assertIs(c["pd.pps"]["value"], True)
        self.assertFalse(c["pd.pps"].get("conditions"))
        self.assertEqual(c["out.max_single_port_w"]["value"], 100)

    def test_complete_enumeration_false(self):
        c = ugreen("Output USB-C1 : 140W Max USB-C2 : 65W Max USB-A : 22.5W Max Ports USB-A*1 USB-C*2 Support Protocol Input:USB-C1/C2 : PD3.0/PD2.0 "
                   "Output:USB-C1/C2 :PD3.0/PD2.0/QC3.0/QC2.0/FCP/AFC/APPLE 5V2.4A/BC1.2 USB-A:QC3.0/QC2.0/FCP/AFC/BC1.2", "90597A")
        self.assertIs(c["pd.pps"]["value"], False)
        self.assertEqual(c["pd.pps"]["conditions"], {"basis": "complete_enumeration"})
        self.assertIn("USB-A:QC3.0", c["pd.pps"]["raw"])

    def test_refused_missing_port(self):         # USB-A printed in the inventory but has no protocol list: not complete
        c = ugreen("Output USB-C1 : 140W Max USB-C2 : 65W Max Ports USB-A*1 USB-C*2 Support Protocol Input:USB-C1/C2 : PD3.0 "
                   "Output:USB-C1/C2 :PD3.0/PD2.0/QC3.0", "90597A")
        self.assertNotIn("pd.pps", c)

    def test_refused_no_inventory_or_etc(self):
        c = ugreen("Output USB-C1 : 140W Max Support Protocol Input:USB-C1 : PD3.0 Output:USB-C1 :PD3.0/PD2.0/QC3.0", "90597A")
        self.assertNotIn("pd.pps", c)
        c = ugreen("Output USB-C1 : 140W Max Ports USB-C*1 Support Protocol Input:USB-C1 : PD3.0 Output:USB-C1 :PD3.0/PD2.0/QC3.0, etc.", "90597A")
        self.assertNotIn("pd.pps", c)

    def test_refused_unnumbered_port_on_two_port_bank(self):
        c = ugreen("Output USB-C1 : 140W Max Ports USB-C*2 Support Protocol Input:USB-C : PD3.0 Output:USB-C :PD3.0/PD2.0/QC3.0", "90597A")
        self.assertNotIn("pd.pps", c)


class Mophie(unittest.TestCase):
    def test_single_port_list(self):
        self.assertEqual(S2.mophie_single("1 USB-C Port - 100W1 USB-C Port - 45W1 USB-C Port - 20W"), 100)
        self.assertEqual(S2.mophie_single("MagSafe - 15W1 USB-C Port - 20W"), 20)
        self.assertEqual(S2.mophie_single("USB-C Lightning - 20WUSB-C Cable - 30W (Input/Output)USB-C Port - 30W (Input/Output)"), 30)

    def test_refused(self):
        for o in ("3 USB-C Ports - 45W", "2 USB-C Ports - 30W", "USB-C Cable and Port: 20W (Input/Output)", "30W USB-C output", "Qi2 Magnetic - 15W1 USB-C Port"):
            self.assertIsNone(S2.mophie_single(o), o)


class Belkin(unittest.TestCase):
    def test_labelled_single(self):
        self.assertEqual(B.single_port({"Wattage": "140W Single 158W Shared"}, "")[0], 140)
        self.assertEqual(B.single_port({"Output": "Maximum total output: Up to 170W | Maximum single USB-C output: Up to 100W"}, "")[0], 100)
        self.assertEqual(B.single_port({"Wattage": "65W"}, "Power Delivery up to 65W from a single USB-C port to recharge your MacBook")[0], 65)

    def test_refused(self):
        self.assertIsNone(B.single_port({"Wattage": "45W"}, "Up to 45W max output for fast, efficient charging"))
        self.assertIsNone(B.single_port({"Wattage": "15W Wireless 22.5W Wired"}, ""))


def anker(rows, title="Anker Power Bank (10K, 30W)"):
    import json
    import anker_powerbanks as A
    kp = [{"key": k, "valueList": [{"name": n, "label": v} for n, v in items]} for k, items in rows]
    nd = {"props": {"pageProps": {"product": {"title": title, "variants": [{"sku": "A1259H11", "metafields": {"infos": {"key_parameter": {"list": kp}}}}]},
                                  "metafields": {}, "deals_type": "US_PPS_collection"}}}
    pr = A.parse_page(snap("anker-us-powerbanks", "a1259"), f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script>')
    return {c["key"]: c for c in pr.claims if c.get("status") != "unknown"}


class AnkerNamedPPS(unittest.TestCase):
    def test_named_pps_row(self):
        c = anker([("Total Output", [("USB-C Output", "5V⎓3A /9V⎓3A (30W Max)"), ("[USB-C]-PPS", "3V-11V⎓2.72 (30W Max)")])])
        self.assertIs(c["pd.pps"]["value"], True)

    def test_pdo_list_is_not_an_enumeration(self):     # fixed PDOs only: never false, and the campaign string 'US_PPS_collection' is not PPS
        c = anker([("Total Output", [("USB-C", "5V⎓3A / 9V⎓3A / 20V⎓5A (100W Max)"), ("USB-A", "5V⎓3A (12W Max)")])])
        self.assertNotIn("pd.pps", c)
        self.assertEqual(c["out.max_single_port_w"]["value"], 100)
        c = anker([("Total Output", [("[USB-A]-PPS", "3V-11V⎓2A")])])
        self.assertNotIn("pd.pps", c)


if __name__ == "__main__":
    unittest.main()
