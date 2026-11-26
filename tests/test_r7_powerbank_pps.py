"""r7 power-bank PPS (A2-pb, 2026-11-26): INIU per-port Supported Protocol block, CUKTECH protocol feature bullet, EcoFlow own-page FAQ,
Samsung SFC 2.0 -> pd.pps true kind derived (basis derived, no range). Pure fixtures (texts trimmed from stored maker pages)."""
import gzip, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import pb_pps_r7 as R  # noqa: E402
import shopify_powerbanks2 as S2  # noqa: E402


def snap(src, key):
    return C.Snapshot("sha256:x", C.Ref(src, key, "https://example.invalid/" + key, {}), 200, "t", "u", {})


class Blobs:
    def __init__(self, page, prod):
        self.b = gzip.compress(json.dumps({"page": page, "product": prod}).encode())

    def read(self, snapshot, ext):
        return self.b


INIU_BLOCK = ("Tech Specs Product Model P73-E1 Category Power Bank Total Capacity 10,000mAh Output OUT1/ OUT2: 5V⎓3A 9V⎓3A 12V⎓3A 15V⎓3A 45W (Max) "
              "Supported Protocol Input port : USB-C / USB-C Cable: PD3.0 / PD2.0 / QC / FCP / AFC / APPLE 2.4A / BC1.2 / 5V ADAPTIVE; Output port: "
              "USB-C / USB-C Cable : UFCS (11V / 3A-33W) / PD3.0 / PD2.0 / QC3.0 / QC2.0 (5V / 9V / 12V) / PPS / SCP (10V / 2.25A) / BC1.2; "
              "Wireless charging: Qi 2.0 (BPP5W / EPP7.5W) Product with feature Magnetic Power Bank")


def pps(ad, src, key, page, title="power bank"):
    pr = ad.parse(snap(src, key), Blobs(page, {"title": title}), None)
    return [c for c in pr.claims if c["key"] == "pd.pps"]


class Iniu(unittest.TestCase):
    def test_output_port_block_names_pps(self):
        c = pps(R.IniuPowerbanksR7(), "iniu-us-powerbanks", "p73", f"<div>{INIU_BLOCK}</div>")
        self.assertEqual(len(c), 1)
        self.assertIs(c[0]["value"], True)
        self.assertEqual(c[0]["kind"], "official")
        self.assertEqual(c[0]["method"]["extractor"], "iniu_powerbanks@7")
        self.assertTrue(c[0]["raw"].startswith("Output port: USB-C"))

    def test_input_only_pps_writes_nothing(self):
        blk = INIU_BLOCK.replace("/ PPS /", "/").replace("PD3.0 / PD2.0 / QC / FCP", "PD3.0 / PPS / QC / FCP")
        self.assertEqual(pps(R.IniuPowerbanksR7(), "iniu-us-powerbanks", "p73", f"<div>{blk}</div>"), [])

    def test_usb_a_output_segment_is_not_pps(self):
        self.assertIsNone(R.protocol_output("Supported Protocol Input port : USB-C: PD3.0; Output port: USB-A : QC3.0 / PPS / BC1.2"))


class Cuktech(unittest.TestCase):
    def test_feature_bullet(self):
        s = R.prose_protocols("Broad Compatibility : Compatible with a wide range of fast-charging protocols, including PD, PPS, QC, FCP, and SCP, "
                              "this power bank supports all your devices. Next.")
        self.assertTrue(s.startswith("Broad Compatibility") and "PPS" in s)
        self.assertIn("ADC 2.0", R.prose_protocols("Upgrade with ADC 2.0 compatibility, supporting multiple fast-charging protocols including PPS, QC."))

    def test_negated_question_input(self):
        self.assertIsNone(R.prose_protocols("It is not compatible with protocols including PPS."))
        self.assertIsNone(R.prose_protocols("Does it support protocols such as PPS?"))
        self.assertIsNone(R.prose_protocols("Input supports protocols including PD and PPS."))


class SamsungSfc2(unittest.TestCase):
    def test_rule_phrases(self):
        self.assertTrue(R.sfc2("3. Only the USB-C port / cable supports 45W max output for Samsung and 40W for iPhone."))
        self.assertTrue(R.sfc2("It also supports Samsung Super Fast Charging 2.0."))
        self.assertIsNone(R.sfc2("The power bank supports Samsung Super Fast Charging."))         # SFC 1 / no 2.0: not the ruling
        self.assertIsNone(R.sfc2("Does not support 45W for Samsung."))
        self.assertIsNone(R.sfc2("Shop Portable Power Bank for Samsung Phone"))

    def test_derived_only_without_stated_claim(self):
        page = ("<div>Tech Specs Product Model P99 Category Power Bank Total Capacity 10,000mAh Output OUT1: 5V⎓3A 9V⎓3A 45W (Max) "
                "Weight 200g</div><p>Supports Samsung Super Fast Charging 2.0 for Galaxy S25.</p>")
        c = pps(R.IniuPowerbanksR7(), "iniu-us-powerbanks", "p99", page)
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0]["kind"], c[0]["value"], c[0]["conditions"]), ("derived", True, {"basis": "derived"}))
        self.assertIn("rule r7-sfc2", c[0]["quote"])
        stated = pps(R.IniuPowerbanksR7(), "iniu-us-powerbanks", "p73", f"<div>{INIU_BLOCK}</div><p>Supports Samsung Super Fast Charging 2.0.</p>")
        self.assertEqual([x["kind"] for x in stated], ["official"])


class EcoflowFaq(unittest.TestCase):
    PRO = ("FAQ What protocols does RAPID Pro power bank support, what is the power distribution? Supports pass-through charging. "
           "Input supports PD3.0, PPS, QC3.0;Output supports PD3.0 PPS, QC3.0, AFC, BC1.2 Why does")

    def test_output_clause_and_title_gate(self):
        self.assertIn("Output supports PD3.0 PPS", S2.ecoflow_faq_pps(self.PRO, "EcoFlow RAPID Pro Power Bank 20,000mAh"))
        self.assertIsNone(S2.ecoflow_faq_pps(self.PRO, "EcoFlow RAPID Power Bank 10,000mAh"))         # FAQ copied from another line

    def test_generic_list_and_input_only(self):
        g = "What are the protocols that support fast charging? BC1.2/Apple2.4A/QC3.0/UFCS/PD3.0/PPS How to keep"
        self.assertTrue(S2.ecoflow_faq_pps(g, "EcoFlow RAPID Power Bank 25,000mAh"))
        self.assertIsNone(S2.ecoflow_faq_pps(self.PRO.replace(";Output supports PD3.0 PPS,", ";Output supports PD3.0,"), "EcoFlow RAPID Pro Power Bank"))


if __name__ == "__main__":
    unittest.main()
