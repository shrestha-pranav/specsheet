#!/usr/bin/env python3
"""Anker US charger adapter (contract ARCHITECTURE 15.5), category chargers. Source = www.anker.com (headless Shopify + Next.js).
New module, not anker_powerbanks: the audited power-bank parser fingerprint does not move.

discover : https://www.anker.com/server-sitemap-index-products.xml (all markets; only bare /products/<handle> US URLs) + the charger collections'
           __NEXT_DATA__ handles, filtered to Anker's charger model ranges: A2xxx (wall/desktop/car chargers; A25xx wireless and A27xx car are
           told apart at parse), A12[01]x (A120F/A121D GaN chargers), A1A0x (travel charging stations), B2xxx/B12xx (newer SKU prefix). Bundles,
           '-f0' outlet clones, N-packs, members-exclusive duplicates and editions are dropped. One Ref per model (shortest handle).
fetch    : product page HTML, gzip. 1 request per model.
parse    : pure. Model = the 5-character model number shared by the page's non-bundle variant SKUs (A2688141 -> A2688). Specs from the page's own
           Specifications table (metafields.components.productSpecs) or the variant key_parameter list (Input / Output / Total Output / Ports /
           Dimensions / Weight). Title wattage is never a spec. Charger semantics in _charger.read_rows.
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _charger as G
import _run

ID, VERSION, SOURCE = "anker_chargers", 1, "anker-us-chargers"
CATEGORIES = {"chargers"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.anker.com"
SITEMAP = BASE + "/server-sitemap-index-products.xml"
COLLECTIONS = [BASE + "/collections/fast-wall-charger", BASE + "/collections/chargers", BASE + "/collections/car-chargers"]
DELAY = 1.0
KEEP = re.compile(r"^(a2[0-9]{3}|a12[01][a-z]|a1a0[0-9]|b2[0-9]{3}|b12[01][a-z])(-[a-z0-9-]+)?$")
DROP = re.compile(r"(^|-)(bundle|combo|f0|2-pack|3-pack|members-exclusive|blindbox|valorant|edition|wukong|trade)(-|$)|wireless|qi2|maggo|magsafe|"
                  r"magnetic|hub|cable|dock(?!ing-station)|power-bank|stand|pad", re.I)
MODEL = re.compile(r"^([AB][0-9][0-9A-Z]{3})", re.I)


def handles_from(text):
    return set(re.findall(r"https://www\.anker\.com/products/([a-z0-9][a-z0-9-]*)</loc>", text)) | set(re.findall(r'"handle":"([a-z0-9][a-z0-9-]*)"', text)) | \
        set(re.findall(r'href="/products/([a-z0-9][a-z0-9-]*)"', text))


class AnkerChargers:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES
    brand, brand_name = "anker", "Anker"

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        hs, ok = set(), 0
        for url in [SITEMAP] + COLLECTIONS:
            r = net.get(url, DELAY)
            if hasattr(r, "status_code") and r.status_code == 200:
                hs |= handles_from(r.text); ok += 1
        by_model = {}
        for h in sorted(hs, key=lambda x: (len(x) != 5, len(x), x)):
            if not KEEP.match(h) or DROP.search(h):
                continue
            by_model.setdefault(h[:5], h)
        refs = [C.Ref(SOURCE, h, f"{BASE}/products/{h}", {}) for m, h in sorted(by_model.items())]
        return C.Discovery(refs, bool(refs) and ok == 1 + len(COLLECTIONS), None if refs else "no handles", {"models": len(refs), "lists_ok": ok})

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


def _items(entry):
    """key_parameter entry -> [(name, value)]: valueList rows keep their names, a plain value is one nameless row."""
    if entry.get("valueList"):
        return [(G.clean(x.get("name")), G.lines_of(x.get("label"))) for x in entry["valueList"]]
    return [("", G.lines_of(entry.get("value")))]


def parse_page(snap, h):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [G.source(snap, "Anker US product page " + key)]
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        pr.absences.append({"key": "*", "reason": "no __NEXT_DATA__ (not a product page)", "source": "s1"})
        return pr
    pp = json.loads(m[1]).get("props", {}).get("pageProps", {})
    p = pp.get("product") or {}
    vs = [v for v in p.get("variants") or [] if v.get("sku") and not str(v["sku"]).upper().startswith(("BUNDLE", "COMBO"))]
    models = {MODEL.match(v["sku"])[1].upper() for v in vs if MODEL.match(v["sku"])}
    title = G.clean(p.get("title"))
    kind = G.charger_kind(title + " " + key)
    if len(models) != 1 or kind is None:
        pr.absences.append({"key": "*", "reason": f"not a single charger model page (models={sorted(models)}, kind={kind})", "source": "s1"})
        pr.fingerprints = {"models": sorted(models), "title": title}
        return pr
    model = models.pop()
    fam = re.match(r"Anker (Prime|Nano|PowerPort|PowerExpand|PowerDrive|Zolo|Charger)", title)
    colors, skus, gtins = [], [], []
    for v in vs:
        skus.append((v["sku"].upper(), G.clean(v.get("name"))))
        if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"])):
            gtins.append(str(v["barcode"]))
        for o in v.get("options") or []:
            if o.get("name", "").lower() in ("color", "colour") and o.get("values"):
                colors.append(o["values"][0]["label"])
    G.identity(pr, "anker", model, title, skus, gtins, basis="5-character model stem of the variant SKUs")
    rows = []
    kp = next(((v.get("metafields") or {}).get("infos", {}).get("key_parameter", {}).get("list") for v in vs
               if (v.get("metafields") or {}).get("infos", {}).get("key_parameter")), None) or []
    spec_items = (((pp.get("metafields") or {}).get("components") or {}).get("productSpecs") or {}).get("items") or []
    for it in spec_items:        # the page's own Specifications table first (it wins every first-row-wins key), then key_parameter
        lab = G.clean(it.get("name")).rstrip(":").strip()
        if lab:
            rows.append((lab, [("", ln) for ln in G.lines_of(it.get("presentation"))]))
    for e in kp:
        lab = G.clean(e.get("key")).rstrip(":")
        items = []
        for n, ls in _items(e):
            items += [(n, x) for x in ls] if ls else [(n, "")]
        rows.append((lab, items))
    table = " + ".join(x for x, y in (("Specifications table", spec_items), ("key_parameter list", kp)) if y) or "none"
    G.read_rows(pr, ADAPTER, snap, model, title, kind, rows, colors=colors, table=table, line=f"Anker {fam[1]}" if fam else None)
    if vs and vs[0].get("price"):
        G.emit(pr, ADAPTER, snap, model, "id.msrp_us", float(vs[0]["price"]), f"${vs[0]['price']} ({vs[0]['sku']}) at fetch", "variant price")
    pr.fingerprints.update({"raw": snap.snapshot, "variants": len(vs), "table": table})
    return pr


if __name__ == "__main__":
    _run.main(AnkerChargers())
