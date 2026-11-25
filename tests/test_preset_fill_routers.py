"""A2 preset fill (2026-11-24): wifi.has_6ghz from complete maker band lists (coordinator ruling 1), NETGEAR 'WiFi Bands' rates. Pure fixtures."""
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
sys.path.insert(0, str(ROOT / "tests"))
import _contract as C  # noqa: E402
import _router as R  # noqa: E402
import _nowifi as NW  # noqa: E402
import netgear_routers as N  # noqa: E402
import tplink_routers as T  # noqa: E402
import ubiquiti_routers as U  # noqa: E402
import glinet_routers as G  # noqa: E402
from test_coverage_r3 import ui_page  # noqa: E402

NEG = {"basis": "complete_enumeration"}


def snap(src, key, hints=None):
    return C.Snapshot("sha256:x", C.Ref(src, key, "https://example.invalid/" + key, hints or {}), 200, "t", "u", {})


def six(pr):
    cs = [c for c in pr.claims if c["key"] == "wifi.has_6ghz"]
    assert len(cs) <= 1, cs
    return (cs[0]["value"], cs[0].get("conditions"), cs[0]["raw"]) if cs else None


class BandEnum(unittest.TestCase):
    def test_positive_negative_refused(self):
        self.assertIs(R.band_enum("6GHz , 5GHz-1 , 5GHz-2, 2.4GHz"), True)
        self.assertIs(R.band_enum("2.4 GHz (2x2) | 5 GHz (2x2)", 2), False)
        self.assertIs(R.band_enum("2.4G Hz, 5 GHz-1, 5 GHz-2", 3), False)       # 2.4/5/5 tri-band without 6 GHz
        self.assertIsNone(R.band_enum("2.4 GHz, 5 GHz", 3))                      # stated tri-band, two listed: incomplete
        self.assertIsNone(R.band_enum("2.4/5 GHz"))                              # shorthand: not every band is a token
        self.assertIsNone(R.band_enum("2.4 GHz up to 600 Mbps, 5 GHz up to 2.4 Gbps"))   # 'up to' never gives a negative
        self.assertIsNone(R.band_enum("5 GHz"))                                  # partial
        self.assertIsNone(R.band_enum(""))

    def test_rates_cover_class(self):
        self.assertTrue(R.rates_cover_class({"5": {"rate": 2882}, "24": {"rate": 688}}, "BE3600"))
        self.assertFalse(R.rates_cover_class({"5": {"rate": 2882}, "24": {"rate": 688}}, "BE9300"))   # a radio is missing from the list
        self.assertFalse(R.rates_cover_class({"5": {"rate": 2882}}, "BE3600"))


def ng_page(rows, band_type="Dual-band WiFi", title="Nighthawk WiFi 7 Router"):
    ld = {"@type": "Product", "sku": "X-100NAS", "additionalProperty": [{"name": "WiFi Technology", "value": "WiFi 7 technology"},
                                                                         {"name": "WiFi Band Type", "value": band_type}]}
    trs = "".join(f"<tr><td><p>{a}</p></td><td><p>{b}</p></td></tr>" for a, b in rows)
    return (f'<title>{title}</title><script type="application/ld+json">{json.dumps(ld)}</script>'
            f"<table><tbody>{trs}</tbody></table>"
            '<table><tr><th scope="row">Bands</th><td><p>2.4 + 5 + 6 GHz</p></td></tr></table>')   # comparison table: never read


