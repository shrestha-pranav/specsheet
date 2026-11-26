"""r10 power-bank PPS (A2-pb, 2026-11-26): Belkin regulatory leaflets (INS_*.pdf on the Demandware file path) are documents, not
marketing, and an IEC/EN/UL 62368-1 power-source class sentence (PS1-3) is never PDO evidence. Fixture text trimmed from the stored
INS_BPB029 leaflet (a 45 W bank that prints the 28 V PS3 sentence of its 240 W sibling)."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
sys.path.insert(0, str(ROOT / "crawler"))
import _docparse as X  # noqa: E402
import documents as D  # noqa: E402

BELKIN = ("https://www.belkin.com/on/demandware.static/-/Sites-master-product-catalog-blk/default/dw5113eef8/datasheets/regulatory/"
          "INS_BPB029_8850bt02241_RC-Web.pdf")

BPB029 = [
    "Do not short-circuit the power bank or store it in a receptacle where it may be short-circuited.",
    "UCB-C cable/ USB-C port (20V/5A, 21V/4.75A, 28V/5A) are classified as PS3 in IEC/EN/UL 62368-1. Only use power",
    "Product Type: UltraCharge Power Bank 10K",
    "Model No: BPB029",
    "Input: (USB-C/USB-C Cable) 5V⎓3.1A, 9V⎓3A, 12V⎓2.5A, 15V⎓2A (30W Max.)",
    "Output: (USB-C/USB-C Cable) 5V⎓3A, 9V⎓3A, 12V⎓3A, 15V⎓3A, 20V⎓2.25A (45W Max.)",
    "(PPS) 5-16V⎓2.8A",
    "Output: (USB-A) 5V⎓3A, 9V⎓2A, 12V⎓1.5A",
    "Les ports et le câble USB-C (20 V / 5 A, 21 V/4,75 A et 28 V / 5 A) sont classifiés PS3 selon la norme IEC/EN/UL 62368-1.",
]


def doc(lines):
    return {"pages": [{"n": 1, "text": "\n".join(lines), "blocks": [], "method": "text_layer"}]}


class Classify(unittest.TestCase):
    def test_demandware_catalog_path_is_not_marketing(self):
        self.assertEqual(D.classify(BELKIN, "Download Regulatory and sustainability information")[0], "certificate")

    def test_real_catalogues_stay_marketing(self):
        self.assertEqual(D.classify("https://x.example/files/2024_catalog.pdf", "")[0], "marketing")
        self.assertEqual(D.classify("https://x.example/files/product-catalog.pdf", "")[0], "marketing")
        self.assertEqual(D.classify("https://x.example/files/a.pdf", "Product Catalogue")[0], "marketing")


class SafetyClass(unittest.TestCase):
    def test_ps3_sentence_is_not_a_pdo(self):
        dev = X.power_output(doc(BPB029))["device"]
        self.assertTrue(dev)
        self.assertFalse([d for d in dev if "PS3" in d["quote"] or "62368" in d["quote"]])
        out = [d for d in dev if d["ctx"]]
        self.assertEqual(max(d["vmax"] or 0 for d in out), 20)                     # not 28 (the sibling's PS3 sentence)
        self.assertIn("5-16V 2.8A", [d["pps"] for d in out])                        # the real PPS row is still read

    def test_ps3_alone_gives_nothing(self):
        self.assertEqual(X.power_output(doc(["Output:", "USB-C port (20V/5A and 28V/5A) are classified as PS3 in IEC/EN/UL 62368-1."]))["device"], [])

    def test_ps2_line_closes_open_row(self):
        r = X.power_output(doc(["Output:", "USB-C: 5V⎓3A, 9V⎓3A", "PS2 per IEC 62368-1: 15V⎓3A", "20V⎓2.25A"]))
        self.assertEqual([p["fixed_pdos"] for p in r["ports"]], ["5V3A 9V3A"])


if __name__ == "__main__":
    unittest.main()
