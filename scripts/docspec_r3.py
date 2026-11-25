"""Document claims r3 (2026-11-25): TV / router / laptop spec-sheet rows -> entities. Transform `docspec-attach-r3@1`, extractors
`docspec-tv@1`, `docspec-router@1`, `docspec-laptop@1` (crawler/adapters/_docspec_{tv,router,laptop}.py). Called by scripts/import.py right
after docspec_attach.apply (same inputs: raw/_documents/discovery.json, snapshots.jsonl, text/<sha>.json; nothing from the network).

Why a separate transform and not a hook inside docspec_attach.py: docspec-attach@2 is fingerprint-pinned by the approved
claim/document-spec-r2@2 (its fingerprint hashes docspec_attach.py itself), so any edit there drifts that policy under --strict-parsers and
would need a reissue (pending) that withholds today's accepted SSD/monitor claims until approval. This module reuses its helpers unchanged.

Identity (review 6 rules, same as docspec-attach@2): a document attaches only along a verified linking edge (DA.edges_of / edge_verified:
the page URL equals the entity's own observation), only when the document text quotes one of that entity's own mfr_model / mfr_sku (or its
6+ char base SKU, DS.named), and never when it also names an identifier of a same-brand catalogued entity that is NOT observed on any of its
linking pages (multi_model_other_page; no sibling bypass). The quoted identifiers ride on every claim as locator.identifiers; conditions carry the docattach@2 identity trust
(text_layer, document scope, exact or model_only when only the base SKU is printed). Facts are
single spanning cells (per-size / per-column cells are never read, see _docspec_tv), so they hold for every model the document names.
Affirmative only; text layer only.
"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import _docspec_tv as TV  # noqa: E402
import _docspec_router as RT  # noqa: E402
import _docspec_laptop as LP  # noqa: E402
import docattach as DA  # noqa: E402
import docspec_attach as DS  # noqa: E402

TRANSFORM = "docspec-attach-r3@1"
SOURCE_ID = DA.SOURCE_ID
KEYS = {
    "tvs": {"hdmi.count", "hdmi.earc", "hdmi.has_4k120", "hdmi.ports_4k120", "refresh.native_hz", "panel.backlight", "panel.lcd_type",
            "vrr.supported"},
    "routers": {"wifi.generation", "wifi.band_count", "wifi.has_6ghz", "port.lan_count", "port.wan_speed_mbps"},
    "laptops": {"mem.soldered", "mem.slots", "mem.max", "pwr.max_pd_in"},
}
PARSERS = {"tvs": (TV, TV.tv), "routers": (RT, RT.router), "laptops": (LP, LP.laptop)}


def extractor(cat):
    m = PARSERS[cat][0]
    return f"{m.NAME}@{m.VERSION}"


def fingerprint():
    h = hashlib.sha256()
    for p in (Path(__file__), CODE / "crawler/adapters/_docspec_tv.py", CODE / "crawler/adapters/_docspec_router.py",
              CODE / "crawler/adapters/_docspec_laptop.py", CODE / "scripts/docspec_attach.py", CODE / "scripts/docattach.py"):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()[:20]


def parsed(d, sha, cat, fp):
    h = sha.split(":", 1)[-1]
    cp = d / "parsed-spec" / f"{h}.r3.{cat}.json"
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
    res = {"facts": PARSERS[cat][1](doc), "text": "\n".join(p.get("text", "") for p in doc["pages"] if p.get("method") == "text_layer")}
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp"); tmp.write_text(json.dumps({"fingerprint": fp, "result": res})); tmp.replace(cp)
    return res


def claim(f, cat, dkind, url, ident, exact):
    return {"key": f["key"], "status": "known", "kind": "official", "value": f["value"], "unit": None, "raw": f["raw"], "quote": f["quote"],
            "conditions": {"document_kind": dkind, "identity": "text_layer", "identity_scope": "document",
                           "identity_variant": "exact" if exact else "model_only"},
            "locator": {"pdf_page": f["page"], "document": url, "identifiers": ident},
            "method": {"stage": "pdf_text", "extractor": extractor(cat)}, "review": {"state": "candidate"}}


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
            st["r3_docs_not_fetched"] += 1
            continue
        for cat in cats:
            res = parsed(d, rec["snapshot"], cat, fp)
            if res is None:
                st["r3_docs_not_extracted"] += 1
                continue
            st[f"r3_docs_parsed:{cat}"] += 1
            if not res["facts"]:
                continue
            text, w = res["text"], worlds[cat]
            linked = [x for x in doc["found_on"] if x.get("category") == cat and x.get("source_id")]
            local = {id(e) for x in linked for e in by_obs.get((cat, x["source_id"], x["ref"]), [])}
            for _, e, fs in DA.edges_of(doc, [cat], by_obs).values():
                mine = DS.named(e, text)
                ob = (SOURCE_ID, doc["norm_url"], rec["snapshot"])
                if not mine:
                    st["r3_proposal_model_not_named"] += 1
                    continue
                others = sorted({v for o in w.ents if id(o) not in local and o.brand == e.brand
                                 for v in DS.named(o, text) if not any(v in m or m in v for m in mine)})
                if others:
                    events.append(("document_proposal", cat, e, w.anchors(e.keys), ob, {"reason": "multi_model_other_page", "url": doc["url"], "others": others[:8]}))
                    st["r3_proposal_multi_model"] += 1
                    continue
                facts = [x for x in res["facts"] if x["key"] in KEYS[cat]]
                if not facts:
                    continue
                edges = 0
                for f in fs:
                    if not DA.edge_verified(e, f):
                        st["r3_edges_unverified"] += 1
                        continue
                    edges += 1
                    DA.add_document(e, doc, f["page_url"])
                    for x in facts:
                        c = claim(x, cat, doc["kind"], doc["url"], mine, bool(set(mine) & set(DA.ident_values(e))))
                        snap = DA.edge_source(e, doc, rec, c["locator"]["pdf_page"], f["page_url"])
                        c["locator"]["linked_from"] = f["page_url"]
                        c["observed_at"] = rec.get("fetched_at") or "1970-01-01T00:00:00Z"
                        e.claims.append((c, (SOURCE_ID, doc["norm_url"], snap)))
                        st[f"r3_claims:{cat}:{c['key']}"] += 1
                if not edges:
                    continue
                e.obs.add(ob)
                events.append(("document_attach", cat, e, w.anchors(e.keys), ob, {"url": doc["url"], "identifiers": mine, "claims": len(facts),
                                                                                 "edges": edges, "transform": TRANSFORM}))
                st["r3_attached"] += 1
    for k, v in st.items():
        stats[k] = stats.get(k, 0) + v
    return st
