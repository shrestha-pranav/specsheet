"""Document claims -> entities (A3 document pipeline, 2026-11-24). Called by scripts/import.py after every source is ingested (entities and
their page observations exist), before ids are minted. Transform `docattach@1`, pinned like a parser (fingerprint = this file +
crawler/adapters/_docparse.py + the page parsers it reuses).

Inputs (all derived from raw/, nothing from the network): raw/_documents/discovery.json (document -> the pages it was found on),
raw/_documents/snapshots.jsonl + text/<sha>.json (crawler/documents.py). Parse results are cached in raw/_documents/parsed/<sha>.json
keyed by the transform fingerprint (a parser edit is a cache miss).

Identity (brief item 5): a document attaches ONLY to an entity observed on a page the document was linked from, and only when the
document's own text names one of that entity's identifiers exactly (mfr_model / mfr_sku, bounded: 'A2667' never matches 'A26671').
If the document also names other models of the same brand in this category it is a multi-model document: a claim attaches only when
the text block it was read from names this entity's identifier (an explicit model row). Everything else is an identity_events row
`document_proposal` (reason model_not_named | multi_model_no_row), never a claim.

Claims (brief item 4): kind official, source = the document URL + '#page=N' (one source entry per document page, carrying the linking page
URL for the source policy's document_host inheritance), conditions {document_kind, ocr?, ocr_conf?} (provenance conditions: resolve.py
does not group on them), locator {pdf_page, document}, quote = the literal row. Extractor docparse@1 (text layer) / docparse-ocr@1 (OCR;
never in an auto-accept policy). Affirmative only: pd.pps / pd.epr are only ever True; nothing is emitted from silence.
Port attribution: a document port row ('USB-C1 / USB-C2 : ...', single-port section or a sectionless table) is mapped onto the linking
page's own out.ports rows by port token (C1, C2, A ...): every token must land on exactly one page row and every page row it lands on must
be fully covered, else the row is not attributable. The out.ports claim carries only the attributed rows, with the page's row names;
resolve.py completes the page's rows from it when they are compatible and keeps a real disagreement visible as a conflict. A PDO line
that names no port sets device-level keys only.
"""
import hashlib, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "crawler"))
import _contract as C  # noqa: E402
import _docparse as X  # noqa: E402
import _powerbank as P  # noqa: E402

TRANSFORM = "docattach@1"
SOURCE_ID = "documents"
EXTRACTOR, EXTRACTOR_OCR = f"{X.NAME}@{X.VERSION}", f"{X.NAME}-ocr@{X.VERSION}"
CATEGORIES = {"chargers": "charger", "power-banks": "power_bank"}      # document parsers in this round (others: report 'next')
MIN_OCR_CONF = 60.0
DOC_DIR = C.ROOT / "raw" / "_documents"
KEYS = {"chargers": {"pd.pps", "pd.pps_max_voltage", "pd.pps_max_current_a", "pd.max_fixed_voltage", "pd.epr", "out.ports"},
        "power-banks": {"pd.pps", "pd.max_fixed_voltage", "out.ports"}}


def fingerprint():
    h = hashlib.sha256()
    for p in (Path(__file__), CODE / "crawler/adapters/_docparse.py", CODE / "crawler/adapters/_powerbank.py", CODE / "crawler/adapters/_charger.py"):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()[:20]


def _load_docs(root=None):
    d = Path(root or DOC_DIR)
    disc = json.loads((d / "discovery.json").read_text()) if (d / "discovery.json").exists() else {"docs": []}
    latest = {}
    if (d / "snapshots.jsonl").exists():
        for l in (d / "snapshots.jsonl").read_text().splitlines():
            r = json.loads(l)
            if r.get("status") == 200 and r.get("blob"):
                latest[r["ref"]] = r
    return disc["docs"], latest, d


def parsed(d, sha, fp):
    """Cached _docparse result for one document text (raw/_documents/parsed/<sha>.json); None when the text is not extracted."""
    h = sha.split(":", 1)[-1]
    cp = d / "parsed" / f"{h}.json"
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
    res = {"power": X.power_output(doc), "text": X.full_text(doc), "blocks": {p["n"]: [" | ".join(b["lines"]) for b in p.get("blocks") or []] for p in doc["pages"]},
           "pages": len(doc["pages"]), "ocr_pages": sum(1 for p in doc["pages"] if p["method"] == "ocr")}
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp"); tmp.write_text(json.dumps({"fingerprint": fp, "result": res})); tmp.replace(cp)
    return res


def ident_values(e):
    return sorted({str(v["value_raw"] or v["value"]) for (scheme, _), v in e.idents.items() if scheme in ("mfr_model", "mfr_sku") and v["valid"]}
                  | {str(v["value"]) for (scheme, _), v in e.idents.items() if scheme in ("mfr_model", "mfr_sku") and v["valid"]}, key=str)


