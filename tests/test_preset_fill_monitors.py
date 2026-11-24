"""A2 preset fill (2026-11-24), monitors: usb.usbc_inputs from full port lists (ruling 1: 0 only as a complete enumeration) and
gen.size_class from the stated class or, failing that, derived from the stated diagonal (ruling 3). Pure fixtures."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _monports as MP  # noqa: E402
import lg_us  # noqa: E402

ENUM = {"basis": "complete_enumeration"}


class SizeClassRule(unittest.TestCase):
    def test_round_half_up(self):
        self.assertEqual([MP.size_class(d) for d in (23.8, 31.5, 26.5, 21.45, 27, 34.14, 15.6, 24.5)], [24, 32, 27, 21, 27, 34, 16, 25])


class PortLists(unittest.TestCase):
    def test_lenovo_style_positive(self):
        n, zero = MP.count_inputs(["1x HDMI® 2.0", "1x USB-C® 3.2 Gen 1 (DP 1.4 Alt Mode and up to 75W PD), USB upstream",
                                   "2x USB-C® (USB 5Gbps / USB 3.2 Gen 1) with up to 15W PD, data transfer only, USB downstream"])
        self.assertEqual((n, zero), (1, False))

    def test_asus_style_complete_zero(self):
        self.assertEqual(MP.count_inputs(["DisplayPort 1.4 x 1", "HDMI (v2.0) x 2"]), (0, True))

    def test_downstream_only_usbc_is_zero_inputs(self):
        self.assertEqual(MP.count_inputs(["1x HDMI 2.0", "1x USB-C® 3.2 Gen 1 (15W), USB downstream"]), (0, True))

    def test_refused(self):
        self.assertEqual(MP.count_inputs(["1x HDMI 2.0", "1x USB-C® 3.2"]), (None, False))                       # role of the USB-C port unstated
        self.assertEqual(MP.count_inputs(["Thunderbolt 4 x 2 (Daisy Chain)", "HDMI(v2.1) x 1"]), (None, False))  # which TB port is the chain-out
        self.assertEqual(MP.count_inputs(["2x Thunderbolt 4 (up to 100W PD, one USB upstream, one USB downstream)"]), (None, False))
        self.assertEqual(MP.count_inputs(["2x USB-A, USB downstream"]), (None, False))                           # names no video input: not an input list
        self.assertEqual(MP.count_inputs([]), (None, False))

    def test_portable_dc_in(self):
        self.assertEqual(MP.count_inputs(["USB-C x 2 (DP Alt Mode x1 + DC In x1)", "Mini HDMI x 1"]), (1, False))


def lg(io, rest=()):
    n, zero, _ = lg_us.lg_usbc_inputs(list(io), list(rest))
    return n, zero


class LgInputOutput(unittest.TestCase):
    def test_upstream_count(self):
        self.assertEqual(lg([("USB Up-stream", "YES (USB-C, 1ea)"), ("USB Type-C", "1"), ("HDMI", "2"), ("USB-C (Power Delivery)", "65 W")]), (1, False))
        self.assertEqual(lg([("USB Type-C", "Yes (1 Up / 2 Down)"), ("USB-C (Power Delivery)", "15 W")]), (1, False))
        self.assertEqual(lg([("USB Down-stream", "YES (USB-C, 2ea)"), ("USB Type-C", "3"), ("USB-C (Power Delivery)", "90 W")]), (1, False))

    def test_complete_zero(self):
        self.assertEqual(lg([("DisplayPort", "Yes x 1"), ("HDMI", "Yes x 2"), ("Headphone Out", "Yes")]), (0, True))

    def test_refused(self):
        self.assertEqual(lg([("USB Up-stream", "Yes (via USB-C)")]), (None, False))                               # data upstream, no video evidence
        self.assertEqual(lg([("USB Type-C", "1")]), (None, False))
        self.assertEqual(lg([("HDMI", "2")], [("USB Type-C Cable", "Yes")]), (None, False))                       # USB-C named elsewhere: not complete
        self.assertEqual(lg([("Headphone Out", "Yes")]), (None, False))                                           # no video input listed
        self.assertEqual(lg([]), (None, False))


if __name__ == "__main__":
    unittest.main()
