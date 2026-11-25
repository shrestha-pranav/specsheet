"""A2-keys (2026-11-25): zero-emitted schema keys. Lenovo PSREF Standard Ports -> per-port port.usbc_list + port.tb_usb4 / video_out /
charge_port (crawler/adapters/_lports.py, lenovo_psref@4). Pure fixtures.

  python3 -I tests/test_zero_keys_ports.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _lports as L  # noqa: E402
import lenovo_psref as P  # noqa: E402
import _monusb as MU  # noqa: E402
import sandisk_ssd as SD  # noqa: E402
import lenovo_monitors as LM  # noqa: E402

T14S = ("1x USB-A (USB 5Gbps)^|^2x Thunderbolt 4, with USB PD 3.1 and DisplayPort 2.1, 140W input / 15W output^|^"
        "1x HDMI 2.1, up to 4K/60Hz^|^1x Headphone / microphone combo jack (3.5mm)")
IDEA = ("1x USB 3.2 Gen 1^|^1x USB-C (USB 5Gbps / USB 3.2 Gen 1), with USB PD 45-65W and DisplayPort 1.2^|^1x HDMI 1.4b^|^"
        "1x Slim tip (rectangle) power connector^|^1x Headphone / microphone combo jack (3.5mm)")
DUAL = ("1x USB-A (USB 5Gbps)^|^2x Thunderbolt 4, with USB PD 15-100W and DisplayPort 2.1 (Gorgon Point) / DisplayPort 1.4a (Hawk Point)^|^"
        "1x HDMI 2.1, up to 4K/60Hz")


class Ports(unittest.TestCase):
    def test_per_port_items_and_tb(self):
        p = L.ports(T14S)
        self.assertEqual(len(p["usbc_list"]), 2)                       # '2x' -> two ports, same stated facts each
        self.assertEqual(p["usbc_list"][0], {"protocol": "Thunderbolt 4", "dp_alt": "DisplayPort 2.1", "pd_in_w": {"max": 140}, "pd_out_w": 15})
        self.assertNotIn("usb_gbps", p["usbc_list"][0])                # 'Thunderbolt 4' prints no Gbps: never inferred
        self.assertEqual(p["tb_usb4"], "Thunderbolt 4")
        self.assertEqual(p["video_out"], "1x HDMI 2.1, up to 4K/60Hz")
        self.assertEqual(p["charge_port"], "usb-c")                    # no power connector + PD input printed
        self.assertEqual(p["segments"]["tb_usb4"], [1])

    def test_dedicated_connector_and_no_tb(self):
        p = L.ports(IDEA)
        self.assertEqual(p["usbc_list"], [{"protocol": "USB 5Gbps / USB 3.2 Gen 1", "usb_gbps": 5, "dp_alt": "DisplayPort 1.2", "pd_in_w": {"min": 45, "max": 65}}])
        self.assertEqual(p["charge_port"], "proprietary")
        self.assertNotIn("tb_usb4", p)                                 # affirmative only: no 'none'

    def test_highest_tb_wins_and_usb4(self):
        p = L.ports("1x USB-C (USB4 40Gbps), with DP 1.4^|^1x Thunderbolt 5, with USB PD 95-100W and DisplayPort 2.1")
        self.assertEqual(p["tb_usb4"], "Thunderbolt 5")
        self.assertEqual(p["segments"]["tb_usb4"], [1])
        self.assertEqual(p["usbc_list"][0]["dp_alt"], "DisplayPort 1.4")

    def test_refusals(self):
        self.assertEqual(L.ports(DUAL), {})                            # platform-dependent DP version: ambiguous for one MTM
        self.assertEqual(L.ports("1x USB-C (USB 10Gbps)^|^1x Mystery port"), {})   # unknown segment: not a complete enumeration
        p = L.ports("1x USB-C (USB 10Gbps / USB 3.2 Gen 2)^|^1x HDMI 1.4")
        self.assertNotIn("dp_alt", p["usbc_list"][0])                  # DP not printed -> absent, not 'no'
        self.assertNotIn("charge_port", p)                             # no PD input printed -> nothing
        p = L.ports("1x USB-C (USB 5Gbps), with USB PD 45-65W^|^1x Slim tip (rectangle) power connector^|^1x Round tip power connector")
        self.assertNotIn("charge_port", p)                             # two different connectors: not stated which

    def test_adapter_claims(self):
        cs = P.port_claims("21N1000AUS", T14S, "lenovo_psref@4", "2026-11-25T00:00:00Z")
        keys = {c["key"]: c for c in cs}
        self.assertEqual(set(keys), {"port.usbc_list", "port.tb_usb4", "port.video_out", "port.charge_port"})
        self.assertEqual(keys["port.usbc_list"]["raw"], T14S[:300])
        self.assertEqual(keys["port.video_out"]["locator"], {"mtm": "21N1000AUS", "column": "Standard Ports", "segments": [2]})
        lit = P.port_claims("21N1000AUS", DUAL, "lenovo_psref@4", "x")
        self.assertEqual([(c["key"], c["value"]) for c in lit], [("port.usbc_list", DUAL)])   # @3 literal kept


class MonitorUsb(unittest.TestCase):
    def test_alt_dp_input_line_only(self):
        lines = ["1x HDMI 2.0", "1x USB-C\u00ae (USB 5Gbps / 3.2 Gen 1) with USB PD 3.0 up to 100W and DisplayPort\u2122 1.4 Alt Mode HBR2, USB upstream",
                 "1x USB-C\u00ae (USB 5Gbps / USB 3.2 Gen 1) with 15W PD, data transfer only, USB downstream"]
        self.assertEqual(MU.alt_dp(lines), ("DP 1.4 Alt Mode", lines[1]))
        self.assertEqual(MU.alt_dp(["USB-C x 1 (DP Alt Mode)", "HDMI(v2.0) x 1"])[0], "DP Alt Mode")

    def test_alt_dp_refusals(self):
        self.assertEqual(MU.alt_dp(["1x Thunderbolt\u2122 4 In (Up to 100W), USB upstream"]), (None, None))     # TB input, no DP printed
        self.assertEqual(MU.alt_dp(["1x USB-C 3.2 Gen 1, USB downstream"]), (None, None))
        two = ["1x USB-C (DP 1.4 Alt Mode, up to 90W), USB upstream", "1x USB-C (DP 1.2 Alt Mode), USB upstream"]
        self.assertEqual(MU.alt_dp(two), (None, None))                                                       # never pooled across ports

    def test_kvm(self):
        self.assertEqual(MU.kvm_lenovo(["HLG^|^KVM Switch (with eKVM)^|^Smart Power"]), (True, "KVM Switch (with eKVM)"))
        self.assertEqual(MU.kvm_lenovo(["Smart Power", "Natural Low Blue Light"]), (None, None))                 # silence != no
        self.assertEqual(MU.kvm_asus({"KVM Switch": "Yes"})[0], True)
        self.assertEqual(MU.kvm_asus({"KVM Switch": "No"})[0], False)                                            # explicit maker no
        self.assertEqual(MU.kvm_asus({"USB 3.2 (Signal)": "x 1 USB Type-C (For KVM Switch)"})[0], True)
        self.assertEqual(MU.kvm_asus({"Low Blue Light": "Yes"}), (None, None))


class SsdHeatsink(unittest.TestCase):
    L = "Dimensions (L x W x H)"

    def test_without_is_none(self):
        self.assertEqual(SD.heatsink_facts("WD_BLACK SN850X 1TB Internal NVMe SSD without Heatsink", self.L, '3.15" x 0.87" x 0.09"'),
                         [("therm.heatsink", "none", "WD_BLACK SN850X 1TB Internal NVMe SSD without Heatsink", "SKU title")])

    def test_with_gives_height_only(self):
        f = SD.heatsink_facts("WD_BLACK SN8100 with Heatsink - 8TB", self.L, '3.15" x 0.98" x 0.44"')
        self.assertEqual(f, [("therm.heatsink_height", 11.18, '3.15" x 0.98" x 0.44"', self.L)])      # no enum: sink style not stated

    def test_refusals(self):
        self.assertEqual(SD.heatsink_facts("SANDISK Optimus GX PRO 8100 NVMe SSD - with Heatsink - 1TB", self.L, '3.15" x 0.87" x 0.09"'), [])  # bare row
        self.assertEqual(SD.heatsink_facts("WD_BLACK SN8100 with Heatsink - 1TB", "Dimensions", '3.15" x 0.98" x 0.38"'), [])   # axis order unstated
        self.assertEqual(SD.heatsink_facts("WD Blue SN5100 NVMe SSD - 1TB", self.L, '3.15" x 0.87" x 0.09"'), [])               # silence


class RefreshNative(unittest.TestCase):
    def test_native_stated(self):
        self.assertEqual(LM.refresh_native("144Hz"), 144)
        self.assertEqual(LM.refresh_native("165Hz (Overclock to 180Hz)\nOverclocking at 180Hz is based on laboratory test data"), 165)
        self.assertEqual(LM.refresh_native("240Hz | 280Hz (Overlock)"), 240)

    def test_never_oc_or_ambiguous(self):
        for c in ("48Hz - 120Hz", "75Hz (HDMI\u00ae only)", "DP: 165Hz (Overclock to 170Hz)", "60Hz (Typical) | 75Hz (Max.)",
                  "UHD:160Hz, FHD:320Hz", "up to 180Hz", "180Hz (OC)", "165Hz (Overclock to 144Hz)"):
            self.assertIsNone(LM.refresh_native(c), c)


if __name__ == "__main__":
    unittest.main()
