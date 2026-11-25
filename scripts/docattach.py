"""Document claims -> entities (A3 document pipeline, 2026-11-24; review 6 fixes 2026-11-25). Called by scripts/import.py after every source is
ingested (entities and their page observations exist), before ids are minted. Transform `docattach@2`, pinned like a parser (fingerprint =
this file + crawler/adapters/_docparse.py + the page parsers it reuses).

Inputs (all derived from raw/, nothing from the network): raw/_documents/discovery.json (document -> the pages it was found on),
raw/_documents/snapshots.jsonl + text/<sha>.json + ocr/<sha>.json (word-level OCR confidences, crawler/documents.py ocr-tokens). Parse
results are cached in raw/_documents/parsed/<sha>.json keyed by the transform fingerprint (a parser edit is a cache miss).

Identity (review 6 fix 1). A document is considered only for an entity observed on a page the document was linked from. Evidence = an
exact, bounded mention of one of the entity's own mfr_model / mfr_sku ('A2667' never matches 'A26671'; an identifier of 3 characters or
fewer only counts after a model label, 'Model: P2', never inside 'USB-C3'). A mention on an OCR page counts only when every word carrying
it has token confidence >= MIN_OCR_CONF (the page mean never vouches for a token); a low-confidence-only mention is a document_proposal
(identity_low_confidence). Siblings = other models the document names: catalogued same-brand entities of the category outside this
entity's own configuration/package lineage (substring-related identifiers included), plus UNCATALOGUED ones (a model-like token with the
same shape as an own identifier, or any token after a model label). Scope of a claim row: with no sibling, the document; otherwise the
row's own block, then its page, must name this entity and no sibling (a block or page naming two models scopes nothing). Variant/region:
the scope is 'exact' only when no other SKU of the same base model (text or file name), no foreign region token in the file name and no
other entity sharing the matched identifier is in play, or the scope names an own SKU itself; otherwise the claim stays a candidate
(extractor docparse-review@2). Identity trust is carried into the claim conditions {identity, identity_scope, identity_variant}
(provenance, resolve.py PROVENANCE): a claim whose identity rests on OCR evidence is OCR-dependent (extractor docparse-ocr@2, candidate)
even when its rows are text layer.

Claims: kind official, source = the document URL + '#page=N', one source entry PER LINKING EDGE (document URL x snapshot x page x the
verified linking page, review 6 fix 3): identical bytes at two URLs, or one document linked from an allowed and a withheld page, keep
their own source entries, claims (locator.linked_from) and documents[] entries ({url, kind, label, linked_from}). An edge whose
discovery page URL is not the URL of the entity's own observation of that page is unverified and attaches nothing. Conditions
{document_kind, ocr?, ocr_conf? (lowest token confidence of the row), identity*}; locator {pdf_page, document, linked_from}; quote = the
literal row. Extractor docparse@2 (text layer, text-layer identity, exact variant scope) / docparse-ocr@2 / docparse-review@2 (never in
an auto-accept policy). Affirmative only: pd.pps / pd.epr are only ever True; nothing is emitted from silence.
Port attribution (review 6 fix 2): a document port row is mapped onto the out.ports rows of the LINKING page's own official claim (the
observation the edge came from; two different layouts on that observation = no port map) by port token: every token must land on exactly
one page row and every page row it lands on must be fully covered. When the entity's pages disagree on the port layout, only rows read
under an explicit single-port heading are attributed. Combination context is document scope in docparse@2 (see _docparse). The
out.ports claim carries only the attributed rows, with the page's row names; resolve.py completes the page's rows from it when
compatible and keeps a real disagreement visible as a conflict. A PDO line that names no port sets device-level keys only.
"""
import hashlib, json, re, sys, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "crawler"))
import _contract as C  # noqa: E402
import _docparse as X  # noqa: E402
import _powerbank as P  # noqa: E402

