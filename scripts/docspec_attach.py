"""Document claims r2 (2026-11-24): SSD datasheet and monitor spec-sheet rows -> entities. Transform `docspec-attach@1`, extractor `docspec@1`
(crawler/adapters/_docspec.py). Called by scripts/import.py right after docattach.apply (same inputs: raw/_documents/discovery.json,
snapshots.jsonl, text/<sha>.json; nothing from the network). A separate transform so docattach@1 / docparse@1, pinned by
claim/document-power-pdo@1, never drift. Parse results cache in raw/_documents/parsed-spec/<sha>.json keyed by this fingerprint.

Identity guard (same rule as docattach@1, plus one bounded widening): a document attaches only to an entity observed on a page the document
was linked from, and only when the document text names one of that entity's own mfr_model / mfr_sku exactly, OR names its base SKU (the
part before the first '-', 6+ chars, letters and digits: datasheets print 'MODEL NUMBER SDSSDE83' for orderable SDSSDE83-2T00-G25; the same
"one is the other plus a -suffix" rule sandisk_datasheets@1 uses). A document that also names an identifier of a same-brand entity NOT
observed on any of its linking pages is a multi-model document: nothing attaches (identity_events document_proposal multi_model_other_page).
The facts are single spanning table cells (no per-capacity column split, no two values for one key in one document, see _docspec), so they
hold for every model the document names. Affirmative only; nothing from silence; text layer only.
docspec-attach@2 (review 6 fix 3): provenance is kept per linking edge exactly as docattach@2 does (DA.edges_of / edge_verified /
edge_source / add_document): one source entry, claim (locator.linked_from) and documents[] entry {url, kind, label, linked_from} per
verified (document URL, snapshot, page, linking page); identical bytes at two URLs never share a source entry. The identity rule is
unchanged: its facts are single spanning cells that hold for every model the document names, so an uncatalogued sibling in the same
table does not change them (docattach@2's sibling scoping is for per-row power tables).
"""
import hashlib, json, re, sys
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import _docspec as X  # noqa: E402
import docattach as DA  # noqa: E402

TRANSFORM = "docspec-attach@2"
SOURCE_ID = DA.SOURCE_ID
EXTRACTOR = f"{X.NAME}@{X.VERSION}"
KEYS = {"ssds": {"if.protocol", "hw.dram_type", "hw.nand_type", "hw.controller"}, "monitors": {"flk.pwm", "usb.usbc_pd_w"}}
PARSERS = {"ssds": X.ssd, "monitors": X.monitor}


def fingerprint():
    h = hashlib.sha256()
    for p in (Path(__file__), CODE / "crawler/adapters/_docspec.py", CODE / "scripts/docattach.py"):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()[:20]


def parsed(d, sha, cat, fp):
    h = sha.split(":", 1)[-1]
    cp = d / "parsed-spec" / f"{h}.{cat}.json"
    if cp.exists():
        try:
            c = json.loads(cp.read_text())
            if c.get("fingerprint") == fp:
                return c["result"]
        except ValueError:
            pass
    tp = d / "text" / f"{h}.json"
    if not tp.exists():
        return None
    doc = json.loads(tp.read_text())
    res = {"facts": PARSERS[cat](doc), "text": "\n".join(p.get("text", "") for p in doc["pages"] if p.get("method") == "text_layer")}
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp"); tmp.write_text(json.dumps({"fingerprint": fp, "result": res})); tmp.replace(cp)
    return res


def base_sku(v):
    b = str(v).split("-", 1)[0]
    return b if b != str(v) and len(b) >= 6 and re.search(r"[A-Z]", b, re.I) and re.search(r"\d", b) else None


def named(e, text):
    vals = DA.ident_values(e)
    hit = [v for v in vals if DA.X.mentions(text, v)]
    hit += [b for b in {base_sku(v) for v in vals} - {None} if DA.X.mentions(text, b)]
    return sorted(set(hit))


