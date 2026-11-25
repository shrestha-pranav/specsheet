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
import docspec_attach as DS  # noqa: E402
import resolve as R  # noqa: E402
import source_policy as SP  # noqa: E402
import yaml  # noqa: E402

FIX = CODE / "tests" / "fixtures" / "documents"
A2667 = json.loads((FIX / "a2667-manual.json").read_text())
PAGE_PORTS = [{"name": "USB-C 1", "type": "usb_c", "direction": "out", "max_w": 65, "fixed_pdos": None, "pps": None},
              {"name": "USB-C 2", "type": "usb_c", "direction": "out", "max_w": 65, "fixed_pdos": None, "pps": None},
              {"name": "USB-A", "type": "usb_a", "direction": "out", "max_w": 22.5, "fixed_pdos": None, "pps": None}]


IDC = {"identity": "text_layer", "identity_scope": "document", "identity_variant": "exact"}


def page(n, lines, method="text_layer", conf=None, tok=None):
    """tok (OCR pages): one token confidence for every word, or {word: conf} overrides on top of `conf` (the word-level sidecar)."""
    p = {"n": n, "method": method, "text": "\n".join(lines), "blocks": [] if method == "ocr" else [{"lines": lines}]}
    if conf is not None:
        p["ocr_conf"] = conf
    if method == "ocr" and tok is not None:
        over = tok if isinstance(tok, dict) else {}
        base = tok if not isinstance(tok, dict) else conf
        p["tokens"] = [[[w, over.get(w, base)] for w in l.split(" ") if w] for l in lines]
    return p


def parsed(doc):
    return {"power": X.power_output(doc), "text": X.full_text(doc), "id_pages": DA._id_pages(doc), "pages": len(doc["pages"]), "ocr_pages": 0}


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
            self.assertEqual(c["conditions"], {"document_kind": "manual", **IDC})
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
    LINES = ["Output", "USB-C1: 5V⎓3A / 9V⎓3A (27W Max)", "PPS: 3.3-11V⎓3A"]

    def test_ocr_condition_and_threshold(self):
        hi = {"pages": [page(2, self.LINES, "ocr", 84.0, tok=84.0)]}
        cs, _ = DA.claims_for("chargers", parsed(hi), "manual", "u", pports(PAGE_PORTS[:1] + PAGE_PORTS[2:]))
        self.assertTrue(cs)
        for c in cs:
            self.assertEqual(c["conditions"], {"document_kind": "manual", "ocr": True, "ocr_conf": 84.0, **IDC})
            self.assertEqual((c["method"]["stage"], c["method"]["extractor"]), ("ocr", DA.EXTRACTOR_OCR))
        lo = {"pages": [page(2, self.LINES, "ocr", DA.MIN_OCR_CONF - 1, tok=DA.MIN_OCR_CONF - 1)]}
        self.assertEqual(DA.claims_for("chargers", parsed(lo), "manual", "u", pports(PAGE_PORTS))[0], [])

    def test_high_page_mean_never_rescues_an_uncertain_digit(self):
        # review 6 exit: page mean 95, but the '3A' / '9V⎓3A' words carry 30: no row, no device value from them
        bad = {"pages": [page(2, self.LINES, "ocr", 95.0, tok={"Output": 95.0, "USB-C1:": 95.0, "5V⎓3A": 95.0, "/": 95.0, "9V⎓3A": 30.0, "(27W": 95.0,
                                                          "Max)": 95.0, "PPS:": 95.0, "3.3-11V⎓3A": 30.0})]}
        self.assertEqual(DA.claims_for("chargers", parsed(bad), "manual", "u", pports(PAGE_PORTS[:1] + PAGE_PORTS[2:]))[0], [])
        nosidecar = {"pages": [page(2, self.LINES, "ocr", 95.0)]}                       # no token evidence at all: uncertain
        self.assertEqual(DA.claims_for("chargers", parsed(nosidecar), "manual", "u", pports(PAGE_PORTS))[0], [])

    def test_ocr_is_not_auto_accepted(self):
        doc = yaml.safe_load((CODE / "data/decisions/policies.yaml").read_text())
        pol = next(p for p in doc["claim_policies"] if p["id"] == "claim/document-power-pdo@4")
        self.assertEqual(pol["match"]["extractors"], [DA.EXTRACTOR])
        self.assertNotIn(DA.EXTRACTOR_OCR, pol["match"]["extractors"]); self.assertNotIn(DA.EXTRACTOR_REVIEW, pol["match"]["extractors"])
        self.assertEqual(pol["approval"]["state"] in ("pending", "approved"), True)
        self.assertEqual(pol["audit"]["parsers"][DA.TRANSFORM], DA.fingerprint())     # pinned: a parser edit needs a new policy id
        spec = next(p for p in doc["claim_policies"] if p["id"] == "claim/document-spec-r2@2")
        self.assertEqual(spec["audit"]["parsers"][DS.TRANSFORM], DS.fingerprint())
        retired = {p["id"]: p for p in doc["retired_policies"]}
        self.assertEqual(retired["claim/document-power-pdo@3"]["retired"]["superseded_by"], "claim/document-power-pdo@4")
        self.assertEqual(retired["claim/document-spec-r2@1"]["retired"]["superseded_by"], "claim/document-spec-r2@2")
        self.assertFalse({"claim/document-power-pdo@3", "claim/document-spec-r2@1"} & {p["id"] for p in doc["claim_policies"]})


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


