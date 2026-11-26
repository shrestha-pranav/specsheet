"""A2-st r7 (2026-11-26): SSD hw.nand_type from maker datasheets / page paragraphs, TV hdmi.ports_4k120 from TCL quick start guides.
Pure fixtures, positive and refused cases. Fixture text is cut from stored datasheets / guides (pdftotext -layout) and TEAMGROUP pages."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import samsung_datasheets as SD  # noqa: E402
import sandisk_datasheets as WD  # noqa: E402
import teamgroup_ssd as TG  # noqa: E402
import _docspec_tvports as TP  # noqa: E402


def nand(pr):
    return {c["locator"].get("sku") or c["locator"].get("value") or str(c["locator"]): c["value"] for c in pr.claims if c["key"] == "hw.nand_type"}


class SamsungNand(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(SD.nand_cell("  Hardware   NAND Flash Memory      Samsung V-NAND 3bit MLC")[1], "tlc")
        self.assertEqual(SD.nand_cell("               NAND Flash Memory      Samsung V-NAND TLC")[1], "tlc")
        self.assertEqual(SD.nand_cell(" Hardware      NAND Flash Memory      Samsung 4bit MLC V-NAND")[1], "qlc")
        self.assertEqual(SD.nand_cell(" Hardware      NAND Flash Memory      Samsung V-NAND 2bit MLC")[1], "mlc")

    def test_refused(self):
        self.assertIsNone(SD.nand_cell("    NAND Flash Memory     Samsung V-NAND")[1])                     # bits per cell unstated
        self.assertIsNone(SD.nand_cell("    NAND Flash Memory     Samsung V-NAND Flash memory")[1])
        self.assertIsNone(SD.nand_cell("    NAND Flash Memory     V-NAND TLC        V-NAND QLC")[1])        # per-capacity cells
        self.assertIsNone(SD.nand_cell("    NAND Flash Memory     V-NAND TLC / QLC")[1])                    # two types

    def test_binding(self):
        txt = "      NAND Flash Memory          Samsung V-NAND 3bit MLC\n  DRAM Cache Memory   1GB LPDDR4   2GB LPDDR4\nMZ-V8P1T0B/AM\nMZ-V8P9T0B/AM\n"
        snap = C.Snapshot("sha256:x", C.Ref(SD.SOURCE, "ds", "https://x/x.pdf", {"configs": [SD.norm("mz-v8p1t0b-am")]}), 200, "t", "https://x/x.pdf", {})
        pr = SD.parse_text(snap, txt)
        self.assertEqual(sorted((c["key"], c["value"]) for c in pr.claims), [("hw.dram_type", "dram"), ("hw.nand_type", "tlc")])


SN3000 = """ Model Number                                      WDS500G4G0E                       WDS100T4G0E                         WDS200T4G0E
 NAND type                                                                       SANDISK® QLC 3D NAND
    Model Number                                                                       WDS250G5G0E                            WDS500G5G0E
    NAND type                                                                                                                               SANDISK® TLC 3D NAND
"""


class SandiskNand(unittest.TestCase):
    def run_txt(self, txt, configs):
        snap = C.Snapshot("sha256:x", C.Ref(WD.SOURCE, "l--d", "https://x/d.pdf", {"line": "l", "configs": configs}), 200, "t", "https://x/d.pdf", {})
        return WD.parse_text(snap, txt)

    def test_per_table(self):
        pr = self.run_txt(SN3000, [["WDS100T4G0E-00CPS0", "WDS100T4G0E"], ["WDS500G5G0E-00VNF0", "WDS500G5G0E"]])
        got = sorted((c["locator"]["value"] if "value" in c["locator"] else str(c["locator"]), c["value"]) for c in pr.claims if c["key"] == "hw.nand_type")
        self.assertEqual([v for _, v in got], ["qlc", "tlc"])
        self.assertTrue(any("WDS100T4G0E" in k for k, v in got if v == "qlc") and any("WDS500G5G0E" in k for k, v in got if v == "tlc"))

    def test_refused(self):
        self.assertIsNone(WD.nand_value("SANDISK® 3D NAND"))
        self.assertIsNone(WD.nand_value("Western Digital® 3D NAND TLC                 Western Digital® 3D NAND QLC"))
        self.assertEqual(WD.nand_value("SANDISK® BiCS6 QLC 3D NAND"), "qlc")
        two = " MODEL NUMBERS    WDS100T4G0E    WDS200T4G0E\n NAND   SANDISK® TLC 3D NAND\n NAND TYPE   SANDISK® QLC 3D NAND\n"
        self.assertEqual(WD.nand_tables(two), [])                                                  # two NAND rows in one table


class TeamParagraph(unittest.TestCase):
    PAGE = ('<html><body>' + 'Home Product SSD Internal ' * 40 + '<div class="prIntro"><span>T-FORCE CARDEA PCIe 4.0 Z44Q SSD adopts QLC Flash and supports '
            'the latest PCIe Gen4x4 interface specifications, and has a capacity of up to 4TB to choose from.</span></div>{extra}</body></html>')

    def test_paragraph_and_conflict(self):
        got = {}
        for block in TG.INTRO.findall(self.PAGE.format(extra="")):
            got.update({k: v[0] for k, v in TG.SP.extract(block)["claims"].items()})
        self.assertEqual(got.get("hw.nand_type"), "qlc")
        two = self.PAGE.format(extra='<div class="prIntro">Built with 3D TLC NAND flash for daily use.</div>')
        vals = {TG.SP.extract(b)["claims"].get("hw.nand_type", (None,))[0] for b in TG.INTRO.findall(two)}
        self.assertEqual(vals, {"qlc", "tlc"})                                                     # parse_html then writes nothing


def doc(text):
    return {"pages": [{"n": 12, "text": text, "method": "text_layer"}]}


class TvPorts(unittest.TestCase):
    def test_qsg(self):
        f = TP.tv(doc("HDMI port 1: Supports up to 4K/144Hz\n  HDMI port 2: Supports up to 4K/120Hz  I CABLE\n HDMI ports 3 & 4: Supports up to 4K/60Hz"))
        self.assertEqual({x["key"]: x["value"] for x in f}, {"hdmi.ports_4k120": 2, "hdmi.has_4k120": True})

    def test_refused(self):
        self.assertEqual(TP.tv(doc("HDMI ports 1 & 2: Supports up to 4K/144Hz\nHDMI port 4: Supports up to 4K/60Hz")), [])      # port 3 missing
        self.assertEqual(TP.tv(doc("HDMI port 1: Supports up to 4K/144Hz")), [])                                                # one statement
        self.assertEqual(TP.tv(doc("HDMI ports 1 & 2: Supports up to 4K/144Hz\nHDMI ports 3 & 4: Supports up to 4K/60Hz\n"
                                   "*120Hz is only supported for 65”/75”.")), [])                                     # size footnote
        self.assertEqual(TP.tv({"pages": [{"n": 1, "text": "HDMI ports 1 & 2: Supports up to 4K/144Hz\nHDMI ports 3 & 4: Supports up to 4K/60Hz",
                                           "method": "ocr"}]}), [])                                                             # OCR not read

    def test_zero(self):
        f = TP.tv(doc("HDMI ports 1 & 2: Supports up to 4K/60Hz\nHDMI port 3: Supports up to 4K/60Hz"))
        self.assertEqual({x["key"]: x["value"] for x in f}, {"hdmi.ports_4k120": 0})


if __name__ == "__main__":
    unittest.main()
