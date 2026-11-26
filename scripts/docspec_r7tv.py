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

@2 (A3-fix, Codex review-9 P1-1): a count needs an independently established complete port inventory bound to the target model:
  - the entity carries exactly one distinct official hdmi.count from a non-document source (its own maker page) and it equals the highest
    port the guide states (TP fact n_ports); otherwise the stated ports are only a prefix and nothing is emitted, not even 0;
  - the guide must quote the entity's own full identifier (a series/base token such as 'QM7K' alone does not bind a size);
  - a guide that also names any other same-brand catalogued model is shared: nothing for anyone. @1 exempted models observed on the
    guide's linking pages, which transferred one model's per-port rates to every linked size; that exemption is gone.
@3 (A3-fix, Codex review-10 P1-1): the supporting hdmi.count must be trusted (accepted by an approved policy or a ledger line), never an
  unreviewed candidate: see inventory(). import.py passes trusted=import.trusted_probe(...); without it nothing is emitted.
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

TRANSFORM = "docspec-attach-tvports@3"
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


def inventory(e, trusted=None):
    """-> the one independent hdmi.count of this entity (official, known, not from a document), else None.
    @3 (review-10 P1-1): the count must itself be TRUSTED: trusted(CAT, e, claim, ob) is true only when the claim would be accepted by a
    recorded decision (an approved policy or a ledger line; import.trusted_probe). A count that is a candidate (pending / half-approved
    policy, no policy) proves nothing, and any disagreeing official count, trusted or not, voids the inventory. trusted=None -> nothing."""
    vals, ok = set(), set()
    for c, ob in e.claims:
        if c.get("key") == "hdmi.count" and c.get("status") == "known" and c.get("kind") == "official" and ob[0] != SOURCE_ID:
            try:
                v = int(float(c.get("value")))
            except (TypeError, ValueError):
                return None
            vals.add(v)
            if trusted is not None and trusted(CAT, e, c, ob):
                ok.add(v)
    return next(iter(ok)) if len(vals) == 1 and len(ok) == 1 else None


def claim(f, dkind, url, ident, exact):
    return {"key": f["key"], "status": "known", "kind": "official", "value": f["value"], "unit": None, "raw": f["raw"], "quote": f["quote"],
            "conditions": {"document_kind": dkind, "identity": "text_layer", "identity_scope": "document",
                           "identity_variant": "exact" if exact else "model_only"},
            "locator": {"pdf_page": f["page"], "document": url, "identifiers": ident},
            "method": {"stage": "pdf_text", "extractor": EXTRACTOR}, "review": {"state": "candidate"}}


def apply(worlds, events, stats, root=None, trusted=None):
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
        for _, e, fs in DA.edges_of(doc, [CAT], by_obs).values():
            own = set(DA.ident_values(e))
            mine = [v for v in DS.named(e, text) if v in own]          # the full identifier, never a base/series token
            ob = (SOURCE_ID, doc["norm_url"], rec["snapshot"])
            if not mine:
                st["r7ports_model_not_named"] += 1
                continue
            others = sorted({v for o in w.ents if o is not e and o.brand == e.brand
                             for v in DS.named(o, text) if not any(v in m or m in v for m in mine)})
            if others:
                events.append(("document_proposal", CAT, e, w.anchors(e.keys), ob, {"reason": "multi_model_shared_guide", "url": doc["url"], "others": others[:8]}))
                st["r7ports_proposal_multi_model"] += 1
                continue
            facts = [x for x in res["facts"] if x["key"] in KEYS]
            inv = inventory(e, trusted)
            if inv is None or any(x.get("n_ports") != inv for x in facts):
                st["r7ports_no_complete_inventory"] += 1
                continue
            edges = 0
            for f in fs:
                if not DA.edge_verified(e, f):
                    st["r7ports_edges_unverified"] += 1
                    continue
                edges += 1
                DA.add_document(e, doc, f["page_url"])
                for x in facts:
                    c = claim({k: v for k, v in x.items() if k != "n_ports"}, doc["kind"], doc["url"], mine, True)
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
