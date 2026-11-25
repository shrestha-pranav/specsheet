#!/usr/bin/env python3
"""Generic document input stage (A3 document pipeline, 2026-11-24). Every source, one store: raw/_documents/.

    python3 -I crawler/documents.py discover            # offline: snapshots -> raw/_documents/discovery.json
    python3 -I crawler/documents.py fetch [--limit N]   # polite: adopt local blobs, then GET what is missing (1 req/s/host, robots)
    python3 -I crawler/documents.py extract             # pdftotext -layout (+ bbox blocks); empty text layer -> tesseract OCR
    python3 -I crawler/documents.py stats

discover  Reads what we already hold, never the network: (a) the latest 200 HTML/JSON snapshot of every registered source
          (raw/<sid>/snapshots.jsonl), (b) the crawl.py v0 stores (raw/<slug>/products/<key>/{assets,extract}.json). Every document link is
          tied to the PAGE it was found on (source_id, ref, page_url). v0 pages are bound to the registered source whose snapshot has the
          same page URL (or, for the legacy power-strip stores, to the slug source itself); an unbound v0 page keeps its link for the audit.
          Classification (URL + link text, never content): kind manual | datasheet | spec_sheet | certificate | other, language from URL
          tokens. Skipped, with the reason recorded: other (warranty, terms, tax forms, MSA, guarantees), brochures/catalogs/comparison
          charts/sales sheets (marketing), non-English duplicates (an English URL of the same document stem exists), documents a dedicated
          adapter already reads (kingston_ssd, sandisk_datasheets, cyberpower). Dedupe: by normalised URL here, by content hash after fetch.
fetch     Budget = one pass over the unique, relevant (decision 'fetch') documents, core categories first. A document whose bytes are
          already on disk (v0 assets blob with a matching sha256) is ADOPTED (snapshot record, adapter crawlpy-assets@0, no request).
          Otherwise GET through crawl.Net (honest UA, robots.txt, per-host delay, breaker; a 403/blocked host is recorded, never worked
          around), conditional with the prior ETag/Last-Modified (304 -> not_modified record pointing at the prior snapshot).
          raw/_documents/snapshots.jsonl is append-only; blobs are content addressed. Snapshot ids are content hashes, independent of the
          parser version (parse caches key on snapshot + parser fingerprint, exactly like registry.py).
extract   raw/_documents/text/<sha>.json (derived, rebuildable): per page {n, text, blocks, method, ocr_conf}. Text layer first
          (`pdftotext -layout`, `pdftotext -bbox-layout` for column blocks); a page whose text layer is empty is rendered (pdftoppm 300 dpi)
          and OCR'd with tesseract (TSV -> mean word confidence). Images (label photos) go straight to OCR.
"""
import argparse, gzip, hashlib, html, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "adapters"))
sys.path.insert(0, str(HERE))
import _contract as C  # noqa: E402

ROOT = C.ROOT
SID = "_documents"
STORE = ROOT / "raw" / SID
FETCHER = "documents@1"
EXTRACTOR = "doctext@1"
DELAY = 1.0
CORE = ["chargers", "power-banks", "monitors", "ssds", "laptops", "tvs", "routers"]   # owner priority: core categories first
PDF_RE = re.compile(r"""(?:https?:)?//[^\s"'<>()\\]+?\.pdf(?:\?[^\s"'<>()\\]*)?|(?<=["'])/[^\s"'<>()\\]+?\.pdf(?:\?[^\s"'<>()\\]*)?""", re.I)
HREF = re.compile(r"""<a\b[^>]*?href\s*=\s*["']([^"']+?\.pdf[^"']*)["'][^>]*>(.*?)</a>""", re.I | re.S)
TAG = re.compile(r"<style\b.*?</style>|<script\b.*?</script>|<[^>]+>", re.S | re.I)

