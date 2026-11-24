"""PSREF multi-target cell split (crawler/adapters/_lcell.py -> import.py+psref-split@1): states only what the cell prints."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _lcell as L  # noqa: E402


class DisplayTest(unittest.TestCase):
    def test_typical_not_peak(self):
        d = L.display('14" WUXGA (1920x1200) OLED 600nits (peak) / 400nits (typical) Glossy, 100% DCI-P3, 60Hz, Touch')
        self.assertEqual(d, {"resolution": "1920x1200", "panel_type": "OLED", "nits_sdr": 400, "refresh": {"max": 60}})

    def test_peak_only_and_no_hz(self):
        d = L.display('16" WQXGA (2560x1600) Tandem OLED 1100nits (peak) Glossy, 100% DCI-P3')
        self.assertEqual(d.get("panel_type"), "Tandem OLED")
        self.assertNotIn("nits_sdr", d)
        self.assertNotIn("refresh", d)          # no Hz printed: never a 60 Hz default

    def test_dual_mode_refresh_ambiguous(self):
        d = L.display('18" WQUXGA (3840x2400) IPS 520nits Glossy, 100% DCI-P3, 240Hz / 440Hz , Dolby Vision')
        self.assertEqual(d["nits_sdr"], 520)
        self.assertNotIn("refresh", d)

    def test_multi_statement_cell(self):
        self.assertEqual(L.display('14" FHD (1920x1080) IPS 300nits^|^14" 2.2K (2240x1400) IPS 300nits'), {})


class MemoryTest(unittest.TestCase):
    def test_slots(self):
        self.assertEqual(L.slots("Memory soldered to systemboard, no slots, dual-channel"), {"total": 0, "soldered": "soldered"})
        self.assertEqual(L.slots("One memory soldered to systemboard, one DDR5 SODIMM slot, dual-channel capable"), {"total": 1, "soldered": "mixed"})
        self.assertEqual(L.slots("Four DDR5 SODIMM  / CSODIMM slots, dual-channel capable"), {"total": 4, "soldered": "socketed"})
        self.assertEqual(L.slots("One LPCAMM2 connector, dual-channel"), {"total": 1, "soldered": "socketed"})
        self.assertEqual(L.slots("Arrow Lake: two DDR5 SODIMM slots, dual-channel capable"), {"total": 2, "soldered": "socketed"})
        self.assertEqual(L.slots("Unified memory, 16-channel"), {})

    def test_memory_cell(self):
        self.assertEqual(L.memory("16GB Soldered LPDDR5X-7500"), {"type": "LPDDR5X-7500", "soldered_hint": "soldered"})
        self.assertEqual(L.memory("8GB Soldered DDR5-5600 + 1x 8GB SODIMM DDR5-5600")["soldered_hint"], "mixed")
        self.assertNotIn("soldered_hint", L.memory("64GB LPDDR5X-9400, 256-bit, Unified Memory"))   # not stated: not inferred


if __name__ == "__main__":
    unittest.main()