TRANSFORM = "docattach@2"
SOURCE_ID = "documents"
EXTRACTOR, EXTRACTOR_OCR, EXTRACTOR_REVIEW = f"{X.NAME}@{X.VERSION}", f"{X.NAME}-ocr@{X.VERSION}", f"{X.NAME}-review@{X.VERSION}"
CATEGORIES = {"chargers": "charger", "power-banks": "power_bank"}      # document parsers in this round (others: report 'next')
MIN_OCR_CONF = 60.0
DOC_DIR = C.ROOT / "raw" / "_documents"
KEYS = {"chargers": {"pd.pps", "pd.pps_max_voltage", "pd.pps_max_current_a", "pd.max_fixed_voltage", "pd.epr", "out.ports"},
        "power-banks": {"pd.pps", "pd.max_fixed_voltage", "out.ports"}}
LINEAGE = ("configuration_of", "package_of", "variant_of")
MODEL_LABEL = r"(?:\b(?:model|modell|mod[eè]le|modelo|modello|型番|型号|产品型号|model\s*number|product\s*(?:number|no\.?|model)|item\s*(?:number|no\.?)))"
LABELED = re.compile(MODEL_LABEL + r"\s*(?:number|no\.?)?[\s|:：#.]*(?:[A-Z0-9]{1,4}-)?([A-Z0-9][A-Z0-9-]{0,24}[A-Z0-9])(?![A-Z0-9])", re.I)
LABEL_VALUE = re.compile(MODEL_LABEL + r"\s*(?:number|no\.?)?[\s|:：#.]*([A-Z0-9][A-Z0-9-]{0,24}[A-Z0-9])(?![A-Z0-9])", re.I)
REGION_TOKENS = {"US", "UK", "EU", "AU", "JP", "CN", "KR", "IN", "UKEU"}


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


def with_tokens(doc, side):
    """Attach the OCR token sidecar (crawler/documents.py ocr-tokens) to the OCR pages whose text it reproduces exactly."""
    pages = (side or {}).get("pages") or {}
    for p in doc.get("pages") or []:
        t = pages.get(str(p["n"]))
        if p.get("method") == "ocr" and t and t.get("text") == p.get("text", ""):
            p["tokens"] = t["lines"]
    return doc


def _id_pages(doc):
    """Identity view of a document: per page its method and blocks; an OCR page = one block whose lines keep their words + confidences."""
    out = []
    for p in doc["pages"]:
        if p.get("method") == "ocr":
            raw = p.get("text", "").split("\n")
            tok = p.get("tokens") if p.get("tokens") is not None and len(p["tokens"]) == len(raw) else None
            out.append({"n": p["n"], "method": "ocr", "blocks": [p.get("text", "")], "lines": [[l, tok[i] if tok else None] for i, l in enumerate(raw) if l.strip()]})
        else:
            out.append({"n": p["n"], "method": p.get("method"), "blocks": [" | ".join(b["lines"]) for b in p.get("blocks") or []] or [p.get("text", "")]})
    return out


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
    sp = d / "ocr" / f"{h}.json"
    doc = with_tokens(json.loads(tp.read_text()), json.loads(sp.read_text()) if sp.exists() else None)
    res = {"power": X.power_output(doc), "text": X.full_text(doc), "id_pages": _id_pages(doc),
           "pages": len(doc["pages"]), "ocr_pages": sum(1 for p in doc["pages"] if p["method"] == "ocr")}
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp"); tmp.write_text(json.dumps({"fingerprint": fp, "result": res})); tmp.replace(cp)
    return res


def ident_values(e):
    return sorted({str(v["value_raw"] or v["value"]) for (scheme, _), v in e.idents.items() if scheme in ("mfr_model", "mfr_sku") and v["valid"]}
                  | {str(v["value"]) for (scheme, _), v in e.idents.items() if scheme in ("mfr_model", "mfr_sku") and v["valid"]}, key=str)