def page_ports(e):
    """The linking page's own out.ports rows (latest official page claim): [(name, tokens, row)]."""
    rows = None
    for c, ob in e.claims:
        if c.get("key") == "out.ports" and c.get("status") == "known" and ob[0] != SOURCE_ID and isinstance(c.get("value"), list):
            rows = c["value"]
    if not rows:
        return None
    return [(r.get("name"), [t for t in P.port_tokens(r.get("name") or "") if t], r) for r in rows if isinstance(r, dict)]


def map_ports(doc_rows, pports):
    """-> ({page row name: doc row}, unattributable doc rows). Exact token cover only."""
    out, bad = {}, []
    for r in doc_rows:
        hits, ok = {}, True
        for t in r["tokens"]:
            cand = [p for p in pports if t in p[1]]
            if len(cand) != 1 and re.fullmatch(r"[AC]", t):                     # unnumbered 'USB-C' on the doc: only if the page has one such port
                typ = "usb_c" if t == "C" else "usb_a"
                cand = [p for p in pports if (p[2].get("type") == typ)]
            if len(cand) != 1:
                ok = False; break
            hits.setdefault(cand[0][0], set()).add(t)
        if ok:
            for name, toks in hits.items():
                need = next(p[1] for p in pports if p[0] == name)
                if need and not set(need) <= toks and not (len(need) == 1 and re.fullmatch(r"[AC]", next(iter(toks)))):
                    ok = False
        if not ok or not hits:
            bad.append(r); continue
        for name in hits:
            if name in out and (out[name]["fixed_pdos"], out[name]["pps"], out[name]["max_w"]) != (r["fixed_pdos"], r["pps"], r["max_w"]):
                bad.append(r); out.pop(name); break
            out[name] = r
    return out, bad


def _claim(key, value, raw, quote, page, ocr, conf, dkind, url):
    cond = {"document_kind": dkind}
    if ocr:
        cond.update(ocr=True, ocr_conf=conf)
    return {"key": key, "status": "known", "kind": "official", "value": value, "unit": None, "raw": (raw or "")[:300], "quote": (quote or "")[:300],
            "conditions": cond, "locator": {"pdf_page": page, "document": url},
            "method": {"stage": "ocr" if ocr else "pdf_text", "extractor": EXTRACTOR_OCR if ocr else EXTRACTOR}, "review": {"state": "candidate"}}


def claims_for(cat, res, dkind, url, pports, allowed_page=None):
    """Pure: one parsed document -> [(claim, page)] for one category; allowed_page(page, quote) filters multi-model docs."""
    pw = res["power"]
    ok = lambda r: (not r.get("ocr") or (r.get("ocr_conf") or 0) >= MIN_OCR_CONF) and (allowed_page is None or allowed_page(r["page"], r.get("block") or r.get("quote") or ""))
    out = []
    dev = [d for d in pw["device"] if ok(d) and d.get("ctx") in ("port", "out")]
    single = [d for d in dev if d["mode"] != "multi"]
    pps_rows = [d for d in dev if d["pps"]]
    named = [n for n in pw["pps_named"] if ok(n)]
    first = (pps_rows or named or [None])[0]
    if first:
        out.append(_claim("pd.pps", True, first["quote"], "the document prints a PPS range for an output" if pps_rows else "the document states PPS support",
                          first["page"], first.get("ocr"), first.get("ocr_conf"), dkind, url))
    rng = []
    for d in single:
        for r in (d["pps"] or "").split("; "):
            m = re.match(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)V (\d+(?:\.\d+)?)A", r)
            if m:
                rng.append((float(m[2]), float(m[3]), d))
    if rng and cat == "chargers":
        hv = max(rng, key=lambda x: x[0]); hc = max(rng, key=lambda x: x[1])
        out.append(_claim("pd.pps_max_voltage", P.fnum(hv[0]), hv[2]["quote"], "highest printed PPS voltage (single-port / sectionless rows)", hv[2]["page"], hv[2].get("ocr"), hv[2].get("ocr_conf"), dkind, url))
        out.append(_claim("pd.pps_max_current_a", P.fnum(hc[1]), hc[2]["quote"], "highest printed PPS current (single-port / sectionless rows)", hc[2]["page"], hc[2].get("ocr"), hc[2].get("ocr_conf"), dkind, url))
    vm = [(d["vmax"], d) for d in single if d.get("vmax")]
    if vm:
        v, d = max(vm, key=lambda x: x[0])
        out.append(_claim("pd.max_fixed_voltage", P.fnum(v), d["quote"], "highest printed fixed PDO voltage", d["page"], d.get("ocr"), d.get("ocr_conf"), dkind, url))
        if v >= 28 and cat == "chargers":
            out.append(_claim("pd.epr", True, d["quote"], "a fixed PDO of 28 V or more is printed (USB PD EPR)", d["page"], d.get("ocr"), d.get("ocr_conf"), dkind, url))
    rows = [r for r in pw["ports"] if ok(r)]
    unattributed = 0
    if rows and pports:
        mapped, bad = map_ports(rows, pports)
        unattributed = len(bad)
        if mapped:
            by_page = defaultdict(list)
            for name, r in mapped.items():
                by_page[(r["page"], bool(r.get("ocr")), r.get("ocr_conf"))].append((name, r))
            for (page, ocr, conf), items in sorted(by_page.items(), key=lambda kv: str(kv[0])):
                prow = {p[0]: p[2] for p in pports}
                val = [{"name": n, "type": prow[n].get("type"), "direction": "out", "max_w": r["max_w"], "fixed_pdos": r["fixed_pdos"], "pps": r["pps"]}
                       for n, r in sorted(items, key=lambda x: [p[0] for p in pports].index(x[0]))]
                quote = " ; ".join(dict.fromkeys(r["quote"] for _, r in items))
                out.append(_claim("out.ports", val, quote, quote, page, ocr, conf, dkind, url))
    elif rows:
        unattributed = len(rows)
    keys = KEYS[cat]
    return [c for c in out if c["key"] in keys], unattributed


