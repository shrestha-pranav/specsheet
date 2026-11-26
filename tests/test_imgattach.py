#!/usr/bin/env python3
"""Spec-image OCR fixtures (A3, brief coord-2026-11-25-ocr-mophie-a3): scripts/imgattach.py (identity binding, value gate, claims) over a
throwaway raw/_specimages-shaped store and import.py's own World/Ent classes (tests/test_documents._Store).

Brief cases: A2667 (PPS 3.3-16V 3.25A must corroborate the manual, not conflict), a multi-SKU page that must NOT attach, a low-confidence image
that must drop, an ambiguous voltage ('3.3-1 1V'). The real A2667 gallery images print no PDO (OCR of all 7: wattage headlines only) and are
named A2667111/A2667113 on a page whose only SKU is A2667114, so the file-name veto applies to them; the A2667 case here is a synthetic spec
card with the manual's own values."""
import json, sys, tempfile, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CODE / "tests"), str(CODE / "scripts"), str(CODE / "crawler"), str(CODE / "crawler" / "adapters")]
import imgattach as IA  # noqa: E402
import specimages as SI  # noqa: E402
import yaml  # noqa: E402
from test_documents import _Store, PAGE_PORTS  # noqa: E402

CARD = ["A2667 Specs", "Output", "USB-C1 / USB-C2: 5V⎓3A / 9V⎓3A / 15V⎓3A / 20V⎓3.25A", "PPS: 3.3-16V⎓3.25A", "USB-A: 5V⎓2.4A / 9V⎓2A / 12V⎓1.5A"]


def ocr(lines, conf=92.0, over=None):
    over = over or {}
    return {"extractor": SI.OCR, "lines": [[[w, over.get(w, conf)] for w in l.split(" ") if w] for l in lines], "text": "\n".join(lines),
            "mean_conf": conf}


class _Img(_Store):
    def images(self, items):
        """items: [(file name, ocr json, [(ref, page_skus)])] -> raw/_specimages-shaped dir."""
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "ocr").mkdir()
        out = []
        for i, (name, o, refs) in enumerate(items):
            h = f"{i:064x}"
            (self.tmp / "ocr" / f"{h}.json").write_text(json.dumps(o))
            url = f"https://cdn.shopify.com/s/files/1/0493/9834/9974/files/{name}"
            out.append({"sha": f"sha256:{h}", "url": url, "blob": f"raw/anker/blobs/{h}.jpg", "file_models": SI.file_models(url),
                        "found_on": [{"source_id": "anker-us-chargers", "ref": r, "page_url": f"https://www.anker.com/products/{r}", "category": "chargers",
                                      "page_skus": skus, "retrieved_at": "2026-11-24T00:00:00Z"} for r, skus in refs]})
        (self.tmp / "discovery.json").write_text(json.dumps({"images": out}))

    def run_img(self, w):
        ev = []
        return IA.apply({"chargers": w}, ev, {}, root=self.tmp), ev

    @staticmethod
    def got(e):
        return {c["key"]: c for c, ob in e.claims if ob[0] == IA.SOURCE_ID}


