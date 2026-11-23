"""Vizio TV adapter: label renaming keeps the printed literal, negation-safe VRR, mixed-rate and legacy pages. Pure fixtures.

  python3 -I tests/test_tvs_vizio.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import vizio_tvs as V  # noqa: E402


def page(rows, model="VQD65M-0804", canon="VQD65M-0804"):
    out, sec = [], None
    for s, l, v in rows:
        if s != sec:
            sec = s
            out.append(f'<span aria-label="{s}"><figure role="none"><svg></svg></figure> {s} </span>')
        out.append(f'<div class="tech-specs_accord__row"><span>{l}</span><span>{v}</span>\n</div>')
    eg = f"<p><strong>Model:</strong> {model}</p>" if model else ""
    return f'<title>VIZIO</title><link rel="canonical" href="https://www.vizio.com/en/tv/quantum/{canon}"/>{"".join(out)}{eg}'


def parse(h, code="M65Q6-L4"):
    snap = C.Snapshot("sha256:x", C.Ref(V.SOURCE, "quantum/" + code.lower(), "u", {"code": code}), 200, "2026-11-23T00:00:00Z", "u", {})
    return V.parse_html(snap, h)


def by_key(pr):
    return {c["key"]: c for c in pr.claims}


class T(unittest.TestCase):
    ROWS = [("Key Specs", "Class Size", '65"'), ("Key Specs", "Refresh Rate", "60Hz"), ("Key Specs", "Dynamic Motion Rate", "120"),
            ("Key Specs", "Variable Refresh Rate Support", "HDMI VRR"), ("Key Specs", "High Dynamic Range", "Dolby Vision, HDR10+, HDR10, HLG"),
            ("HDMI Inputs", "Ports", "3 (sidex3)"), ("Size and Weight", "Weight with Stand", "30.80lbs (14.0kg)"),
            ("Size and Weight", "Dimensions with Stand", '56.90" x 35.50" x 12.80" (1445.3mm x 901.7mm x325.1mm)'),
            ("Wall Mount Specifications", "Pattern", "400mm x 300mm")]

    def test_mapping_and_literal(self):
        pr = parse(page(self.ROWS))
        k = by_key(pr)
        self.assertEqual(k["refresh.native_hz"]["value"], 60)
        self.assertEqual(k["refresh.marketing"]["raw"], "Dynamic Motion Rate: 120")          # marketing rate never native
        self.assertEqual(k["hdmi.count"]["value"], 3)
        self.assertNotIn("hdmi.ports_4k120", k)                                         # no per-port statement -> unknown
        self.assertEqual(k["phys.vesa"]["value"], "400x300")
        self.assertEqual(k["phys.weight_with_stand"]["value"], 30.8)
        self.assertEqual(k["phys.width_with_stand"]["value"], 56.9)
        self.assertEqual(k["gen.size_class"]["raw"], 'Class Size: 65"')                 # printed label restored
        self.assertEqual(k["vrr.supported"]["raw"], "Variable Refresh Rate Support: HDMI VRR")
        self.assertEqual(k["vrr.supported"]["locator"]["label"], "Variable Refresh Rate Support")
        self.assertEqual(pr.identifiers[0]["value"], "VQD65M-0804")
        self.assertEqual(pr.identifiers[1]["scheme"], "x_vizio_shortcode")

    def test_no_negation_blind_vrr(self):
        rows = [r for r in self.ROWS if r[1] != "Variable Refresh Rate Support"] + [("Key Specs", "Variable Refresh Rate Support", "No VRR")]
        self.assertNotIn("vrr.supported", by_key(parse(page(rows))))

    def test_missing_formats_stay_unknown(self):
        rows = [r for r in self.ROWS if r[1] != "High Dynamic Range"] + [("Key Specs", "High Dynamic Range", "HDR10 & HLG")]
        k = by_key(parse(page(rows)))
        self.assertEqual(k["hdr.formats"]["value"], ["hdr10", "hlg"])
        self.assertNotIn("hdr.dolby_vision", k)
        self.assertNotIn("hdr.hdr10plus", k)

    def test_two_refresh_rates_not_native(self):
        rows = [r for r in self.ROWS if r[1] != "Refresh Rate"] + [("Key Specs", "Refresh Rate", "120Hz @UHD, 240Hz @FHD")]
        self.assertNotIn("refresh.native_hz", by_key(parse(page(rows))))

    def test_legacy_and_conflicting_pages_yield_nothing(self):
        self.assertTrue(parse("<title>x</title>").absences)
        pr = parse(page(self.ROWS, model="VQD65M-0804", canon="VQD55M-0804"))
        self.assertTrue(pr.absences and not pr.claims)

    def test_dimming_zones_only_from_explicit_count(self):
        rows = self.ROWS + [("Key Specs", "Local Dimming Zones", "Yes with Active LED Zones® x180")]
        self.assertEqual(by_key(parse(page(rows)))["hdr.dimming_zones"]["value"], 180)
        rows = self.ROWS + [("Key Specs", "Local Dimming Zones", "Yes")]
        self.assertNotIn("hdr.dimming_zones", by_key(parse(page(rows))))


if __name__ == "__main__":
    unittest.main()
