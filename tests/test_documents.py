#!/usr/bin/env python3
"""Document pipeline fixtures (A3 document pipeline 2026-11-24): crawler/documents.py (classification, decisions), crawler/adapters/_docparse.py
(PDO/PPS rows), scripts/docattach.py (identity guard, port attribution, claims), scripts/resolve.py (provenance conditions, item merge, gate
support), scripts/source_policy.py (document_host inheritance), policy pinning.

Cases required by the brief: the A2667 manual (PPS recorded per port only where the manual attributes it), a multi-model manual, an OCR doc,
a non-English duplicate, a document whose model text does not match the linking page."""
import json, os, sys, tempfile, unittest
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CODE / "scripts"), str(CODE / "crawler"), str(CODE / "crawler" / "adapters")]
import importlib  # noqa: E402
import documents as D  # noqa: E402
import _docparse as X  # noqa: E402
import docattach as DA  # noqa: E402
import resolve as R  # noqa: E402
import source_policy as SP  # noqa: E402
import yaml  # noqa: E402

FIX = CODE / "tests" / "fixtures" / "documents"
A2667 = json.loads((FIX / "a2667-manual.json").read_text())
PAGE_PORTS = [{"name": "USB-C 1", "type": "usb_c", "direction": "out", "max_w": 65, "fixed_pdos": None, "pps": None},
              {"name": "USB-C 2", "type": "usb_c", "direction": "out", "max_w": 65, "fixed_pdos": None, "pps": None},
              {"name": "USB-A", "type": "usb_a", "direction": "out", "max_w": 22.5, "fixed_pdos": None, "pps": None}]


def page(n, lines, method="text_layer", conf=None):
    p = {"n": n, "method": method, "text": "\n".join(lines), "blocks": [] if method == "ocr" else [{"lines": lines}]}
    if conf is not None:
        p["ocr_conf"] = conf
    return p


def parsed(doc):
    return {"power": X.power_output(doc), "text": X.full_text(doc), "blocks": {}, "pages": len(doc["pages"]), "ocr_pages": 0}


def pports(rows):
    return [(r["name"], [t for t in DA.P.port_tokens(r["name"]) if t], r) for r in rows]


class A2667Manual(unittest.TestCase):
    def test_single_port_rows_only(self):
        rows = {r["name"]: r for r in X.power_output(A2667)["ports"]}
        self.assertEqual(set(rows), {"USB-C1 / USB-C2", "USB-A"})          # combination sections ('Use Two Ports') never set a port
        c = rows["USB-C1 / USB-C2"]
        self.assertEqual((c["mode"], c["pps"], c["max_w"]), ("single", "3.3-16V 3.25A", 65))
        self.assertEqual(c["fixed_pdos"], "5V3A 9V3A 15V3A 20V3.25A")
        self.assertIsNone(rows["USB-A"]["pps"])

    def test_claims_per_port_and_device(self):
        cs, unattr = DA.claims_for("chargers", parsed(A2667), "manual", "https://cdn.shopify.com/x/A2667_Manual.pdf", pports(PAGE_PORTS))
        by = {c["key"]: c for c in cs}
        self.assertEqual(unattr, 0)
        ports = {r["name"]: r for r in by["out.ports"]["value"]}
        self.assertEqual(ports["USB-C 1"]["pps"], "3.3-16V 3.25A")
        self.assertEqual(ports["USB-C 2"]["pps"], "3.3-16V 3.25A")
        self.assertIsNone(ports["USB-A"]["pps"])
        self.assertEqual((by["pd.pps"]["value"], by["pd.pps_max_voltage"]["value"], by["pd.pps_max_current_a"]["value"]), (True, 16, 3.25))
        for c in cs:
            self.assertEqual(c["kind"], "official")
            self.assertEqual(c["conditions"], {"document_kind": "manual"})
            self.assertEqual(c["locator"]["pdf_page"], 2)
            self.assertTrue(c["quote"])
            self.assertEqual(c["method"]["extractor"], DA.EXTRACTOR)

    def test_resolution_completes_page_rows(self):
        cs, _ = DA.claims_for("chargers", parsed(A2667), "manual", "u", pports(PAGE_PORTS))
        doc_val = next(c["value"] for c in cs if c["key"] == "out.ports")
        spec = {"key": "out.ports", "type": "list", "items": {"id_field": "name"}}
        claims = [{"id": "c_page", "status": "known", "kind": "official", "cond": {}, "ok": True, "value": PAGE_PORTS, "source": "s1"},
                  {"id": "c_doc", "status": "known", "kind": "official", "cond": {"document_kind": "manual"}, "ok": True, "value": doc_val, "source": "s2"}]
        r = R.resolve_spec(spec, claims, [])
        self.assertEqual(r["status"], "known")
        self.assertEqual(r["note"], R.MERGE_NOTE)
        self.assertEqual([p["pps"] for p in r["value"]], ["3.3-16V 3.25A", "3.3-16V 3.25A", None])
        self.assertEqual([p["max_w"] for p in r["value"]], [65, 65, 22.5])           # page values untouched
        self.assertTrue(R.supports(PAGE_PORTS, r["value"]) and R.supports(doc_val, r["value"]))
        # a document that disagrees with a value the page states stays a visible conflict, never an overwrite
        bad = [dict(doc_val[0], max_w=45)]
        r2 = R.resolve_spec(spec, claims[:1] + [dict(claims[1], value=bad)], [])
        self.assertEqual(r2["status"], "conflicted")

    def test_scalar_conflict_visible(self):
        spec = {"key": "pd.pps_max_voltage", "type": "number"}
        cs = [{"id": "a", "status": "known", "kind": "official", "cond": {}, "ok": True, "value": 21, "source": "s1"},
              {"id": "b", "status": "known", "kind": "official", "cond": {"document_kind": "manual"}, "ok": True, "value": 16, "source": "s2"}]
        self.assertEqual(R.resolve_spec(spec, cs, [])["status"], "conflicted")
        cs[1]["value"] = 21
        r = R.resolve_spec(spec, cs, [])
        self.assertEqual((r["status"], r["sources"]), ("known", ["s1", "s2"]))