class Binding(_Img, unittest.TestCase):
    def test_a2667_single_sku_card_corroborates_manual(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]})])
        self.images([("A2667111_TD09_US_V1.jpg", ocr(CARD), [("a2667", ["A2667111"])])])
        st, ev = self.run_img(w)
        by = self.got(ents["A2667"])
        self.assertEqual(st["image_bound:single_sku_page"], 1)
        self.assertEqual((by["pd.pps"]["value"], by["pd.pps_max_voltage"]["value"], by["pd.pps_max_current_a"]["value"], by["pd.max_fixed_voltage"]["value"]),
                         (True, 16, 3.25, 20))                         # = the A2667 manual (tests/test_documents.A2667Manual): corroborates
        ports = {r["name"]: r for r in by["out.ports"]["value"]}
        self.assertEqual((ports["USB-C 1"]["pps"], ports["USB-C 2"]["fixed_pdos"]), ("3.3-16V 3.25A", "5V3A 9V3A 15V3A 20V3.25A"))
        for c in by.values():
            self.assertEqual((c["kind"], c["method"]["extractor"], c["conditions"]["document_kind"], c["conditions"]["ocr"]),
                             ("official", IA.EXTRACTOR, "spec_image", True))
            self.assertEqual(c["locator"]["linked_from"], "https://www.anker.com/products/a2667")
        src = next(s for k, s in ents["A2667"].srcs.items() if "#image#" in k)
        self.assertEqual((src["tier"], src["linked_from"]), ("manufacturer", "https://www.anker.com/products/a2667"))

    def test_multi_sku_page_does_not_attach(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111", "A2667113"]})])
        card = [l.replace("A2667 Specs", "Specs") for l in CARD]       # no model number in the image
        self.images([("TD09_US_V1.jpg", ocr(card), [("a2667", ["A2667111", "A2667113"])])])
        st, ev = self.run_img(w)
        self.assertFalse(self.got(ents["A2667"]))
        self.assertEqual(st["image_unbound:multi_sku_page_no_ocr_model"], 1)
        self.assertEqual([e[5]["reason"] for e in ev if e[0] == "image_proposal"], ["multi_sku_page_no_ocr_model"])

    def test_multi_sku_page_with_confident_ocr_model(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111", "A2667113"]})])
        self.images([("TD09_US_V1.jpg", ocr(CARD), [("a2667", ["A2667111", "A2667113"])])])
        self.run_img(w)
        by = self.got(ents["A2667"])
        self.assertEqual(by["pd.pps"]["conditions"]["identity"], "ocr")
        self.assertEqual(by["pd.pps"]["method"]["extractor"], IA.EXTRACTOR_REVIEW)    # model-level mention on a multi-SKU page: review only

    def test_low_confidence_model_token_drops(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111", "A2667113"]})])
        self.images([("TD09_US_V1.jpg", ocr(CARD, over={"A2667": 41.0}), [("a2667", ["A2667111", "A2667113"])])])
        st, _ = self.run_img(w)
        self.assertFalse(self.got(ents["A2667"]))
        self.assertEqual(st["image_unbound:identity_low_confidence"], 1)

    def test_file_name_other_sku_vetoes_inheritance(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667114"]})])
        card = [l.replace("A2667 Specs", "Specs") for l in CARD]
        self.images([("A2667113_TD01_V1_1.png", ocr(card), [("a2667", ["A2667114"])])])   # the real a2667 page / image naming
        st, _ = self.run_img(w)
        self.assertFalse(self.got(ents["A2667"]))
        self.assertEqual(st["image_unbound:file_name_names_other_sku"], 1)

    def test_other_model_in_image_never_inherits(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]})])
        card = [l.replace("A2667 Specs", "A2663 Specs") for l in CARD]
        self.images([("TD09_US_V1.jpg", ocr(card), [("a2667", ["A2667111"])])])
        st, _ = self.run_img(w)
        self.assertFalse(self.got(ents["A2667"]))
        self.assertEqual(st["image_unbound:names_other_model"], 1)

    # review-8 P1: conflicting-identity vetoes apply BEFORE single-SKU inheritance (no exact claim from another configuration's image)
    def _no_exact(self, ents, m="A2667"):
        for c in self.got(ents[m]).values():
            self.assertNotEqual(c["conditions"]["identity_variant"], "exact", c["key"])
            self.assertEqual(c["method"]["extractor"], IA.EXTRACTOR_REVIEW, c["key"])

    def test_ocr_variant_vetoes_single_sku_inheritance(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]})])
        card = [l.replace("A2667 Specs", "A2667113 Specs") for l in CARD]      # the image names another SKU of the base; empty file_models
        self.images([("TD09_V1.jpg", ocr(card), [("a2667", ["A2667111"])])])
        st, _ = self.run_img(w)
        self.assertEqual(st["image_bound:single_sku_page"], 0)
        self._no_exact(ents)

    def test_ocr_variant_no_model_mention_stays_unbound(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]})])
        card = [l.replace("A2667 Specs", "Specs") for l in CARD] + ["Model A2667113"]
        self.images([("TD09_V1.jpg", ocr(card), [("a2667", ["A2667111"])])])
        st, _ = self.run_img(w)
        self.assertEqual(st["image_bound:single_sku_page"], 0)
        self._no_exact(ents)

    def test_foreign_region_vetoes_single_sku_inheritance(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]})])
        card = [l.replace("A2667 Specs", "Specs") for l in CARD]
        self.images([("TD09_UK_V1.jpg", ocr(card), [("a2667", ["A2667111"])])])
        st, _ = self.run_img(w)
        self.assertFalse(self.got(ents["A2667"]))
        self.assertEqual(st["image_unbound:conflicting_variant_region_shared"], 1)

    def test_shared_identifier_vetoes_exact(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]}), ("A2668", "a2668", {"skus": ["A2667111"]})])
        card = [l.replace("A2667 Specs", "A2667111 Specs") for l in CARD]
        self.images([("TD09_V1.jpg", ocr(card), [("a2667", ["A2667111"])])])
        st, _ = self.run_img(w)
        self.assertEqual(st["image_bound:single_sku_page"], 0)
        self._no_exact(ents)