def sku_values(e):
    return {str(v["value"]).upper() for (scheme, _), v in e.idents.items() if scheme == "mfr_sku" and v["valid"]} | \
           {str(v["value_raw"]).upper() for (scheme, _), v in e.idents.items() if scheme == "mfr_sku" and v["valid"] and v["value_raw"]}


def model_values(e):
    return {str(v["value"]).upper() for (scheme, _), v in e.idents.items() if scheme == "mfr_model" and v["valid"]}


# ---------------------------------------------------------------------------------------------------------------- identity evidence
def _shape(v):
    m = re.fullmatch(r"([A-Z]+)(\d+)([A-Z0-9]*)", v.upper())
    return (m[1], len(v)) if m else None


def mention(text, v):
    """Bounded mention; a short identifier (<= 3 chars) only after a model label."""
    if len(str(v)) <= 3:
        return any(m[1].upper() == str(v).upper() or m[1].upper().endswith("-" + str(v).upper()) for m in LABELED.finditer(text))
    return X.mentions(text, v)


def _ocr_hit(line_words, v):
    """Every OCR word carrying identifier v must be confident (None = no token evidence = uncertain)."""
    if line_words is None:
        return False
    ws = [(w, c) for w, c in line_words if v.upper() in w.upper() or (len(v) > 3 and w.upper() in v.upper() and len(w) >= 2)]
    return bool(ws) and all(c >= MIN_OCR_CONF for _, c in ws)


def hits(res, values):
    """-> [(page, block index, 'text' | 'ocr' | 'ocr_low', value)] for every mention of one of `values`."""
    out = []
    for p in res["id_pages"]:
        for bi, b in enumerate(p["blocks"]):
            for v in values:
                if not mention(b, v):
                    continue
                if p["method"] != "ocr":
                    out.append((p["n"], bi, "text", v))
                    continue
                lines = [lw for l, lw in p["lines"] if mention(l, v)]
                ok = bool(lines) and any(_ocr_hit(lw, v) for lw in lines)
                out.append((p["n"], bi, "ocr" if ok else "ocr_low", v))
    return out


def lineage(e):
    """e plus every entity connected to it by configuration/package/variant relations (either direction, transitively)."""
    return e.__dict__.get("_lineage") or {id(e)}


def _compute_lineage(ents):
    adj = defaultdict(set)
    for e in ents:
        for r in e.rels:
            if r[0] in LINEAGE:
                adj[id(e)].add(id(r[1])); adj[id(r[1])].add(id(e))
    for e in ents:
        seen, todo = {id(e)}, [id(e)]
        while todo:
            for n in adj[todo.pop()] - seen:
                seen.add(n); todo.append(n)
        e._lineage = seen


def file_tokens(url):
    base = urllib.parse.unquote(str(url).split("?")[0].split("#")[0].rsplit("/", 1)[-1]).upper()
    return [t for t in re.split(r"[^A-Z0-9]+", base) if t]