class Attribution(unittest.TestCase):
    def test_unnamed_pdo_line_is_device_level_only(self):
        doc = {"pages": [page(1, ["Output", "5V⎓3A / 9V⎓3A / 15V⎓3A / 20V⎓3.25A", "PPS 3.3-11V⎓5A"])]}
        cs, _ = DA.claims_for("chargers", parsed(doc), "manual", "u", pports(PAGE_PORTS))
        keys = {c["key"] for c in cs}
        self.assertNotIn("out.ports", keys)
        self.assertIn("pd.pps", keys)
        self.assertEqual(next(c["value"] for c in cs if c["key"] == "pd.pps_max_voltage"), 11)

    def test_ambiguous_port_not_attributed(self):
        doc = {"pages": [page(1, ["USB-C: 5V⎓3A / 9V⎓3A / 20V⎓3.25A (65W Max)"])]}    # unnumbered USB-C, page has two C ports
        cs, unattr = DA.claims_for("chargers", parsed(doc), "manual", "u", pports(PAGE_PORTS))
        self.assertNotIn("out.ports", {c["key"] for c in cs})
        self.assertEqual(unattr, 1)

    def test_input_section_ignored(self):
        doc = {"pages": [page(1, ["Input: 5V⎓3A / 9V⎓2A (18W)", "USB-C: 5V⎓2A"])]}
        self.assertEqual(X.power_output(doc)["device"], [])

    def test_mains_range_is_not_pps(self):
        doc = {"pages": [page(1, ["Output", "USB-A: 100-240V 1.4A 5V⎓2.4A"])]}
        self.assertEqual([d["pps"] for d in X.power_output(doc)["device"]], [""])


class OcrDocument(unittest.TestCase):
    def test_ocr_condition_and_threshold(self):
        hi = {"pages": [page(2, ["Output", "USB-C1: 5V⎓3A / 9V⎓3A (27W Max)", "PPS: 3.3-11V⎓3A"], "ocr", 84.0)]}
        cs, _ = DA.claims_for("chargers", parsed(hi), "manual", "u", pports(PAGE_PORTS[:1] + PAGE_PORTS[2:]))
        self.assertTrue(cs)
        for c in cs:
            self.assertEqual(c["conditions"], {"document_kind": "manual", "ocr": True, "ocr_conf": 84.0})
            self.assertEqual((c["method"]["stage"], c["method"]["extractor"]), ("ocr", DA.EXTRACTOR_OCR))
        lo = {"pages": [page(2, hi["pages"][0]["text"].splitlines(), "ocr", DA.MIN_OCR_CONF - 1)]}
        self.assertEqual(DA.claims_for("chargers", parsed(lo), "manual", "u", pports(PAGE_PORTS))[0], [])

    def test_ocr_is_not_auto_accepted(self):
        pol = next(p for p in yaml.safe_load((CODE / "data/decisions/policies.yaml").read_text())["claim_policies"] if p["id"] == "claim/document-power-pdo@3")
        self.assertEqual(pol["match"]["extractors"], [DA.EXTRACTOR])
        self.assertEqual(pol["approval"]["state"] in ("pending", "approved"), True)
        self.assertEqual(pol["audit"]["parsers"][DA.TRANSFORM], DA.fingerprint())     # pinned: a parser edit needs a new policy id


