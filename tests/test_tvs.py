"""TVs: review-3 rules applied to the shared row mapper (crawler/adapters/_tv.py) and the ENERGY STAR declaration parser. Pure fixtures.

  python3 -I tests/test_tvs.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import _tv as T  # noqa: E402
import energystar_tvs as ES  # noqa: E402


def run(rows, brand="fixture", model="QN65X1"):
    pr = C.ParseResult()
    T.emit(pr, brand, model, {T.clean(k): T.clean(v) for k, v in rows.items()}, "fixture@1", "fixture", "2026-11-23T00:00:00Z")
    out = {}
    for c in pr.claims:
        out.setdefault(c["key"], []).append(c)
    return out


def known(cs, key):
    return [c.get("value") for c in cs.get(key, []) if c["status"] == "known"]


def unres(cs, key):
    return [c for c in cs.get(key, []) if c["status"] == "unknown"]


class Hdmi(unittest.TestCase):
    def test_explicit_port_lists(self):
        for v, n in (("4K 144Hz (for HDMI 1/2/3/4)", 4), ("4K 60Hz (for HDMI 1/2/3)", 0), ("4x HDMI 2.1 (HDMI 1-2: 4K@144Hz) | (HDMI 3-4: 4K@60Hz)", 2),
                     ("HDMI2.1*4（1-4K@144HZ/2-4K@144HZ/3 4-4K@60HZ） HDMI4 with eARC", 2), ("4x HDMI 2.1 (4K@144HZ) HDMI 1 with eARC", 4),
                     ("4ea (supports 4K 120Hz, eARC, VRR, ALLM, QMS as specified in HDMI 2.1 (2 port))", 2)):
            self.assertEqual(T.hdmi_4k120(T.clean(v)), n, v)

    def test_feature_list_without_port_count_is_unresolved(self):
        cs = run({"HDMI Input": "3ea (supports 4K 120Hz, eARC, VRR, ALLM, QMS, QFT)"})
        self.assertEqual(known(cs, "hdmi.ports_4k120"), [])
        self.assertEqual(len(unres(cs, "hdmi.ports_4k120")), 1)
        self.assertEqual(known(cs, "hdmi.count"), [3])

    def test_plain_arc_is_not_earc(self):
        self.assertEqual(known(run({"HDMI Audio Return Channel": "Yes"}), "hdmi.earc"), [])
        self.assertEqual(known(run({"HDMI Audio Return Channel": "eARC (HDMI 3)"}), "hdmi.earc"), [True])


class Negation(unittest.TestCase):
    def test_format_list_never_gives_false(self):
        cs = run({"HDR (High Dynamic Range)": "HDR10 / HLG"})
        self.assertEqual(known(cs, "hdr.formats"), [["hdr10", "hlg"]])
        self.assertEqual(known(cs, "hdr.dolby_vision"), [])
        self.assertEqual(known(cs, "hdr.hdr10plus"), [])

    def test_own_row_no_is_false_brand_name_is_nothing(self):
        self.assertEqual(known(run({"Dolby Vision Mode": "No"}), "hdr.dolby_vision"), [False])
        self.assertEqual(known(run({"HDR (High Dynamic Range)": "OLED HDR+"}), "hdr.formats"), [])

    def test_vrr_row_with_other_text_is_nothing(self):
        self.assertEqual(known(run({"Variable Refresh Rate (VRR)": "Game Enhancement Technology"}), "vrr.supported"), [])
        self.assertEqual(known(run({"Variable Refresh Rate (VRR)": "No"}), "vrr.supported"), [False])

    def test_shifted_freesync_row_ignored(self):
        self.assertEqual(known(run({"FreeSync": "Closed Caption (Subtitle), Multi-output Audio"}), "vrr.formats"), [])
        self.assertEqual(known(run({"FreeSync": "FreeSync Premium Pro", "G-SYNC": "Yes"}), "vrr.formats"), [["freesync_premium_pro", "gsync_compatible"]])

    def test_dimming_processing_names_are_not_local_dimming(self):
        self.assertEqual(known(run({"Micro Dimming": "Supreme UHD Dimming"}), "hdr.local_dimming"), [])

    def test_atsc(self):
        self.assertEqual(known(run({"Tuner Type": "ATSC 3.0 / ATSC 1.0 / NTSC / Clear QAM"}), "conn.atsc3"), [True])
        self.assertEqual(known(run({"TV Tuner": "ATSC1.0 (Terrestrial), QAM (Cable)"}), "conn.atsc3"), [False])
        self.assertEqual(known(run({"Digital Broadcasting": "ATSC/ClearQAM"}), "conn.atsc3"), [])


class Refresh(unittest.TestCase):
    def test_native_vs_marketing(self):
        cs = run({"Refresh Rate": "120Hz (Up to 144Hz)", "Motion Technology": "Motion Xcelerator 144Hz"})
        self.assertEqual(known(cs, "refresh.native_hz"), [120])
        self.assertEqual(known(cs, "refresh.max_hz"), [144])
        self.assertEqual(known(cs, "refresh.marketing"), ["Motion Technology: Motion Xcelerator 144Hz"])

    def test_dlg_is_not_native(self):
        cs = run({"Panel Refresh": "144Hz/DLG 288Hz"})
        self.assertEqual(known(cs, "refresh.native_hz"), [144])
        self.assertEqual(known(cs, "refresh.dlg_hz"), [288])

    def test_marketing_in_refresh_row_is_not_native(self):
        cs = run({"Refresh Rate": "TruMotion 120 (60Hz Native)"})
        self.assertEqual(known(cs, "refresh.native_hz"), [60])
        self.assertEqual(known(run({"Refresh Rate": "Motion Rate 240"}), "refresh.native_hz"), [])


class Plausibility(unittest.TestCase):
    def test_mm_under_inch_label_is_unresolved(self):
        cs = run({"Screen Size": '65"', "Set Size without Stand (WxHxD)": "1224.6 x 707.8 x 76.6 inch"}, model="QN65X1")
        self.assertEqual(known(cs, "phys.width_no_stand"), [])
        self.assertEqual(len(unres(cs, "phys.width_no_stand")), 1)

    def test_inch_dims_kept(self):
        cs = run({"Size": '65"', "TV Dimensions without Stand (WxHxD)": '57.0" x 32.8" x 1.8"'}, model="OLED65B5PUA")
        self.assertEqual(known(cs, "phys.width_no_stand"), [57.0])

    def test_size_contradicting_model_number(self):
        cs = run({"Screen Size": '55"'}, model="QN65X1")
        self.assertEqual(known(cs, "gen.size_class"), [])

    def test_zone_lower_bound(self):
        self.assertEqual(len(unres(run({"Dimming Zones": "Local Dimming Pro+ with up to 1,300+ Discrete Dimming Zones"}), "hdr.dimming_zones")), 1)
        self.assertEqual(known(run({"Dimming Zones": "Up to 4000 Discrete Dimming Zones"}), "hdr.dimming_zones"), ["Up to 4000"])


class EnergyStarDeclarations(unittest.TestCase):
    def test_declared_vs_plain(self):
        toks, ph = ES.split_additional("QN65S90DDF,QN65S90DDF,Same as basic model except model designation; QN65S92DAF,QN65S92DAF,Same as basic "
                                       "model except model designation", "QN65S90DAF")
        self.assertEqual(toks, [("QN65S90DDF", "declared_same_hardware"), ("QN65S92DAF", "declared_same_hardware")])
        toks, ph = ES.split_additional("65N1; RTAU6504", "65D1")
        self.assertEqual({k for _, k in toks}, {"model_variant"})


if __name__ == "__main__":
    unittest.main()
