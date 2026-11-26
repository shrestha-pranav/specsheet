#!/usr/bin/env python3
"""Anker SOLIX US portable power station adapter v1 (contract ARCHITECTURE 15.5), category power-stations. Source = www.ankersolix.com (headless
Shopify + Next.js; www.anker.com/products/a17xx redirects here). /products.json is 404, so discovery reads the collection page.

discover : https://www.ankersolix.com/collections/power-stations (__NEXT_DATA__ / href handles) filtered to station handles (C/F/S series,
           PowerHouse 5xx, a17xx); refurbished, solar-panel, expansion-battery, kit, cover, gift, -edm/-flash-sale/-add-on and multi-pack (-2/-3)
           handles are packages or duplicates and are not discovered.
fetch    : product page HTML (gzip). 1 request per page, 1 req/s, crawler UA.
parse    : pure. __NEXT_DATA__ props.pageProps.product: the page title must say Power Station / PowerHouse. Unit variants = variants whose
           metafields.specs table is non-empty and whose SKU starts with A17 (A17631A1 'Go Without Solar'); variants B17631A9 / G17631A5
           (+ solar panel) are packages, recorded in fingerprints, never aliases. Model = Anker's 5-character model number shared by the unit
           variants (A1763); >1 = absence. Spec rows = the unit variant's metafields.specs {label: value}; '-' cells are absences.
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _powerbank as P
import _powerstation as PS
import _run

ID, VERSION, SOURCE = "ankersolix_stations", 9, "ankersolix-us-stations"     # v9 (A3-fix review-10 P1-3): shared _powerstation alternatives after the figure / trailing lower bounds never exact; v8 (A3-fix review-9 P1-3): shared _powerstation validates the qualification around each UPS figure (trailing bounds, between-ranges, lower bounds, approx -> unresolved); v7 (A3-fix review-8): shared _powerstation UPS bounds/ranges/exact prose identity; v6 (A2-dell r6): shared _powerstation labelled UPS bound -> up to N; v5 (A2-mon r5b): shared _powerstation capacity label widened, no Anker change; v4 (A2-mon r5): LiFePO\u2084 chemistry; ups.switchover_ms from description prose (coordinator ruling r5); r7: shared _powerbank changed (energy_basis pairs, case-insensitive Wh); v2: r6 shared _powerbank changed; station rules unchanged
CATEGORIES = {"power-stations"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.ankersolix.com"
COLLECTION = BASE + "/collections/power-stations"
DELAY = 1.0
KEEP = re.compile(r"^(?:c\d{3,4}x?(?:-dc)?(?:-gen-?2)?(?:-portable-power-station-us)?|c\d{3,4}x-dc-portable-power-station-us|f\d{4}(?:-plus)?|"
                  r"s\d{4}(?:-portable-power-station)?|5\d{2}|a17[0-9a-z]{2,6})$")


class AnkerSolixStations:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)
        self.adapter = ADAPTER

    def discover(self, checkpoint, net):
        r = net.get(COLLECTION, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"collection: {getattr(r, 'status_code', r)}", {})
        hs = set(re.findall(r'"handle":"([a-z0-9][a-z0-9-]*)"', r.text)) | set(re.findall(r'href="/products/([a-z0-9][a-z0-9-]*)"', r.text))
        refs = [C.Ref(SOURCE, h, f"{BASE}/products/{h}", {}) for h in sorted(hs) if KEEP.match(h)]
        return C.Discovery(refs, bool(refs), None if refs else "no handles", {"handles": len(hs), "products": len(refs)})

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


def parse_page(snap, page):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [L.source(snap, f"Anker SOLIX US store page {key}")]
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    prod = (((json.loads(m[1]).get("props") or {}).get("pageProps") or {}).get("product") or {}) if m else {}
    title = P.clean(prod.get("title")) or key
    pr.fingerprints = {"raw": snap.snapshot, "title": title, "final_url": snap.final_url}
    if not re.search(r"power ?station|powerhouse", title, re.I) or re.search(r"refurb|expansion battery|\+|bundle|kit\b", title, re.I):
        pr.absences.append({"key": "*", "reason": f"page is not a single power station: {title[:80]}", "source": "s1"})
        return pr
    unit, pkg = [], []
    for v in prod.get("variants") or []:
        sp = (v.get("metafields") or {}).get("specs") or {}
        sku = (v.get("sku") or "").strip().upper()
        (unit if sp and sku.startswith("A17") else pkg).append((v, sp, sku))
    if not unit:                     # older pages carry no metafields.specs: the unit SKU still names the model (specs stay absent)
        unit = [x for x in pkg if x[2].startswith("A17") and not re.search(r"solar|panel|\+|battery|bundle", (x[0].get("title") or x[0].get("name") or ""), re.I)]
        pkg = [x for x in pkg if x not in unit]
    pr.fingerprints["packages"] = [{"sku": s, "title": v.get("title") or v.get("name")} for v, _, s in pkg][:40]
    stems = {s[:5] for _, _, s in unit}
    if len(stems) != 1:
        pr.absences.append({"key": "*", "reason": f"no model identity: {len(stems)} unit-variant model stems ({', '.join(sorted(stems))})", "source": "s1"})
        return pr
    model = stems.pop()
    pr.identifiers.append(L.ident("mfr_model", model, "model", "anker"))
    pr.aliases.append({"text": title, "kind": "marketing_name"})
    for v, _, s in unit:
        if s != model:
            pr.identifiers.append(L.ident("mfr_sku", s, "configuration", "anker", role="alias", variant=v.get("title") or v.get("name")))
        if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"])):
            pr.identifiers.append(L.ident("gtin", str(v["barcode"]), "package", "GS1", role="alias"))
    rows = {}
    for x in (unit[0][1] or {}).values():
        if isinstance(x, dict) and x.get("label") and not PS.dash(PS.txt(str(x.get("value") or ""))):
            rows.setdefault(P.clean(x["label"]), PS.txt(str(x["value"])))
    pr.fingerprints["labels"] = list(rows)
    if not rows:
        PS.emit_ups_prose(pr, ADAPTER, snap, model, prod.get("descriptionHtml") or prod.get("description"), (title,))   # v4: UPS-prose ruling r5
        pr.absences.append({"key": "*", "reason": "no spec table (metafields.specs) on this page; figures only in images/prose", "source": "s1"})
        return pr
    pr.fingerprints["unmapped"] = {k: v[:80] for k, v in PS.emit_rows(pr, ADAPTER, snap, model, rows, "specs").items()}
    PS.emit_ups_prose(pr, ADAPTER, snap, model, prod.get("descriptionHtml") or prod.get("description"), (title,))   # v4: UPS-prose ruling r5
    pr.claims = list({c["id"]: c for c in reversed(pr.claims)}.values())[::-1]
    return pr


if __name__ == "__main__":
    _run.main(AnkerSolixStations())
