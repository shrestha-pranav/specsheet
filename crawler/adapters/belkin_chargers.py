#!/usr/bin/env python3
"""Belkin US charger adapter (contract ARCHITECTURE 15.5), category chargers. Source = www.belkin.com (Salesforce Commerce Cloud).
New module, not belkin_powerbanks: the audited power-bank parser fingerprint does not move.

discover : https://www.belkin.com/sitemap-variant_products_us_001.xml (US variant URLs /p/<slug>/<SKU>.html; robots allows /p/) filtered to
           wall/car charger model ranges WCA/WCB/WCC/WCH (BoostCharge wall), BBC (Amazon-channel wall), CCA/CCB/CCC (car), INC (Core GaN),
           ENA (licensed console chargers). Excluded: B2B charging lockers (AC outlets for fleets), SRZ surge stations (power-strip category),
           wireless/MagSafe/stand slugs, cables. Variant SKUs are grouped by model = 3 letters + 3 digits (WCH010dqBK -> WCH010); one Ref per model.
fetch    : that one variant page, gzip. 1 request per model.
parse    : pure. JSON-LD ProductGroup (name, productGroupID P-WCH010, variants + GTIN) + the 'Technical Specifications' table
           (span.spec-attr-label + span.spec-attr-value). Charger semantics in _charger.read_rows. Belkin's 'Wattage' row does not say total
           or single port; it goes to out.rated_w ('Rated output, basis not stated'), never to the total or single-port keys.
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _charger as G
import _run

ID, VERSION, SOURCE = "belkin_chargers", 3, "belkin-us-chargers"     # r9: _charger port-name variants normalised (claims unchanged)
CATEGORIES = {"chargers"}
ADAPTER = f"{ID}@{VERSION}"
SITEMAP = "https://www.belkin.com/sitemap-variant_products_us_001.xml"
DELAY = 1.0
LOC = re.compile(r"<loc>(https://www\.belkin\.com/p/([a-z0-9.-]+)/([A-Za-z0-9-]+)\.html)</loc>")
MODEL = re.compile(r"^((?:WC[ABCH]|BBC|CC[ABC]|INC|ENA)\d{3})")
SLUG_NOT = re.compile(r"wireless|magsafe|qi2?|power-bank|pad|stand|cable|dock|watch|airpods|mount|grip|screen-protector|power-extender")


class BelkinChargers:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES
    brand, brand_name = "belkin", "Belkin"

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        by = {}
        for url, slug, sku in LOC.findall(r.text):
            m = MODEL.match(sku.upper())
            if not m or SLUG_NOT.search(slug) or not re.search(r"charger|power-adapter", slug):
                continue
            by.setdefault(m[1], []).append((url, sku, slug))
        refs = []
        for model, vs in sorted(by.items()):
            vs.sort(key=lambda x: ("-" in x[1], x[1]))
            refs.append(C.Ref(SOURCE, model.lower(), vs[0][0], {"skus": sorted({v[1] for v in vs}), "slug": vs[0][2]}))
        return C.Discovery(refs, True, None, {"models": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_page(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


def jsonld(h):
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try:
            d = json.loads(m[1])
        except ValueError:
            continue
        for x in (d if isinstance(d, list) else [d]):
            if isinstance(x, dict) and x.get("@type") in ("ProductGroup", "Product"):
                return x
    return {}


def parse_page(snap, h):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [G.source(snap, "Belkin US product page " + key.upper())]
    j = jsonld(h)
    url_model = key.upper()
    gid = str(j.get("productGroupID") or "").upper().removeprefix("P-")
    model = gid if gid and MODEL.match(gid) and gid[:6] == url_model else url_model
    name = G.clean(j.get("name"))
    tm = re.search(r"<title>(.*?)</title>", h, re.S)
    title = G.clean(tm[1]).split("|")[0].strip() if tm else name
    kind = G.charger_kind(f"{name} {title} {snap.ref.hints.get('slug', '').replace('-', ' ')}")
    if kind is None:
        pr.absences.append({"key": "*", "reason": f"not a charger page ({title[:60]})", "source": "s1"})
        return pr
    skus = [(s.upper(), None) for s in snap.ref.hints.get("skus") or []]
    gtins = []
    hv = j.get("hasVariant")
    for v in (hv if isinstance(hv, list) else [hv] if hv else []):
        g = str(v.get("gtin13") or v.get("gtin12") or v.get("gtin") or "")
        if re.fullmatch(r"\d{12,14}", g):
            gtins.append(g)
    G.identity(pr, "belkin", model, title, skus, gtins, basis="productGroupID / 3 letters + 3 digits of the variant SKU", extra_names=[name])
    rows = []
    for m in re.finditer(r'<span class="spec-attr-label">(.*?)</span>\s*<ul class="spec-attr-list">(.*?)</ul>', h, re.S):
        vals = [G.clean(x) for x in re.findall(r'<span class="spec-attr-value">(.*?)</span>', m[2], re.S)]
        rows.append((G.clean(m[1]), [("", v) for v in vals if v]))
    fam = re.match(r"(BoostCharge Pro|BoostCharge|UltraCharge Pro|UltraCharge)", title)
    G.read_rows(pr, ADAPTER, snap, model, title, kind, rows, table="Technical Specifications", line=f"Belkin {fam[1]}" if fam else None)
    pr.fingerprints.update({"raw": snap.snapshot})
    return pr


if __name__ == "__main__":
    _run.main(BelkinChargers())
