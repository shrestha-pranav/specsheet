"""Hub-page documents -> entities (coordinator ruling 2026-11-25, mophie). Transform `hubattach@1`, extractor `hubdoc@1` (+ `hubdoc-review@1`,
never in an auto-accept policy). Called by scripts/import.py after docattach; a separate transform so docattach@2 stays pinned.

A hub (data/document-hubs.yaml, kind: hub, e.g. www.mophie.com/pages/user-manuals) lists documents for many products. It is never an entity
source: no entity, observation or claim comes from the hub page. A hub -> document edge (crawler/documents.py discover: found_on {link_role: hub})
binds a document to an entity ONLY through the document's own text:
  - candidates = catalogued entities of the hub's brand in the edge's category whose own mfr_model / mfr_sku the document quotes (docattach
    identity: bounded mention, short ids only after a model label, an OCR mention only with every word >= 60);
  - any ambiguity = no bind: the quoted identifier is shared with another entity, another SKU of the same base / a foreign region token is in
    play (docattach 'variants' / 'region'), or two candidates' rows cannot be told apart;
  - rows are scoped exactly as docattach@2 (docattach.scope_of): with a sibling model named, a row binds only when its own block, else page,
    names this entity and no sibling; a document-wide (shared) row of a multi-SKU document binds to nobody;
  - a document quoting no catalogued entity attaches nothing (counted, no proposal: we do not carry that SKU).
Claims = docattach.claims_for (same grammar, keys, port attribution onto the entity's own official out.ports when all its pages agree).
Provenance: locator {linked_from: hub URL, link_role: hub, identity_basis: document_quote}; source entry per document x page x hub edge
(docattach.edge_source, linked_from = hub URL); documents[] entry with linked_from = hub URL. The document URL is on the maker's own host
(www.mophie.com/cdn/shop, listed there as kind maker), so it carries mophie.com's disposition directly. Extractor hubdoc@1 only for
text-layer rows with text-layer identity; anything OCR-dependent is hubdoc-review@1.
"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "scripts"))
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
import _docparse as X  # noqa: E402
import docattach as DA  # noqa: E402
import yaml  # noqa: E402

TRANSFORM = "hubattach@1"
EXTRACTOR, EXTRACTOR_REVIEW = "hubdoc@1", "hubdoc-review@1"
HUBS = CODE / "data" / "document-hubs.yaml"


def fingerprint():
    h = hashlib.sha256()
    for p in (Path(__file__), CODE / "crawler/adapters/_docparse.py", CODE / "crawler/adapters/_powerbank.py", CODE / "crawler/adapters/_charger.py",
              CODE / "scripts/docattach.py", HUBS):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()[:20]


def hubs(path=None):
    p = Path(path or HUBS)
    return {h["url"]: h for h in (yaml.safe_load(p.read_text()) or {}).get("hubs") or [] if h.get("kind") == "hub"} if p.exists() else {}


def parse(d, sha):
    """Uncached docattach-shaped parse (no write into docattach's parsed/ cache, which keys on docattach's own fingerprint)."""
    h = sha.split(":", 1)[-1]
    tp = d / "text" / f"{h}.json"
    if not tp.exists():
        return None
    sp = d / "ocr" / f"{h}.json"
    doc = DA.with_tokens(json.loads(tp.read_text()), json.loads(sp.read_text()) if sp.exists() else None)
    return {"power": X.power_output(doc), "text": X.full_text(doc), "id_pages": DA._id_pages(doc), "pages": len(doc["pages"]),
            "ocr_pages": sum(1 for p in doc["pages"] if p["method"] == "ocr")}


def apply(worlds, events, stats, root=None, hubs_path=None):
    docs, latest, d = DA._load_docs(root)
    reg = hubs(hubs_path)
    st = Counter()
    lineage_done = set()
    for doc in docs:
        hf = [f for f in doc.get("found_on") or [] if f.get("link_role") == "hub" and f.get("page_url") in reg]
        if not hf or doc.get("decision") != "fetch":
            continue
        rec = latest.get(doc["norm_url"])
        res = parse(d, rec["snapshot"]) if rec else None
        if res is None:
            st["hub_docs_not_fetched_or_extracted"] += 1
            continue
        st["hub_docs_parsed"] += 1
        for f in hf:
            hub = reg[f["page_url"]]
            cat = f.get("category")
            if cat not in worlds or cat not in DA.CATEGORIES or cat not in hub.get("categories", []):
                continue
            w = worlds[cat]
            if cat not in lineage_done:
                DA._compute_lineage(w.ents); lineage_done.add(cat)
            cands = []
            for e in w.ents:
                if e.brand != hub["brand"] or not DA.ident_values(e):
                    continue
                idn = DA.identity(e, w, res, doc["url"])
                if idn["mine"]:
                    cands.append((e, idn))
            if not cands:
                st[f"hub_docs_no_catalogued_entity:{cat}"] += 1
                continue
            for e, idn in cands:
                ob = (DA.SOURCE_ID, doc["norm_url"], rec["snapshot"])
                if idn["shared"] or idn["variants"] or idn["region"]:
                    st["hub_bind_ambiguous"] += 1
                    events.append(("document_proposal", cat, e, w.anchors(e.keys), ob, {"reason": "hub_identity_ambiguous", "url": doc["url"],
                                                                                       "page": f["page_url"], "shared": idn["shared"][:4],
                                                                                       "variants": idn["variants"][:4], "region": idn["region"]}))
                    continue
                allowed = lambda page, btxt, idn=idn: DA.scope_of(idn, res, page, btxt)
                pp, disagree = DA.page_ports(e, None)
                cs, unattr = DA.claims_for(cat, res, doc["kind"], doc["url"], pp, allowed, disagree)
                st["hub_port_rows_unattributable"] += unattr
                if not cs:
                    st["hub_bound_no_rows"] += 1
                    continue
                DA.add_document(e, doc, f["page_url"])
                for c in cs:
                    ocr_dep = c["conditions"].get("ocr") or c["conditions"].get("identity") == "ocr" or c["conditions"].get("identity_variant") != "exact"
                    c["method"]["extractor"] = EXTRACTOR_REVIEW if ocr_dep else EXTRACTOR
                    page = c["locator"]["pdf_page"]
                    snap = DA.edge_source(e, doc, rec, page, f["page_url"])
                    c["locator"].update(linked_from=f["page_url"], link_role="hub", identity_basis="document_quote")
                    c["observed_at"] = rec.get("fetched_at") or "1970-01-01T00:00:00Z"
                    e.claims.append((c, (DA.SOURCE_ID, doc["norm_url"], snap)))
                    st[f"hub_claims:{cat}:{c['key']}"] += 1
                    st[f"hub_claims_by_extractor:{c['method']['extractor']}"] += 1
                e.obs.add(ob)
                events.append(("document_attach", cat, e, w.anchors(e.keys), ob, {"url": doc["url"], "identifiers": idn["mine"], "claims": len(cs),
                                                                                 "link_role": "hub", "linked_from": f["page_url"],
                                                                                 "identity_basis": "document_quote", "multi_model": bool(idn["siblings"])}))
                st["hub_attached"] += 1
    for k, v in st.items():
        stats[k] = stats.get(k, 0) + v
    return st