class Classification(unittest.TestCase):
    def test_non_english_duplicate(self):
        mk = lambda u: dict(zip(("kind", "lang"), D.classify(u)), url=u, stem=D.stem(u), dedicated=False, categories=["chargers"],
                            found_on=[{"source_id": "anker-us-chargers", "ref": "a1"}])
        docs = D.decide([mk("https://cdn.shopify.com/f/A2667_Manual_EN.pdf"), mk("https://cdn.shopify.com/f/A2667_Manual_DE.pdf"),
                         mk("https://cdn.shopify.com/f/A9999_Manual_FR.pdf")])
        self.assertEqual([d["decision"] for d in docs], ["fetch", "skip:non_english_duplicate", "fetch"])   # a sole French manual is kept

    def test_kinds(self):
        self.assertEqual(D.classify("https://x/Warranty_terms.pdf")[0], "other")
        self.assertEqual(D.classify("https://x/Power-Series-Comparison.pdf")[0], "marketing")
        self.assertEqual(D.classify("https://x/A2147_User_Manual.pdf")[0], "manual")
        self.assertEqual(D.classify("https://x/RBE872_TS.pdf")[0], "spec_sheet")
        self.assertEqual(D.classify("https://x/INS_8850bt00870_Online.pdf")[0], "certificate")
        self.assertEqual(D.norm_url("https://CDN.shopify.com/a.pdf?v=1"), D.norm_url("https://cdn.shopify.com/a.pdf?v=2"))


class IdentityGuard(unittest.TestCase):
    """apply() over a throwaway document store and import.py's own World/Ent classes."""
    def setUp(self):
        self.imp = importlib.import_module("import")
        self.tmp = Path(tempfile.mkdtemp())

    def world(self, models):
        class Dec:
            def merge_allowed(self, a):
                return False
        w = self.imp.World("chargers", Dec(), [], {})
        ents = {}
        for m, ref in models:
            e = w.get("model", "anker", [self.imp.K("mfr_model", m, "anker", "model")], ("anker-us-chargers", ref, "sha256:p" + ref))
            self.imp.add_ident(e, {"scheme": "mfr_model", "value": m}, role="key", level="model")
            e.claims.append(({"key": "out.ports", "status": "known", "value": PAGE_PORTS}, ("anker-us-chargers", ref, "sha256:p" + ref)))
            ents[m] = e
        return w, ents

    def store(self, docs):
        """docs: [(name, doc json, found_on refs)] -> a raw/_documents-shaped dir."""
        disc, snaps = [], []
        (self.tmp / "text").mkdir(exist_ok=True)
        for i, (name, doc, refs) in enumerate(docs):
            url = f"https://cdn.shopify.com/files/{name}.pdf"
            sha = f"sha256:{i:064x}"
            (self.tmp / "text" / f"{i:064x}.json").write_text(json.dumps(doc))
            disc.append({"url": url, "norm_url": D.norm_url(url), "kind": "manual", "categories": ["chargers"], "link_text": name, "decision": "fetch",
                         "found_on": [{"source_id": "anker-us-chargers", "ref": r, "page_url": f"https://www.anker.com/products/{r}", "category": "chargers"} for r in refs]})
            snaps.append({"snapshot": sha, "ref": D.norm_url(url), "url": url, "status": 200, "blob": f"blobs/{i}.pdf", "fetched_at": "2026-11-24T00:00:00Z"})
        (self.tmp / "discovery.json").write_text(json.dumps({"docs": disc}))
        (self.tmp / "snapshots.jsonl").write_text("".join(json.dumps(s) + "\n" for s in snaps))

    def test_a2667_attaches_and_mismatch_proposes(self):
        w, ents = self.world([("A2667", "a2667"), ("A2663", "a2663")])
        self.store([("A2667_Manual", A2667, ["a2667", "a2663"])])        # the same manual linked from the A2663 page as well
        ev = []
        st = DA.apply({"chargers": w}, ev, {}, root=self.tmp)
        self.assertEqual((st["attached"], st["proposal_model_not_named"]), (1, 1))
        got = [c for c, ob in ents["A2667"].claims if ob[0] == DA.SOURCE_ID]
        self.assertIn("out.ports", {c["key"] for c in got})
        self.assertFalse([c for c, ob in ents["A2663"].claims if ob[0] == DA.SOURCE_ID])      # model text does not match: no claim
        prop = [e for e in ev if e[0] == "document_proposal"]
        self.assertEqual((prop[0][2] is ents["A2663"], prop[0][5]["reason"]), (True, "model_not_named"))
        src = next(s for k, s in ents["A2667"].srcs.items() if "#page=" in k)
        self.assertEqual(src["linked_from"], "https://www.anker.com/products/a2667")
        self.assertTrue(src["url"].endswith(".pdf#page=2"))

    def test_multi_model_needs_explicit_row(self):
        w, ents = self.world([("A1001", "a1001"), ("A1002", "a1002")])
        rows = {"pages": [{"n": 1, "method": "text_layer", "text": "Models A1001 and A1002\nA1001\nUSB-C1: 5V⎓3A / 20V⎓5A (100W Max)\nPPS 3.3-21V⎓5A",
                           "blocks": [{"lines": ["Models A1001 and A1002"]},
                                      {"lines": ["A1001 Output", "USB-C1: 5V⎓3A / 20V⎓5A (100W Max)", "PPS 3.3-21V⎓5A"]},
                                      {"lines": ["Output", "USB-C2: 5V⎓3A / 9V⎓2A (20W Max)"]}]}]}
        self.store([("Family_Guide", rows, ["a1001", "a1002"])])
        ev = []
        st = DA.apply({"chargers": w}, ev, {}, root=self.tmp)
        a = [c for c, ob in ents["A1001"].claims if ob[0] == DA.SOURCE_ID]
        b = [c for c, ob in ents["A1002"].claims if ob[0] == DA.SOURCE_ID]
        ports = [r["name"] for c in a if c["key"] == "out.ports" for r in c["value"]]
        self.assertEqual(ports, ["USB-C 1"])                           # USB-C2's block does not name A1001: not attached
        self.assertTrue(any(c["key"] == "pd.pps" for c in a))
        self.assertEqual(b, [])                                        # no block names A1002: proposal, never a claim
        self.assertEqual(st["proposal_multi_model"], 1)
        self.assertEqual(st["multi_model_docs"], 2)