def apply(worlds, events, stats, root=None):
    """worlds: {category: World} of import.py. Attaches claims, records proposals. -> per-category counters (also into stats)."""
    docs, latest, d = _load_docs(root)
    fp = fingerprint()
    by_obs = {}
    for cat, w in worlds.items():
        if cat not in CATEGORIES:
            continue
        for e in w.ents:
            for ob in e.obs:
                by_obs.setdefault((cat, ob[0], ob[1]), []).append(e)
    st = Counter()
    for doc in docs:
        cats = [c for c in doc.get("categories") or [] if c in CATEGORIES and c in worlds]
        if not cats:
            continue
        st["docs_linked"] += 1
        if doc.get("decision") != "fetch":
            st[f"docs_skipped:{doc.get('decision')}"] += 1
            continue
        rec = latest.get(doc["norm_url"])
        if rec is None:
            st["docs_not_fetched"] += 1
            continue
        res = parsed(d, rec["snapshot"], fp)
        if res is None:
            st["docs_not_extracted"] += 1
            continue
        st["docs_parsed"] += 1
        text = res["text"]
        for f in doc["found_on"]:
            cat = f.get("category")
            if cat not in cats or not f.get("source_id"):
                continue
            w = worlds[cat]
            for e in by_obs.get((cat, f["source_id"], f["ref"]), []):
                done = e.__dict__.setdefault("_doc_done", set())
                if doc["norm_url"] in done:
                    continue
                done.add(doc["norm_url"])
                mine = [v for v in ident_values(e) if X.mentions(text, v)]
                ob = (SOURCE_ID, doc["norm_url"], rec["snapshot"])
                if not mine:
                    events.append(("document_proposal", cat, e, w.anchors(e.keys), ob, {"reason": "model_not_named", "url": doc["url"], "page": f["page_url"],
                                                                                       "identifiers": ident_values(e)[:6]}))
                    st["proposal_model_not_named"] += 1
                    continue
                others = sorted({v for o in w.ents if o is not e and o.brand == e.brand and o.kind == e.kind
                                 for v in ident_values(o) if len(v) >= 4 and v not in mine and not any(v in m or m in v for m in mine) and X.mentions(text, v)})
                allowed = None
                if others:
                    st["multi_model_docs"] += 1
                    allowed = lambda page, btxt, mine=mine: any(X.mentions(btxt, v) for v in mine)
                cs, unattr = claims_for(cat, res, doc["kind"], doc["url"], page_ports(e), allowed)
                st["port_rows_unattributable"] += unattr
                if others and not cs:
                    events.append(("document_proposal", cat, e, w.anchors(e.keys), ob, {"reason": "multi_model_no_row", "url": doc["url"], "others": others[:8]}))
                    st["proposal_multi_model"] += 1
                    continue
                e.obs.add(ob)
                e.documents.append({"url": doc["url"], "kind": doc["kind"], "label": (doc.get("link_text") or doc["kind"])[:120]})
                events.append(("document_attach", cat, e, w.anchors(e.keys), ob, {"url": doc["url"], "identifiers": mine, "claims": len(cs), "multi_model": bool(others)}))
                st["attached"] += 1
                for c in cs:
                    page = c["locator"]["pdf_page"]
                    snap = f"{rec['snapshot']}#page={page}"
                    e.srcs.setdefault(snap, {"url": f"{doc['url'].split('#')[0]}#page={page}", "tier": "manufacturer",
                                             "label": f"{doc['kind'].replace('_', ' ')} (PDF p.{page})", "snapshot": snap,
                                             "retrieved_at": rec.get("fetched_at"), "linked_from": f["page_url"]})
                    c["observed_at"] = rec.get("fetched_at") or "1970-01-01T00:00:00Z"
                    e.claims.append((c, (SOURCE_ID, doc["norm_url"], snap)))
                    st[f"claims:{cat}:{c['key']}"] += 1
    for k, v in st.items():
        stats[k] = stats.get(k, 0) + v
    return st
