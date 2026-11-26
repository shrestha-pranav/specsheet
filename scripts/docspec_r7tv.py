"""Document claims r7 (2026-11-26, A2-st): TV per-port HDMI rates from maker quick start guides -> entities. Transform
`docspec-attach-tvports@1`, extractor `docspec-tv-ports@1` (crawler/adapters/_docspec_tvports.py). Called by scripts/import.py right after
docspec_r3.apply (same inputs: raw/_documents/discovery.json, snapshots.jsonl, text/<sha>.json; nothing from the network).

Why a separate transform: docspec-attach-r3@2 is fingerprint-pinned by the approved claim/document-spec-r3@2 (its fingerprint hashes
_docspec_tv.py and docspec_r3.py), so adding a reader there would drift that policy and withhold today's TV / router / laptop document claims
behind a reissue. This module reuses the docattach / docspec_attach helpers unchanged.

Identity = the docspec-attach-r3@2 TV rule, unchanged: a document attaches only along a verified linking edge (DA.edges_of / edge_verified:
the page URL equals the entity's own observation), only when the document's text layer quotes one of that entity's own mfr_model / mfr_sku
(DS.named), and never when it also names an identifier of a same-brand catalogued entity that is NOT observed on any of its linking pages
(multi_model_other_page). A size-range guide whose text names no model (TCL '50-85QM7K' guides print the range only as artwork) attaches
nothing. Keys: hdmi.ports_4k120 and hdmi.has_4k120 only. Affirmative only; text layer only.
"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import _docspec_tvports as TP  # noqa: E402
import docattach as DA  # noqa: E402
import docspec_attach as DS  # noqa: E402

TRANSFORM = "docspec-attach-tvports@1"
SOURCE_ID = DA.SOURCE_ID
CAT = "tvs"
KEYS = {"hdmi.ports_4k120", "hdmi.has_4k120"}
EXTRACTOR = f"{TP.NAME}@{TP.VERSION}"


def fingerprint():
    h = hashlib.sha256()
    for p in (Path(__file__), CODE / "crawler/adapters/_docspec_tvports.py", CODE / "scripts/docspec_attach.py", CODE / "scripts/docattach.py"):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()[:20]


def parsed(d, sha, fp):
    h = sha.split(":", 1)[-1]
    cp = d / "parsed-spec" / f"{h}.r7ports.{CAT}.json"
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
    res = {"facts": TP.tv(doc), "text": "\n".join(p.get("text", "") for p in doc["pages"] if p.get("method") == "text_layer")}
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp"); tmp.write_text(json.dumps({"fingerprint": fp, "result": res})); tmp.replace(cp)
    return res


def claim(f, dkind, url, ident, exact):
    return {"key": f["key"], "status": "known", "kind": "official", "value": f["value"], "unit": None, "raw": f["raw"], "quote": f["quote"],
            "conditions": {"document_kind": dkind, "identity": "text_layer", "identity_scope": "document",
                           "identity_variant": "exact" if exact else "model_only"},
            "locator": {"pdf_page": f["page"], "document": url, "identifiers": ident},
            "method": {"stage": "pdf_text", "extractor": EXTRACTOR}, "review": {"state": "candidate"}}


def apply(worlds, events, stats, root=None):
    if CAT not in worlds:
        return Counter()
    docs, latest, d = DA._load_docs(root)
    fp = fingerprint()
    w = worlds[CAT]
    by_obs = {}
    for e in w.ents:
        for ob in e.obs:
            by_obs.setdefault((CAT, ob[0], ob[1]), []).append(e)
    st = Counter()
    for doc in docs:
        if CAT not in (doc.get("categories") or []) or doc.get("decision") != "fetch":
            continue
        rec = latest.get(doc["norm_url"])
        if rec is None:
            continue
        res = parsed(d, rec["snapshot"], fp)
        if res is None or not res["facts"]:
            continue
        st["r7ports_docs_with_facts"] += 1
        text = res["text"]
        linked = [x for x in doc["found_on"] if x.get("category") == CAT and x.get("source_id")]
        local = {id(e) for x in linked for e in by_obs.get((CAT, x["source_id"], x["ref"]), [])}
        for _, e, fs in DA.edges_of(doc, [CAT], by_obs).values():
            mine = DS.named(e, text)
            ob = (SOURCE_ID, doc["norm_url"], rec["snapshot"])
            if not mine:
                st["r7ports_model_not_named"] += 1
                continue
            others = sorted({v for o in w.ents if id(o) not in local and o.brand == e.brand
                             for v in DS.named(o, text) if not any(v in m or m in v for m in mine)})
            if others:
                events.append(("document_proposal", CAT, e, w.anchors(e.keys), ob, {"reason": "multi_model_other_page", "url": doc["url"], "others": others[:8]}))
                st["r7ports_proposal_multi_model"] += 1
                continue
            facts = [x for x in res["facts"] if x["key"] in KEYS]
            edges = 0
            for f in fs:
                if not DA.edge_verified(e, f):
                    st["r7ports_edges_unverified"] += 1
                    continue
                edges += 1
                DA.add_document(e, doc, f["page_url"])
                for x in facts:
                    c = claim(x, doc["kind"], doc["url"], mine, bool(set(mine) & set(DA.ident_values(e))))
                    snap = DA.edge_source(e, doc, rec, c["locator"]["pdf_page"], f["page_url"])
                    c["locator"]["linked_from"] = f["page_url"]
                    c["observed_at"] = rec.get("fetched_at") or "1970-01-01T00:00:00Z"
                    e.claims.append((c, (SOURCE_ID, doc["norm_url"], snap)))
                    st[f"r7ports_claims:{c['key']}"] += 1
            if not edges:
                continue
            e.obs.add(ob)
            events.append(("document_attach", CAT, e, w.anchors(e.keys), ob, {"url": doc["url"], "identifiers": mine, "claims": len(facts),
                                                                             "edges": edges, "transform": TRANSFORM}))
            st["r7ports_attached"] += 1
    for k, v in st.items():
        stats[k] = stats.get(k, 0) + v
    return st