class DocumentHostPolicy(unittest.TestCase):
    def setUp(self):
        doc = yaml.safe_load((CODE / "data" / "source-policy.yaml").read_text())
        doc["sources"].append({"domain": "maker-b.example", "match": "exact", "kind": "maker", "free": False, "paid": False, "licence_grant": False,
                               "evidence": {"level": "blocked", "checked": None}})
        p = Path(tempfile.mkdtemp()) / "p.yaml"
        p.write_text(yaml.safe_dump(doc))
        self.pol = SP.load(p)

    def test_inherits_linking_page(self):
        u = "https://cdn.shopify.com/s/files/1/A2667_Manual.pdf#page=2"
        self.assertFalse(self.pol.allowed(u, "free"))                                   # no linking page: withheld
        self.assertTrue(self.pol.allowed(u, "free", linked_from="https://www.anker.com/products/a2667"))
        self.assertTrue(self.pol.allowed({"url": u, "linked_from": "https://www.anker.com/products/a2667"}, "free"))
        self.assertFalse(self.pol.allowed(u, "free", linked_from="https://maker-b.example/p"))     # same CDN, other maker's disposition
        self.assertFalse(self.pol.allowed(u, "free", linked_from="https://cdn.shopify.com/other.pdf"))   # no chains
        self.assertFalse(self.pol.allowed(u, "paid", linked_from="https://www.anker.com/products/a2667"))

    def test_validation(self):
        doc = yaml.safe_load((CODE / "data" / "source-policy.yaml").read_text())
        doc["sources"].append({"domain": "cdn.bad.example", "kind": "document_host", "free": True, "paid": False, "licence_grant": False,
                               "evidence": {"level": "none"}})
        bad = SP.validate(doc)
        self.assertTrue(any("inherit: linking_page" in b for b in bad) and any("must all be false" in b for b in bad))

    def test_merged_value_needs_every_source(self):
        sp = {"value": [{"name": "C1", "pps": "3.3-16V 3A"}], "status": "known", "sources": ["s1", "s2"], "claims": ["a", "b"], "note": R.MERGE_NOTE}
        urls = {"s1": "https://www.anker.com/p", "s2": {"url": "https://cdn.shopify.com/m.pdf", "linked_from": "https://maker-b.example/p"}}
        out, withheld = self.pol.gate_spec("out.ports", sp, "free", urls.get)
        self.assertTrue(withheld)
        urls["s2"]["linked_from"] = "https://www.anker.com/p"
        out, withheld = self.pol.gate_spec("out.ports", sp, "free", urls.get)
        self.assertFalse(withheld)


if __name__ == "__main__":
    unittest.main()
