#!/usr/bin/env python3
"""LG US televisions adapter v1 (contract ARCHITECTURE 15.5), category tvs.

discover : https://www.lg.com/us/sitemap.xml (one request; robots `User-agent: *` Allow /) -> /us/tvs/lg-<slug> product pages. Category,
           buying-guide and landing pages (no 'lg-' prefix) are dropped. 1 req/s.
fetch    : the SSR product page, stored gzip-compressed (.html.gz). Same page family as lg_us.py (monitors): __NEXT_DATA__
           props.pageProps.productData.product {sku = model number e.g. OLED65B5PUA, modelCode = LG material code, productIdentifier = UPC,
           modelStatus} and .allInfo[].tableData[] = [{term, description}] spec table.
parse    : pure over the blob; labelled rows only, mapped by _tv.emit() to research/tvs/spec-profile.yaml keys. One page = one model
           (each screen size is its own LG model number, so panel/refresh/HDMI facts are per size).
Identity : mfr_model = sku verbatim (US market). The channel letter (OLED65B5PUA vs OLED65B5AUA) makes a different model string; LG pages never
           state that two strings are the same hardware, so they stay separate models (stem proposal only, research/tvs/identity.md).
"""
import gzip, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _tv as T
import _run

ID, VERSION, SOURCE = "lg_tvs", 2, "lg-us-tvs"
CATEGORIES = {"tvs"}
SITEMAP = "https://www.lg.com/us/sitemap.xml"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
# fetch-order heuristic (not identity): LG model-year codes 2021+ (OLED..C1-C6/B1-B6/G1-G6/Z/M/A, QNED, NANO..UP/UQ, UHD ..UQ/UR/UT/UA/UB, MRGB, LX)
RECENT = re.compile(r"/lg-(oled\d{2}[a-z]{1,2}[1-6]|\d{2,3}qned|\d{2}nano\d{2}u[pqr]|\d{2}u[qrtab]\d|\d{2,3}mrgb|\d{2}lx|\d{2,3}u[qrtab][a-z]?\d|\d{2,3}uc\d|oled\d{2}m[3-6]|\d{2}art)", re.I)


def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    try:
        return json.loads(m.group(1)) if m else None
    except ValueError:
        return None


class LgTvs:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        urls = sorted(set(re.findall(r"<loc>(https://www\.lg\.com/us/tvs/lg-[^<]+)</loc>", r.text)))
        refs = [C.Ref(SOURCE, u.rsplit("/", 1)[1], u, {"slug": u.rsplit("/", 1)[1], "recent": bool(RECENT.search(u))}) for u in urls]
        refs.sort(key=lambda r: (not r.hints["recent"], r.key))      # fetch order only: 2021+ lines first (pages are ~2 MB, ~5 s each)
        return C.Discovery(refs, True, None, {"tv_urls": len(refs), "recent_first": sum(r.hints["recent"] for r in refs)})

    def fetch(self, ref, prior, net):
        import time
        r = net.get(ref.url, DELAY)
        now = time.strftime("%FT%TZ", time.gmtime())
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        sha = self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz")
        s = C.Snapshot(sha, ref, 200, now, r.url, {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        html = gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace")
        return parse_html(snap, html)


def parse_html(snap, html):
    pr, obs = C.ParseResult(), snap.fetched_at
    nd = next_data(html)
    try:
        pd = nd["props"]["pageProps"]["productData"]
        p = pd["product"]
        model = p["sku"].strip()
    except (TypeError, KeyError, AttributeError):
        pr.absences.append({"key": "*", "reason": "no __NEXT_DATA__ productData/sku (not a product page)", "source": "s1"})
        return pr
    pr.sources = [{"id": "s1", "url": snap.ref.url, "label": "LG US product page " + model, "source_id": SOURCE, "tier": "manufacturer",
                   "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "lg", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"]})
    if p.get("modelCode"):
        pr.identifiers.append({"scheme": "x_lg_material_code", "value": p["modelCode"], "value_raw": p["modelCode"], "issuer": "lg", "sources": ["s1"]})
    pi = p.get("productIdentifier") or {}
    if pi.get("type") == "UPC" and re.fullmatch(r"\d{11,14}", pi.get("value") or ""):
        pr.identifiers.append({"scheme": "gtin", "value": pi["value"].zfill(14), "value_raw": pi["value"], "issuer": "GS1", "package_level": "package",
                               "role": "alias", "sources": ["s1"]})
    if p.get("title"):
        pr.aliases.append({"text": T.clean(p["title"]), "kind": "marketing_name", "source": "s1", "observed_at": obs})
    rows = {}
    for g in pd.get("allInfo") or []:
        for row in g.get("tableData") or []:
            if row.get("term"):
                rows.setdefault(T.clean(row["term"]), T.clean(str(row.get("description") or "")))   # first wins (terms repeat across groups)
    used = T.emit(pr, "lg", model, rows, ADAPTER, "next_data", obs)
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "status": p.get("modelStatus"), "terms": len(rows),
                       "unmapped": {k: v for k, v in rows.items() if k not in used}}
    return pr


if __name__ == "__main__":
    _run.main(LgTvs())