# ---------------------------------------------------------------------------------------------------------------- classification
KIND_RULES = [   # first match wins; tested against "<url path> | <link text>" lowercased
    ("other", r"warrant|terms|guarantee|\bmsa[_ ]statement|irs\.gov|/irs-pdf/|privacy|return[_ -]policy|\bform \d|recycl|battery[_ -]?disposal|w-?9\b"),
    ("marketing", r"brochure|catalog(?:ue)?\b|comparison|sales[_ -]?sheet|line[_ -]?card|flyer|lookbook|compatibility[_ -]?chart|buyers?[_ -]?guide"),
    ("certificate", r"regulatory|rc[_ -]?statement|declaration|\bdoc\b|\bce[_ -]doc|certificat|compliance|fcc|rohs|reach|\bweee\b|sustainab|"
                    r"/ins_|\bins_|[_-]ftc[_.-]|energy[_ -]?guide|safety[_ -]?(?:information|instructions|sheet)|\bsds\b|\bmsds\b|un38\.3|test[_ -]?report"),
    ("datasheet", r"data[_ -]?sheet|datasheet|\bds\b|[_-]ds[_.-]|product[_ -]data"),
    ("spec_sheet", r"spec(?:ification)?s?[_ -]?sheet|spec[_ -]sheet|[_-]ts\.pdf|specifications?\b|tech[_ -]?specs?|\bspecs?\b|quickspecs|psref|product[_ -]?sheet"),
    ("manual", r"manual|user[_ -]?guide|owner|instruction|\bqsg\b|quick[_ -]?start|quickstart|getting[_ -]?started|setup[_ -]?guide|install|"
               r"\bguide\b|\bum\b|[_-]um[_.-]|handbook|e-?manual"),
]
KIND_RX = [(k, re.compile(rx, re.I)) for k, rx in KIND_RULES]
LANG_TOK = {
    "de": r"german|deutsch|[_/-]de(?:[_-]de)?(?=[_./-])|de-de", "fr": r"french|fran[cç]ais|[_/-]fr(?:[_-](?:fr|ca))?(?=[_./-])|fr-fr|fr-ca",
    "es": r"spanish|espa[nñ]ol|[_/-]es(?:[_-](?:es|mx))?(?=[_./-])|es-es|es-mx", "it": r"italian|[_/-]it(?:[_-]it)?(?=[_./-])|it-it",
    "ja": r"japanese|[_/-]j[ap](?:[_-]jp)?(?=[_./-])|ja-jp", "zh": r"chinese|[_/-](?:cn|zh|tw|chs|cht)(?=[_./-])|zh-cn|zh-tw",
    "ko": r"korean|[_/-]k[or](?=[_./-])|ko-kr", "nl": r"dutch|[_/-]nl(?=[_./-])|nl-nl", "pt": r"portug|[_/-]pt(?:[_-]br)?(?=[_./-])|pt-br",
    "ru": r"russian|[_/-]ru(?=[_./-])", "pl": r"polish|[_/-]pl(?=[_./-])", "ar": r"arabic|[_/-]ar(?=[_./-])",
}
LANG_RX = {k: re.compile(v, re.I) for k, v in LANG_TOK.items()}
EN_RX = re.compile(r"english|[_/-](?:en|us|usa|na)(?:[_-](?:us|gb|ca))?(?=[_./-])|en-us|en_us|/us/|/en/", re.I)
SKIP_KINDS = {"other": "skip:other", "marketing": "skip:marketing"}


def classify(url, text=""):
    p = urllib.parse.urlsplit(url)
    dp = urllib.parse.parse_qs(p.query).get("docPath")          # handler links: classify by the document path they point at
    hay = (urllib.parse.unquote(p.netloc + p.path) + (" " + dp[0].replace("/doc-library/", "/") if dp else "") + " | " + (text or "")).lower()
    kind = next((k for k, rx in KIND_RX if rx.search(hay)), "other_unlabelled")
    path = "/" + urllib.parse.unquote(p.path).lower()
    lang = "en" if EN_RX.search(path) else next((k for k, rx in LANG_RX.items() if rx.search(path)), "und")
    return kind, lang


def stem(url):
    """Document identity across language variants: path basename minus language tokens, version query, case."""
    b = urllib.parse.unquote(urllib.parse.urlsplit(url).path).rsplit("/", 1)[-1].lower()
    b = re.sub(r"\.pdf$", "", b)
    for rx in list(LANG_RX.values()) + [EN_RX]:
        b = rx.sub("_", "_" + b + "_")
    return re.sub(r"[_\s-]+", "_", b).strip("_")


