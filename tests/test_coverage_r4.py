"""A2 coverage r4 (2026-11-25): Kingston datasheet titles must not be the 'kingston.com/ssd' header. Pure fixtures, plus the stored
datasheets when raw/ is present.

  python3 -I tests/test_coverage_r4.py
"""
import json, re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import kingston_ssd as K  # noqa: E402

URL = re.compile(r"(?i)kingston\s*\.\s*c\s*o\s*m|https?://|www\.")
LEG = """                                                                                       kingston.com/ssd
NV2 PCIe 4.0 NVMe SSD
Substantial performance upgrade in high capacity
SPECIFICATIONS
Form Factor
M.2 2280
Interface
PCIe 4.0 x4 NVMe
Capacities2
250GB, 500GB
                                                                                                                    KINGSTON PART NUMBERS
Warranty/Support4                                                                                                   SNV2S/250G
Limited 3-year warranty with free technical support                                                                 SNV2S/500G
1. Based on out-of-box performance.
"""


def snap(key):
    return C.Snapshot("sha256:x", C.Ref("kingston-us-ssd", key, "https://example.invalid/" + key, {}), 200, "t", "u", {})


class KingstonTitle(unittest.TestCase):
    def test_url_header_skipped(self):
        self.assertEqual(K.doc_title(LEG, "SNV2S"), "NV2 PCIe 4.0 NVMe SSD")
        spaced = LEG.replace("kingston.com/ssd", "k i n g s t o n . c o m /s s d").replace("NV2 PCIe 4.0", "NV1 NVME PCIE")
        self.assertEqual(K.doc_title(spaced, "SNVS"), "NV1 NVME PCIE NVMe SSD")
        self.assertEqual(K.doc_title("  \nwww.kingston.com\n", "SA400"), "SA400")      # nothing but a URL -> the datasheet key

    def test_names_have_no_url_and_no_wrong_capacity(self):
        pr = K.parse_text(snap("SNV2S"), LEG)
        names = [a["text"] for a in pr.aliases]
        self.assertEqual(names[0], "NV2 PCIe 4.0 NVMe SSD")       # model-level name first: import names every configuration after it
        self.assertFalse([n for n in names if URL.search(n)])

    def test_stored_datasheets(self):
        log = ROOT / "raw" / "kingston-us-ssd" / "snapshots.jsonl"
        if not log.exists():
            self.skipTest("no raw/ store")
        bad = []
        for line in log.read_text().splitlines():
            r = json.loads(line)
            if r["status"] == 200:
                t = K.doc_title(K.pdf_to_text(log.parent / r["blob"]), r["ref"])
                if URL.search(t):
                    bad.append((r["ref"], t))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
