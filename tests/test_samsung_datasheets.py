"""A2-ssd (2026-11-25): Samsung consumer SSD datasheet DRAM rows (crawler/adapters/samsung_datasheets.py). Pure fixtures, positive and
refused cases. Fixture text is cut from the stored 980 PRO Rev 2.1 / 990 EVO Rev 1.1 / 9100 PRO Rev 2.0 datasheets (pdftotext -layout)."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import samsung_datasheets as D  # noqa: E402

PRO980 = """                                          Capacity1)                    250GB               500GB                  1TB                 2TB
                                          Controller                                     Samsung in-house Controller
                                  DRAM Cache Memory                           512MB LPDDR4                   1GB LPDDR4          2GB LPDDR4
       1TB                                              Samsung SSD 980 PRO 1TB                                MZ-V8P1T0BW
                           MZ-V8P1T0
   (1,000GB*)                                              Warranty Statement                                 MZ-V8P1T0B/AM
                                                                                                              MZ-V8P2T0B/AM
"""
EVO990 = """Hardware Information                   Cache Memory                                           HMB(Host Memory Buffer)
      1TB          MZ-V9E1T0B/AM
      2TB          MZ-V9E2T0B/AM
"""
PRO9100 = "Information                  Cache Memory                   1GB LPDDR4X      2GB LPDDR4X       4GB LPDDR4X        8GB LPDDR4X\nMZ-VAP1T0B/AM\n"
CFG = [D.norm(x) for x in ("mz-v8p1t0b-am", "mz-v8p2t0b-am", "mz-v9e1t0b-am", "mz-v9e2t0b-am", "mz-vap1t0b-am")]


def run(txt, configs=CFG):
    snap = C.Snapshot("sha256:x", C.Ref(D.SOURCE, "ds", "https://semiconductor.samsung.com/x.pdf", {"configs": configs}), 200, "t",
                      "https://download.semiconductor.samsung.com/x.pdf", {})
    pr = D.parse_text(snap, txt)
    return {c["locator"]["sku"]: c["value"] for c in pr.claims if c["key"] == "hw.dram_type"}, pr


class SamsungDatasheet(unittest.TestCase):
    def test_every_cell_dram(self):
        got, pr = run(PRO980)
        self.assertEqual(got, {"MZ-V8P1T0B/AM": "dram", "MZ-V8P2T0B/AM": "dram"})       # MZ-V8P1T0BW / bare MZ-V8P1T0: not configurations
        self.assertEqual({i["scheme"] for i in pr.identifiers}, {"mfr_sku"})
        self.assertFalse(any("parent" in i for i in pr.identifiers))
        self.assertEqual({c["key"] for c in pr.claims}, {"hw.dram_type"})                 # one key only
        self.assertEqual(run(PRO9100)[0], {"MZ-VAP1T0B/AM": "dram"})                     # group label prefix, LPDDR4X

    def test_hmb(self):
        self.assertEqual(run(EVO990)[0], {"MZ-V9E1T0B/AM": "dramless_hmb", "MZ-V9E2T0B/AM": "dramless_hmb"})

    def test_refused(self):
        self.assertEqual(run(PRO980.replace("1GB LPDDR4 ", "HMB        "))[0], {})           # cells disagree = per-capacity: nothing
        self.assertEqual(run(PRO980.replace("DRAM Cache Memory", "Other Thing      "))[0], {})  # no row = silence
        self.assertEqual(run(EVO990.replace("HMB(Host Memory Buffer)", "-"))[0], {})        # a dash is not a statement
        self.assertEqual(run(PRO980, [])[0], {})                                            # untied model codes write nothing
        _, pr = run(PRO980, [])
        self.assertEqual(pr.identifiers, [])


if __name__ == "__main__":
    unittest.main()