def identity(e, w, res, url):
    """Identity evidence of one entity for one document. -> dict(mine, siblings, variants, shared, region, low)."""
    own = ident_values(e)
    ownu = {v.upper() for v in own}
    h = hits(res, own)
    good = [x for x in h if x[2] != "ocr_low"]
    lin = lineage(e)
    text = res["text"]
    cat_others = sorted({v for o in w.ents if id(o) not in lin and o.brand == e.brand
                         for v in ident_values(o) if len(v) >= 4 and v.upper() not in ownu and X.mentions(text, v)})
    labeled = {m[1].upper() for m in LABEL_VALUE.finditer(text)}
    toks = set(X.MODEL_TOKEN.findall(text.upper())) | labeled
    ftoks = set(file_tokens(url))
    shapes = {_shape(v) for v in own} - {None}
    bases = {b for b in model_values(e) | {v.upper() for v in own if not any(v.upper() != o and v.upper().startswith(o) for o in ownu)} if len(b) >= 4}
    uncat, variants = set(), set()
    for t in toks | ftoks:
        if t in ownu or (len(t) >= 4 and any(o.startswith(t) for o in ownu)) or any(o in t.split("-") for o in ownu):
            continue                                   # an own identifier, the base model of an own SKU, or an own id with a label prefix ('BI-B43')
        if any(t.startswith(b) and len(t) > len(b) for b in bases):
            variants.add(t)                            # another SKU of an own base model (regional / colour / bundle variant)
            continue
        if t not in toks:
            continue                                   # file-name tokens only ever reveal variants, not sibling models
        if _shape(t) in shapes or (t in labeled and re.search(r"\d", t) and re.search(r"[A-Z]", t)):
            uncat.add(t)
    uncat -= {v.upper() for v in cat_others}
    region = sorted({t for t in file_tokens(url) if t in REGION_TOKENS} - {"US"})
    shared = sorted({v for o in w.ents if id(o) not in lin for v in ident_values(o) if v.upper() in {x[3].upper() for x in good}})
    return {"hits": good, "low": [x for x in h if x[2] == "ocr_low"], "mine": sorted({x[3] for x in good}),
            "siblings": sorted(set(cat_others) | uncat), "catalogued": cat_others, "uncatalogued": sorted(uncat), "variants": sorted(variants),
            "region": region, "shared": shared, "skus": sku_values(e)}


def scope_of(idn, res, page, block_text):
    """Identity scope of one claim row -> None (not scoped to this entity) or {identity, identity_scope, identity_variant}."""
    sib = idn["siblings"]
    hs = idn["hits"]
    names = lambda t: [v for v in idn["mine"] if mention(t, v)]
    names_sib = lambda t: any(mention(t, v) for v in sib)
    pg = next((p for p in res["id_pages"] if p["n"] == page), None)
    used, scope = [], None
    if block_text and names_sib(block_text):
        return None                                    # the row's own block names another model (two models in one block)
    if block_text and names(block_text):
        used, scope = [x for x in hs if x[0] == page and x[3] in names(block_text)], "block"
    if not used and pg is not None:
        ptxt = "\n".join(pg["blocks"])
        if names_sib(ptxt):
            return None
        if names(ptxt):
            used, scope = [x for x in hs if x[0] == page], "page"
    if not used and not sib:
        used, scope = hs, "document"
    if not used:
        return None
    trust = "text_layer" if any(x[2] == "text" for x in used) else "ocr"
    exact_named = any(x[3].upper() in idn["skus"] and x[3].upper() not in {s.upper() for s in idn["shared"]} for x in used)
    clean = not idn["variants"] and not idn["region"] and not idn["shared"]
    return {"identity": trust, "identity_scope": scope, "identity_variant": "exact" if (clean or exact_named) else "model_only"}


# ---------------------------------------------------------------------------------------------------------------- port attribution
def _layout(rows):
    return tuple(sorted((tuple(t for t in P.port_tokens(r.get("name") or "") if t), r.get("type")) for r in rows if isinstance(r, dict)))


def page_ports(e, edge=None):
    """The linking page's own out.ports rows: the official out.ports claim of the observation the edge came from (edge = (source_id, ref)).
    -> ([(name, tokens, row)] | None, layouts_disagree)."""
    vals, layouts = [], set()
    for c, ob in e.claims:
        if c.get("key") != "out.ports" or c.get("status") != "known" or ob[0] == SOURCE_ID or (c.get("kind") or "official") != "official" \
                or not isinstance(c.get("value"), list):
            continue
        layouts.add(_layout(c["value"]))
        if edge is None or (ob[0], str(ob[1])) == (edge[0], str(edge[1])):
            vals.append(c["value"])
    canon = {json.dumps(v, sort_keys=True) for v in vals}
    if len(canon) != 1:
        return None, len(layouts) > 1
    rows = vals[0]
    return [(r.get("name"), [t for t in P.port_tokens(r.get("name") or "") if t], r) for r in rows if isinstance(r, dict)], len(layouts) > 1