class _Store:
    """apply() over a throwaway document store and import.py's own World/Ent classes."""
    def setUp(self):
        self.imp = importlib.import_module("import")
        self.tmp = Path(tempfile.mkdtemp())

    def world(self, models):
        """models: [(model, ref)] or [(model, ref, {skus, pages: [(source_id, ref, page_url, ports)]})]; every page observation gets its own
        source entry (the page URL docattach verifies an edge against) and its own official out.ports claim."""
        class Dec:
            def merge_allowed(self, a):
                return False
        w = self.imp.World("chargers", Dec(), [], {})
        ents = {}
        for m, ref, *opt in models:
            o = opt[0] if opt else {}
            pages = o.get("pages") or [("anker-us-chargers", ref, f"https://www.anker.com/products/{ref}", PAGE_PORTS)]
            e = None
            for sid, r, url, ports in pages:
                ob = (sid, r, "sha256:p" + sid + r)
                e = w.get("model", "anker", [self.imp.K("mfr_model", m, "anker", "model")], ob) if e is None else e
                e.obs.add(ob)
                e.srcs.setdefault(ob[2], {"url": url, "tier": "manufacturer", "label": "page", "snapshot": ob[2], "retrieved_at": None})
                if ports is not None:
                    e.claims.append(({"key": "out.ports", "status": "known", "kind": "official", "value": ports}, ob))
            self.imp.add_ident(e, {"scheme": "mfr_model", "value": m}, role="key", level="model")
            for sku in o.get("skus") or []:
                self.imp.add_ident(e, {"scheme": "mfr_sku", "value": sku}, role="alias", level=None)
            ents[m] = e
        return w, ents

    def store(self, docs):
        """docs: [(name, doc json, found_on refs)] -> a raw/_documents-shaped dir. A name may be a full URL; a ref may be a full found_on
        dict; doc json may carry "_sha" (identical bytes at two URLs)."""
        disc, snaps = [], []
        self.tmp = Path(tempfile.mkdtemp())            # fresh store: parsed/ caches key on the snapshot hash
        (self.tmp / "text").mkdir(exist_ok=True)
        for i, (name, doc, refs) in enumerate(docs):
            url = name if name.startswith("http") else f"https://cdn.shopify.com/files/{name}.pdf"
            h = doc.get("_sha") or f"{i:064x}"
            sha = f"sha256:{h}"
            (self.tmp / "text" / f"{h}.json").write_text(json.dumps({k: v for k, v in doc.items() if k != "_sha"}))
            found = [r if isinstance(r, dict) else {"source_id": "anker-us-chargers", "ref": r, "page_url": f"https://www.anker.com/products/{r}",
                                                    "category": "chargers"} for r in refs]
            disc.append({"url": url, "norm_url": D.norm_url(url), "kind": "manual", "categories": ["chargers"], "link_text": "manual", "decision": "fetch",
                         "found_on": found})
            snaps.append({"snapshot": sha, "ref": D.norm_url(url), "url": url, "status": 200, "blob": f"blobs/{i}.pdf", "fetched_at": "2026-11-24T00:00:00Z"})
        (self.tmp / "discovery.json").write_text(json.dumps({"docs": disc}))
        (self.tmp / "snapshots.jsonl").write_text("".join(json.dumps(s) + "\n" for s in snaps))

    def run_(self, w):
        ev = []
        st = DA.apply({"chargers": w}, ev, {}, root=self.tmp)
        return st, ev

    @staticmethod
    def got(e):
        return [c for c, ob in e.claims if ob[0] == DA.SOURCE_ID]



