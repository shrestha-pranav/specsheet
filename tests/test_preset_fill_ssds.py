"""A2 preset fill (2026-11-24): coordinator rulings 4 (portable if.protocol affirmative only) and 5 (_ssd.dram: DRAM-less cell = dramless,
HMB unknown). Pure fixtures, positive and refused cases."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import _ssd as S  # noqa: E402
import sandisk_ssd as SD  # noqa: E402


def dt(cell):
    return dict(S.dram(cell)).get("hw.dram_type")


class DramCell(unittest.TestCase):
    def test_dramless_cell_is_hmb_unknown(self):
        for cell in ("DRAM-less", "None", "No", "DRAMless"):
            self.assertEqual(dt(cell), "dramless", cell)

    def test_no_hmb_only_when_denied(self):
        self.assertEqual(dt("DRAM-less, no HMB"), "dramless_none")
        self.assertEqual(dt("DRAM-less; HMB: No"), "dramless_none")

    def test_hmb_named(self):
        self.assertEqual(dt("HMB (Host Memory Buffer)"), "dramless_hmb")
        self.assertEqual(dt("DRAM-less, HMB"), "dramless_hmb")

    def test_dram_and_refused(self):
        self.assertEqual(S.dram("Samsung 2GB Low Power DDR4 SDRAM"), [("hw.dram_type", "dram"), ("hw.dram_size", 2), ("hw.dram_gen", "ddr4")])
        self.assertEqual(S.dram("N/A"), [])
        self.assertEqual(S.dram(""), [])


class UsbProtocol(unittest.TestCase):
    def test_affirmative(self):
        self.assertEqual(S.usb_protocol("USB 3.2 Gen 2"), "usb")
        self.assertEqual(S.usb_protocol("USB Type-C SuperSpeed USB 10Gb/s"), "usb")
        self.assertEqual(S.usb_protocol("USB 3.2 Gen 2x2 (UASP)"), "usb_uasp")

    def test_refused(self):
        for cell in ("Thunderbolt 3", "Thunderbolt 3 USB 3.2 Gen 2", "USB4 Gen 3x2 (40Gbps)", "USB Type-C", "", None):
            self.assertIsNone(S.usb_protocol(cell), cell)

    def test_registered_pcie(self):
        self.assertEqual(S.interface("PCIe® 5.0 x4, NVMe™ 2.0")[:3], [("if.protocol", "nvme"), ("if.pcie_gen", 5), ("if.pcie_lanes", 4)])


def sd_page(title, og, pairs):
    rows = "".join(f'<div class="font-bold inheritPara">{a}</div>\n<div class="inheritPara text-grey-4">{b}</div>' for a, b in pairs)
    return (f'<meta property="og:title" content="{og} | Sandisk"/><span class="product-title x" data-sku="ABC-1" data-sku-title="{title}"></span>'
            f'<div id="product-specifications"><div class="active" data-sku="ABC-1">{rows}</div></div>')


def proto(h, kind=None):
    snap = C.Snapshot("sha256:x", C.Ref("sandisk-us-ssd", "line", "https://example.invalid/line", {"kind": kind} if kind else {}), 200, "t", "u", {})
    return [c["value"] for c in SD.parse_html(snap, h).claims if c["key"] == "if.protocol"]


class SandiskName(unittest.TestCase):
    def test_title_then_og(self):
        self.assertEqual(proto(sd_page("WD Blue SN5100 NVMe SSD - 500GB", "x", [("Capacity", "500GB")])), ["nvme"])
        self.assertEqual(proto(sd_page("WD_BLACK SN8100 Bare Drive - 1TB", "1TB WD_BLACK SN8100 NVMe SSD", [("Capacity", "1TB")])), ["nvme"])
        self.assertEqual(proto(sd_page("WD Green SATA SSD 2.5in - 250GB", "x", [("Capacity", "250GB")])), ["sata_ahci"])

    def test_refused(self):
        self.assertEqual(proto(sd_page("SanDisk Ultra 3D SSD - 500GB", "500GB SanDisk Ultra 3D SSD (V2)", [("Capacity", "500GB")])), [])
        self.assertEqual(proto(sd_page("Drive NVMe to SATA kit", "x", [("Capacity", "500GB")])), [])
        # portable: the product name is never read; only an affirmative USB interface cell
        self.assertEqual(proto(sd_page("Extreme Portable SSD", "NVMe portable", [("Capacity", "1TB")]), "external-ssd"), [])
        self.assertEqual(proto(sd_page("Extreme Portable SSD", "x", [("Capacity", "1TB"), ("Interface", "USB 3.2 Gen 2")]), "external-ssd"), ["usb"])
        self.assertEqual(proto(sd_page("PRO-G40", "x", [("Capacity", "1TB"), ("Interface", "Thunderbolt 3 USB 3.2 Gen 2")]), "external-ssd"), [])


if __name__ == "__main__":
    unittest.main()
