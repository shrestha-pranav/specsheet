"""A2-ref r10 (2026-11-26): res.refresh_native / res.refresh_max for monitors (asus_monitors@5, benq_monitors@5, lenovo_monitors@7 refresh_max only,
lg_us@5) and the Dell TÜV flicker-free footnote (dell_monitors@3). Pure fixtures."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import asus_monitors as A  # noqa: E402
import benq_monitors as B  # noqa: E402
import dell_monitors as D  # noqa: E402
import lenovo_monitors as L  # noqa: E402
import lg_us  # noqa: E402

BOILER = "<footer>The first ASUS ROG motherboards made hardcore overclocking more accessible; built for competitive overclockers.</footer>"
F = {"Refresh Rate (Max)": "180Hz", "Digital Signal Frequency": "HDMI: 30~225 KHz (H) / 48~180 Hz (V)", "Analog Signal Frequency": "48~75 Hz (V)"}


class AsusPlainNative(unittest.TestCase):
    def test_no_overclock_on_either_page(self):
        n, q = A.plain_native("<p>spec</p>" + BOILER, "<h1>VA27</h1>" + BOILER, F, "VA27DQ", 1)
        self.assertEqual(n, 180)
        self.assertIn("Refresh Rate (Max): 180Hz", q)

    def test_overview_states_overclock(self):
        for ov in ("Fast IPS, Overclockable 280Hz (Above 240Hz, 144Hz)", '<div class="fp-tooltip">165Hz Overclocking</div>', "180Hz(OC) FHD IPS",
                   "ultrafast 380Hz (OC) refresh"):
            self.assertIsNone(A.plain_native("<p>spec</p>", ov, F, "TUF", 1)[0], ov)

    def test_techspec_states_overclock(self):
        self.assertIsNone(A.plain_native("48Hz ~ 170Hz(V)(OverClocking)", "", F, "XG", 1)[0])

    def test_refused(self):
        self.assertEqual(A.plain_native("", None, F, "VA27DQ", 1), (None, "no overview page stored"))        # fail closed
        self.assertIsNone(A.plain_native("", "", F, "VA27DQ", 2)[0])                                       # multi-model page
        self.assertIsNone(A.plain_native("", "", dict(F, **{"Dual Mode": "Yes"}), "PG27", 1)[0])
        self.assertIsNone(A.plain_native("", "", dict(F, **{"Digital Signal Frequency": "DP: 48~280 Hz (V)"}), "VG", 1)[0])   # higher Hz
        self.assertIsNone(A.plain_native("", "", {"Refresh Rate (Max)": "165Hz (DP)"}, "VG", 1)[0])           # not a plain cell
        self.assertEqual(A.plain_native("", "", dict(F, **{"Analog Signal Frequency": "50~240 Hz (V)"}), "VA", 1)[0], 180)  # analog ignored

    def test_overview_lookup_fails_closed_without_store(self):
        self.assertIsNone(A.overview_of(object(), "VA27DQ"))


def benq_page(rr, extra=""):
    items = "".join(f'<li class="item"> <div class="name">{n}</div> <div class="detail">{d}</div></li>'
                    for n, d in (("Refresh Rate (Hz)", rr), ("Resolution (max.)", "2560x1440"), ("Screen Size", "27 inch")))
    return ('<p>localNavigation.type = g6-product-spec-page</p> <p> EX2710Q </p>'
            f'<div class="spec-container"><p class="category">Display</p><ul>{items}</ul></div>{extra}')


def benq_claims(h):
    snap = C.Snapshot("sha256:x", C.Ref("benq-us-monitors", "ex2710q", "u", {}), 200, "2026-11-26T00:00:00Z", "u", {})
    return {c["key"]: c["value"] for c in B.parse_html(snap, h).claims}


class BenqRefresh(unittest.TestCase):
    def test_plain_rate_and_native_resolution(self):
        c = benq_claims(benq_page("165"))
        self.assertEqual((c["res.refresh_native"], c["res.refresh_max"], c["res.native"]), (165, 165, "2560x1440"))

    def test_refused(self):
        self.assertNotIn("res.refresh_native", benq_claims(benq_page("165 (DP), 144 (HDMI)")))
        self.assertNotIn("res.refresh_native", benq_claims(benq_page("165", "<p>Overclocking to 180Hz</p>")))


class LenovoRefresh(unittest.TestCase):
    def test_bare_range_stays_a_vrr_window(self):               # v6 ruling kept (tests/test_zero_keys_ports.py)
        self.assertIsNone(L.refresh_native("48Hz - 120Hz"))
        self.assertIsNone(L.refresh_native("UHD:160Hz, FHD:320Hz"))

    def test_v6_unchanged(self):
        self.assertEqual(L.refresh_native("165Hz (Overclock to 180Hz)\nOverclocking at 180Hz is based on laboratory test data"), 165)
        self.assertEqual(L.refresh_native("240Hz"), 240)

    def test_refresh_max_is_highest_figure(self):
        self.assertEqual(max(int(x) for x in L.HZ_ALL.findall("48Hz - 120Hz")), 120)
        self.assertEqual(max(int(x) for x in L.HZ_ALL.findall("165Hz (Overclock to 180Hz)")), 180)
        self.assertEqual(L.HZ_ALL.findall("5Hz"), [])


class LgRefresh(unittest.TestCase):
    def test_native_beside_oc(self):
        self.assertEqual(lg_us.lg_refresh("144Hz (160Hz O/C)", False), (160, 144))
        self.assertEqual(lg_us.lg_refresh("Refresh Rate 144Hz (O/C 165Hz)", False), (165, 144))
        self.assertEqual(lg_us.lg_refresh("144hz (160hz o/c)", False), (160, 144))

    def test_max_is_highest_figure(self):
        self.assertEqual(lg_us.lg_refresh("H-Frequency: 88~143kHz V-Frequency: 48~60Hz", False), (60, None))
        self.assertEqual(lg_us.lg_refresh("60 Hz (up to 75Hz w/ Display Port + Freesync mode)", False), (75, None))

    def test_refused(self):
        self.assertEqual(lg_us.lg_refresh("144Hz (O/C)", False), (144, None))                # which rate is OC is unsaid
        self.assertEqual(lg_us.lg_refresh("Up to 165Hz w/ OverClock", False), (165, None))
        self.assertEqual(lg_us.lg_refresh("240Hz", True), (240, None))                       # Dual Mode page
        self.assertEqual(lg_us.lg_refresh("240Hz", False), (240, 240))                       # v4 unchanged


class DellFootnote(unittest.TestCase):
    def test_tuv_footnote(self):
        h = '{"@type":"PropertyValue","value":"T\\u00DCV Rheinland certified \\u2013 Low Blue Light Hardware solution and Flicker Free.","name":"footnotes"}'
        self.assertIsNotNone(D.FOOTNOTE_FF.search(h))

    def test_prose_never_maps(self):
        for h in ('{"value":"A 120Hz refresh rate delivers less flicker.","name":"footnotes"}',
                  '{"value":"TÜV Rheinland certified – Low Blue Light Hardware solution.","name":"footnotes"}',
                  '{"value":"Easy on the eyes with a flicker-free screen","name":"Designed for comfort"}'):
            self.assertIsNone(D.FOOTNOTE_FF.search(h), h)


if __name__ == "__main__":
    unittest.main()
