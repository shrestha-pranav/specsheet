"""A2 coverage r2 (2026-11-24): Lenovo upstream PD, SSD page-prose silicon statements, Kingston datasheet blocks. Pure fixtures, no network."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import lenovo_monitors as LM  # noqa: E402
import _ssdprose as SP  # noqa: E402
import kingston_ssd as K  # noqa: E402


class LenovoUpstreamPd(unittest.TestCase):
    def test_number_before_pd_and_upstream_only(self):
        self.assertEqual(LM.upstream_pd_w("1x USB-C® 3.2 Gen 1 (DP 1.4 Alt Mode and up to 90W PD), USB upstream"), 90.0)
        self.assertEqual(LM.upstream_pd_w("1x USB-C® (USB 10Gbps / 3.2 Gen 2) with USB PD 3.1 up to 140W and DisplayPort™ 1.4 Alt Mode HBR3, USB upstream"), 140.0)
        self.assertIsNone(LM.upstream_pd_w("1x USB-C® (USB 5Gbps / USB 3.2 Gen 1) with 15W PD, data transfer only, USB downstream"))
        self.assertIsNone(LM.upstream_pd_w("1x USB-B 3.2 Gen 1, USB upstream"))
        self.assertEqual(LM.upstream_pd_w("2x Thunderbolt™ 4 (up to 100W PD, one USB upstream, one USB downstream)"), 100.0)


class SsdProse(unittest.TestCase):
    def test_affirmative_only(self):
        r = SP.extract("<p>The A440 Lite features the PHISON PS5027-E27T control chip and 3D TLC NAND.</p>")["claims"]
        self.assertEqual((r["hw.controller"][0], r["hw.controller_vendor"][0], r["hw.nand_type"][0]), ("Phison PS5027-E27T", "phison", "tlc"))
        self.assertEqual(SP.extract("<p>T-FORCE G70 Pro / G70 PCIe 4.0 SSD use InnoGrit controller solutions by default.</p>")["claims"], {})
        self.assertEqual(SP.extract("<p>nCache 2.0 uses a combination of both SLC and TLC flash blocks to improve endurance.</p>")["claims"], {})
        r = SP.extract("<p>A vertically integrated DRAM-less design for laptops and desktops.</p>")["claims"]   # r3: bare DRAM-less = dramless (HMB unstated)
        self.assertEqual(r["hw.dram_type"][0], "dramless", "bare DRAM-less says neither HMB nor none")
        r = SP.extract("<p>Built with 3D QLC NAND flash memory, the SSD supports SLC Caching and Host Memory Buffer (HMB) technologies.</p>")["claims"]
        self.assertEqual((r["hw.nand_type"][0], r["hw.dram_type"][0]), ("qlc", "dramless_hmb"))
        c = SP.extract("<p>Built with Sandisk TLC 3D NAND for gamers.</p><p>Get cost-efficient QLC 3D NAND storage today.</p>")
        self.assertIn("hw.nand_type", c["conflicts"]); self.assertNotIn("hw.nand_type", c["claims"])

    def test_vendor_only_inside_the_nand_phrase(self):
        r = SP.extract("<p>Powered by PCIe Gen 5.0 and next-gen TLC 3D NAND, the Sandisk PC SN8050S delivers speed.</p>")["claims"]
        self.assertNotIn("hw.nand_vendor", r)
        r = SP.extract("<p>It is powered by our 8th generation SANDISK BiCS TLC 3D CBA NAND.</p>")["claims"]
        self.assertEqual(r["hw.nand_vendor"][0], "sandisk")


KTXT = """Specifications M.2 2280
  Form factor                                      M.2 2280
  Interface                                        PCIe 4.0 x4 NVMe
  Capacities3                                      1024GB, 2048GB
  Controller                                       Phison E18
  NAND                                             3D TLC
  DRAM Cache                                       Yes
  Sequential read/write1                           1024GB – 7,000/6,000MB/s
                                                   2048GB – 7,000/7,000MB/s
  Total Bytes Written (TBW)3                       1024GB – 800TBW
                                                   2048GB – 1.6PBW
  Warranty/support4                                Limited 5-year warranty with free technical support
Part Numbers
  SKC3000D/1T0                                                      SKC3000D/2048G
"""


class KingstonDatasheet(unittest.TestCase):
    def test_per_capacity_rows(self):
        import _contract as C
        snap = C.Snapshot("sha256:x", C.Ref("kingston-us-ssd", "KC3000", "https://www.kingston.com/datasheets/KC3000_us.pdf", {}), 200, "t", "u", {})
        pr = K.parse_text(snap, KTXT)
        got = {(c["locator"]["sku"], c["key"]): c["value"] for c in pr.claims}
        self.assertEqual(got[("SKC3000D/1T0", "gen.capacity")], 1024)
        self.assertEqual((got[("SKC3000D/1T0", "perf.seq_write")], got[("SKC3000D/2048G", "perf.seq_write")]), (6000, 7000))
        self.assertEqual(got[("SKC3000D/2048G", "end.tbw")], 1600)
        self.assertEqual((got[("SKC3000D/1T0", "hw.controller_vendor")], got[("SKC3000D/1T0", "hw.dram_type")]), ("phison", "dram"))


if __name__ == "__main__":
    unittest.main()