class Netgear(unittest.TestCase):
    def test_band_list_false_and_rates(self):
        h = ng_page([("Speed", "5Gbps<sup>1</sup>"),
                     ("WiFi Bands", "- 2.4 GHz (2x2), 0.7 Gbps, 40 to 20 MHz, 4K-QAM - 5 GHz (3x3), 4.3 Gbps, 160 to 20 MHz, 4K-QAM")])
        pr = N.parse_html(snap("netgear-us-routers", "rs150", {"section": "routers"}), h)
        v, cond, raw = six(pr)
        self.assertEqual((v, cond), (False, NEG)); self.assertIn("2.4 GHz", raw)
        c = {x["key"]: x["value"] for x in pr.claims}
        self.assertEqual((c["wifi.rate_5_mbps"], c["wifi.streams_5"], c["wifi.rate_24_mbps"]), (4300, 3, 700))
        self.assertNotIn("wifi.max_width_5_mhz", c, "'160 to 20 MHz' is not read as a width")

    def test_product_attribute_rates(self):
        rec = ('<script>{"c_modelNumber":"RS300","c_wifiBands":"- 2.4GHz (2x2), 0.7Gbps, 40MHz - 5GHz (2x2), 2.9Gbps,160MHz - 6GHz (2x2), 5.8Gbps, 320MHz"}'
               '{"c_modelNumber":"RS700S","c_wifiBands":"- 5GHz (4x4), 5.8Gbps"}</script>')
        h = ng_page([("WiFi Bands", "- 2.4 GHz<br/><br/>- 5 GHz<br/><br/>- 6 GHz")], "Tri-band WiFi") + rec
        pr = N.parse_html(snap("netgear-us-routers", "rs300", {"section": "routers"}), h)
        c = {x["key"]: x["value"] for x in pr.claims}
        self.assertEqual((c["wifi.rate_5_mbps"], c["wifi.rate_6_mbps"], six(pr)[0]), (2900, 5800, True))
        pr = N.parse_html(snap("netgear-us-routers", "rs150", {"section": "routers"}), ng_page([("Speed", "5Gbps")]) + rec)
        self.assertNotIn("wifi.rate_5_mbps", {x["key"] for x in pr.claims}, "another product's attribute record is never read")

    def test_orbi_dual_band_rows(self):
        h = ng_page([("Simultaneous Dual-Band WiFi with enhanced backhaul", "5 GHz, 2.4 GHz"),
                     ("Simultaneous Dual-Band WiFi with enhanced backhaul", "5 GHz<br/><br/>2.4GHz")])
        self.assertEqual(six(N.parse_html(snap("netgear-us-routers", "rbe372", {"section": "mesh"}), h))[:2], (False, NEG))

    def test_affirmative_rows(self):
        h = ng_page([("Multi-link Operation: Combines two WiFi bands", "Backhaul: Shared 5 GHz &amp; 6 GHz<br/>Fronthaul: 5 GHz &amp; 6 GHz")], "Tri-band WiFi")
        self.assertEqual(six(N.parse_html(snap("netgear-us-routers", "rbe870", {"section": "mesh"}), h))[:2], (True, None))

    def test_refused(self):
        # an MLO row names two bands but is not a band list: no False; a stated tri-band listing two radios: no False; 'up to': no False
        for rows, bt in (([("Multi-link Operation: Combines two WiFi bands", "5 GHz &amp; 2.4 GHz")], "Dual-band WiFi"),
                         ([("Simultaneous Tri-Band WiFi", "5 GHz, 2.4 GHz")], "Tri-band WiFi"),
                         ([("WiFi Bands", "2.4 GHz AX: 2x2, up to 600 Mbps 5 GHz AX: 2x2, up to 2.4 Gbps")], "Dual-band WiFi")):
            self.assertIsNone(six(N.parse_html(snap("netgear-us-routers", "x", {"section": "routers"}), ng_page(rows, bt))))
        self.assertIsNone(six(N.parse_html(snap("netgear-us-routers", "x", {"section": "routers"}),
                                           ng_page([("Implicit &amp; Explicit Beamforming", "for 2.4GHz &amp; 5GHz")], "Dual-band WiFi"))))


def tp_page(rows):
    trs = "".join(f'<tr id="tr_{i}"><th width="20%">{a}</th><td>{b}</td></tr>' for i, (a, b) in enumerate(rows))
    return f'<span class="model-name">Archer BE230</span><table>{trs}</table>'


