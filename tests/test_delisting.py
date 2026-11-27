#!/usr/bin/env python3
"""Delisting safety (A3-rob r11): a model the store's discovery stops listing keeps its stored claims and is marked delisted, never dropped.
Regression: Roborock Q7 Max / Q7 Max+ vanished from published data when a re-discover listed 33 of 35 models."""
import importlib.util, sys, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import _run  # noqa: E402

spec = importlib.util.spec_from_file_location("specsheet_import", CODE / "scripts" / "import.py")
IMP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(IMP)


def ref(key, **hints):
    return {"source_id": "s", "key": key, "url": f"https://x.example/{key}", "hints": hints}


class Carry(unittest.TestCase):
    def test_dropped_ref_kept_and_marked(self):
        prev = {"refs": [ref("a"), ref("q7-max", model="Q7 Max"), ref("q7-max-plus")], "complete": True}
        doc = {"refs": [ref("a")], "complete": True}
        self.assertEqual(_run.carry_delisted(prev, doc, today="2026-11-26"), 2)
        by = {r["key"]: r["hints"] for r in doc["refs"]}
        self.assertEqual(by["q7-max"], {"model": "Q7 Max", "listing": "delisted", "delisted_at": "2026-11-26"})
        self.assertNotIn("listing", by["a"])

    def test_date_kept_across_runs_and_relisting(self):
        prev = {"refs": [ref("a"), ref("b", listing="delisted", delisted_at="2026-11-01")]}
        doc = {"refs": [ref("a")], "complete": True}
        _run.carry_delisted(prev, doc, today="2026-12-01")
        self.assertEqual({r["key"]: r["hints"].get("delisted_at") for r in doc["refs"]}["b"], "2026-11-01")
        doc2 = {"refs": [ref("a"), ref("b")], "complete": True}                 # listed again: NOT resurrected by discovery (review-11)
        _run.carry_delisted(doc, doc2, today="2026-12-02")
        self.assertEqual([r["hints"] for r in doc2["refs"] if r["key"] == "b"],
                         [{"listing": "delisted", "delisted_at": "2026-11-01", "relisted_at": "2026-12-02"}])

    def test_incomplete_discovery_carries_unmarked(self):
        doc = {"refs": [], "complete": False}
        _run.carry_delisted({"refs": [ref("a")]}, doc, today="2026-11-26")
        self.assertEqual([(r["key"], r["hints"]) for r in doc["refs"]], [("a", {})])

    def test_legacy_rows(self):
        doc = {"refs": [], "complete": True}
        _run.carry_delisted({"refs": [{"key": "k", "url": "u", "model": "M"}]}, doc, today="2026-11-26")
        self.assertEqual(doc["refs"][0]["hints"], {"model": "M", "listing": "delisted", "delisted_at": "2026-11-26"})


class Mark(unittest.TestCase):
    def ent(self, *obs):
        e = IMP.Ent("robot-vacuums", "model", "roborock")
        e.obs = set(obs)
        return e

    def test_mark(self):
        listing = {("store", "q7-max"): "2026-11-26", ("store", "q5"): None, ("store", "q7-dup"): "2026-11-20"}
        gone = self.ent(("store", "q7-max", "sha:1"))
        live = self.ent(("store", "q5", "sha:2"))
        mixed = self.ent(("store", "q7-max", "sha:1"), ("store", "q5", "sha:2"))          # still listed under another ref
        cert = self.ent(("store", "q7-max", "sha:1"), ("store", "q7-dup", "sha:3"), ("csa-dcl", "x", "sha:4"))   # other source: no listing
        other = self.ent(("csa-dcl", "x", "sha:4"))
        w = type("W", (), {"ents": [gone, live, mixed, cert, other]})()
        self.assertEqual(IMP.mark_delisted({"robot-vacuums": w}, listing), 2)
        self.assertEqual(gone.extra["listing"], {"state": "delisted", "since": "2026-11-26", "sources": ["store"]})
        self.assertEqual(cert.extra["listing"]["since"], "2026-11-26")
        for e in (live, mixed, other):
            self.assertNotIn("listing", e.extra)


if __name__ == "__main__":
    unittest.main()