class ValueGate(_Img, unittest.TestCase):
    def test_low_conf_image_drops(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]})])
        self.images([("TD09_US_V1.jpg", ocr(CARD, conf=66.0), [("a2667", ["A2667111"])])])   # every token >= 60 but mean < 70
        st, _ = self.run_img(w)
        self.assertFalse(self.got(ents["A2667"]))
        self.assertGreaterEqual(st["images_lines_low_conf"], 3)

    def test_ambiguous_voltage_never_attaches(self):
        w, ents = self.world([("A2667", "a2667", {"skus": ["A2667111"]})])
        card = CARD[:3] + ["PPS: 3.3-1 1V⎓3.25A"] + CARD[4:]
        self.images([("TD09_US_V1.jpg", ocr(card), [("a2667", ["A2667111"])])])
        st, _ = self.run_img(w)
        by = self.got(ents["A2667"])
        self.assertNotIn("pd.pps_max_voltage", by)
        self.assertFalse(any((r.get("pps") or "").startswith("3.3-1") for c in by.values() if c["key"] == "out.ports" for r in c["value"]))
        self.assertEqual(st["images_lines_ambiguous"], 1)

    def test_ambiguity_patterns(self):
        for s in ["PPS 3.3-1 1V 3A", "1JOOW Max", "2O.0V 5A", "3. 25A"]:
            self.assertTrue(IA.ambiguous(s), s)
        for s in ["USB-C 1 65W Max", "5V⎓3A / 20V⎓3.25A", "PPS: 3.3-16V⎓3.25A", "100W Max"]:
            self.assertFalse(IA.ambiguous(s), s)


class Policy(unittest.TestCase):
    def test_pending_policy_allowlists(self):
        pol = yaml.safe_load((CODE / "data" / "decisions" / "policies.yaml").read_text())
        p = next(x for x in pol["claim_policies"] if x["id"] == "claim/spec-image-power-pdo@2")   # review-8 re-pin
        a = p["approval"]; self.assertIn(a["state"], ("pending", "approved")); self.assertTrue(a["state"] == "pending" or (a.get("by") and a.get("at")))
        self.assertEqual(p["match"]["extractors"], [IA.EXTRACTOR])
        self.assertEqual(p["match"]["source_ids"], [IA.SOURCE_ID])
        self.assertNotIn(IA.EXTRACTOR_REVIEW, p["match"]["extractors"])
        self.assertEqual(p["audit"]["parsers"][IA.TRANSFORM], IA.fingerprint())


if __name__ == "__main__":
    unittest.main()
