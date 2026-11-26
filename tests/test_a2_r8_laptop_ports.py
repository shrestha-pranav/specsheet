"""A2-lap r8 (2026-11-26): per-port USB-C facts for ASUS / Dell / Microsoft Surface (crawler/adapters/_xports.py; asus@3, dell@2,
surface@2). Pure fixtures: positive cases and the refusals (hedges, platform conditions, unknown segments, pooled facts).

  python3 -I tests/test_a2_r8_laptop_ports.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _xports as X  # noqa: E402
import _contract as C  # noqa: E402

ROG = ("1x 3.5mm Combo Audio Jack, 1x HDMI 2.0b, 1x USB 3.2 Gen 2 Type-C with support for DisplayPort™ / power delivery (data speed up to 10Gbps)\\n"
       "1x USB 3.2 Gen 2 Type-A (data speed up to 10Gbps)\\n1x Thunderbolt™ 4 support DisplayPort™ / power delivery\\n1x RJ45 LAN port")
EXPERT = ("2x Thunderbolt™ 4, compliant with USB4, supports display / power delivery 2x USB 3.2 Gen 1 Type-A, 1x RJ45 Gigabit Ethernet "
          "1x 3.5mm Combo Audio Jack 1x HDMI 2.1 TMDS, Smart card reader Micro SD card reader, *Smart card reader is an optional feature.")
DELL = ["2x USB Type‑C with Thunderbolt™ 4 (40 Gbps) – supporting USB4, DisplayPort™ 2.1 and Power Delivery",
        "1x USB Type‑A 3.2 Gen 1 (5 Gbps) – with PowerShare", "1x HDMI 2.1", "1x Global headset jack"]
ULTRA = ["2 × USB-C® / USB4® ports", "1 × USB-C® / USB4® port with Magnetic Connect",
         "All USB-C® ports support 140W charging, 40 Gbps data transfer, and DisplayPort 2.1 with support for up to three 4K monitors at 60 Hz",
         "Fast charging with a minimum 115W Surface Power Supply or minimum 115W USB-C® PD charger", "HDMI 2.1b", "USB-A 3.1", "SD card reader",
         "3.5 mm headphone jack"]


class Asus(unittest.TestCase):
    def test_per_port_items(self):
        p = X.asus(ROG)
        self.assertEqual(p["usbc_list"], [{"protocol": "USB 3.2 Gen 2", "usb_gbps": 10, "dp_alt": "DisplayPort"},
                                          {"protocol": "Thunderbolt 4", "dp_alt": "DisplayPort"}])   # 40Gbps not printed on the TB4 group: absent
        self.assertEqual(p["tb_usb4"], "Thunderbolt 4")
        self.assertEqual(p["video_out"], "1x HDMI 2.0b")
        self.assertNotIn("charge_port", p)            # bare 'power delivery': direction and W unstated
        self.assertNotIn("pd_in_w", p["usbc_list"][0])

    def test_comma_inside_group_and_footnote(self):
        p = X.asus(EXPERT)
        self.assertEqual(len(p["usbc_list"]), 2)
        self.assertNotIn("dp_alt", p["usbc_list"][0])  # 'support display' does not name DisplayPort
        self.assertEqual(p["video_out"], "1x HDMI 2.1 TMDS")

    def test_refusals(self):
        self.assertEqual(X.asus("Up to 2x USB 3.2 Gen 1 Type C support display/power delivery Up to 2x USB 3.2 Gen 1 Type-A"), {})   # hedged USB-C
        self.assertEqual(X.asus("2x USB 3.2 Gen 1 Type-A, 1x 3.5mm Combo Audio Jack"), {})            # no USB-C: nothing (never 'none')
        self.assertEqual(X.asus("1x Type-C USB 4 (data speed up to 40Gbps) 1x Mystery port"), {})     # unknown group
        self.assertEqual(X.asus_options(["1x Thunderbolt 4 with support for DisplayPort", "1x USB 3.2 Gen 2 Type-C"]), {})  # options disagree
        self.assertEqual(X.asus("Up to 2x USB 3.2 Gen 1 Type-A 1x Type-C USB 4")["tb_usb4"], "USB4")  # hedge on USB-A only is harmless


class Dell(unittest.TestCase):
    def test_tb4_and_usb4(self):
        p = X.dell(DELL)
        self.assertEqual(p["usbc_list"], [{"protocol": "Thunderbolt 4", "usb_gbps": 40, "dp_alt": "DisplayPort 2.1"}] * 2)
        self.assertEqual(p["tb_usb4"], "Thunderbolt 4")  # TB4 outranks the 'supporting USB4' on the same group
        self.assertEqual(p["segments"]["video_out"], [2])

    def test_barrel_and_unknown_power(self):
        p = X.dell(["1 x USB Type‑C 3.2 Gen 2 (10 Gbps) – supporting DisplayPort™ and Power Delivery", "1 x 4.5 mm barrel power port"])
        self.assertEqual(p["charge_port"], "barrel")
        p = X.dell(["2 USB-C 3.2 Gen 2 (10 Gbps) ports with DisplayPort™ and Power Delivery", "1 power-adapter port"])
        self.assertNotIn("charge_port", p)            # dedicated port of unstated shape: nothing
        self.assertEqual(p["usbc_list"][0]["dp_alt"], "DisplayPort")

    def test_refusals(self):
        self.assertEqual(X.dell(["AMD Ryzen™ 200 Series:", "2 x USB Type‑C with Thunderbolt™ 4.0 (40 Gbps) – supporting DisplayPort™ 1.4a"]), {})
        self.assertEqual(X.dell(["1x USB Type‑C 3.2 Gen 2x2 (20 Gbps) – supporting DisplayPort™ 1.4 and Power Delivery OR 1x USB Type‑A"]), {})
        self.assertEqual(X.dell(["1 Thunderbolt™ 4 (40 Gbps) with Power Delivery (optional)"]), {})
        self.assertEqual(X.dell(["2x Thunderbolt™ 5 (80/120 Gbps) – supporting DisplayPort 2.1"])["usbc_list"][0].get("usb_gbps"), None)  # two figures


class Surface(unittest.TestCase):
    def test_all_ports_line_is_attributed(self):
        p = X.surface(ULTRA)
        self.assertEqual(len(p["usbc_list"]), 3)
        self.assertEqual(p["usbc_list"][2], {"protocol": "USB4", "usb_gbps": 40, "dp_alt": "DisplayPort 2.1", "pd_in_w": {"max": 140}})
        self.assertEqual(p["charge_port"], "usb-c")
        self.assertEqual(p["video_out"], "HDMI 2.1b")

    def test_surface_connect_clash_and_unattributed_dp(self):
        ls = ["2 × USB-C® / USB4® ports with support for charging and data transfer", "DisplayPort 1.4 with support for up to three 4K monitors at 60 Hz",
              "Fast charging through Surface Connect or USB-C®", "USB-A 3.2", "Surface Connect port"]
        p = X.surface(ls)
        self.assertNotIn("charge_port", p)            # two charge paths stated
        self.assertNotIn("dp_alt", p["usbc_list"][0])  # the DP line is not attributed to a port

    def test_sections_must_agree(self):
        a = ["2 × USB-C / USB4 ports with support for charging", "USB-A 3.2"]
        b = ["2 × USB-C with USB4 / Thunderbolt 4 with support for charging", "USB-A 3.2"]
        self.assertEqual(X.surface(["13.8-inch:"] + a + ["15-inch:"] + a)["tb_usb4"], "USB4")
        self.assertEqual(X.surface(["13.8-inch:"] + a + ["15-inch:"] + b), {})
        self.assertEqual(X.surface(a + ["15\" model only:", "1 × HDMI 2.1"]), {})   # a model-only section carrying a port


class Claims(unittest.TestCase):
    def test_replace_keeps_literal_when_not_understood(self):
        pr = C.ParseResult()
        pr.claims.append(C.claim("X1", "port.usbc_list", ["1x Mystery"], None, "1x Mystery", "s1", "dell@2", "adapter", "t", locator={"model_code": "X1"}))
        self.assertFalse(X.replace_claims(pr, C, pr.claims[0], X.dell(["1x Mystery"]), "X1"))
        self.assertEqual([c["key"] for c in pr.claims], ["port.usbc_list"])
        self.assertTrue(X.replace_claims(pr, C, pr.claims[0], X.dell(DELL), "X1"))
        self.assertEqual({c["key"] for c in pr.claims}, {"port.usbc_list", "port.tb_usb4", "port.video_out"})
        self.assertEqual(next(c for c in pr.claims if c["key"] == "port.video_out")["locator"], {"model_code": "X1", "segments": [2]})


if __name__ == "__main__":
    unittest.main()
