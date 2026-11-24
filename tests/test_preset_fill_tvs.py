"""A2 preset fill (2026-11-24): TV display tech from a Backlight Type row (A1 ruling 2) and LG's explicit 4K 120 Hz port list. Pure fixtures."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import _tv as T  # noqa: E402


def run(rows, model="OLED65X1"):
    pr = C.ParseResult()
    T.emit(pr, "fixture", model, {T.clean(k): T.clean(v) for k, v in rows.items()}, "fixture@1", "fixture", "2026-11-24T00:00:00Z")
    return {c["key"]: c["value"] for c in pr.claims if c.get("status", "known") == "known" and c["value"] is not None}


class BacklightTable(unittest.TestCase):
    def test_table_values_give_lcd(self):
        for v, b in (("Full Array LED", "direct_led"), ("Active Full Array", "direct_led"), ("Mini LED", "mini_led"), ("Edge", "edge_led"),
                     ("Direct", "direct_led")):
            got = run({"Backlight Type": v})
            self.assertEqual((got.get("panel.display_tech"), got.get("panel.backlight")), ("lcd", b), v)

    def test_unmapped_values_say_nothing(self):
        for v in ("DLED", "Local Dimming", "LED", "Full Array LED with Local Dimming", "Yes"):
            self.assertNotIn("panel.display_tech", run({"Backlight Type": v}), v)

    def test_other_labels_and_display_type_win(self):
        self.assertNotIn("panel.display_tech", run({"Mini-LED / Local Dimming Type": "Mini LED"}))      # not a Backlight Type row
        self.assertEqual(run({"Display Type": "OLED evo", "Backlight Type": "Direct"})["panel.display_tech"], "oled")
        self.assertNotIn("panel.display_tech", run({"Display Type": "4K UHD"}))                         # resolution, not a technology


class LatestHdmi(unittest.TestCase):
    def test_explicit_lists(self):
        self.assertEqual(run({"Latest HDMI (4K @ 120Hz)": "HDMI ports 3,4"})["hdmi.ports_4k120"], 2)
        self.assertEqual(run({"Latest HDMI (4K @ 120Hz)": "HDMI 3,4"})["hdmi.ports_4k120"], 2)
        self.assertEqual(run({"Latest HDMI (4K @ 120Hz)": "HDMI ports 1,2,3,4"})["hdmi.ports_4k120"], 4)
        self.assertEqual(run({"Latest HDMI (4K @ 120Hz)": "HDMI ports 3"})["hdmi.ports_4k120"], 1)

    def test_refused(self):
        self.assertNotIn("hdmi.ports_4k120", run({"Latest HDMI (4K @ 120Hz)": "Yes"}))
        # LG's union feature list (eARC sits on one port only) never gives a per-port count
        self.assertNotIn("hdmi.ports_4k120", run({"HDMI Input": "4ea (supports 4K 120Hz, eARC, VRR, ALLM, QMS, QFT)"}))


if __name__ == "__main__":
    unittest.main()
