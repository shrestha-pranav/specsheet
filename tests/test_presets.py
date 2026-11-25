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


class PresetDefsR2(unittest.TestCase):
    """docs/presets.json r2 (team/briefs/coord-2026-11-25-a4-presets-r2.md): definitions only; the gate decides showcase vs help-us-fill."""
    SRC = __import__("json").loads((P.DOCS / "presets.json").read_text())

    def test_new_presets_and_stable_ids(self):
        ids = [p["id"] for p in self.SRC["presets"]]
        for pid in ("monitor-1440p-144", "robovac-under-89mm", "station-lfp-1kwh", "surge-ul1449-2000j", "power-bank-samsung-45w", "tv-4-hdmi-4k120"):
            self.assertIn(pid, ids)
        self.assertFalse(any("passes" in p or "showcase" in p or "gate" in p for p in self.SRC["presets"]), "no forced gate in the source file")

    def test_tv_title_matches_gate(self):
        tv = next(p for p in self.SRC["presets"] if p["id"] == "tv-4-hdmi-4k120")
        self.assertEqual(tv["filters"].get("f_hdmi.has_4k120_value"), "yes")
        self.assertNotIn("f_hdmi.ports_4k120_min", tv["filters"], "the >= 4 port gate waits for 80% fill (next_gate)")
        self.assertIn("at least one", tv["title"])
        self.assertEqual(tv["next_gate"]["filters"], {"f_hdmi.ports_4k120_min": "4"})

    def test_filters_parse_against_published_schemas(self):
        api = P.DOCS / "api" / "v1"
        if not (api / "categories.json").exists():
            self.skipTest("no published index")
        cats = __import__("json").loads((api / "categories.json").read_text())
        built = P.build(api, cats, self.SRC)
        self.assertEqual([p["id"] for p in built["presets"]], [p["id"] for p in self.SRC["presets"]])


if __name__ == "__main__":
    unittest.main()