def map_ports(doc_rows, pports):
    """-> ({page row name: doc row}, unattributable doc rows). Exact token cover only."""
    out, bad = {}, []
    for r in doc_rows:
        hits_, ok = {}, True
        for t in r["tokens"]:
            cand = [p for p in pports if t in p[1]]
            if len(cand) != 1 and re.fullmatch(r"[AC]", t):                     # unnumbered 'USB-C' on the doc: only if the page has one such port
                typ = "usb_c" if t == "C" else "usb_a"
                cand = [p for p in pports if (p[2].get("type") == typ)]
            if len(cand) != 1:
                ok = False; break
            hits_.setdefault(cand[0][0], set()).add(t)
        if ok:
            for name, toks in hits_.items():
                need = next(p[1] for p in pports if p[0] == name)
                if need and not set(need) <= toks and not (len(need) == 1 and re.fullmatch(r"[AC]", next(iter(toks)))):
                    ok = False
        if not ok or not hits_:
            bad.append(r); continue
        for name in hits_:
            if name in out and (out[name]["fixed_pdos"], out[name]["pps"], out[name]["max_w"]) != (r["fixed_pdos"], r["pps"], r["max_w"]):
                bad.append(r); out.pop(name); break
            out[name] = r
    return out, bad


# ---------------------------------------------------------------------------------------------------------------- claims
def _claim(key, value, raw, quote, page, ocr, conf, dkind, url, idc=None):
    cond = {"document_kind": dkind}
    if ocr:
        cond.update(ocr=True, ocr_conf=conf)
    idc = idc or {"identity": "text_layer", "identity_scope": "document", "identity_variant": "exact"}
    cond.update(idc)
    ocr_dep = ocr or idc["identity"] == "ocr"
    ex = EXTRACTOR_OCR if ocr_dep else (EXTRACTOR_REVIEW if idc["identity_variant"] != "exact" else EXTRACTOR)
    return {"key": key, "status": "known", "kind": "official", "value": value, "unit": None, "raw": (raw or "")[:300], "quote": (quote or "")[:300],
            "conditions": cond, "locator": {"pdf_page": page, "document": url},
            "method": {"stage": "ocr" if ocr else "pdf_text", "extractor": ex}, "review": {"state": "candidate"}}


def _row_ok(r):
    """OCR rows: every critical token confident (token sidecar); the page mean alone never qualifies a row."""
    return not r.get("ocr") or (r.get("tok_conf") is not None and r["tok_conf"] >= MIN_OCR_CONF)


def _conf(r):
    return r.get("tok_conf") if r.get("ocr") else None


