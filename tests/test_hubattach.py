#!/usr/bin/env python3
"""Hub-page document fixtures (coordinator ruling 2026-11-25, mophie): scripts/hubattach.py. Positive bind by document quote, a multi-SKU manual
whose shared rows must not bind, a manual for an SKU we do not carry (no attach), plus ambiguity and hub-is-never-a-source checks."""
import sys, tempfile, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CODE / "tests"), str(CODE / "scripts"), str(CODE / "crawler"), str(CODE / "crawler" / "adapters")]
import hubattach as HA  # noqa: E402
import docattach as DA  # noqa: E402
import yaml  # noqa: E402
from test_documents import _Store  # noqa: E402

HUB = "https://www.anker.com/pages/user-manuals"
PB_PORTS = [{"name": "USB-C", "type": "usb_c", "direction": "out", "max_w": 30, "fixed_pdos": None, "pps": None}]


def edge(cat="chargers"):
    return {"source_id": None, "ref": HUB, "page_url": HUB, "category": cat, "via": "hub", "link_role": "hub", "brand": "anker"}


def doc(blocks):
    return {"pages": [{"n": 1, "method": "text_layer", "text": "\n".join(l for b in blocks for l in b), "blocks": [{"lines": b} for b in blocks]}]}


class Hub(_Store, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.hubs = Path(tempfile.mkdtemp()) / "hubs.yaml"
        self.hubs.write_text(yaml.safe_dump({"hubs": [{"url": HUB, "kind": "hub", "brand": "anker", "categories": ["chargers", "power-banks"]}]}))

    def run_hub(self, w):
        ev = []
        return HA.apply({"chargers": w}, ev, {}, root=self.tmp, hubs_path=self.hubs), ev

    def test_positive_bind_by_document_quote(self):
        w, ents = self.world([("401114325", "p1", {"pages": [("mophie-us-powerbanks", "p1", "https://www.anker.com/products/p1", PB_PORTS)]})])
        self.store([("https://www.mophie.com/cdn/shop/files/401114325_Manual.pdf",
                     doc([["Model: 401114325"], ["Output", "USB-C: 5V⎓3A / 9V⎓3A / 15V⎓2A (30W Max)", "PPS: 3.3-11V⎓3A"]]), [edge()])])
        st, ev = self.run_hub(w)
        got = {c["key"]: c for c, ob in ents["401114325"].claims if ob[0] == DA.SOURCE_ID}
        self.assertEqual(st["hub_attached"], 1)
        self.assertEqual((got["pd.pps"]["value"], got["pd.pps_max_voltage"]["value"]), (True, 11))
        for c in got.values():
            self.assertEqual(c["method"]["extractor"], HA.EXTRACTOR)
            self.assertEqual({k: c["locator"][k] for k in ("linked_from", "link_role", "identity_basis")}, {"linked_from": HUB, "link_role": "hub", "identity_basis": "document_quote"})
        src = next(s for k, s in ents["401114325"].srcs.items() if "#page=" in k)
        self.assertEqual(src["linked_from"], HUB)
        self.assertEqual([x["linked_from"] for x in ents["401114325"].documents], [HUB])
        self.assertNotIn(("hub", HUB), {(o[0], o[1]) for o in ents["401114325"].obs})        # the hub never becomes an observation

    def test_multi_sku_shared_rows_do_not_bind(self):
        w, ents = self.world([("401114324", "p1"), ("401114325", "p2")])
        m = doc([["Models 401114324 and 401114325"], ["Output", "USB-C: 5V⎓3A / 9V⎓3A (20W Max)", "PPS: 3.3-11V⎓2A"],
                 ["401114325 Output", "USB-C1: 5V⎓3A / 20V⎓1.5A (30W Max)"]])
        self.store([("https://www.mophie.com/cdn/shop/files/family.pdf", m, [edge()])])
        st, _ = self.run_hub(w)
        a = [c for c, ob in ents["401114324"].claims if ob[0] == DA.SOURCE_ID]
        b = {c["key"]: c for c, ob in ents["401114325"].claims if ob[0] == DA.SOURCE_ID}
        self.assertEqual(a, [])                                       # only shared rows name it: nothing binds
        self.assertNotIn("pd.pps", b)                                 # the shared PPS row binds to nobody
        self.assertEqual(b["pd.max_fixed_voltage"]["value"], 20)      # its own scoped block only

    def test_uncarried_sku_does_not_attach(self):
        w, ents = self.world([("401114325", "p1")])
        self.store([("https://www.mophie.com/cdn/shop/files/401999999.pdf", doc([["Model: 401999999"], ["Output", "USB-C: 5V⎓3A / 20V⎓3A (60W Max)"]]), [edge()])])
        st, ev = self.run_hub(w)
        self.assertFalse([c for c, ob in ents["401114325"].claims if ob[0] == DA.SOURCE_ID])
        self.assertEqual(st["hub_docs_no_catalogued_entity:chargers"], 1)
        self.assertFalse(ev)

    def test_shared_identifier_is_ambiguous(self):
        w, ents = self.world([("401114325", "p1"), ("PS20K", "p2", {"skus": ["401114325"]})])
        self.store([("https://www.mophie.com/cdn/shop/files/x.pdf", doc([["Model: 401114325"], ["Output", "USB-C: 5V⎓3A / 20V⎓3A (60W Max)"]]), [edge()])])
        st, ev = self.run_hub(w)
        self.assertFalse([c for e in ents.values() for c, ob in e.claims if ob[0] == DA.SOURCE_ID])
        self.assertGreaterEqual(st["hub_bind_ambiguous"], 1)

    def test_unregistered_hub_edge_ignored(self):
        w, ents = self.world([("401114325", "p1")])
        e = dict(edge(), page_url="https://www.anker.com/pages/other", ref="https://www.anker.com/pages/other")
        self.store([("https://www.mophie.com/cdn/shop/files/y.pdf", doc([["Model: 401114325"], ["Output", "USB-C: 5V⎓3A / 20V⎓3A (60W Max)"]]), [e])])
        st, _ = self.run_hub(w)
        self.assertEqual(st["hub_attached"], 0)

    def test_docattach_ignores_hub_edges(self):
        w, ents = self.world([("401114325", "p1")])
        self.store([("https://www.mophie.com/cdn/shop/files/z.pdf", doc([["Model: 401114325"], ["Output", "USB-C: 5V⎓3A / 20V⎓3A (60W Max)"]]), [edge()])])
        st, _ = self.run_(w)
        self.assertEqual(st["attached"], 0)


class Policy(unittest.TestCase):
    def test_pending_policy(self):
        pol = yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())
        p = next(x for x in pol["claim_policies"] if x["id"] == "claim/hub-document-power-pdo@2")
        a = p["approval"]; self.assertIn(a["state"], ("pending", "approved")); self.assertTrue(a["state"] == "pending" or (a.get("by") and a.get("at")))
        self.assertEqual(p["match"]["extractors"], [HA.EXTRACTOR])
        self.assertEqual(p["audit"]["parsers"][HA.TRANSFORM], HA.fingerprint())


if __name__ == "__main__":
    unittest.main()