class Tplink(unittest.TestCase):
    def parse(self, rows):
        return T.parse_pages(snap("tplink-us-routers", "archer-be230", {"kind": "router"}), tp_page(rows), None)

    def test_speeds_sum_to_class(self):
        pr = self.parse([("WiFi Speeds", "BE3600<br>5 GHz: 2882 Mbps (802.11be)<br>2.4 GHz: 688 Mbps (802.11be)"), ("WiFi Capacity", "High<br>Dual-Band")])
        self.assertEqual(six(pr)[:2], (False, NEG))

    def test_frequency_row(self):
        self.assertEqual(six(self.parse([("Frequency", "2.4 GHz, 5 GHz"), ("Signal Rate", "3891 Mbps (5 GHz) + 688 Mbps (2.4 GHz)")]))[:2], (False, NEG))

    def test_refused(self):
        self.assertIsNone(six(self.parse([("WiFi Speeds", "BE9700"), ("WiFi Capacity", "High<br>Tri-Band")])))           # class only
        self.assertIsNone(six(self.parse([("WiFi Speeds", "BE9300<br>5 GHz: 2882 Mbps<br>2.4 GHz: 688 Mbps")])))         # sum short of class
        self.assertIsNone(six(self.parse([("WiFi Speeds", "BE3600<br>5 GHz: 2882 Mbps<br>2.4 GHz: 688 Mbps"), ("WiFi Capacity", "Tri-Band")])))


class Ubiquiti(unittest.TestCase):
    def test_per_radio_groups(self):
        rows = [(None, "WiFi Standard", "WiFi 7"), ("MIMO", "5 GHz", "2 x 2 (DL/UL MU-MIMO)"), ("MIMO", "2.4 GHz", "2 x 2 (DL/UL MU-MIMO)"),
                ("Max. Data Rate", "5 GHz", "4.3 Gbps (BW240)"), ("Max. Data Rate", "2.4 GHz", "688 Mbps (BW40)")]
        pr = U.parse_html(snap("ubiquiti-us-routers", "u7-lite", {"device_type": "access_point", "category": "wifi"}), ui_page(rows, "U7-Lite"))
        self.assertEqual(six(pr)[:2], (False, NEG))
        rows2 = rows + [("Max. TX Power", "6 GHz", "23 dBm")]          # another per-band group names a radio the MIMO list lacks
        self.assertIsNone(six(U.parse_html(snap("ubiquiti-us-routers", "x", {}), ui_page(rows2, "X"))))
        rows3 = [r for r in rows if r[0] != "Max. Data Rate"]          # no rate group to cross-check: refused
        self.assertIsNone(six(U.parse_html(snap("ubiquiti-us-routers", "y", {}), ui_page(rows3, "Y"))))


def gl_page(sp):
    return ('<h2 class="x">Specifications</h2><table class="table">'
            '<tr><td class="td-left">CPU</td><td class="td-right">MediaTek Quad-core, @2.0 GHz</td></tr>'
            '<tr><td class="td-left">Protocol</td><td class="td-right">IEEE 802.11a/b/g/n/ac/ax/be</td></tr>'
            f'<tr><td class="td-left">Wi-Fi Speed</td><td class="td-right">{sp}</td></tr></table>')


class Glinet(unittest.TestCase):
    def test_class_sum(self):
        pr = G.parse_html(snap("glinet-us-routers", "gl-be3600", {"title": "Slate 7 (GL-BE3600) Travel Router", "product_type": "Travel Router"}),
                          gl_page("688Mbps (2.4GHz), 2882Mbps (5GHz)"))
        self.assertEqual(six(pr)[:2], (False, NEG))
        pr = G.parse_html(snap("glinet-us-routers", "gl-mt3600be", {"title": "Beryl 7 (GL-MT3600BE) Travel Router", "product_type": "Travel Router"}),
                          gl_page("688Mbps (2.4GHz), 2882Mbps (5GHz)"))
        self.assertIsNone(six(pr), "no class number to prove the list complete")


# ---- r2, coordinator ruling 2: Wi-Fi keys not_applicable on wired gateways (complete enumeration, never absence alone)
def na(pr):
    return sorted(c["key"] for c in pr.claims if c["status"] == "not_applicable" and c.get("conditions") == NEG)


def ui_sections(rows, slugs, name="UCG-Max"):
    h = ui_page(rows, name)
    pp = json.loads(h.split(">", 1)[1].rsplit("</script>", 1)[0])
    feats = pp["props"]["pageProps"]["product"]["technicalSpecification"]["sections"][0]["features"]
    pp["props"]["pageProps"]["product"]["technicalSpecification"]["sections"] = (
        [{"section": {"label": sl, "slug": sl}, "features": feats if i == 0 else []} for i, sl in enumerate(slugs)])
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(pp) + "</script>"