class IdentityGuard(_Store, unittest.TestCase):
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


def tpage(n, *blocks):
    return {"n": n, "method": "text_layer", "text": "\n".join(l for b in blocks for l in b), "blocks": [{"lines": list(b)} for b in blocks]}


ROWS = ["Output", "USB-C1: 5V⎓3A / 20V⎓5A (100W Max)", "PPS 3.3-21V⎓5A"]
MAKER_B = {"domain": "maker-b.example", "match": "exact", "kind": "maker", "free": False, "paid": False, "licence_grant": False,
           "evidence": {"level": "blocked", "checked": None}}


class Review6Identity(_Store, unittest.TestCase):
    """Review 6 fix 1 exit fixtures: proposals / candidates, never trusted cross-attachments."""
    def test_unknown_sibling_scopes_rows(self):
        w, ents = self.world([("A1001", "a1001")])                          # A1003 is NOT catalogued
        fam = {"pages": [tpage(1, ["Applicable models: A1001, A1003"], ROWS)]}
        self.store([("Family", fam, ["a1001"])])
        st, ev = self.run_(w)
        self.assertEqual(self.got(ents["A1001"]), [])                      # docattach@1 attached all of these (no catalogued sibling)
        prop = next(x[5] for x in ev if x[0] == "document_proposal")
        self.assertEqual((prop["reason"], prop["uncatalogued"]), ("multi_model_no_row", ["A1003"]))
        w, ents = self.world([("A1001", "a1001")])
        self.store([("Family", {"pages": [tpage(1, ["Applicable models: A1001, A1003"], ["A1001 " + ROWS[0]] + ROWS[1:])]}, ["a1001"])])
        self.run_(w)
        cs = self.got(ents["A1001"])
        self.assertTrue(cs and all(c["conditions"]["identity_scope"] == "block" and c["method"]["extractor"] == DA.EXTRACTOR for c in cs))

    def test_two_models_in_one_block(self):
        w, ents = self.world([("A1001", "a1001"), ("A1002", "a1002")])
        self.store([("Pair", {"pages": [tpage(1, ["A1001 / A1002 " + ROWS[0]] + ROWS[1:])]}, ["a1001", "a1002"])])
        st, ev = self.run_(w)
        self.assertEqual((self.got(ents["A1001"]), self.got(ents["A1002"])), ([], []))
        self.assertEqual(st["proposal_multi_model"], 2)

    def test_base_model_regional_variant_stays_candidate(self):
        for url in ("https://cdn.shopify.com/files/51005003915_A2669211_Manual.pdf", "https://cdn.shopify.com/files/A2669_UK_Manual.pdf"):
            w, ents = self.world([("A2669", "a2669", {"skus": ["A2669113"]})])
            self.store([(url, {"pages": [tpage(1, ["Model: A2669"], ROWS)]}, ["a2669"])])
            self.run_(w)
            cs = self.got(ents["A2669"])
            self.assertTrue(cs)
            for c in cs:
                self.assertEqual((c["conditions"]["identity_variant"], c["method"]["extractor"]), ("model_only", DA.EXTRACTOR_REVIEW))
        w, ents = self.world([("A2669", "a2669", {"skus": ["A2669113"]})])      # the block names our own SKU: exact
        self.store([("https://cdn.shopify.com/files/A2669211_A2669113_Manual.pdf", {"pages": [tpage(1, ["A2669113 " + ROWS[0]] + ROWS[1:])]}, ["a2669"])])
        self.run_(w)
        self.assertTrue(all(c["method"]["extractor"] == DA.EXTRACTOR for c in self.got(ents["A2669"])))

    def test_shared_sku_stays_candidate(self):
        w, ents = self.world([("A4001", "a4001", {"skus": ["S4001US"]}), ("A4002", "a4002", {"skus": ["S4001US"]})])
        self.store([("Shared", {"pages": [tpage(1, ["Item number: S4001US"], ROWS)]}, ["a4001", "a4002"])])
        self.run_(w)
        for m in ("A4001", "A4002"):
            cs = self.got(ents[m])
            self.assertTrue(cs and all(c["method"]["extractor"] == DA.EXTRACTOR_REVIEW for c in cs))

    def test_low_confidence_ocr_identity_never_authorizes_text_rows(self):
        def doc(tok):
            return {"pages": [page(1, ["Product Number: A1001"], "ocr", 90.0, tok={"Product": 96.0, "Number:": 96.0, "A1001": tok}), tpage(2, ROWS)]}
        w, ents = self.world([("A1001", "a1001")])
        self.store([("Low", doc(20.0), ["a1001"])])                       # page mean 90, the model token 20
        st, ev = self.run_(w)
        self.assertEqual(self.got(ents["A1001"]), [])
        self.assertEqual(st["proposal_identity_low_confidence"], 1)
        w, ents = self.world([("A1001", "a1001")])
        self.store([("Ok", doc(91.0), ["a1001"])])                        # confident OCR identity: OCR-dependent candidates
        self.run_(w)
        cs = self.got(ents["A1001"])
        self.assertTrue(cs)
        for c in cs:
            self.assertEqual((c["conditions"]["identity"], c["method"]["extractor"], "ocr" in c["conditions"]), ("ocr", DA.EXTRACTOR_OCR, False))

    def test_short_identifier_needs_a_model_label(self):
        self.assertFalse(DA.mention("Port Type: USB-C3", "C3"))
        self.assertTrue(DA.mention("Model: C3 Port Type", "C3"))
        self.assertTrue(DA.mention("Model Number | BI-B43", "B43"))


