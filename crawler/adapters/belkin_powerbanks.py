#!/usr/bin/env python3
"""Belkin US power-bank adapter v1 (contract ARCHITECTURE 15.5), category power-banks. Source = www.belkin.com (Salesforce Commerce Cloud).

discover : https://www.belkin.com/sitemap-variant_products_us_001.xml (US variant URLs /p/<slug>/<SKU>.html; robots allows /p/) filtered to
           slugs that say power-bank (camera grips, Vision Pro battery holders dropped). Variant SKUs are grouped by model number = the first
           3 letters + 3 digits (BPB012btBK, BPB012btWH -> BPB012); one Ref per model, url = its first variant, hints.skus = all colour SKUs.
fetch    : that one variant page (~600 KB), gzip. 1 request per model.
parse    : pure. JSON-LD ProductGroup (name, description, productGroupID P-BPB012) + the 'Technical Specifications' table
           (span.spec-attr-label + span.spec-attr-value) + the 'At a Glance' bullets. Model = productGroupID minus 'P-' when it matches the URL
           model, else the URL model. Colour SKUs from the sitemap are mfr_sku aliases.
Traps    : Belkin's table has no capacity row; the capacity is the title class ('10K') -> cap.class_mah, never cap.cell_mah. A real mAh/Wh
           is taken only from 'At a Glance' text. 'Wattage' is the maximum output (single port or total, not distinguished) -> out.max_output_w.
           BBA0xx and BPB0xx pages can share one slug (Amazon/retailer model numbers); they stay separate models (identity.md).
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _powerbank as P
import _run

ID, VERSION, SOURCE = "belkin_powerbanks", 3, "belkin-us-powerbanks"     # v3: r6 shared _powerbank (repeated port row = one port); v2: shared _powerbank parser changed (review 3); Belkin rules unchanged
CATEGORIES = {"power-banks"}
ADAPTER = f"{ID}@{VERSION}"
SITEMAP = "https://www.belkin.com/sitemap-variant_products_us_001.xml"
DELAY = 1.0
LOC = re.compile(r"<loc>(https://www\.belkin\.com/p/([a-z0-9.-]+)/([A-Za-z0-9-]+)\.html)</loc>")
MODEL = re.compile(r"^([A-Z]{3}\d{3})")


class BelkinPowerbanks:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        by = {}
        for url, slug, sku in LOC.findall(r.text):
            if "power-bank" not in slug or re.search(r"camera-grip|battery-holder|vision-pro", slug):
                continue
            m = MODEL.match(sku.upper())
            if m:
                by.setdefault(m[1], []).append((url, sku, slug))
        refs = []
        for model, vs in sorted(by.items()):
            vs.sort(key=lambda x: ("-" in x[1], x[1]))
            refs.append(C.Ref(SOURCE, model.lower(), vs[0][0], {"skus": [v[1] for v in vs], "slug": vs[0][2]}))
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
    pr.sources = [L.source(snap, "Belkin US product page " + key.upper())]
    j = jsonld(h)
    url_model = key.upper()
    gid = str(j.get("productGroupID") or "").upper().removeprefix("P-")
    model = gid if gid and MODEL.match(gid) and gid[:6] == url_model else url_model
    name = P.clean(j.get("name"))
    tm = re.search(r"<title>(.*?)</title>", h, re.S)
    title = P.clean(tm[1]).split("|")[0].strip() if tm else name
    if not re.search(r"power ?bank|battery", f"{name} {title} {snap.ref.hints.get('slug', '')}", re.I):
        pr.absences.append({"key": "*", "reason": "not a power bank page", "source": "s1"})
        return pr
    pr.identifiers.append(L.ident("mfr_model", model, "model", "belkin"))
    for t in dict.fromkeys(x for x in (title, name) if x):
        pr.aliases.append({"text": t, "kind": "marketing_name"})
    for sku in snap.ref.hints.get("skus") or []:
        pr.identifiers.append(L.ident("mfr_sku", sku.upper(), "configuration", "belkin", role="alias"))
    hv = j.get("hasVariant")
    for v in (hv if isinstance(hv, list) else [hv] if hv else []):
        g = str(v.get("gtin13") or v.get("gtin12") or v.get("gtin") or "")
        if re.fullmatch(r"\d{12,14}", g):
            pr.identifiers.append(L.ident("gtin", g, "package", "GS1", role="alias"))
    rows = {}
    for m in re.finditer(r'<span class="spec-attr-label">(.*?)</span>\s*<ul class="spec-attr-list">(.*?)</ul>', h, re.S):
        rows.setdefault(P.clean(m[1]), " | ".join(P.clean(x) for x in re.findall(r'<span class="spec-attr-value">(.*?)</span>', m[2], re.S)))
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    text = P.clean(s)
    gi = text.find("At a Glance")
    glance = text[gi: gi + 1500] if gi >= 0 else ""
    glance = glance.split("What’s in the Box")[0].split("What's in the Box")[0]

    def add(k, val, raw, label):
        L.add(pr, ADAPTER, snap, k, val, raw, "model_code", model, label)

    fam = re.match(r"(BoostCharge Pro|BoostCharge|UltraCharge Pro|UltraCharge)", title)
    add("gen.product_line", f"Belkin {fam[1]}" if fam else None, title, "title")
    add("gen.form_factor", P.form_factor(title + " " + snap.ref.hints.get("slug", "")), title, "title (derived)")
    km = re.search(r"\b(\d{1,2}(?:\.\d)?)K\b", f"{title} {name} {snap.ref.hints.get('slug', '').replace('-k', 'K').upper()}")
    add("cap.class_mah", int(float(km[1]) * 1000) if km else None, km[0] if km else "", "title class (K)")
    if (mm := re.search(r"(\d{1,3},\d{3}|\d{4,5})\s*mAh", glance)):
        add("cap.cell_mah", int(mm[1].replace(",", "")), glance[max(0, mm.start() - 80): mm.end() + 40], "At a Glance")
    if (wm := re.search(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*Wh\b", glance)):
        add("cap.energy_wh", P.fnum(wm[1]), glance[max(0, wm.start() - 80): wm.end() + 40], "At a Glance")
    for lab, val in rows.items():
        ll = lab.lower()
        if ll == "number of usb-a ports":
            add("out.usb_a_count", int(val) if val.isdigit() else None, val, lab)
        elif ll == "number of usb-c ports":
            add("out.usb_c_count", int(val) if val.isdigit() else None, val, lab)
        elif ll in ("wattage", "max power"):
            w = re.search(P.NUM + r"\s*W\b", val)
            add("out.max_output_w", P.fnum(w[1]) if w else None, val, lab)
        elif ll.startswith("dimensions"):
            add("phys.dimensions", P.dims_mm(val), val, lab)
        elif ll == "integrated/included cable length":
            add("out.cable_note", val, val, lab)
        elif ll == "weight":
            add("phys.weight", P.grams(val), val, lab)
    if re.search(r"integrated cable|built-in cable|integrated usb-c", title + " " + snap.ref.hints.get("slug", "").replace("-", " "), re.I):
        add("out.builtin_cable", "usb_c", title, "title")
    std, ww = P.wireless(title + " " + glance)
    add("out.wireless_standard", std, title, "title / At a Glance")
    add("out.wireless_w", ww, title, "title / At a Glance")
    d = P.display(title + " " + glance)
    add("phys.display", d, title, "title / At a Glance")
    if re.search(r"TSA|carry-on", glance):
        i = re.search(r"TSA|carry-on", glance).start()
        add("cap.under_100wh", True, glance[max(0, i - 60): i + 60], "At a Glance (manufacturer TSA statement)")
    pt = P.passthrough(glance)
    add("in.passthrough", pt, glance[:200] if pt is not None else "", "At a Glance")
    if re.search(r"boostsolid|semi-?solid", title + " " + glance, re.I):
        add("bat.chemistry", "semi_solid", title, "title (BoostSolid cell)")
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "unmapped": {k: v[:100] for k, v in rows.items() if k in ("Certifications", "Inputs", "Output", "USB-A Output")}}
    return pr


if __name__ == "__main__":
    _run.main(BelkinPowerbanks())