GW = [(None, "Default WAN Ports", "(1) 2.5 GbE RJ45"), (None, "Max. WAN Port Count", "4"), ("Port Layout", "2.5 GbE RJ45", "5\n(2.5G/1G/100M/10M)"),
      (None, "Processor", "Quad-core ARM Cortex-A53 at 1.5 GHz"), (None, "Management", "Ethernet\nBluetooth")]
GW_HINT = {"device_type": "router", "category": "cloud-gateways"}


class WiredGateways(unittest.TestCase):
    def test_ubiquiti_gateway_without_wifi_section(self):
        pr = U.parse_html(snap("ubiquiti-us-routers", "ucg-max", GW_HINT), ui_sections(GW, ["overview", "networking", "hardware"]))
        self.assertEqual(na(pr), sorted(NW.WIFI_KEYS))
        self.assertFalse([c for c in pr.claims if c["key"].startswith("wifi.") and c["status"] == "known"])

    def test_ubiquiti_refused(self):
        for rows, slugs, hint in ((GW, ["overview", "networking", "integrated-wifi", "hardware"], GW_HINT),    # the Wi-Fi section exists
                                  (GW, ["overview", "networking"], GW_HINT),                                    # template incomplete
                                  (GW, ["overview", "hardware"], {"device_type": "access_point", "category": "wifi"}),
                                  ([r for r in GW if r[0] != "Port Layout"], ["overview", "hardware"], GW_HINT),  # no port enumeration
                                  (GW + [(None, "Mesh", "Wireless uplink")], ["overview", "hardware"], GW_HINT)):
            self.assertEqual(na(U.parse_html(snap("ubiquiti-us-routers", "x", hint), ui_sections(rows, slugs))), [], (slugs, hint))

    def gl(self, rows, title="Brume 3 (GL-MT5000) High-Speed VPN Gateway"):
        t = "".join(f'<tr><td class="td-left">{k}</td><td class="td-right">{v}</td></tr>' for k, v in rows)
        return G.parse_html(snap("glinet-us-routers", "gl-mt5000", {"title": title, "product_type": "VPN Gateway"}),
                            f'<h2 class="x">Specifications</h2><table class="table">{t}</table>')

    def test_glinet_brume(self):
        base = [("Interface", "1 x WAN Ethernet port<br>2 x LAN Ethernet ports<br>1 x USB 3.0 port<br>1 x Type-C power<br>port<br>1 x Reset button"),
                ("CPU", "MediaTek, Quad-core @2.0GHz"), ("Ethernet Speed", "10/100/1000/2500Mbps")]
        self.assertEqual(na(self.gl(base)), sorted(NW.WIFI_KEYS))
        self.assertEqual(na(self.gl(base + [("WiFi Speed", "Brume-W only: 300Mbps (2.4GHz)")])), [])     # a Wi-Fi variant exists
        self.assertEqual(na(self.gl(base + [("LEDs", "Power, WAN/WIFI, VPN")])), [])
        self.assertEqual(na(self.gl(base, "Puli (GL-XE300) 4G LTE Wireless VPN Gateway")), [])
        self.assertEqual(na(self.gl([("CPU", "MediaTek, Quad-core @2.0GHz"), ("Interface", "LAN and WAN ports")])), [])   # not an N x list

    def test_glinet_wifi4(self):
        pr = self.gl([("CPU", "QCA9531, @650MHz SoC"), ("Interface", "1 x WAN Ethernet port<br>1 x LAN Ethernet port"),
                      ("Protocol", "IEEE 802.11b/g/n"), ("Wi-Fi Speed", "300Mbps (2.4GHz)")], "Mango (GL-MT300N-V2) Wireless Mini Router")
        self.assertEqual({c["key"]: c.get("value") for c in pr.claims}.get("wifi.generation"), "wifi4")
        self.assertEqual(na(pr), [])


if __name__ == "__main__":
    unittest.main()
