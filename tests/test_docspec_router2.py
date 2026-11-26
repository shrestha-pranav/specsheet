#!/usr/bin/env python3
"""docspec-router@2 / docspec-attach-r3@2 (r6, 2026-11-25): NETGEAR bullet prose, GL.iNet in-cell sub-labels, Ubiquiti cells with
continuation lines, kit satellite blocks, and row-scoped binding on a multi-model sheet (must not cross-bind)."""
import sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CODE / "scripts"), str(CODE / "crawler"), str(CODE / "crawler" / "adapters"), str(CODE / "tests")]
import _docspec_router as RT  # noqa: E402
import docspec_r3 as R3  # noqa: E402
from test_docspec_r3 import Attach, doc, kv  # noqa: E402

# NETGEAR RS300 Technical Specifications, three-column layout as pdftotext -layout prints it (footnote digits glued to words)
NETGEAR = [
    "                                                                                                 Nighthawk® WiFi 7 Tri-Band Router",
    "    Key Features                                               Technical Specifications                                  Services & Security",
    "•   WiFi 7 from the Leader in WiFi Innovation—             •   WiFi 7 BE9300 Router Tri-band WiFi1                   •   NETGEAR Armor powered by Bitdefender®—",
    "                                                               -   2.4 GHz (2x2)",
    "    innovation and precision-engineered to NETGEAR’s           -   5 GHz (2x2)                                           enhanced security and privacy for your",
    "                                                               -   6 GHz3 (2x2)                                          connected devices and personal data, at home",
    "•   Multi-Gig Speeds with 2.5GbE Internet Port—Use             •   Powerful quad-core 2.0 GHz processor",
    "    the 2.5 Gig internet port for cable and fiber plans    •   Ports:",
    "                                                               -   (1) 2.5 Gbps internet port                        •   Access Control helps to prevent rogue devices",
    "                                                               -   (2) 2.5 Gbps Ethernet LAN ports",
    "•   2.5GbE Wired Port and More—Plug in wired                   -   (2) 10/100/1000 Mbps Gigabit Ethernet LAN         •   Supports automatic firmware updates to help",
    "    devices to improve performance via two 2.5Gbps                 ports                                                 improve security and performance*",
    "                                                               -   (1) USB 3.0 port",
]
# Orbi kit: router block read, satellite block never read
KIT = [
    "                                                                                      Whole Home Tri-band Mesh WiFi 7 System",
    "                                                         •   Tri-band with 6 streams of WiFi",
    "                                                             -   6 GHz2 (2x2)",
    "                                                         •   Multi-Gig Ethernet ports - Orbi Router",
    "                                                             -   (3) 10/100/1000/2500 Mbps Multi-Gig Ethernet",
    "                                                                 LAN ports",
    "                                                             -   (1) 10/100/1000/2500 Mbps Multi-Gig Ethernet",
    "                                                                 WAN port",
    "                                                         •   Multi-Gig Ethernet ports - Orbi Satellites",
    "                                                             -   (2) 10/100/1000/2500 Mbps Multi-Gig Ethernet",
    "                                                                 LAN ports (each)",
    "                                                         •   Processor - Satellite",
    "                                                             -   Powerful quad-core 1.5 GHz processor",
]
GLINET = [
    "    CPU                                                         Qualcomm Quad-core @1.1GHz",
    "                                                            2.4GHz: 802.11b/g/n/ax/be, 688Mbps",
    "    Wi-Fi",
    "                                                            5GHz: 802.11a/n/ac/ax/be, 2882Mbps",
    "                                                     WAN Port: 1 x 2.5G Port (10/100/1000/2500Mbps)",
    "    Ethernet Speed",
    "                                                     LAN Port: 1 x 2.5G Port (10/100/1000/2500Mbps)",
    "    Ethernet Port                                                  1 x 2.5G WAN, 1 x 2.5G LAN",
]
UBNT = [
    "Processor                          Dual-core Arm® Cortex® A53 at 1.35 GHz",
    "Networking interface               LAN: (4) GbE RJ45 ports",
    "                                   WAN: (1) GbE RJ45 port",
    "MIMO                       2.4 GHz                                  2 x 2 (UL MU-MIMO)",
    "",
    "                           6 GHz                                    4 x 4 (DL/UL MU-MIMO)",
    "WiFi standards            802.11a/b/g",
    "                          WiFi 4/WiFi 5/WiFi 6E",
]


