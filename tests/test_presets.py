"""D8 preset gate (scripts/presets.py): synthetic rows, no build needed.

  python3 -I tests/test_presets.py
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import presets as P  # noqa: E402

SCHEMA = {"fields": [{"key": "a", "label": "A", "type": "number", "facet": {"kind": "range"}}, {"key": "b", "label": "B", "type": "bool", "facet": {"kind": "bool"}},
                     {"key": "hidden", "label": "H", "type": "number", "facet": None, "column": False}]}
CAT = {"id": "c"}


def row(brand, v=None, s=None, t=("manufacturer",), lc="current"):
    return {"brand": brand, "v": v or {}, "s": s or {}, "t": list(t), "lifecycle": lc}


def gate(preset, rows, **kw):
    return P.measure({"id": "p", **preset}, CAT, SCHEMA, rows, 0.8, **kw)[0]


PRE = {"filters": {"f_a_min": "10", "f_b_value": "yes"}, "scope": {"by": ["a"]}}
FULL = [row("X", {"a": 20, "b": True}), row("X", {"a": 30, "b": True})]


class D8(unittest.TestCase):
    def test_unknown_stays_in_and_key_not_scoped_by_itself(self):
        g = gate(PRE, [row("X", {"a": 20, "b": True}), row("X", {"a": 5}), row("X")], default_min_brands=1)
        self.assertEqual([(k["key"], k["known"], k["total"]) for k in g["keys"]], [("a", 2, 3), ("b", 1, 2)])
        self.assertEqual(g["scope"]["excluded"]["by"], {"a": 1})

    def test_not_applicable_leaves_denominator(self):
        g = gate(PRE, [row("X", {"a": 20, "b": True}), row("X", {"a": 20}, {"b": "not_applicable"})], default_min_brands=1)
        self.assertEqual(g["keys"][1]["total"], 1)

    def test_min_brands(self):
        self.assertTrue(gate(PRE, FULL, default_min_brands=1)["passes"])
        g = gate(PRE, FULL, default_min_brands=2)
        self.assertEqual(g["fill"], 1.0); self.assertFalse(g["passes"])
        self.assertTrue(gate(PRE, FULL + [row("Y", {"a": 20, "b": True})], default_min_brands=2)["passes"])

    def test_scope_tier_and_lifecycle(self):
        sc = {"scope": {"by": ["a"], "sources": ["manufacturer"]}, "filters": PRE["filters"]}
        rows = FULL + [row("Y", {"a": 20}, t=("regulatory",)), row("Y", {"a": 20}, lc="discontinued"), row("Z", {"a": 20}, lc="unknown")]
        g = gate(sc, rows, default_min_brands=1)
        self.assertEqual(g["scope"]["in_scope"], 3); self.assertEqual(g["scope"]["excluded"]["source_tier"], 1); self.assertEqual(g["scope"]["excluded"]["discontinued"], 1)
        self.assertEqual(gate({**sc, "scope": {"by": ["a"], "sources": None, "include_discontinued": True}}, rows, default_min_brands=1)["scope"]["in_scope"], 5)

    def test_guard_keys_not_in_index(self):
        with self.assertRaises(SystemExit):
            gate({"filters": {}, "require": ["hidden"]}, FULL)
        with self.assertRaises(SystemExit):
            gate({"filters": PRE["filters"], "scope": {"by": ["hidden"]}}, FULL)


if __name__ == "__main__":
    unittest.main()
