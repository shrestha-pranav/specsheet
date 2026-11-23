"""Identity primitives (review P0-3): GTIN validation, scoped keys, quarantine on conflicting strong ids, registry stability."""
import sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "crawler" / "adapters"))
import identity as I  # noqa: E402
from decisions import Decisions  # noqa: E402
import importlib  # noqa: E402
imp = importlib.import_module("import")


class GtinTest(unittest.TestCase):
    def test_valid_forms_coincide(self):
        self.assertEqual(I.norm_gtin("037332118479"), "00037332118479")          # UPC-A
        self.assertEqual(I.norm_gtin("0037332118479"), "00037332118479")         # EAN-13 form of the same item
        self.assertEqual(I.norm_gtin("0 37332 11847 9"), "00037332118479")       # printed spacing
        self.assertEqual(I.norm_gtin("96385074"), "00000096385074")              # GTIN-8

    def test_invalid_rejected(self):
        self.assertIsNone(I.norm_gtin("037332118478"))     # bad check digit
        self.assertIsNone(I.norm_gtin("12345"))            # unsupported length
        self.assertIsNone(I.norm_gtin("UPC 037332118479")) # arbitrary text is never stripped into a key

    def test_packaging_indicator_kept(self):
        self.assertEqual(I.norm_gtin("10037332118476"), "10037332118476")


class ScopeTest(unittest.TestCase):
    def test_levels_and_issuers_scope(self):
        a = I.key("mfr_model", "CSB604", "cyberpower", None, "model")
        b = I.key("mfr_model", "CSB604", "cyberpower", None, "configuration")
        c = I.key("mfr_model", "CSB604", "tripplite", None, "model")
        self.assertNotEqual(a, b); self.assertNotEqual(a, c)
        self.assertEqual(I.key("gtin", "037332118479", "anyone", "US", "package")[1:4], ("GS1", "00037332118479", None))

    def test_separator_rules_are_issuer_specific(self):
        self.assertEqual(I.norm_value("mfr_model", "PS-415-HG", "tripplite"), "PS415HG")
        self.assertEqual(I.norm_value("mfr_model", "Mac14,5", "apple"), "MAC14,5")
        self.assertNotEqual(I.norm_value("mfr_sku", "90NR0K51-M000N0", "asus"), I.norm_value("mfr_sku", "90NR0K51M000N0", "asus"))


class WorldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.events = []
        self.w = imp.World("power-strips", Decisions(self.tmp), self.events)

    def test_conflicting_strong_ids_quarantine(self):
        ka = imp.K("mfr_sku", "AAA1", "asus", "configuration"); kb = imp.K("mfr_model", "BBB2", "asus", "configuration")
        a = self.w.get("configuration", "asus", [ka], ("s", "1", "x")); b = self.w.get("configuration", "asus", [kb], ("s", "2", "y"))
        self.assertIsNot(a, b)
        self.assertIsNone(self.w.get("configuration", "asus", [ka, kb], ("s", "3", "z")))
        self.assertEqual(len(self.w.quarantine), 1)
        self.assertEqual(len(self.w.ents), 2, "no silent merge")
        self.assertIn("quarantine", [e[0] for e in self.events])

    def test_ledger_merge_allows_unify(self):
        ka = imp.K("mfr_sku", "AAA1", "asus", "configuration"); kb = imp.K("mfr_model", "BBB2", "asus", "configuration")
        (self.tmp / "decisions").mkdir()
        anchors = sorted(I.anchor("power-strips", k) for k in (ka, kb))
        (self.tmp / "decisions" / "ledger.jsonl").write_text('{"id":"d_1","by":"human","action":"merge","anchors":%s}\n' % str(anchors).replace("'", '"'))
        w = imp.World("power-strips", Decisions(self.tmp), [])
        w.get("configuration", "asus", [ka], None); w.get("configuration", "asus", [kb], None)
        self.assertIsNotNone(w.get("configuration", "asus", [ka, kb], None))
        self.assertEqual(len(w.ents), 1)

    def test_package_gtin_never_merges_models(self):
        e1 = self.w.get("model", "cyberpower", [imp.K("mfr_model", "CSB604", "cyberpower", "model")], None)
        e2 = self.w.get("model", "cyberpower", [imp.K("mfr_model", "CSB606", "cyberpower", "model")], None)
        for e in (e1, e2):
            imp.add_ident(e, {"scheme": "gtin", "value": "649532604163"}, role="key")
        self.assertIsNot(e1, e2)
        for e in (e1, e2):
            d = next(v for (s, _), v in e.idents.items() if s == "gtin")
            self.assertEqual((d["role"], d["package_level"]), ("alias", "package"))

    def test_suffix_link_is_only_proposed(self):
        base = self.w.get("model", "cyberpower", [imp.K("mfr_model", "CSB604", "cyberpower", "model")], None)
        mp = self.w.get("model", "cyberpower", [imp.K("mfr_model", "CSB604MP2", "cyberpower", "model")], None)
        for e, v in ((base, "CSB604"), (mp, "CSB604MP2")):
            imp.add_ident(e, {"scheme": "mfr_model", "value": v}, role="key", level="model")
        import collections
        imp.strip_variants(self.w, collections.Counter())
        self.assertEqual(mp.rels[0][0], "package_of"); self.assertEqual(mp.rels[0][2], "suffix:cyberpower")
        self.assertEqual(mp.kind, "model", "kind changes only after a human approval")
        st, _ = Decisions(self.tmp).relation_state("cyberpower-csb604mp2", "package_of", "cyberpower-csb604", "suffix:cyberpower")
        self.assertEqual(st, "proposed")


class RegistryTest(unittest.TestCase):
    def test_ids_are_reused_and_never_reminted(self):
        tmp = Path(tempfile.mkdtemp()) / "registry.jsonl"
        r = I.IdRegistry(tmp)
        a = r.mint("acme-x1", ["c|mfr_model|acme|X1|"], "c", "model", set())
        b = r.mint("acme-x1", ["c|mfr_model|acme|X-1B|"], "c", "model", set())
        self.assertEqual((a, b), ("acme-x1", "acme-x1-2"))
        r.flush()
        r2 = I.IdRegistry(tmp)
        self.assertEqual(r2.lookup(["c|mfr_model|acme|X-1B|"]), ["acme-x1-2"])
        self.assertEqual(r2.mint("acme-x1", ["c|mfr_model|acme|NEW|"], "c", "model", set()), "acme-x1-3", "issued ids are never reused")


if __name__ == "__main__":
    unittest.main()
