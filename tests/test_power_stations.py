"""Power stations: review-3 rules applied to the shared row mapper (crawler/adapters/_powerstation.py). Pure fixtures, no raw/ data.

  python3 -I tests/test_power_stations.py
"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import _powerstation as PS  # noqa: E402


def run(rows):
    pr = C.ParseResult()
    snap = C.Snapshot("sha256:x", C.Ref("fixture", "k", "https://example.invalid/k"), 200, "2026-11-23T00:00:00Z", "https://example.invalid/k", {})
    PS.emit_rows(pr, "fixture@1", snap, "M1", rows, "Specs")
    out = {}
    for c in pr.claims:
        out.setdefault(c["key"], []).append(c)
    return out


def known(cs, key):
    return [c.get("value") for c in cs.get(key, []) if c["status"] == "known"]


def unres(cs, key):
    return [c for c in cs.get(key, []) if c["status"] == "unknown"]


class Totals(unittest.TestCase):
    def test_ac_rating_from_tagged_row_boost_and_surge_apart(self):
        cs = run({"AC Output": "6 outlets, 1800W total (Surge 3600W)", "Max Device(s) Power (with X-Boost)": "2200W"})
        self.assertEqual(known(cs, "out.ac_continuous_w"), [1800])
        self.assertEqual(known(cs, "out.ac_surge_w"), [3600])
        self.assertEqual(known(cs, "out.ac_boost_w"), [2200])
        self.assertEqual(known(cs, "out.ac_outlets"), [6])

    def test_several_untagged_ac_figures_unresolved(self):
        cs = run({"AC Output 120V": "1800W", "AC Output 240V": "3600W"})
        self.assertFalse(known(cs, "out.ac_continuous_w"))
        self.assertTrue(unres(cs, "out.ac_continuous_w"))

    def test_n_ports_w_max_is_not_per_port(self):
        cs = run({"USB-C Output": "2 ports, 140W Max"})
        self.assertEqual(known(cs, "out.usb_c_count"), [2])
        self.assertTrue(unres(cs, "out.usb_c_max_w"))
        cs = run({"USB-C Output": "2 ports, 5/9/12/15/20V, 5A, 100W Max per port"})
        self.assertEqual(known(cs, "out.usb_c_max_w"), [100])

    def test_solar_per_port_is_not_a_total(self):
        cs = run({"Solar Charging": "2 ports, DC Charge Input, 11V-60V 500W Max*2"})
        self.assertEqual(known(cs, "in.solar_port_w"), [500])
        self.assertFalse(known(cs, "in.solar_w"))
        cs = run({"Solar Charging": "11-60V 15A, single port 500W; dual port 1,000W"})
        self.assertEqual(known(cs, "in.solar_w"), [1000])

    def test_labelled_combined_solar_total_wins(self):
        cs = run({"Input Ports / 8mm Input (solar)": "300W max ; 13.2-30V, 10A", "Input Ports / HPP Input (solar)": "600W max ; 12.3-60V, 20A",
                  "Input Ports / Total Combined DC/Solar Input": "900W"})
        self.assertEqual(known(cs, "in.solar_w"), [900])
        self.assertEqual(len(known(cs, "in.solar_voltage")), 2)               # one window per port, never merged
        self.assertTrue(all("port" in c["conditions"] for c in cs["in.solar_voltage"]))


class Bases(unittest.TestCase):
    def test_capacity_two_figures_unresolved_and_no_computation(self):
        cs = run({"Capacity": "1,152Wh (AC180) / 1,440Wh (AC180P)"})
        self.assertFalse(known(cs, "cap.energy_wh"))
        cs = run({"Battery / Capacity": "30.4Ah/35.2V DC (1070 Wh)"})
        self.assertEqual(known(cs, "cap.energy_wh"), [1070])
        self.assertEqual(known(cs, "cap.pack_voltage_v"), [35.2])
        self.assertEqual(known(cs, "cap.pack_ah"), [30.4])

    def test_cycle_life_needs_retention(self):
        cs = run({"Cycle Life": "4000 cycles to 80+% capacity"})
        self.assertEqual(known(cs, "bat.cycle_life"), [4000])
        self.assertEqual(cs["bat.cycle_life"][0]["conditions"], {"retention_pct": 80})
        self.assertTrue(unres(run({"Cycle Life": "3000 cycles"}), "bat.cycle_life"))

    def test_recharge_time_needs_charge_range(self):
        cs = run({"Recharge Times / AC Fast Charge (included cable)": "1.1 hrs ; 0-80%: 0.8 hrs"})
        ks = [c for c in cs["in.recharge_ac_h"] if c["status"] == "known"]
        self.assertEqual([c["value"] for c in ks], [{"min": 0.8, "max": 0.8}])
        self.assertEqual(ks[0]["conditions"]["charge_to_pct"], 80)
        self.assertEqual(len(unres(cs, "in.recharge_ac_h")), 1)              # the 1.1 h figure has no printed range


class Affirmative(unittest.TestCase):
    def test_waveform_and_ul_need_affirmative_rows(self):
        self.assertEqual(known(run({"OUTPUT / Inverter Type": "Pure Sine Wave"}), "out.ac_waveform"), ["pure_sine"])
        self.assertFalse(known(run({"OUTPUT / Inverter Type": "Non-pure sine"}), "out.ac_waveform"))
        self.assertEqual(known(run({"GENERAL / Certifications": "UL2743, FCC ID, CE"}), "cert.ul2743"), [True])
        self.assertFalse(known(run({"GENERAL / Certifications": "UL Standard, CE"}), "cert.ul2743"))
        self.assertFalse(known(run({"GENERAL / Certifications": "UL 2743 pending, CE"}), "cert.ul2743"))

    def test_expandability(self):
        self.assertEqual(known(run({"GENERAL / Chainable": "No"}), "exp.expandable"), [False])
        self.assertFalse(known(run({"PORTS / Expansion Module Port": "Under the lid - for expansion modules only"}), "exp.expandable"))
        cs = run({"Extra Battery": "Supports up to two DELTA 2 Max Smart Extra Batteries / DELTA Max Smart Extra Battery"})
        self.assertEqual(known(cs, "exp.expandable"), [True])
        self.assertEqual(known(cs, "exp.max_batteries"), [2])

    def test_weight_tolerance_and_dual_units(self):
        self.assertEqual(known(run({"Net Weight": "33.7±0.6kg"}), "phys.weight"), [33.7])
        self.assertEqual(known(run({"Net Weight": "22.1+0.4kg"}), "phys.weight"), [22.1])
        self.assertEqual(known(run({"Net weight (lbs)": "50 lbs", "Net weight (kg)": "23kg"}), "phys.weight"), [23])


if __name__ == "__main__":
    unittest.main()
