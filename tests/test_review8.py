"""Codex review-8 fixes (A3-fix, 2026-11-26): UPS switchover bounds/ranges/model identity (crawler/adapters/_powerstation.py, stations @7).
Pure fixtures, no network. The other review-8 fixtures live beside their code: tests/test_build_r2.py (gated alternatives),
tests/test_imgattach.py (identity vetoes before inheritance), api-worker/test/fixtures/verdict-rows.json (null endpoints, key order),
tests/test_review8.py::Naming (per-capacity names)."""
import importlib.util, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import _contract as C  # noqa: E402
import _powerstation as PS  # noqa: E402

SNAP = C.Snapshot("sha256:x", C.Ref("jackery-us-stations", "e1000", "https://www.jackery.com/products/e1000"), 200, "2026-11-26T00:00:00Z", "u", {})


def row(v, label="UPS Switchover Time"):
    pr = C.ParseResult()
    PS.emit_rows(pr, "x@1", SNAP, "Explorer 1000", {label: v}, "spec")
    return [(c.get("value"), c["status"]) for c in pr.claims if c["key"] == "ups.switchover_ms"]


class UpsRows(unittest.TestCase):
    def test_up_to_kept(self):
        for v in ("up to 20 ms", "Up to 20ms", "<=20ms", "Max. 20ms", "no more than 20 ms", "＜20ms, Online UPS: 0ms"):
            self.assertEqual(row(v), [("up to 20", "known")], v)
        self.assertEqual(row("20ms"), [(20, "known")])

    def test_range_never_endpoint(self):
        for v in ("10-20 ms", "10–20ms", "10 ms ~ 20 ms", "10 to 20 ms", "10ms-20ms"):
            got = row(v)
            self.assertTrue(all(st != "known" for _, st in got), (v, got))
            self.assertNotIn(20, [x for x, _ in got]); self.assertNotIn(10, [x for x, _ in got])


class UpsProse(unittest.TestCase):
    OWN = ("Jackery Explorer 1000 Portable Power Station", "Explorer 1000")

    def prose(self, sent, own=OWN):
        return PS.ups_prose(f"<p>{sent}</p>", own)[0]

    def test_up_to_kept(self):
        self.assertEqual(self.prose("UPS switchover in up to 20 ms."), "up to 20")
        self.assertEqual(self.prose("The Explorer 1000 switches to UPS in under 20ms."), "up to 20")
        self.assertEqual(self.prose("Explorer 1000 UPS switchover 20ms."), 20)

    def test_range_never_endpoint(self):
        for s in ("UPS switchover in 10–20 ms.", "UPS switch time 10-20ms.", "UPS switchover 10 to 20 ms.", "UPS: 10 ms ~ 20 ms switchover."):
            self.assertIsNone(self.prose(s), s)

    def test_suffixed_sibling_never_own(self):
        for s in ("The Explorer 1000 Plus switches to UPS in 20ms.", "Explorer 1000 Pro UPS switchover under 20 ms.",
                  "Unlike the Explorer 1000 v2, UPS switchover is 20ms."):
            self.assertIsNone(self.prose(s), s)
        # the suffixed model's own page still reads its own copy
        self.assertEqual(self.prose("The Explorer 1000 Plus switches to UPS in 20ms.", ("Jackery Explorer 1000 Plus Portable Power Station",)), 20)


_spec = importlib.util.spec_from_file_location("specsheet_import_r8", ROOT / "scripts" / "import.py")
IMP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IMP)


def cap(sku, gb):
    return {"key": "gen.capacity", "value": gb, "locator": {"sku": sku, "label": "Capacity"}}


def mk(aliases, claims, skus=()):
    return {"aliases": [{"text": t, "kind": "marketing_name"} for t in aliases], "claims": claims,
            "identifiers": [{"scheme": "mfr_sku", "value": v, "package_level": "configuration", "role": "key"} for v in skus]}


class Naming(unittest.TestCase):
    def test_equal_capacity_siblings_not_bound_by_capacity(self):
        pr = mk(["SN850X 1TB", "SN850X 1TB with Heatsink"], [cap("WDS100T2X0E", 1000), cap("WDS100T2XHE", 1000)])
        self.assertIsNone(IMP.own_alias(pr, "WDS100T2X0E"))
        self.assertIsNone(IMP.own_alias(pr, "WDS100T2XHE"))

    def test_sku_bound_alias_wins(self):
        pr = mk(["SN850X 1TB WDS100T2X0E", "SN850X 1TB with Heatsink WDS100T2XHE"], [cap("WDS100T2X0E", 1000), cap("WDS100T2XHE", 1000)])
        self.assertEqual(IMP.own_alias(pr, "WDS100T2XHE"), "SN850X 1TB with Heatsink WDS100T2XHE")
        self.assertEqual(IMP.own_alias(pr, "WDS100T2X0E"), "SN850X 1TB WDS100T2X0E")

    def test_alias_naming_another_sku_never_binds(self):
        pr = mk(["990 PRO 2TB MZ-V9P2T0B/AM"], [cap("MZ-V9P2T0BW", 2000), cap("MZ-V9P2T0B/AM", 2000 * 1.5)])
        self.assertIsNone(IMP.own_alias(pr, "MZ-V9P2T0BW"))

    def test_neutral_fallback(self):
        pr = mk([], [cap("A", 1000), cap("B", 4000)])
        self.assertEqual(IMP.neutral_name("Samsung 990 PRO 4TB", pr, "A"), "Samsung 990 PRO")     # wrong capacity removed
        self.assertEqual(IMP.neutral_name("Samsung 990 PRO 4TB", pr, "B"), "Samsung 990 PRO 4TB")  # own capacity kept
        self.assertEqual(IMP.neutral_name("Samsung 990 PRO - 4TB", pr, "C"), "Samsung 990 PRO")    # no own capacity: neutral
        self.assertEqual(IMP.neutral_name("Laptop 15 512GB", {"claims": [], "aliases": []}, "A"), "Laptop 15 512GB")   # no capacity claims: as before


if __name__ == "__main__":
    unittest.main()
