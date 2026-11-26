"""A2-mon r8 (2026-11-26): aoc_monitors@1 (AOC US product-page spec accordion). Pure fixtures, no network."""
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import aoc_monitors as A  # noqa: E402
import registry  # noqa: E402


def page(rows, key="q27g40sde", model="Q27G40SDE", desc="", title=None):
    snap = C.Snapshot("sha256:x", C.Ref("aoc-us-monitors", key, f"https://www.aoc.com/us/gaming/monitors/{key}"), 200, "2026-11-26T00:00:00Z", "u", {})
    ld = json.dumps({"@type": "Product", "name": f"AGON by AOC {model} monitor", "brand": {"@type": "Brand", "name": "AGON by AOC"},
                     "model": model, "description": desc})
    body = "".join(f'<span class="accordion__section-button-title"><h3 class="heading heading--h5">{g}</h3></span>' if l is None else
                   f'<div class="product-specification__label"><span class="subtitle">{l}</span></div><div class="product-specification__value">'
                   + "".join(f'<span class="heading heading--h4">{x}</span>' for x in (v if isinstance(v, list) else [v])) + "</div></div>"
                   for g, l, v in rows)
    h = f"<title>{title or model}</title><script type=\"application/ld+json\">{ld}</script>{body}"
    return A.parse_html(snap, h)


def vals(pr):
    return {c["key"]: c["value"] for c in pr.claims}


G = [("Display information", None, None)]


class AocParse(unittest.TestCase):
    def test_registered(self):
        self.assertEqual(registry.SOURCES["aoc-us-monitors"]["module"], "aoc_monitors")

    def test_identity_from_jsonld_not_title(self):
        pr = page(G + [("", "Panel type", "IPS")], key="22b30h3", model="22B30H3", title="AOC 24B3HM 23.8 inch monitor")
        self.assertEqual([(i["scheme"], i["value"]) for i in pr.identifiers], [("mfr_model", "22B30H3")])
        pr = page(G + [("", "Panel type", "IPS")], key="24b3hm", model="22B30H3")          # model disagrees with the URL slug -> skipped
        self.assertFalse(pr.identifiers); self.assertTrue(pr.absences)

    def test_refresh_native_vs_oc(self):
        v = vals(page(G + [("", "Max Refresh rate", "260Hz (OC, 240Hz Native)")]))
        self.assertEqual((v["res.refresh_max"], v["res.refresh_native"]), (260, 240))
        v = vals(page(G + [("", "Max Refresh rate", "120Hz (OC, Native 100Hz)")]))
        self.assertEqual((v["res.refresh_max"], v["res.refresh_native"]), (120, 100))
        v = vals(page(G + [("", "Max Refresh rate", "180Hz OC")]))
        self.assertEqual(v["res.refresh_max"], 180); self.assertNotIn("res.refresh_native", v)
        v = vals(page(G + [("", "Max Refresh rate", "180 Hz")]))
        self.assertEqual((v["res.refresh_max"], v["res.refresh_native"]), (180, 180))

    def test_refresh_plain_blocked_by_page_copy(self):
        v = vals(page(G + [("", "Max Refresh rate", "144 Hz")], desc="With a 144Hz/OC 180Hz refresh rate"))      # 24G51F
        self.assertNotIn("res.refresh_native", v); self.assertNotIn("res.refresh_max", v)
        v = vals(page(G + [("", "Max Refresh rate", "240 Hz")], desc="an overclocked refresh rate"))
        self.assertEqual(v["res.refresh_max"], 240); self.assertNotIn("res.refresh_native", v)
        v = vals(page(G + [("", "Max Refresh rate", "144 Hz"), ("", "Digital Signal Frequency Vertical", "48~165Hz")]))
        self.assertEqual(v["res.refresh_native"], 144)                     # signal-frequency rows are not refresh claims

    def test_flicker_explicit_only(self):
        self.assertEqual(vals(page(G + [("", "Flicker-Free", "Flicker Free")]))["flk.pwm"], "none")
        self.assertEqual(vals(page(G + [("", "Flicker-Free", "TUV Flicker Free")]))["flk.pwm"], "none")
        self.assertNotIn("flk.pwm", vals(page(G + [("", "Flicker-Free", "No")])))
        self.assertNotIn("flk.pwm", vals(page(G + [("", "Blue Light Technology", "Anti Blue Light")])))

    def test_port_counts(self):
        v = vals(page(G + [("", "HDMI", "HDMI 1.4 x 1, HDMI 2.0 x 1"), ("", "DisplayPort", "Display port 1.4 (DSC) x2")]))
        self.assertEqual(v["vin.hdmi_count"], 2); self.assertNotIn("vin.hdmi_version", v); self.assertEqual(v["vin.dp_count"], 2)
        v = vals(page(G + [("", "HDMI", "HDMI 2.1 x 2"), ("", "DisplayPort", "DisplayPort 1.2 x 1, DisplayPort Out")]))
        self.assertEqual((v["vin.hdmi_count"], v["vin.hdmi_version"]), (2, "2.1")); self.assertNotIn("vin.dp_count", v)
        self.assertNotIn("vin.hdmi_count", vals(page(G + [("", "HDMI", "3x 2.1 TMDS")])))

    def test_usbc(self):
        v = vals(page(G + [("", "USB-C connectivity", "USB-C 3.2 x 1 (DP alt mode, upstream, power delivery up to 90 W)"), ("", "KVM", "1x USB3.2 Gen 2 type C + 1x type B")]))
        self.assertEqual((v["usb.usbc_inputs"], v["usb.usbc_pd_w"], v["usb.usbc_alt_dp"], v["usb.kvm"]), (1, 90, "DP Alt Mode", True))
        v = vals(page(G + [("", "USB-C connectivity", "USB-C (PD 90W) x 1"), ("", "KVM", "No")]))      # no video named: ambiguous -> nothing
        self.assertFalse({"usb.usbc_inputs", "usb.usbc_pd_w", "usb.kvm"} & set(v))
        self.assertNotIn("usb.usbc_inputs", vals(page(G + [("", "HDMI", "HDMI 2.0 x 1")])))            # zero is never written

    def test_panel(self):
        self.assertEqual(vals(page(G + [("", "Panel type", "OLED"), ("", "Backlight type", "QD OLED")]))["panel.technology"], "QD-OLED")
        self.assertEqual(vals(page(G + [("", "Panel type", "QD-OLED (5th Generation)")]))["panel.technology"], "QD-OLED")
        self.assertNotIn("panel.technology", vals(page(G + [("", "Panel type", "OLED"), ("", "Backlight type", "WLED")])))
        self.assertEqual(vals(page(G + [("", "Screen size (inch)", "23.8")]))["gen.size_class"], 24)

    def test_excerpt_drops_page_body(self):
        h = '<html><title>T</title><p>marketing</p><span class="accordion__section-button-title"><h3>G</h3></span>' \
            '<div class="product-specification__value"><span>x</span></div></div><footer>f</footer>'
        e = A.excerpt(h)
        self.assertIn("product-specification__value", e); self.assertNotIn("marketing", e); self.assertNotIn("footer", e)


if __name__ == "__main__":
    unittest.main()