def subsumed(e, f):
    """A document 'DRAM Cache NO' (dramless, HMB unknown) next to the page's own dramless_hmb / dramless_none is the same fact, less specific:
    not emitted (it would show as a false conflict). Any other disagreement is emitted and stays visible."""
    if f["key"] != "hw.dram_type" or f["value"] != "dramless":
        return False
    return any(c.get("key") == "hw.dram_type" and c.get("status") == "known" and c.get("value") in ("dramless_hmb", "dramless_none") and ob[0] != SOURCE_ID
               for c, ob in e.claims)


def claim(f, dkind, url):
    return {"key": f["key"], "status": "known", "kind": "official", "value": f["value"], "unit": None, "raw": f["raw"], "quote": f["quote"],
            "conditions": {"document_kind": dkind}, "locator": {"pdf_page": f["page"], "document": url},
            "method": {"stage": "pdf_text", "extractor": EXTRACTOR}, "review": {"state": "candidate"}}


def apply(worlds, events, stats, root=None):
    docs, latest, d = DA._load_docs(root)
    fp = fingerprint()
    by_obs = {}
    for cat, w in worlds.items():
        if cat in KEYS:
            for e in w.ents:
                for ob in e.obs:
                    by_obs.setdefault((cat, ob[0], ob[1]), []).append(e)
    st = Counter()
    for doc in docs:
        cats = [c for c in doc.get("categories") or [] if c in KEYS and c in worlds]
        if not cats or doc.get("decision") != "fetch":
            continue
        rec = latest.get(doc["norm_url"])
        if rec is None:
            st["spec_docs_not_fetched"] += 1
            continue
        for cat in cats:
            res = parsed(d, rec["snapshot"], cat, fp)
            if res is None:
                st["spec_docs_not_extracted"] += 1
                continue
            st[f"spec_docs_parsed:{cat}"] += 1
            if not res["facts"]:
                continue
            text, w = res["text"], worlds[cat]
            linked = [x for x in doc["found_on"] if x.get("category") == cat and x.get("source_id")]
            local = {id(e) for x in linked for e in by_obs.get((cat, x["source_id"], x["ref"]), [])}
            for _, e, fs in DA.edges_of(doc, [cat], by_obs).values():
                mine = named(e, text)
                ob = (SOURCE_ID, doc["norm_url"], rec["snapshot"])
                if not mine:
                    st["spec_proposal_model_not_named"] += 1
                    continue
                others = sorted({v for o in w.ents if id(o) not in local and o.brand == e.brand
                                 for v in named(o, text) if not any(v in m or m in v for m in mine)})
                if others:
                    events.append(("document_proposal", cat, e, w.anchors(e.keys), ob, {"reason": "multi_model_other_page", "url": doc["url"], "others": others[:8]}))
                    st["spec_proposal_multi_model"] += 1
                    continue
                facts = [x for x in res["facts"] if x["key"] in KEYS[cat] and not subsumed(e, x)]
                if not facts:
                    continue
                edges = 0
                for f in fs:            # review 6 fix 3: one source entry, claim and documents[] entry per verified linking edge
                    if not DA.edge_verified(e, f):
                        st["spec_edges_unverified"] += 1
                        continue
                    edges += 1
                    DA.add_document(e, doc, f["page_url"])
                    for x in facts:
                        c = claim(x, doc["kind"], doc["url"])
                        page = c["locator"]["pdf_page"]
                        snap = DA.edge_source(e, doc, rec, page, f["page_url"])
                        c["locator"]["linked_from"] = f["page_url"]
                        c["observed_at"] = rec.get("fetched_at") or "1970-01-01T00:00:00Z"
                        e.claims.append((c, (SOURCE_ID, doc["norm_url"], snap)))
                        st[f"claims:{cat}:{c['key']}"] += 1
                if not edges:
                    continue
                e.obs.add(ob)
                events.append(("document_attach", cat, e, w.anchors(e.keys), ob, {"url": doc["url"], "identifiers": mine, "claims": len(facts), "edges": edges,
                                                                                 "transform": TRANSFORM}))
                st["spec_attached"] += 1
    for k, v in st.items():
        stats[k] = stats.get(k, 0) + v
    return st