class Parser(unittest.TestCase):
    def test_netgear_bullets(self):
        self.assertEqual(kv(RT.router(doc(*NETGEAR))), {"wifi.generation": "wifi7", "wifi.band_count": 3, "wifi.has_6ghz": True, "hw.cpu_cores": 4,
                                                       "hw.cpu_ghz": 2.0, "port.wan_speed_mbps": 2500, "port.lan_count": 4, "port.lan_max_mbps": 2500})

    def test_netgear_prose_is_not_read(self):
        # Key Features prose names WiFi 7, a 2.5 Gig internet port and two 2.5Gbps LAN ports, but no item opens with a key phrase
        self.assertEqual(RT.router(doc("•   Multi-Gig Speeds with 2.5GbE Internet Port—Use the 2.5 Gig internet port for cable and fiber plans",
                                       "•   WiFi 7 from the Leader in WiFi Innovation—Nighthawk WiFi 7 is built on 30+ years",
                                       "•   2.5GbE Wired Port and More—Plug in wired devices via two 2.5Gbps Ethernet LAN ports")), [])

    def test_kit_satellite_block_not_read(self):
        got = kv(RT.router(doc(*KIT)))
        self.assertEqual(got, {"wifi.generation": "wifi7", "wifi.band_count": 3, "wifi.has_6ghz": True, "port.lan_count": 3,
                               "port.lan_max_mbps": 2500, "port.wan_speed_mbps": 2500})          # satellite LAN (each) and CPU not read

    def test_partial_port_group_reads_no_lan(self):
        got = kv(RT.router(doc("   •   Ports:", "       -   (1) 2.5 Gbps internet port", "       -   (2) 2.5 Gbps Ethernet LAN ports",
                               "       -   Ethernet LAN ports for wired devices")))
        self.assertEqual(got, {"port.wan_speed_mbps": 2500})

    def test_split_wan_lan(self):
        got = kv(RT.router(doc("   •   (5) 10/100/1000 Mbps Gigabit Ethernet ports", "       -   1 WAN & 4 LAN")))
        self.assertEqual(got, {"port.wan_speed_mbps": 1000, "port.lan_count": 4, "port.lan_max_mbps": 1000})
        self.assertEqual(RT.router(doc("   •   (4) 10/100/1000 Mbps Gigabit Ethernet ports", "       -   1 WAN & 4 LAN")), [])   # counts disagree

    def test_glinet_in_cell(self):
        self.assertEqual(kv(RT.router(doc(*GLINET))), {"hw.cpu_cores": 4, "hw.cpu_ghz": 1.1, "hw.soc_vendor": "qualcomm", "port.wan_speed_mbps": 2500,
                                                      "port.lan_count": 1, "port.lan_max_mbps": 2500, "wifi.generation": "wifi7"})

    def test_ubiquiti_cells(self):
        self.assertEqual(kv(RT.router(doc(*UBNT))), {"hw.cpu_cores": 2, "hw.cpu_ghz": 1.35, "port.lan_count": 4, "port.lan_max_mbps": 1000,
                                                    "port.wan_speed_mbps": 1000, "wifi.has_6ghz": True, "wifi.generation": "wifi6e"})
        # two WAN statements that disagree (UDM-Pro RJ45 1G + SFP+ 10G): no WAN speed
        got = kv(RT.router(doc("Networking interface      (8) LAN: GbE RJ45 ports", "                          (1) WAN: GbE RJ45 port",
                               "SFP+ interface            (1) LAN: 10G SFP+", "                          (1) WAN: 10G SFP+")))
        self.assertNotIn("port.wan_speed_mbps", got)
        self.assertNotIn("port.lan_count", got)

    def test_ax_6ghz_not_promoted(self):
        got = kv(RT.router(doc("   •   Simultaneous quad-band WiFi", "       -   Radio 1: IEEE 802.11b/g/n/ax 2.4GHz –",
                               "       -   Radio 2: IEEE 802.11a/n/ac/ax 6GHz –")))
        self.assertEqual(got, {"wifi.band_count": 4, "wifi.has_6ghz": True})                     # 802.11ax + 6 GHz: no generation


class RowScoped(Attach):
    """A sheet naming two catalogued models, both linked from the same pages: only facts whose own row quotes the model bind (r3@2)."""

    def test_multi_model_sheet_does_not_cross_bind(self):
        d = doc("Technical Specifications      RS300   RS280S",
                "   •   Ports – RS300", "       -   (1) 2.5 Gbps internet port",
                "   •   Ports – RS280S", "       -   (4) 10/100/1000 Mbps Gigabit Ethernet LAN ports",
                "Bands        Tri-band")
        w, ents = self.world("routers", ["RS300", "RS280S"], ("wifi.band_count", 3))
        tmp = self.store("routers", d, ["rs300", "rs280s"])
        st = R3.apply({"routers": w}, [], {}, root=tmp)
        mine = {c["key"]: c for c, ob in ents["RS300"].claims if ob[0] == R3.SOURCE_ID}
        other = {c["key"]: c for c, ob in ents["RS280S"].claims if ob[0] == R3.SOURCE_ID}
        self.assertEqual(set(mine), {"port.wan_speed_mbps"})                  # the row names RS300 only
        self.assertEqual(mine["port.wan_speed_mbps"]["conditions"]["identity_scope"], "row")
        self.assertEqual(set(other), {"port.lan_count", "port.lan_max_mbps"})   # RS280S gets only its own block; the band row names no model
        self.assertGreaterEqual(st["r3_row_scoped_dropped"], 2)

    def test_manual_not_read_for_routers(self):
        d = doc("Model: RS700", "WiFi Standard        WiFi 7 (802.11be)")
        w, ents = self.world("routers", ["RS700"], ("wifi.band_count", 3))
        tmp = self.store("routers", d, ["rs700"])
        disc = tmp / "discovery.json"
        disc.write_text(disc.read_text().replace('"spec_sheet"', '"manual"'))
        st = R3.apply({"routers": w}, [], {}, root=tmp)
        self.assertEqual(st["r3_kind_skipped:routers"], 1)
        self.assertFalse([c for c, ob in ents["RS700"].claims if ob[0] == R3.SOURCE_ID])


del Attach

if __name__ == "__main__":
    unittest.main()