class Review6Combination(_Store, unittest.TestCase):
    """Review 6 fix 2 exit fixtures."""
    def test_split_block_plus_heading(self):
        doc = {"pages": [tpage(1, ["Output", "USB-C1 + USB-C2"], ["USB-C1: 5V⎓3A / 9V⎓2A (18W Max)"])]}
        pw = X.power_output(doc)
        self.assertEqual(pw["ports"], [])
        self.assertEqual({d["mode"] for d in pw["device"]}, {"multi"})
        keys = {c["key"] for c in DA.claims_for("chargers", parsed(doc), "manual", "u", pports(PAGE_PORTS))[0]}
        self.assertFalse(keys & {"out.ports", "pd.max_fixed_voltage"})

    def test_page_spanning_multi_port_table(self):
        doc = {"pages": [tpage(1, ["Use Two Ports:", "USB-C1 + USB-C2 :"]),
                         tpage(2, ["USB-C1: 5V⎓3A / 20V⎓2.25A (45W Max)", "USB-C2: 5V⎓3A (15W Max)"])]}
        self.assertEqual(X.power_output(doc)["ports"], [])
        cs, _ = DA.claims_for("chargers", parsed(doc), "manual", "u", pports(PAGE_PORTS))
        self.assertFalse({c["key"] for c in cs} & {"out.ports", "pd.max_fixed_voltage"})      # 20 V of a combination row is no device maximum
        doc["pages"].append(tpage(3, ["Use One Port:", "USB-C1: 5V⎓3A / 20V⎓3.25A (65W Max)"]))     # an explicit single heading reopens
        rows = X.power_output(doc)["ports"]
        self.assertEqual([(r["page"], r["mode"]) for r in rows], [(3, "single")])

    def test_conflicting_layouts_and_linking_observation(self):
        other = [{"name": "USB-C", "type": "usb_c", "direction": "out", "max_w": 65, "fixed_pdos": None, "pps": None},
                 {"name": "USB-A", "type": "usb_a", "direction": "out", "max_w": 12, "fixed_pdos": None, "pps": None}]
        pages = [("anker-us-chargers", "x1", "https://www.anker.com/products/x1", PAGE_PORTS), ("anker-us-chargers", "x2", "https://www.anker.com/products/x2", other)]
        line = "USB-C1: 5V⎓3A / 20V⎓3.25A (65W Max)"
        for head, want in ((["Output"], []), (["Use One Port:"], [["USB-C 1"]])):
            w, ents = self.world([("A1001", "a1001", {"pages": pages})])
            self.store([("A1001_Manual", {"pages": [tpage(1, ["Model: A1001"], head + [line])]}, ["x1", "x2"])])
            self.run_(w)
            got = [[r["name"] for r in c["value"]] for c in self.got(ents["A1001"]) if c["key"] == "out.ports"]
            self.assertEqual(got, want)       # sectionless rows under disagreeing layouts: none; single-port rows: only the x1 edge's own names
            if want:
                lf = [c["locator"]["linked_from"] for c in self.got(ents["A1001"]) if c["key"] == "out.ports"]
                self.assertEqual(lf, ["https://www.anker.com/products/x1"])

    def test_valid_sectionless_row_attributable(self):
        doc = {"pages": [tpage(1, ["Output", "USB-C1: 5V⎓3A / 20V⎓3.25A (65W Max)"])]}
        cs, _ = DA.claims_for("chargers", parsed(doc), "manual", "u", pports(PAGE_PORTS))
        self.assertEqual([[r["name"] for r in c["value"]] for c in cs if c["key"] == "out.ports"], [["USB-C 1"]])

    def test_conflicts_preserved_order_independent(self):
        spec = {"key": "out.ports", "type": "list", "items": {"id_field": "name"}}
        page_c = {"id": "c_page", "status": "known", "kind": "official", "cond": {}, "ok": True, "value": PAGE_PORTS, "source": "s1"}
        bad = [dict(PAGE_PORTS[0], max_w=45, pps="3.3-16V 3A")]
        doc_c = {"id": "c_doc", "status": "known", "kind": "official", "cond": {"document_kind": "manual", **IDC}, "ok": True, "value": bad, "source": "s2"}
        r1, r2 = R.resolve_spec(spec, [page_c, doc_c], []), R.resolve_spec(spec, [doc_c, page_c], [])
        self.assertEqual((r1["status"], r2["status"]), ("conflicted", "conflicted"))
        self.assertEqual(json.dumps(r1, sort_keys=True, default=str), json.dumps(r2, sort_keys=True, default=str))
        sc = {"key": "pd.pps_max_voltage", "type": "number"}
        a = {"id": "a", "status": "known", "kind": "official", "cond": {}, "ok": True, "value": 21, "source": "s1"}
        b = {"id": "b", "status": "known", "kind": "official", "cond": {"document_kind": "manual", **IDC}, "ok": True, "value": 16, "source": "s2"}
        self.assertEqual(json.dumps(R.resolve_spec(sc, [a, b], []), sort_keys=True, default=str), json.dumps(R.resolve_spec(sc, [b, a], []), sort_keys=True, default=str))


