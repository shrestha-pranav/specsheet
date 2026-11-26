"""A2-dell r6 (2026-11-25): dell_monitors@2 (Dell US /apd/ Tech Specs block) and the labelled UPS-row bound (_powerstation, stations @6).
Pure fixtures, no network."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
sys.path.insert(0, str(ROOT / "scripts"))
import _contract as C  # noqa: E402
import _powerstation as PS  # noqa: E402
import dell_monitors as D  # noqa: E402
import registry  # noqa: E402

SNAP = C.Snapshot("sha256:x", C.Ref("dell-us-monitors", "p2726he", "https://www.dell.com/x/p2726he/-"), 200, "2026-11-25T00:00:00Z", "u", {})


def page(rows, key="p2726he"):
    snap = C.Snapshot("sha256:x", C.Ref("dell-us-monitors", key, f"https://www.dell.com/x/{key}/-"), 200, "2026-11-25T00:00:00Z", "u", {})
    body = "".join(f'<div class=spec__child__heading>{g}</div>' if l is None else
                   f'<div class=spec__item><div class=spec__item__title>{l}</div>{v}</div>' for g, l, v in rows)
    return D.parse_html(snap, '<div id=accessoriesTechSpecs class="x">' + body + "</div>")


def vals(pr):
    return {c["key"]: (c["value"], c.get("conditions")) for c in pr.claims}


GEN = [("General Information", None, None), ("", "Manufacturer Part Number", "ABC12"), ("", "Product Model", "P2726HE")]


class DellParse(unittest.TestCase):
    def test_identity_and_wost(self):
        pr = page(GEN)
        self.assertEqual([(i["scheme"], i["value"]) for i in pr.identifiers], [("mfr_model", "P2726HE"), ("x_dell_part_number", "ABC12")])
        pr = page([GEN[0], GEN[1], ("", "Product Model", "P2426H WOST")], key="p2426h_wost")
        self.assertEqual(pr.identifiers[0]["value"], "P2426H")
        pr = page([GEN[0], ("", "Product Model", "P2426H")], key="s2725qs_monitor")    # URL code disagrees -> skipped
        self.assertFalse(pr.identifiers); self.assertTrue(pr.absences)

    def test_flicker_explicit_only(self):
        self.assertEqual(vals(page(GEN + [("", "Flicker Free", "Yes")]))["flk.pwm"][0], "none")
        self.assertEqual(vals(page(GEN + [("", "Features", "<ul><li>Anti-glare</li><li>Flicker-free</li></ul>")]))["flk.pwm"][0], "none")
        self.assertNotIn("flk.pwm", vals(page(GEN + [("", "Flicker Free", "No")])))
        self.assertNotIn("flk.pwm", vals(page(GEN + [("", "Features", "<ul><li>ComfortView Plus</li><li>Eye Comfort Technology</li></ul>")])))

    def test_refresh_native_needs_agreement(self):
        base = GEN + [("", "Maximum Resolution", "1920 x 1080")]
        v = vals(page(base + [("", "Standard Refresh Rate", "500 Hz"), ("", "Maximum Preset Resolution", "<ul><li>1920 x 1080 at 255Hz (HDMI)</li><li>1920 x 1080 at 480Hz</li></ul>")]))
        self.assertNotIn("res.refresh_native", v); self.assertEqual(v["res.refresh_max"][0], 500)
        v = vals(page(base + [("", "Standard Refresh Rate", "120 Hz"), ("", "Maximum Preset Resolution", "1920 x 1080 at 120 Hz")]))
        self.assertEqual(v["res.refresh_native"][0], 120)
        self.assertNotIn("res.refresh_native", vals(page(base + [("", "Standard Refresh Rate", "120 Hz")])))

    def test_usbc_ports(self):
        det = ("", "Interface/Port Details", "<ul><li>1 HDMI port</li><li>2 USB Type-A 5Gbps downstream port/s1 USB-C 5Gbps upstream port/s (DisplayPort 1.4 Alt Mode, "
               "Power Delivery up to 100W)</li><li>2 USB-C 5Gbps downstream port/s (Power Delivery up to 15 W)</li></ul>")
        v = vals(page(GEN + [det, ("", "USB Type-C (Power Delivery) Downstream", "15 W")]))
        self.assertEqual(v["usb.usbc_inputs"][0], 1)                    # the glued line is split, so the input is not lost (no false 0)
        self.assertEqual(v["usb.usbc_pd_w"][0], 100)                    # the downstream row never counts
        self.assertEqual(v["usb.usbc_alt_dp"][0], "DP 1.4 Alt Mode")
        v = vals(page(GEN + [("", "USB Type-C", "No"), ("", "Interface/Port Details", "<ul><li>1 HDMI port</li></ul>")]))
        self.assertEqual(v["usb.usbc_inputs"], (0, None))
        down = ("", "Interface/Port Details", "<ul><li>1 x HDMI port</li><li>2 USB-C 5Gbps downstream port/s</li></ul>")
        self.assertEqual(vals(page(GEN + [down, ("", "Total Number of USB Type-C Ports", "2")]))["usb.usbc_inputs"], (0, {"basis": "complete_enumeration"}))
        self.assertNotIn("usb.usbc_inputs", vals(page(GEN + [down, ("", "Total Number of USB Type-C Ports", "3")])))   # a USB-C port is not listed
        usb = ("", "Interface/Port Details", "<ul><li>1 HDMI port</li><li>1 USB 5Gbps Type-B upstream port</li><li>2 USB 5Gbps Type-A downstream ports</li></ul>")
        self.assertEqual(vals(page(GEN + [usb, ("", "Number of USB Ports", "3")]))["usb.usbc_inputs"], (0, {"basis": "complete_enumeration"}))
        self.assertNotIn("usb.usbc_inputs", vals(page(GEN + [usb, ("", "Number of USB Ports", "5")])))            # list incomplete
        self.assertNotIn("usb.usbc_inputs", vals(page(GEN + [usb, ("", "Number of USB Ports", "3"), ("", "USB Type-C", "Yes")])))   # a USB-C port exists
        amb = ("", "Interface/Port Details", "<ul><li>1 HDMI port</li><li>3 USB-C 10Gbps upstream port/s</li></ul>")
        self.assertNotIn("usb.usbc_inputs", vals(page(GEN + [amb])))

    def test_counts_cross_checked(self):
        det = ("", "Interface/Port Details", "<ul><li>2 HDMI port/s</li><li>2 DisplayPort 1.4 port/s</li></ul>")
        v = vals(page(GEN + [det, ("", "Total Number of HDMI Ports", "2"), ("", "Number of DisplayPorts", "0")]))
        self.assertEqual(v["vin.hdmi_count"][0], 2); self.assertNotIn("vin.dp_count", v)    # U5226KW-style contradiction -> nothing

    def test_kvm(self):
        self.assertEqual(vals(page(GEN + [("", "Built-in Devices", "<ul><li>KVM Switch</li><li>USB Hub</li></ul>")]))["usb.kvm"][0], True)
        self.assertNotIn("usb.kvm", vals(page(GEN + [("", "Built-in Devices", "USB Hub")])))


class UpsRowBound(unittest.TestCase):
    def run_row(self, v):
        pr = C.ParseResult()
        PS.emit_rows(pr, "x@1", SNAP, "M1", {"Backup UPS": v}, "spec")
        return [c["value"] for c in pr.claims if c["key"] == "ups.switchover_ms"]

    def test_bounds(self):
        for v in ("＜20ms, Online UPS: 0ms", "≤20ms", "<20ms", "under 20 ms", "within 20ms", "less than 20ms"):
            self.assertEqual(self.run_row(v), ["up to 20"], v)
        self.assertEqual(self.run_row("20ms"), [20])
        self.assertEqual(self.run_row("10 ms"), [10])


class Policies(unittest.TestCase):
    def test_pins(self):
        import yaml
        pol = {p["id"]: p for p in yaml.safe_load((ROOT / "data/decisions/policies.yaml").read_text())["claim_policies"]}
        self.assertEqual(pol["claim/mfr-monitor-dell@2"]["audit"]["parsers"]["dell_monitors@2"], registry.parser_fingerprint("dell_monitors"))
        st = pol["claim/mfr-power-stations-structured@9"]["audit"]["parsers"]   # review-9: stations @8
        self.assertEqual(st["jackery_stations@8"], registry.parser_fingerprint("shopify_powerstations"))
        self.assertEqual(st["ankersolix_stations@8"], registry.parser_fingerprint("ankersolix_stations"))


if __name__ == "__main__":
    unittest.main()
