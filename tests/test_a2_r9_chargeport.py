"""A2-lap r9 (2026-11-26): port.charge_port enum value `dedicated` (maker names a DC-in / power-adapter / power connector of unstated shape).

  python3 -I tests/test_a2_r9_chargeport.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _xports as X  # noqa: E402
import _lports as L  # noqa: E402


class ChargePort(unittest.TestCase):
    def test_asus_dc_in(self):
        p = X.asus("1x USB 3.2 Gen 1 Type-C support display / power delivery, 1x DC-in 1x 3.5mm Combo Audio Jack 1x HDMI 1.4")
        self.assertEqual(p["charge_port"], "dedicated")
        self.assertEqual(p["segments"]["charge_port"], [1])

    def test_never_from_absence(self):
        self.assertNotIn("charge_port", X.asus("1x USB 3.2 Gen 1 Type-C support display / power delivery, 1x HDMI 1.4"))
        self.assertNotIn("charge_port", X.dell(["1 x USB Type-C 3.2 Gen 2 (10 Gbps) - supporting DisplayPort and Power Delivery"]))

    def test_dell_power_adapter_port(self):
        p = X.dell(["2 USB-C 3.2 Gen 2 (10 Gbps) ports with DisplayPort and Power Delivery", "1 power-adapter port"])
        self.assertEqual(p["charge_port"], "dedicated")

    def test_shape_stated_stays_specific(self):
        self.assertEqual(X.dell(["1 x USB Type-C 3.2 Gen 2 (10 Gbps) - DisplayPort", "1 x 4.5 mm barrel power port"])["charge_port"], "barrel")

    def test_dedicated_plus_usbc_charging_is_both(self):
        p = X.asus("2x Thunderbolt 4 with support for DisplayPort / charging, 1x DC-in")
        self.assertEqual(p["charge_port"], ["dedicated", "usb-c"])

    def test_lenovo_generic_connector(self):
        p = L.ports("1x USB-C (USB 5Gbps)^|^1x Power connector^|^1x HDMI 2.1")
        self.assertEqual(p["charge_port"], "dedicated")
        p = L.ports("1x USB-C (USB 5Gbps), with USB PD 45-65W^|^1x Slim tip (rectangle) power connector^|^1x Power connector")
        self.assertNotIn("charge_port", p)            # two different connectors named


if __name__ == "__main__":
    unittest.main()