class Review6PolicyEdge(_Store, unittest.TestCase):
    """Review 6 fix 3 exit fixtures: attachment -> source entries / documents[] -> source policy, independent of discovery order."""
    def setUp(self):
        super().setUp()
        doc = yaml.safe_load((CODE / "data" / "source-policy.yaml").read_text())
        doc["sources"].append(MAKER_B)
        p = self.tmp / "policy.yaml"
        p.write_text(yaml.safe_dump(doc))
        self.pol = SP.load(p)

    PAGES = [("anker-us-chargers", "a1001", "https://www.anker.com/products/a1001", PAGE_PORTS), ("makerb", "p1", "https://maker-b.example/p1", PAGE_PORTS)]
    EDGES = [{"source_id": "anker-us-chargers", "ref": "a1001", "page_url": "https://www.anker.com/products/a1001", "category": "chargers"},
             {"source_id": "makerb", "ref": "p1", "page_url": "https://maker-b.example/p1", "category": "chargers"}]

    def outcome(self, docs):
        w, ents = self.world([("A1001", "a1001", {"pages": self.PAGES})])
        self.store(docs)
        self.run_(w)
        e = ents["A1001"]
        doc_srcs = {k: s for k, s in e.srcs.items() if "#page=" in k}
        free_docs = sorted((d["url"], d["linked_from"]) for d in self.pol.documents(e.documents, "free"))
        free_srcs = sorted((s["url"], s["linked_from"]) for s in self.pol.source_entries(list(doc_srcs.values()), "free"))
        pps = [ob[2] for c, ob in e.claims if ob[0] == DA.SOURCE_ID and c["key"] == "pd.pps"]
        sp = {"status": "known", "value": True, "sources": pps, "claims": ["x"]}
        url_of = lambda sid: {"url": doc_srcs[sid]["url"], "linked_from": doc_srcs[sid]["linked_from"]}
        g, withheld = self.pol.gate_spec("pd.pps", sp, "free", url_of)
        return e, doc_srcs, free_docs, free_srcs, (withheld, sorted(doc_srcs[s]["linked_from"] for s in g["sources"]))

    def test_allowed_and_withheld_linking_pages_any_order(self):
        doc = {"pages": [tpage(1, ["Model: A1001"], ROWS)]}
        res = []
        for edges in (self.EDGES, self.EDGES[::-1]):
            e, srcs, docs, kept, gate = self.outcome([("A1001_Manual", doc, edges)])
            self.assertEqual(sorted(d["linked_from"] for d in e.documents), ["https://maker-b.example/p1", "https://www.anker.com/products/a1001"])
            self.assertEqual(len({s["linked_from"] for s in srcs.values()}), 2)               # one source entry per linking edge
            res.append((docs, kept, gate))
        self.assertEqual(res[0], res[1])                                                       # discovery order changes nothing
        docs, kept, gate = res[0]
        self.assertEqual([lf for _, lf in docs], ["https://www.anker.com/products/a1001"])
        self.assertEqual({lf for _, lf in kept}, {"https://www.anker.com/products/a1001"})
        self.assertEqual(gate, (False, ["https://www.anker.com/products/a1001"]))

    def test_identical_bytes_at_two_urls(self):
        doc = {"pages": [tpage(1, ["Model: A1001"], ROWS)], "_sha": "ab" * 32}
        for order in ((0, 1), (1, 0)):
            pair = [("https://cdn.shopify.com/files/A1001.pdf", doc, [self.EDGES[0]]), ("https://images.salsify.com/x/A1001.pdf", doc, [self.EDGES[1]])]
            e, srcs, docs, kept, gate = self.outcome([pair[i] for i in order])
            self.assertEqual(sorted(s["url"].split("#")[0] for s in srcs.values()),
                             ["https://cdn.shopify.com/files/A1001.pdf", "https://images.salsify.com/x/A1001.pdf"])      # never collapsed to the first URL
            self.assertEqual(docs, [("https://cdn.shopify.com/files/A1001.pdf", "https://www.anker.com/products/a1001")])
            self.assertEqual(gate, (False, ["https://www.anker.com/products/a1001"]))

    def test_unverified_edge_attaches_nothing(self):
        w, ents = self.world([("A1001", "a1001")])
        self.store([("A1001_Manual", {"pages": [tpage(1, ["Model: A1001"], ROWS)]},
                     [{"source_id": "anker-us-chargers", "ref": "a1001", "page_url": "https://www.anker.com/products/other", "category": "chargers"}])])
        st, _ = self.run_(w)
        self.assertEqual((self.got(ents["A1001"]), ents["A1001"].documents, st["edges_unverified"]), ([], [], 1))

    def test_no_chain_independent_of_classification(self):
        s = "https://images.salsify.com/image/upload/x/manual.pdf"
        self.assertTrue(self.pol.allowed(s, "free", linked_from="https://www.anker.com/products/a1001"))
        for lf in (None, "https://cdn.shopify.com/s/files/1/page", "https://images.salsify.com/other", "https://www.anker.com/files/other.pdf",
                   "https://unlisted.example/p", "https://maker-b.example/p1"):
            self.assertFalse(self.pol.allowed(s, "free", linked_from=lf), lf)                 # missing / ambiguous / chained edges stay withheld
        rec_docs = [{"url": s, "kind": "manual"}, {"url": s, "kind": "manual", "linked_from": "https://www.anker.com/products/a1001"}]
        self.assertEqual(self.pol.documents(rec_docs, "free"), rec_docs[1:])                   # no fallback to the record's first source


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