def claims_for(cat, res, dkind, url, pports, allowed_page=None, layouts_disagree=False):
    """Pure: one parsed document -> ([claim], unattributable port rows) for one category. allowed_page(page, block) -> None (row not scoped to
    the entity) | identity conditions; None = no identity restriction (unit fixtures: text-layer, document scope, exact)."""
    pw = res["power"]
    scope = (lambda r: allowed_page(r["page"], r.get("block") or r.get("quote") or "")) if allowed_page else (lambda r: {})
    ok = lambda r: _row_ok(r) and scope(r) is not None
    out = []

    def mk(key, value, raw, quote, r):
        return _claim(key, value, raw, quote, r["page"], r.get("ocr"), _conf(r), dkind, url, scope(r) or None)
    dev = [d for d in pw["device"] if ok(d) and d.get("ctx") in ("port", "out")]
    single = [d for d in dev if d["mode"] != "multi"]
    pps_rows = [d for d in dev if d["pps"]]
    named = [n for n in pw["pps_named"] if ok(n)]
    first = (pps_rows or named or [None])[0]
    if first:
        out.append(mk("pd.pps", True, first["quote"], "the document prints a PPS range for an output" if pps_rows else "the document states PPS support", first))
    rng = []
    for d in single:
        for r in (d["pps"] or "").split("; "):
            m = re.match(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)V (\d+(?:\.\d+)?)A", r)
            if m:
                rng.append((float(m[2]), float(m[3]), d))
    if rng and cat == "chargers":
        hv = max(rng, key=lambda x: x[0]); hc = max(rng, key=lambda x: x[1])
        out.append(mk("pd.pps_max_voltage", P.fnum(hv[0]), hv[2]["quote"], "highest printed PPS voltage (single-port / sectionless rows)", hv[2]))
        out.append(mk("pd.pps_max_current_a", P.fnum(hc[1]), hc[2]["quote"], "highest printed PPS current (single-port / sectionless rows)", hc[2]))
    vm = [(d["vmax"], d) for d in single if d.get("vmax")]
    if vm:
        v, d = max(vm, key=lambda x: x[0])
        out.append(mk("pd.max_fixed_voltage", P.fnum(v), d["quote"], "highest printed fixed PDO voltage", d))
        if v >= 28 and cat == "chargers":
            out.append(mk("pd.epr", True, d["quote"], "a fixed PDO of 28 V or more is printed (USB PD EPR)", d))
    rows = [r for r in pw["ports"] if ok(r) and (not layouts_disagree or r.get("mode") == "single")]
    unattributed = len([r for r in pw["ports"] if ok(r) and r not in rows])
    if rows and pports:
        mapped, bad = map_ports(rows, pports)
        unattributed += len(bad)
        if mapped:
            by_page = defaultdict(list)
            for name, r in mapped.items():
                by_page[(r["page"], bool(r.get("ocr")), _conf(r), json.dumps(scope(r), sort_keys=True))].append((name, r))
            for (page, ocr, conf, _), items in sorted(by_page.items(), key=lambda kv: str(kv[0])):
                prow = {p[0]: p[2] for p in pports}
                val = [{"name": n, "type": prow[n].get("type"), "direction": "out", "max_w": r["max_w"], "fixed_pdos": r["fixed_pdos"], "pps": r["pps"]}
                       for n, r in sorted(items, key=lambda x: [p[0] for p in pports].index(x[0]))]
                quote = " ; ".join(dict.fromkeys(r["quote"] for _, r in items))
                out.append(mk("out.ports", val, quote, quote, items[0][1]))
    elif rows:
        unattributed += len(rows)
    keys = KEYS[cat]
    return [c for c in out if c["key"] in keys], unattributed


# ---------------------------------------------------------------------------------------------------------------- edges
def _norm_page(u):
    s = urllib.parse.urlsplit(str(u or "").strip())
    return urllib.parse.urlunsplit((s.scheme.lower(), (s.hostname or "").lower().rstrip("."), s.path.rstrip("/"), s.query, ""))


def edge_verified(e, f):
    """The discovery edge (source_id, ref, page_url) must be the entity's own observation of exactly that page URL."""
    urls = {_norm_page(e.srcs.get(ob[2], {}).get("url")) for ob in e.obs if ob[0] == f.get("source_id") and str(ob[1]) == str(f.get("ref"))}
    return bool(f.get("page_url")) and _norm_page(f["page_url"]) in urls


def edges_of(doc, cats, by_obs):
    """-> {(cat, id(entity)): (cat, entity, [unique found_on edges])} in discovery order."""
    out = {}
    for f in doc["found_on"]:
        cat = f.get("category")
        if cat not in cats or not f.get("source_id"):
            continue
        for e in by_obs.get((cat, f["source_id"], f["ref"]), []):
            slot = out.setdefault((cat, id(e)), (cat, e, []))
            key = (f["source_id"], str(f["ref"]), f.get("page_url"))
            if key not in [(x["source_id"], str(x["ref"]), x.get("page_url")) for x in slot[2]]:
                slot[2].append(f)
    return out


