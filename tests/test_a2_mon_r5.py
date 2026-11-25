"""A2-mon r5 (2026-11-25): LG badge flk.pwm / usb.kvm / res.refresh_native (lg_us@4), BenQ usb.kvm (benq_monitors@4), ASUS explicit-native
refresh (asus_monitors@4), station LiFePO₄ chemistry and the coordinator UPS-prose ruling (_powerstation, stations @4). Pure fixtures."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _powerstation as PS  # noqa: E402
import lg_us  # noqa: E402


def asset(sku, alt):
    return {"metaproperties": {"nodes": [{"name": "SKU", "options": [{"name": n} for n in sku]}]},
            "textMetaproperties": [{"name": "AltText", "value": alt}]}


def nd(*assets):
    return {"props": {"pageProps": {"cmsProductData": {"overview_feature_tab": [{"media": list(assets)}]}}}}


class LgBadge(unittest.TestCase):
    def test_exact_sku_badge(self):
        r = lg_us.lg_flicker_badge(nd(asset(["34GX900A-B"], "Flicker-Free\r\nDiscomfort Glare Free\r\nLow Blue Light Platinum")), "34GX900A-B")
        self.assertEqual(r[1], "Badge alt text: Flicker-Free / Discomfort Glare Free / Low Blue Light Platinum")

    def test_refused(self):
        self.assertIsNone(lg_us.lg_flicker_badge(nd(asset(["45GX900A-B"], "Flicker-Free")), "34GX900A-B"))            # another model's asset
        self.assertIsNone(lg_us.lg_flicker_badge(nd(asset([], "Flicker-Free")), "34GX900A-B"))                       # untagged asset
        self.assertIsNone(lg_us.lg_flicker_badge(nd(asset(["34GX900A-B", "39GX900A-B"], "Flicker-Free")), "34GX900A-B"))   # shared asset
        self.assertIsNone(lg_us.lg_flicker_badge(nd(asset(["34GX900A-B"], "Reduces screen flicker")), "34GX900A-B"))  # not the badge line


class Chemistry(unittest.TestCase):
    def test_subscript_four(self):
        self.assertEqual(PS.chemistry("LiFePO₄"), "lfp")
        self.assertEqual(PS.chemistry("LiFePO4"), "lfp")
        self.assertIsNone(PS.chemistry("Lithium"))


class UpsProse(unittest.TestCase):
    def v(self, html, names=("EL100V2", "Elite 100 V2")):
        return PS.ups_prose(html, names)[0]

    def test_exact_and_bounds(self):
        self.assertEqual(self.v("<p>10ms UPS Backup: Switches to battery power in just 10 ms.</p>"), 10)
        self.assertEqual(self.v("<li>≤10ms Pro-Grade UPS Backup: seamless switch</li>"), "up to 10")
        self.assertEqual(self.v("<p>Switchover happens in under 20ms so your router stays online.</p>"), "up to 20")
        self.assertEqual(self.v("<p>With &lt;10 ms UPS switchover, power switches to battery.</p>"), "up to 10")
        self.assertEqual(self.v("<p>sub-10ms UPS switch keeps PCs on.</p>"), "up to 10")

    def test_refused(self):
        self.assertIsNone(self.v("<p>10ms Auto-Switch: keeps NAS running.</p>"))                         # no UPS / switchover word
        self.assertIsNone(self.v("<p>&lt;30ms EPS auto-switch for essential devices</p>"))                # EPS only
        self.assertIsNone(self.v("<p>0ms Power Transition, zero worries</p>"))                             # no UPS / switchover word
        self.assertIsNone(self.v("<table><tr><td>UPS switch time</td><td>10ms</td><td>20ms</td></tr></table>"))   # comparison table
        self.assertIsNone(self.v("<p>Unlike the AC180 with 20ms UPS, this one is faster.</p>"))           # names another model
        self.assertIsNone(self.v("<p>10ms UPS.</p><p>Switchover under 20ms.</p>"))                         # two different figures
        self.assertIsNone(self.v("<p>A blink takes 100-400 ms.</p>"))


if __name__ == "__main__":
    unittest.main()