def norm_url(u):
    """Dedupe key: https, lowercase host, no fragment; query kept except cache-busters (?v= / ?ref= / ?_ / utm)."""
    p = urllib.parse.urlsplit(u.strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if k.lower() not in ("v", "ref", "_", "ver", "version") and not k.lower().startswith("utm")]
    return urllib.parse.urlunsplit(("https", p.netloc.lower(), p.path, urllib.parse.urlencode(q), ""))


def page_key(u):
    p = urllib.parse.urlsplit((u or "").strip())
    return (p.netloc.lower().removeprefix("www.") + p.path.rstrip("/")).lower()


# ---------------------------------------------------------------------------------------------------------------- discovery
def _registry():
    import registry
    return registry


def _read_body(path):
    b = path.read_bytes()
    if path.name.endswith(".gz"):
        b = gzip.decompress(b)
    return b.decode("utf-8", "replace")


def links_in(page_url, body):
    """-> {abs url: link text} for every PDF link in one HTML/JSON body (anchor text when it is an <a>, else '')."""
    out = {}
    for href, txt in HREF.findall(body):
        u = urllib.parse.urljoin(page_url, html.unescape(href.strip()).replace("\\/", "/"))
        out.setdefault(u, " ".join(html.unescape(TAG.sub(" ", txt)).split())[:120])
    for m in PDF_RE.findall(body.replace("\\/", "/")):
        u = urllib.parse.urljoin(page_url, html.unescape(m))
        if u.startswith("http"):
            out.setdefault(u, "")
    return {u: t for u, t in out.items() if len(u) < 600 and urllib.parse.urlsplit(u).netloc}


def dedicated_urls():
    """Document URLs already read by a dedicated adapter (their own snapshot logs): never double-counted here."""
    out = set()
    for sid in ("kingston-us-ssd", "sandisk-us-ssd-datasheets", "cyberpower"):
        log = ROOT / "raw" / sid / "snapshots.jsonl"
        if log.exists():
            for l in log.read_text().splitlines():
                r = json.loads(l)
                for f in ("url", "final_url"):
                    if str(r.get(f) or "").lower().split("?")[0].endswith(".pdf") or "documentRequestHandler" in str(r.get(f) or ""):
                        out.add(norm_url(r[f]))
                        out.add("basename:" + doc_basename(r[f]))
    return out


def doc_basename(url):
    """File name of a document URL; for a handler URL ('/tools/documentRequestHandler?docPath=/x/y.pdf') the docPath's file name, never the
    handler's own name (r2 fix: 'documentrequesthandler' matched every SanDisk handler link, so portable datasheets were skipped as dedicated)."""
    p = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(p.query).get("docPath")
    return (q[0] if q else urllib.parse.unquote(p.path)).rsplit("/", 1)[-1].lower()