def edge_source(e, doc, rec, page, linked_from):
    """One source entry per (document URL, snapshot, PDF page, linking page): never shared with another URL or linking context."""
    h = hashlib.sha256(f"{doc['norm_url']}\0{linked_from}".encode()).hexdigest()[:12]
    snap = f"{rec['snapshot']}#page={page}#edge={h}"
    e.srcs.setdefault(snap, {"url": f"{doc['url'].split('#')[0]}#page={page}", "tier": "manufacturer",
                             "label": f"{doc['kind'].replace('_', ' ')} (PDF p.{page})", "snapshot": snap,
                             "retrieved_at": rec.get("fetched_at"), "linked_from": linked_from})
    return snap


def add_document(e, doc, linked_from):
    ent = {"url": doc["url"], "kind": doc["kind"], "label": (doc.get("link_text") or doc["kind"])[:120], "linked_from": linked_from}
    if not any(x.get("url") == ent["url"] and x.get("linked_from") == linked_from for x in e.documents):
        e.documents.append(ent)


def apply(worlds, events, stats, root=None):
    """worlds: {category: World} of import.py. Attaches claims, records proposals. -> per-category counters (also into stats)."""
    docs, latest, d = _load_docs(root)
    fp = fingerprint()
    by_obs = {}
    for cat, w in worlds.items():
        if cat not in CATEGORIES:
            continue
        _compute_lineage(w.ents)
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
        for cat, e, fs in edges_of(doc, cats, by_obs).values():
            w = worlds[cat]
            ob = (SOURCE_ID, doc["norm_url"], rec["snapshot"])
            idn = identity(e, w, res, doc["url"])
            if not idn["mine"]:
                reason = "identity_low_confidence" if idn["low"] else "model_not_named"
                events.append(("document_proposal", cat, e, w.anchors(e.keys), ob, {"reason": reason, "url": doc["url"], "page": fs[0]["page_url"],
                                                                                   "identifiers": ident_values(e)[:6]}))
                st[f"proposal_{reason}"] += 1
                continue
            if idn["siblings"]:
                st["multi_model_docs"] += 1
            allowed = lambda page, btxt, idn=idn: scope_of(idn, res, page, btxt)
            attached, ncl = 0, 0
            for f in fs:
                if not edge_verified(e, f):
                    st["edges_unverified"] += 1
                    continue
                pp, disagree = page_ports(e, (f["source_id"], f["ref"]))
                cs, unattr = claims_for(cat, res, doc["kind"], doc["url"], pp, allowed, disagree)
                st["port_rows_unattributable"] += unattr
                if idn["siblings"] and not cs:
                    continue
                attached += 1
                add_document(e, doc, f["page_url"])
                st["edges_attached"] += 1
                for c in cs:
                    page = c["locator"]["pdf_page"]
                    snap = edge_source(e, doc, rec, page, f["page_url"])
                    c["locator"]["linked_from"] = f["page_url"]
                    c["observed_at"] = rec.get("fetched_at") or "1970-01-01T00:00:00Z"
                    e.claims.append((c, (SOURCE_ID, doc["norm_url"], snap)))
                    st[f"claims:{cat}:{c['key']}"] += 1
                    st[f"claims_by_extractor:{c['method']['extractor']}"] += 1
                    ncl += 1
            if not attached:
                if idn["siblings"]:
                    events.append(("document_proposal", cat, e, w.anchors(e.keys), ob, {"reason": "multi_model_no_row", "url": doc["url"],
                                                                                       "others": idn["siblings"][:8], "uncatalogued": idn["uncatalogued"][:8]}))
                    st["proposal_multi_model"] += 1
                continue
            e.obs.add(ob)
            events.append(("document_attach", cat, e, w.anchors(e.keys), ob, {"url": doc["url"], "identifiers": idn["mine"], "claims": ncl,
                                                                             "multi_model": bool(idn["siblings"]), "edges": attached,
                                                                             "variants": idn["variants"][:8], "region": idn["region"], "shared": idn["shared"][:4]}))
            st["attached"] += 1
    for k, v in st.items():
        stats[k] = stats.get(k, 0) + v
    return st
