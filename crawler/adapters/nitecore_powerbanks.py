#!/usr/bin/env python3
"""NITECORE power-bank adapter v1 (contract ARCHITECTURE 15.5), category power-banks, source nitecore-us-powerbanks (A2-bat r11).

Host     : www.nitecore.com, NITECORE's own global product site (the maker; www.nitecorestore.com is a US reseller and is not used).
           robots.txt 'User-agent: *' + 'User-agent: ClaudeBot' Allow / (Disallow /api/ /admin/ only); the site publishes /llms.txt asking AI
           systems to represent its products accurately. No terms-of-use page is linked from the site or listed in its sitemap.
discover : https://www.nitecore.com/sitemap.xml (complete product list) -> /product/<slug> whose slug names a power-bank line
           (NB / Carbo / Carbon Battery / Summit / Pocket / NW / NPB). Headlamp + power-bank kits, chargers (NH, UM, SC) and cells (NL) are not banks.
fetch    : product page HTML (server-rendered, the spec table is in the HTML) -> one gzip blob per page, 1 req/s, crawler UA.
parse    : pure. Rows = 'spec-row' / 'spec-key' / 'spec-value' pairs (the maker's Specifications table, never marketing prose), mapped by the
           shared power-bank row mapper shopify_powerbanks2.parse2 (the same rules as SHARGE/KUXIU/EcoFlow rows: capacity cell, rated capacity,
           per-port Output list, Total Output, Input, Weight, Dimensions, Battery type).
Identity : the product name printed in the page <h1>/og:title minus 'NITECORE' and the descriptive tail ('NB20000 Gen3'), which must also be the
           page's own slug name (nb20000Gen3 -> NB20000GEN3). Model = upper-case compact form ('NB20000 GEN3'). Two names / no match -> absence.
           v2 (review-11): every og:title / <h1> / <title> naming a power-bank line is read; if they name different models the page is an
           absence ('contradictory page titles'), never the first match.
           NITECORE sells the same model names worldwide; the site has no US-only model numbers, so market US is the maker's global model.
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _powerbank as P
import _run
import shopify_powerbanks2 as S2

ID, VERSION, SOURCE = "nitecore_powerbanks", 2, "nitecore-us-powerbanks"
CATEGORIES = {"power-banks"}
DELAY = 1.0
BASE = "https://www.nitecore.com"
BANK_SLUG = re.compile(r"^(?:nb\w*|carbo\w*|carbon_battery_\w+|summit\w*|pocket\w*|nw\d+\w*|npb\w*)$", re.I)
NAME = re.compile(r"^(?:NITECORE\s+)?((?:Carbon Battery(?:™)?|NB|NW|NPB|CARBO|Carbo|SUMMIT|Summit|POCKET|Pocket)\s?[A-Za-z0-9]*(?:\s+(?:Gen\s?\d+|Air|Plus|Pro|\d+K))?)\b")


def rows_of(page):
    rows = {}
    for k, v in re.findall(r'<div class="spec-key"[^>]*>(.*?)</div>\s*<div class="spec-value"[^>]*>(.*?)</div>', page, re.S):
        lab = P.clean(k).rstrip(":").strip()
        if re.fullmatch(r"(?i)output|input", lab):      # one port per line: 'USB-C: ... (20W MAX)\nUSB-A: ... (18W MAX)' -> ';' port segments
            v = " ; ".join(x for x in (P.clean(y) for y in re.split(r"\n|<br\s*/?>", v)) if x)
        if lab:
            rows.setdefault(lab, P.clean(v))
    return rows


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def page_names(page):
    """Every product name the page prints in og:title, each <h1> and <title> -> [(name, text)] (texts naming no power-bank line are skipped)."""
    out = []
    for pat in (r'<meta property="og:title" content="([^"]+)"', r"<h1[^>]*>(.*?)</h1>", r"<title>(.*?)</title>"):
        for m in re.finditer(pat, page, re.S):
            t = P.clean(m[1])
            n = NAME.match(t)
            if n:
                out.append((re.sub(r"\s+", " ", n[1].replace("™", "")).strip(), t))
    return out


def page_name(page):
    """-> (name, title, contradiction). v2 (review-11): the og:title / h1 / title names must agree; two different names = (None, title,
    'og:title X vs h1 Y') rather than the first match winning."""
    names = page_names(page)
    if not names:
        return None, None, None
    distinct = list(dict.fromkeys(norm(n) for n, _ in names))
    if len(distinct) > 1:
        return None, names[0][1], "contradictory page titles: " + " vs ".join(repr(n) for n in dict.fromkeys(n for n, _ in names))
    return names[0][0], names[0][1], None


class NitecorePowerbanks:
    id, source_id, brand, version, categories = ID, SOURCE, "nitecore", VERSION, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(self.source_id)
        self.adapter = f"{self.id}@{self.version}"

    def discover(self, checkpoint, net):
        r = net.get(f"{BASE}/sitemap.xml", DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap: {getattr(r, 'status_code', r)}", {})
        refs, n = [], 0
        for u in dict.fromkeys(re.findall(r"<loc>\s*(https://www\.nitecore\.com/product/([A-Za-z0-9_]+))\s*</loc>", r.text)):
            n += 1
            if BANK_SLUG.match(u[1]):
                refs.append(C.Ref(self.source_id, u[1], u[0], {}))
        return C.Discovery(refs, True, None, {"products": n, "banks": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            s = C.Snapshot("sha256:", ref, (r if (r is None or isinstance(r, str)) else r.status_code) or "breaker", now, ref.url, {})
            self.store.append(s, self.adapter, ".html.gz")
            return s
        s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, self.adapter, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        page = gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace")
        return parse_page(self, snap, page)

    # parse2 hooks
    def rows(self, page, prod, title):
        rows = rows_of(page)
        return rows, (None if rows else "no Specifications rows on the page")

    def model(self, rows, prod, page):
        return prod.get("_model")


def parse_page(ad, snap, page):
    name, title, clash = page_name(page)
    slug = snap.ref.key
    model = None
    if name and norm(name) == norm(slug.replace("_", "")):
        model = re.sub(r"\s+", " ", name.upper()).strip()
    rows = rows_of(page)
    if model and rows and "Output" not in rows:
        model, why = None, "no Output row: a battery pack / cell, not a power bank"
    elif clash:
        why = f"no model identity: {clash}"
    else:
        why = f"no model identity: page name {name!r} does not equal the page's own product slug {slug!r}"
    pr = S2.parse2(ad, snap, page, {"title": title or slug, "variants": [], "_model": model})
    pr.sources = [L.source(snap, f"NITECORE product page {slug}")]
    pr.fingerprints["name"] = name
    if not model:
        pr.absences = [{"key": "*", "reason": why, "source": "s1"}]
        return pr
    if not rows:
        pr.identifiers, pr.aliases = [], []          # no spec table: nothing to attach, no entity minted
        return pr

    def add(k, val, raw, label, cond=None, quote=None):
        P.emit(pr, ad.adapter, snap, k, val, raw, label, model, cond, quote)
    if (bt := rows.get("Cell")) and not any(c["key"] == "bat.chemistry" for c in pr.claims):
        add("bat.chemistry", P.chemistry(bt), bt, "Cell")
    if (re_ := rows.get("Rated Energy")) and re.search(r"mAh", re_):      # NITECORE labels the 5 V rated capacity 'Rated Energy': '6,400mAh 5V (TYP 1A)'
        n, cond = P.rated(re_)
        if n is not None:
            add("cap.rated_mah", n, re_, "Rated Energy", cond)
    return pr


CLASSES = (NitecorePowerbanks,)

if __name__ == "__main__":
    _run.main(NitecorePowerbanks())
