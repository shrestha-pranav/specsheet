"""A2 preset fill (2026-11-24), laptops / ram-upgradable: PSREF platform-labelled Max Memory (lenovo_psref@3) and ASUS Memory-cell
mem.max / mem.soldered (asus@2). Pure fixtures: positive cases and the refusals (nothing from silence, nothing from disagreeing options)."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
sys.path.insert(0, str(ROOT / "scripts"))
import lenovo_psref as L  # noqa: E402
import asus as A  # noqa: E402
import normalize as N  # noqa: E402

SPEC = {"key": "mem.max", "label": "Max RAM possible for this config", "type": "number", "unit": "GB"}


def gb(v):
    return N.to_number(SPEC, v, None, N.units())


class PsrefMaxMemory(unittest.TestCase):
    def test_platform_label_dropped(self):
        self.assertEqual(gb(L.max_memory("Arrow Lake: up to 64GB DDR5-5600", {})), 64)
        self.assertEqual(gb(L.max_memory("Lunar Lake: 32GB soldered memory, not upgradable", {})), 32)
        self.assertEqual(gb(L.max_memory("Raptor Lake with H Series processors, Meteor Lake and Arrow Lake: up to 64GB DDR5-5600", {})), 64)
        self.assertEqual(L.max_memory("Up to 64GB DDR5-5600", {}), "Up to 64GB DDR5-5600")      # old layout untouched

    def test_ecc_split_from_own_memory_cell(self):
        v = ("Models with Non-ECC memory: Up to 192GB (4x 48GB SODIMM DDR5-5600 Non-ECC / CSODIMM DDR5-6400 Non-ECC )^|^"
             "Models with ECC memory: Up to 128GB (4x 32GB SODIMM DDR5-5600 ECC)")
        self.assertEqual(gb(L.max_memory(v, {"Memory": "2x 16GB SODIMM DDR5-5600 Non-ECC"})), 192)
        self.assertEqual(gb(L.max_memory(v, {"Memory": "2x 32GB SODIMM DDR5-5600 ECC"})), 128)

    def test_refused(self):
        v = "Models with Non-ECC memory: Up to 192GB^|^Models with ECC memory: Up to 128GB"
        self.assertIsNone(gb(L.max_memory(v, {"Memory": "2x 16GB SODIMM DDR5-5600"})))       # Memory cell does not settle ECC
        self.assertIsNone(gb(L.max_memory("Arrow Lake: up to 64GB^|^Lunar Lake: 32GB soldered", {})))   # other multi-variant: literal


class AsusMemory(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(A.memory_facts(["16GB DDR5-5600 SO-DIMM x 2,  - Max Capacity:64GB"]), {"mem.max": 64, "mem.soldered": "socketed"})
        self.assertEqual(A.memory_facts(["32GB LPDDR5X 8533 on board(Actual memory speeds may vary by CPU configuration.),  - Max Capacity:32GB, "
                                         "Support dual channel memory, Memory Slot:No expansion possible"]), {"mem.max": 32, "mem.soldered": "soldered"})
        self.assertEqual(A.memory_facts(["32GB LPDDR5X on board Max Total system memory up to:32GB"]), {"mem.max": 32, "mem.soldered": "soldered"})
        self.assertEqual(A.memory_facts(["8GB DDR5 on board, 8GB DDR5-4800 SO-DIMM,  - Max Capacity:40GB"]), {"mem.max": 40, "mem.soldered": "mixed"})
        self.assertEqual(A.memory_facts(["48GB LPDDR5X Memory on Package Max Total system memory up to:48GB"]), {"mem.max": 48, "mem.soldered": "soldered"})

    def test_refused(self):
        self.assertEqual(A.memory_facts([" - Max Capacity:64GB, Support dual channel memory"]), {"mem.max": 64})          # placement unstated
        self.assertEqual(A.memory_facts(["16GB DDR5 on board,  - Max Capacity:32GB"]), {"mem.max": 32})                   # free slot possible
        self.assertEqual(A.memory_facts(["24GB LPDDR5X on board"]), {})                                                    # no max, max != stated
        self.assertEqual(A.memory_facts(["16GB LPDDR4X on board, Memory Max Up to:16GB", "8GB LPDDR4X on board, Memory Max Up to:8GB"]),
                         {"mem.soldered": "soldered"})                                                                     # options disagree on max
        self.assertEqual(A.memory_facts(["16GB DDR5 on board 16GB DDR5 SO-DIMM Max Total system memory up to:32GB",
                                         "16GB DDR5 on board Max Total system memory up to:32GB"]), {"mem.max": 32})      # placement disagrees
        self.assertEqual(A.memory_facts(["8GB LPDDR5X on board 4GB LPDDR5X on board, Memory Max Up to:8GB 4GB"]), {})      # two configs run together
        self.assertEqual(A.memory_facts(["16GB DDR5 SO-DIMM", "*Dual-channel memory support requires at least one SO-DIMM module."]),
                         {"mem.soldered": "socketed"})                                                                     # footnote ignored


if __name__ == "__main__":
    unittest.main()