def discover():
    reg = _registry()
    pages = {}                                  # page_key -> (sid, ref, url) of the latest registered snapshot
    links = defaultdict(lambda: {"texts": set(), "found_on": {}, "local": None})
    n_pages = Counter()
    blob_links = {}                             # one blob shared by many refs (CARB list page) is read once
    for sid, meta in sorted(reg.SOURCES.items()):
        if meta.get("legacy"):
            continue
        t0 = time.time()
        store = C.BlobStore.__new__(C.BlobStore)
        store.dir = ROOT / "raw" / sid; store.log = store.dir / "snapshots.jsonl"
        if not store.log.exists():
            continue
        for ref, rec in store.latest().items():
            for u in (rec.get("url"), rec.get("final_url")):
                if u:
                    pages.setdefault(page_key(u), (sid, str(ref), rec["url"]))
            b = rec.get("blob") or ""
            if not re.search(r"\.(html|json)(\.gz)?$", b):
                continue
            p = store.dir / b
            if (p, rec["final_url"]) not in blob_links:
                found = {}
                if p.exists() and p.stat().st_size <= 15e6:
                    raw = p.read_bytes()
                    if b.endswith(".gz"):
                        try:
                            raw = gzip.decompress(raw)
                        except OSError:
                            raw = b""
                    if b".pdf" in raw.lower():
                        found = links_in(rec["final_url"] or rec["url"], raw.decode("utf-8", "replace"))
                blob_links[(p, rec["final_url"])] = found
            for u, t in blob_links[(p, rec["final_url"])].items():
                L = links[norm_url(u)]
                L.setdefault("url", u)
                if t:
                    L["texts"].add(t)
                L["found_on"][(sid, str(ref))] = {"source_id": sid, "ref": str(ref), "page_url": rec["url"], "category": meta["category"], "via": "snapshot"}
                n_pages[sid] += 1
        if time.time() - t0 > 5:
            print(f"[documents] discover {sid}: {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    legacy = {sid for sid, m in reg.SOURCES.items() if m.get("legacy")}
    unbound = Counter()
    for f in sorted((ROOT / "raw").glob("*/products/*/assets.json")) + sorted((ROOT / "raw").glob("*/products/*/extract.json")):
        slug, key = f.parts[-4], f.parts[-2]
        try:
            d = json.loads(f.read_text())
        except ValueError:
            continue
        ex = f.parent / "extract.json"
        try:
            purl = json.loads(ex.read_text()).get("url") if ex.exists() else None
        except ValueError:
            purl = None
        bind = pages.get(page_key(purl)) if purl else None
        if slug in legacy:
            bind = (slug, key, purl)
        for doc in d.get("documents") or []:
            u = doc["url"] if isinstance(doc, dict) else doc
            if not re.search(r"\.pdf(\?|$)", urllib.parse.urlsplit(u).path + "?", re.I):
                continue
            L = links[norm_url(u)]
            L.setdefault("url", u)
            if isinstance(doc, dict):
                if doc.get("text"):
                    L["texts"].add(" ".join(doc["text"].split())[:120])
                if doc.get("blob") and doc.get("sha256") and (f.parents[2] / doc["blob"]).exists():
                    L["local"] = {"path": str((f.parents[2] / doc["blob"]).relative_to(ROOT)), "sha256": doc["sha256"],
                                  "fetched_at": (json.loads((f.parent / "http.json").read_text()).get("fetched_at") if (f.parent / "http.json").exists() else None),
                                  "content_type": doc.get("content_type")}
            if bind:
                sid, ref, pu = bind
                L["found_on"].setdefault((sid, ref), {"source_id": sid, "ref": ref, "page_url": pu or purl, "category": reg.SOURCES[sid]["category"], "via": f"v0:{slug}/{key}"})
            else:
                L["found_on"].setdefault((f"v0:{slug}", key), {"source_id": None, "ref": key, "page_url": purl, "category": None, "via": f"v0:{slug}/{key}"})
                unbound[slug] += 1
    ded = dedicated_urls()
    docs = []
    for nu, L in links.items():
        text = " / ".join(sorted(L["texts"]))[:300]
        kind, lang = classify(L["url"], text)
        cats = sorted({x["category"] for x in L["found_on"].values() if x["category"]})
        docs.append({"doc_id": hashlib.sha256(nu.encode()).hexdigest()[:16], "url": L["url"], "norm_url": nu, "kind": kind, "lang": lang,
                     "stem": stem(L["url"]), "link_text": text, "categories": cats,
                     "found_on": sorted(L["found_on"].values(), key=lambda x: (str(x["source_id"]), x["ref"])), "local": L["local"],
                     "dedicated": nu in ded or "basename:" + doc_basename(L["url"]) in ded})
    decide(docs)
    docs.sort(key=lambda d: (d["priority"], d["norm_url"]))
    STORE.mkdir(parents=True, exist_ok=True)
    out = {"generated_at": time.strftime("%FT%TZ", time.gmtime()), "format": 1, "pages_with_links": dict(n_pages), "unbound_v0_links": dict(unbound),
           "counts": {"documents": len(docs), "by_decision": dict(Counter(d["decision"] for d in docs)), "by_kind": dict(Counter(d["kind"] for d in docs))},
           "docs": docs}
    tmp = STORE / "discovery.json.tmp"
    tmp.write_text(json.dumps(out, indent=0, sort_keys=True))
    tmp.replace(STORE / "discovery.json")
    return out


def decide(docs):
    """Fetch decision per discovered document (pure; fixture-tested): dedicated adapter > other/marketing > non-English duplicate of an
    English (or language-unmarked) document with the same stem > page not registered > fetch."""
    by_stem = defaultdict(list)
    for d in docs:
        by_stem[d["stem"]].append(d)
    for d in docs:
        if d["dedicated"]:
            d["decision"] = "skip:dedicated_adapter"
        elif d["kind"] in SKIP_KINDS:
            d["decision"] = SKIP_KINDS[d["kind"]]
        elif d["lang"] not in ("en", "und") and any(x["lang"] in ("en", "und") and x is not d for x in by_stem[d["stem"]]):
            d["decision"] = "skip:non_english_duplicate"
        elif not any(x["source_id"] for x in d["found_on"]):
            d["decision"] = "skip:page_not_registered"
        else:
            d["decision"] = "fetch"
        d["priority"] = priority(d)
    return docs


def priority(d):
    """Lower = sooner. Core categories (presets + demand survey) first, then spec-bearing kinds, then the rest."""
    cats = d["categories"]
    core = min((CORE.index(c) for c in cats if c in CORE), default=len(CORE))
    kind = {"datasheet": 0, "spec_sheet": 0, "manual": 1, "other_unlabelled": 2, "certificate": 3}.get(d["kind"], 4)
    return core * 10 + kind


def load_discovery():
    p = STORE / "discovery.json"
    return json.loads(p.read_text()) if p.exists() else {"docs": []}


# ---------------------------------------------------------------------------------------------------------------- fetch
def store():
    return C.BlobStore(SID)


def latest_by_url(st):
    out = {}
    for r in st.snapshots():
        if r["status"] == 200 or r.get("not_modified"):
            out[norm_url(r["ref"])] = r
    return out


def _append(st, rec):
    with st.log.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def is_pdf(body, ctype):
    return body[:5] == b"%PDF-" or "pdf" in (ctype or "").lower() and body[:5] == b"%PDF-"


def fetch(limit=None, max_bytes=60_000_000, dry=False, workers=6, categories=None):
    """One pass. Adoption first (no network), then the remaining documents in priority order, one worker per host (so the per-host
    delay of crawl.Net is the only rate limit that matters: ~1 req/s/host), at most `workers` hosts at a time."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    disc = load_discovery()
    st = store()
    have = latest_by_url(st)
    tried = {norm_url(r["ref"]) for r in st.snapshots()}
    stats = Counter()
    lock = threading.Lock()
    queue = defaultdict(list)
    for d in disc["docs"]:
        if d["decision"] != "fetch":
            continue
        if categories and not set(d["categories"]) & set(categories):
            stats["deferred_by_category"] += 1
            continue
        nu = d["norm_url"]
        if nu in have:
            stats["already"] += 1
            continue
        loc = d.get("local")
        if loc:
            src = ROOT / loc["path"]
            body = src.read_bytes()
            sha = hashlib.sha256(body).hexdigest()
            if sha == loc["sha256"] and body[:5] == b"%PDF-":
                dst = st.blobs / f"{sha}.pdf"
                if not dst.exists():
                    try:
                        os.link(src, dst)
                    except OSError:
                        shutil.copyfile(src, dst)
                _append(st, {"snapshot": f"sha256:{sha}", "ref": nu, "url": d["url"], "final_url": d["url"], "status": 200,
                             "fetched_at": loc.get("fetched_at"), "etag": None, "last_modified": None, "adapter": "crawlpy-assets@0",
                             "blob": f"blobs/{sha}.pdf", "content_type": loc.get("content_type"), "adopted_from": loc["path"]})
                stats["adopted"] += 1
                have[nu] = True
                continue
        if nu in tried:
            stats["tried_before"] += 1      # one pass: a document that failed (404/robots/blocked/not_pdf) is not retried by this stage
            continue
        queue[urllib.parse.urlsplit(d["url"]).netloc.lower()].append(d)
    budget = [limit if limit is not None else 10 ** 9]

    def one(d):
        nu = d["norm_url"]
        r = C.NET.get(d["url"], DELAY, stream=True)
        now = time.strftime("%FT%TZ", time.gmtime())
        rec = {"ref": nu, "url": d["url"], "fetched_at": now, "adapter": FETCHER, "etag": None, "last_modified": None}
        if r is None or isinstance(r, str):
            return dict(rec, snapshot="sha256:", final_url=d["url"], status=r or "breaker", blob=None), None
        ct = r.headers.get("Content-Type", "")
        if r.status_code != 200:
            return dict(rec, snapshot="sha256:", final_url=r.url, status=r.status_code, blob=None), None
        try:
            body = b""
            for chunk in r.iter_content(1 << 16):
                body += chunk
                if len(body) > max_bytes:
                    break
        except Exception as e:  # noqa
            return dict(rec, snapshot="sha256:", final_url=r.url, status=f"error:{type(e).__name__}", blob=None), None
        if len(body) > max_bytes:
            return dict(rec, snapshot="sha256:", final_url=r.url, status="too_large", blob=None), None
        if body[:5] != b"%PDF-":
            return dict(rec, snapshot="sha256:", final_url=r.url, status=f"not_pdf:{ct.split(';')[0][:40]}", blob=None), None
        return dict(rec, final_url=r.url, status=200, etag=r.headers.get("ETag"), last_modified=r.headers.get("Last-Modified"), content_type=ct), body

    def host_worker(host):
        for d in queue[host]:
            with lock:
                if budget[0] <= 0:
                    stats["deferred_by_limit"] += 1
                    continue
                budget[0] -= 1
                stats["requests"] += 1
            if dry:
                continue
            rec, body = one(d)
            with lock:
                if body is not None:
                    sha = st.put(body, ".pdf")
                    rec.update(snapshot=sha, blob=f"blobs/{sha.split(':', 1)[1]}.pdf")
                _append(st, rec)
                stats[f"status:{rec['status']}"] += 1
                if stats["requests"] % 50 == 0:
                    print(f"[documents] fetch {time.strftime('%T')} {dict(stats)}", file=sys.stderr, flush=True)
            if C.NET.fails.get(host, 0) >= 15:
                with lock:
                    stats[f"breaker_open:{host}"] += 1
                break
    hosts = sorted(queue, key=lambda h: min(x["priority"] for x in queue[h]))
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(host_worker, hosts))
    return dict(stats)


def refresh(nu, st, prior):
    """Conditional re-GET of one known document (not used by the one-pass budget; kept for the periodic refresh job)."""
    h = {}
    if prior.get("etag"):
        h["If-None-Match"] = prior["etag"]
    if prior.get("last_modified"):
        h["If-Modified-Since"] = prior["last_modified"]
    r = C.NET.get(prior["url"], DELAY, headers=h)
    if r is not None and not isinstance(r, str) and r.status_code == 304:
        _append(st, dict(prior, fetched_at=time.strftime("%FT%TZ", time.gmtime()), adapter=FETCHER, not_modified=True))
        return "not_modified"
    return getattr(r, "status_code", r)


# ---------------------------------------------------------------------------------------------------------------- extract
BLOCK = re.compile(r'<block xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</block>', re.S)
LINE = re.compile(r"<line[^>]*>(.*?)</line>", re.S)
WORD = re.compile(r"<word[^>]*>(.*?)</word>", re.S)


def bbox_blocks(path):
    """-> {page_no: [{x, y, w, h, lines: [text]}]} from `pdftotext -bbox-layout` (column-local text: multi-column manuals stay readable)."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "b.html"
        subprocess.run(["pdftotext", "-q", "-bbox-layout", str(path), str(out)], capture_output=True, timeout=180)
        if not out.exists():
            return {}
        t = out.read_text("utf-8", "replace")
    pages = {}
    for n, pg in enumerate(t.split("<page ")[1:], 1):
        bl = []
        for x0, y0, x1, y1, inner in BLOCK.findall(pg):
            lines = [" ".join(html.unescape(w) for w in WORD.findall(l)) for l in LINE.findall(inner)]
            lines = [l for l in lines if l.strip()]
            if lines:
                bl.append({"x": round(float(x0)), "y": round(float(y0)), "w": round(float(x1) - float(x0)), "h": round(float(y1) - float(y0)), "lines": lines})
        pages[n] = bl
    return pages


def layout_pages(path):
    r = subprocess.run(["pdftotext", "-q", "-layout", str(path), "-"], capture_output=True, timeout=180)
    return r.stdout.decode("utf-8", "replace").split("\f")


def ocr_image(img):
    """tesseract TSV -> (text, mean confidence of words with conf >= 0, words)."""
    r = subprocess.run(["tesseract", str(img), "-", "-l", "eng", "--psm", "3", "tsv"], capture_output=True, timeout=300)
    rows = r.stdout.decode("utf-8", "replace").splitlines()[1:]
    lines, confs = defaultdict(list), []
    for row in rows:
        f = row.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        conf = float(f[10])
        if conf >= 0:
            confs.append(conf)
        lines[(int(f[2]), int(f[3]), int(f[4]))].append(f[11])
    text = "\n".join(" ".join(ws) for _, ws in sorted(lines.items()))
    return text, (round(sum(confs) / len(confs), 1) if confs else 0.0), len(confs)


def ocr_pdf_page(path, n, dpi=300):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-q", "-r", str(dpi), "-f", str(n), "-l", str(n), "-png", str(path), f"{td}/p"], capture_output=True, timeout=300)
        imgs = sorted(Path(td).glob("p*.png"))
        return ocr_image(imgs[0]) if imgs else ("", 0.0, 0)


def extract_one(path, max_ocr_pages=12):
    """-> {extractor, pages: [{n, text, blocks, method, ocr_conf}]} for one PDF blob (pure function of the bytes + tool versions)."""
    lay = layout_pages(path)
    blocks = bbox_blocks(path)
    pages, ocr_n = [], 0
    for i, txt in enumerate(lay, 1):
        if i == len(lay) and not txt.strip() and i > max(blocks or {0: 0}):
            break           # trailing form feed
        if len(re.sub(r"\s", "", txt)) >= 20:
            pages.append({"n": i, "text": txt, "blocks": blocks.get(i, []), "method": "text_layer"})
        elif ocr_n < max_ocr_pages:
            t, conf, nw = ocr_pdf_page(path, i)
            ocr_n += 1
            pages.append({"n": i, "text": t, "blocks": [], "method": "ocr", "ocr_conf": conf, "ocr_words": nw})
        else:
            pages.append({"n": i, "text": "", "blocks": [], "method": "ocr_skipped_budget"})
    return {"extractor": EXTRACTOR, "pages": pages}


def text_path(sha):
    return STORE / "text" / f"{sha.split(':', 1)[-1]}.json"


def extract(force=False, categories=None):
    st = store()
    stats = Counter()
    seen = set()
    cats = {d["norm_url"]: set(d["categories"]) for d in load_discovery()["docs"]}
    for r in st.snapshots():
        if r["status"] != 200 or not r.get("blob"):
            continue
        if categories and not cats.get(r["ref"], set()) & set(categories):
            stats["deferred_by_category"] += 1
            continue
        sha = r["snapshot"]
        if sha in seen:
            continue
        seen.add(sha)
        tp = text_path(sha)
        if tp.exists() and not force:
            try:
                if json.loads(tp.read_text()).get("extractor") == EXTRACTOR:
                    stats["cached"] += 1
                    continue
            except ValueError:
                pass
        try:
            res = extract_one(st.dir / r["blob"])
        except subprocess.TimeoutExpired:
            res = {"extractor": EXTRACTOR, "pages": [], "error": "timeout"}
        tp.parent.mkdir(parents=True, exist_ok=True)
        tmp = tp.with_suffix(".tmp"); tmp.write_text(json.dumps(res)); tmp.replace(tp)
        stats["extracted"] += 1
        stats["ocr_pages"] += sum(1 for p in res["pages"] if p["method"] == "ocr")
    return dict(stats)


def load_text(sha):
    tp = text_path(sha)
    return json.loads(tp.read_text()) if tp.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "fetch", "extract", "stats"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--categories", help="comma list: fetch only documents linked from these categories (rest deferred)")
    a = ap.parse_args()
    if a.cmd == "discover":
        print(json.dumps({k: v for k, v in discover().items() if k != "docs"}, indent=1))
    elif a.cmd == "fetch":
        print(json.dumps(fetch(a.limit, dry=a.dry, categories=a.categories.split(",") if a.categories else None), indent=1))
    elif a.cmd == "extract":
        print(json.dumps(extract(categories=a.categories.split(",") if a.categories else None), indent=1))
    else:
        d = load_discovery()
        st = store()
        print(json.dumps({"discovery": d.get("counts"), "snapshots": dict(Counter(str(r["status"]) for r in st.snapshots()))}, indent=1))


if __name__ == "__main__":
    main()
