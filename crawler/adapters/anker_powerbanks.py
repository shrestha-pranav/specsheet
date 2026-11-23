#!/usr/bin/env python3
"""Anker US power-bank adapter v1 (contract ARCHITECTURE 15.5), category power-banks. Source = www.anker.com (headless Shopify + Next.js).

discover : https://www.anker.com/server-sitemap-index-products.xml (one urlset, all markets; only /products/<handle> US URLs kept) plus the
           /collections/power-banks page (its __NEXT_DATA__ handles), filtered to power-bank model handles: a1xxx/a110x (A12xx/A13xx/A16xx
           and A110x = Anker's power-bank model ranges; A17xx = SOLIX power stations, excluded) or a 'power-bank' slug. Bundles
           (bundle-/combo-/b110x 'with charging base'), '-f0' outlet clones, '-2-pack' and members-exclusive duplicates are dropped.
fetch    : product page HTML (~1.8 MB, __NEXT_DATA__ carries the Shopify product + per-variant metafields), gzip. 1 request per model.
parse    : pure. Model = the 5-character Anker model number shared by the non-bundle variant SKUs (A1695H11, A1695H41 -> A1695). Variant SKUs
           are colour/edition configurations (mfr_sku aliases); variants whose SKU starts with BUNDLE- are bundles and ignored. Specs come from
           the first non-bundle variant's metafields.infos.key_parameter list (Total Capacity / Total number of ports / Total Input / Total Output
           / Dimensions / Weight); Wh, pass-through, display, chemistry and recharge time only from the product's own description, key features
           and FAQ (never from related products in buildProps).
Traps    : 'Total Capacity' is the cell mAh (3.6-3.85 V), never the 5 V rated capacity. 'USB-C Cable / Port' merges two ports that share one
           PDO list. Title wattage may be total or per port; the Total Output row decides. A page can mix power bank and bundle variants.
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _powerbank as P
import _run

ID, VERSION, SOURCE = "anker_powerbanks", 3, "anker-us-powerbanks"     # v3: r6 shared _powerbank (repeated port row = one port); v2: review 3
CATEGORIES = {"power-banks"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.anker.com"
SITEMAP = BASE + "/server-sitemap-index-products.xml"
COLLECTION = BASE + "/collections/power-banks"
DELAY = 1.0
KEEP = re.compile(r"^(a1[2-6][0-9]{2}|a110[a-z])(-[a-z0-9-]+)?$")
DROP = re.compile(r"(^|-)(bundle|combo|f0|2-pack|3-pack|members-exclusive|boa|blindbox|wukong|trade)(-|$)|charging-base|gan-charger|fast-charger|wall-charger|ports-charger|wireless-charg|station|adapter|stand", re.I)
MODEL = re.compile(r"^(A1[0-9A-Z]{3})", re.I)


def handles_from(text):
    return set(re.findall(r"https://www\.anker\.com/products/([a-z0-9][a-z0-9-]*)</loc>", text)) | set(re.findall(r'"handle":"([a-z0-9][a-z0-9-]*)"', text)) | \
        set(re.findall(r'href="/products/([a-z0-9][a-z0-9-]*)"', text))


class AnkerPowerbanks:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        hs = set()
        for url in (SITEMAP, COLLECTION):
            r = net.get(url, DELAY)
            if hasattr(r, "status_code") and r.status_code == 200:
                hs |= handles_from(r.text)
        by_model = {}
        for h in sorted(hs, key=lambda x: (len(x) != 5, "power-bank" not in x, len(x), x)):   # bare model handle, then a power-bank slug
            if not KEEP.match(h) or DROP.search(h):
                continue
            by_model.setdefault(h[:5], h)            # shortest handle per model prefix (a1229 before a1229-xyz)
        refs = [C.Ref(SOURCE, h, f"{BASE}/products/{h}", {}) for m, h in sorted(by_model.items())]
        return C.Discovery(refs, bool(refs), None if refs else "no handles", {"models": len(refs)})

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


def _kv(entry):
    """key_parameter entry -> list of (name, label) or [('', value)]."""
    if entry.get("valueList"):
        return [(P.clean(x.get("name")), P.clean(x.get("label"))) for x in entry["valueList"]]
    return [("", P.clean(entry.get("value")))]


def parse_page(snap, h):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [L.source(snap, "Anker US product page " + key)]
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        pr.absences.append({"key": "*", "reason": "no __NEXT_DATA__ (not a product page)", "source": "s1"})
        return pr
    pp = json.loads(m[1]).get("props", {}).get("pageProps", {})
    p = pp.get("product") or {}
    vs = [v for v in p.get("variants") or [] if v.get("sku") and not str(v["sku"]).upper().startswith(("BUNDLE", "COMBO"))]
    models = {MODEL.match(v["sku"])[1].upper() for v in vs if MODEL.match(v["sku"])}
    title = P.clean(p.get("title"))
    if len(models) != 1 or not re.search(r"power ?bank|powercore|battery|portable charger|maggo|fusion", title + " " + key, re.I):
        pr.absences.append({"key": "*", "reason": f"not a single power-bank model page (models={sorted(models)})", "source": "s1"})
        pr.fingerprints = {"models": sorted(models), "title": title}
        return pr
    model = models.pop()
    fam = re.match(r"Anker (Prime|Nano|Zolo|MagGo|PowerCore|Laptop)", title)
    pr.identifiers.append(L.ident("mfr_model", model, "model", "anker", series=fam[1] if fam else None))
    pr.aliases.append({"text": title, "kind": "marketing_name"})
    colors = []
    for v in vs:
        pr.identifiers.append(L.ident("mfr_sku", v["sku"].upper(), "configuration", "anker", role="alias", variant=P.clean(v.get("name"))))
        if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"])):
            pr.identifiers.append(L.ident("gtin", str(v["barcode"]), "package", "GS1", role="alias"))
        for o in v.get("options") or []:
            if o.get("name", "").lower() in ("color", "colour") and o.get("values"):
                colors.append(o["values"][0]["label"])

    def add(k, val, raw, label, cond=None, quote=None):
        P.emit(pr, ADAPTER, snap, k, val, raw, label, model, cond, quote)

    kp = next(((v.get("metafields") or {}).get("infos", {}).get("key_parameter", {}).get("list") for v in vs
               if (v.get("metafields") or {}).get("infos", {}).get("key_parameter")), None) or []
    rows = {P.clean(e.get("key")).rstrip(":"): _kv(e) for e in kp}
    comps = ((pp.get("metafields") or {}).get("components") or {})
    for it in (comps.get("productSpecs") or {}).get("items") or []:      # the page's own Specifications table wins over key_parameter
        lab = P.clean(it.get("name")).rstrip(":").strip()
        items = []
        lines_ = re.split(r"<\s*/?\s*br\s*/?>|\n", it.get("presentation") or "")
        lines_ = [x for ln in lines_ for x in re.split(r"(?<=\))\s+(?=[A-Z][A-Za-z /-]{2,30}:)", P.clean(ln))]   # '(30W Max) Wireless Charger: 5W'
        for line in lines_:
            line = P.clean(line)
            if not line:
                continue
            mm = re.match(r"^([A-Za-z][A-Za-z0-9 /+&()-]{1,40}?)\s*:\s*(.+)$", line)
            items.append((mm[1].strip(), mm[2].strip()) if mm and not re.match(r"^\d", mm[1]) else ("", line))
        if lab and items:
            rows[lab] = items
    add("gen.product_line", f"Anker {fam[1]}" if fam else None, title, "title")
    add("gen.form_factor", P.form_factor(title), title, "title (derived)")
    add("gen.color", list(dict.fromkeys(colors)), " | ".join(dict.fromkeys(colors)), "variant option Color")
    unmapped = {}
    for lab, items in rows.items():
        raw = " | ".join(f"{n}: {v}" if n else v for n, v in items)
        ll = lab.lower()
        if ll in ("total capacity", "capacity", "battery capacity"):
            vm = re.search(r"(\d+(?:\.\d+)?)\s*V(?:DC)?\b", raw)
            if vm and float(vm[1]) >= 5:      # '5,000mAh, 7.4VDC / 37Wh (Two Cells in Series)': pack mAh at series voltage, not cell mAh
                pass
            else:
                add("cap.cell_mah", P.mah(raw), raw, lab)
                add("cap.cell_voltage", float(vm[1]) if vm else None, raw, lab)
            add("cap.energy_wh", P.energy(raw), raw, lab)
        elif ll == "total number of ports":
            c = a = 0; cable = []
            for n, v in items:
                k = int(v) if v.isdigit() else 1
                t = P.port_type(n)
                if t == "usb_a":
                    a += k
                elif t in ("cable_c", "cable_lightning"):
                    cable.append(t)
                elif t == "usb_c":
                    c += k
            add("out.usb_c_count", c, raw, lab); add("out.usb_a_count", a, raw, lab)
            add("out.builtin_cable", ("usb_c" if "cable_c" in cable else "lightning") if cable else "none", raw, lab)
        elif ll in ("number of usb-c ports", "number of usb-a ports"):
            n_ = re.match(r"\d+", raw)
            add("out.usb_c_count" if "usb-c" in ll else "out.usb_a_count", int(n_[0]) if n_ else None, raw, lab)
        elif ll in ("total wattage", "total output") and all(not n for n, _ in items):
            tm = re.search(P.NUM + r"\s*W", raw)
            add("out.max_total_w", P.fnum(tm[1]) if tm else None, raw, lab, quote=f"all-ports output: the maker's labelled '{lab}' row")
        elif ll in ("recharging time", "recharge time"):
            hm = re.search(P.NUM + r"\s*(?:hours?|hrs?)", raw, re.I)
            add("in.recharge_time_h", P.fnum(hm[1]) if hm else None, raw, lab)
        elif ll in ("total input", "input", "usb-c input", "input battery") or (ll.endswith("input") and "charger" not in ll):
            fx, pps, mw, _ = P.pdos(raw)
            add("in.max_w", mw, raw, lab); add("in.pdos", (fx + (f"; PPS {pps}" if pps else "")).strip("; ") or None, raw, lab)
        elif ll in ("total output", "output", "usb-c output", "output battery mode") or ll.startswith("total output (battery"):
            ports, tot, combos = [], None, []
            for n, v in items:
                if n.lower().startswith("total"):
                    tot = P.fnum(re.search(P.NUM + r"\s*W", v)[1]) if re.search(P.NUM + r"\s*W", v) else None
                    continue
                fx, pps, mw, _ = P.pdos(v)
                if not n:          # a nameless line in a 'Total Output' row is the total ('140W Max'); elsewhere it is not read as one
                    if ll.startswith("total"):
                        tot = tot if tot is not None else mw
                    continue
                if re.match(r"(?i)combined\b", n) or "+" in n:       # 'Combined USB-C Port, USB-C Cable and USB-A Port: 22.5W Max' = a combination
                    combos.append((n, v))
                    continue
                ports.append({"name": n or "output", "type": P.port_type(n), "direction": "out", "max_w": mw, "fixed_pdos": fx or None, "pps": pps or None})
            if tot is not None:
                add("out.max_total_w", tot, raw, lab, quote=f"all-ports output: the maker's labelled '{lab}' total")
            else:          # review 3: only a printed combination naming every port is an all-ports figure; one listed port is not a total
                t, toks, why = P.all_port_total([x["name"] for x in ports], combos)
                add("out.max_total_w", t if t is not None else (P.Unresolved(why) if why else None), raw, lab,
                    quote=("all-ports output: " + " + ".join(toks)) if toks else None)
            single = [x["max_w"] for x in ports if x["max_w"] and x["type"] != "wireless"]
            add("out.max_single_port_w", max(single) if single else None, raw, lab)
            add("out.ports", ports, raw, lab)
            add("pd.pps", True if any(x["pps"] and x["type"] in ("usb_c", "cable_c") for x in ports) else None, raw, lab)
            vmax = [P.pdos(v)[3] for n, v in items if not n.lower().startswith("total")]
            add("pd.max_fixed_voltage", max([x for x in vmax if x] or [0]) or None, raw, lab)
        elif ll.startswith("dimensions"):
            add("phys.dimensions", P.dims_mm(raw), raw, lab)
            if "weight" in ll:
                add("phys.weight", P.grams(raw.split("Weight", 1)[-1]), raw, lab)
        elif ll == "weight":
            add("phys.weight", P.grams(raw), raw, lab)
        elif "wireless" in ll:
            std, w = P.wireless(lab + " " + raw)
            add("out.wireless_w", w or (P.fnum(re.search(P.NUM + r"\s*W", raw)[1]) if re.search(P.NUM + r"\s*W", raw) else None), raw, lab)
        else:
            unmapped[lab] = raw[:100]
    if not any(c["key"] == "cap.cell_mah" for c in pr.claims):
        add("cap.class_mah", P.mah(title), title, "title (marketing capacity, never cell mAh)")
    std, w = P.wireless(title)
    add("out.wireless_standard", std if std != "magsafe_compatible" or "maggo" in (title + key).lower() else None, title, "title")
    if w and not any(c["key"] == "out.wireless_w" for c in pr.claims):
        add("out.wireless_w", w, title, "title")
    # the product's own prose: description, key features, FAQ (not buildProps: those are related products)
    feats = ((p.get("metafields") or {}).get("productInfos") or {}).get("key_features", {}).get("list") or []
    faq = ((pp.get("metafields") or {}).get("components") or {}).get("faq", {}).get("items") or []
    prose = " ".join([P.clean(p.get("description"))] + [P.clean(f"{f.get('key')}: {f.get('value')}") for f in feats] +
                     [P.clean(f"{q.get('question')} {q.get('answer')}") for q in faq])
    whm = re.search(r"(?:equal to|equivalent to|rated (?:energy|capacity) of|\(|/)\s*(\d{1,3}(?:\.\d+)?)\s*Wh\b", prose)
    if whm and not any(c["key"] == "cap.energy_wh" and c["status"] == "known" for c in pr.claims):
        i = whm.start()
        add("cap.energy_wh", P.fnum(whm[1]), prose[max(0, i - 120):i + 40], "FAQ / description")
    if (cv := re.search(r"(\d\.\d{1,2})\s*V\b[^.]{0,30}(?:cell|nominal)|(?:cell|nominal)[^.]{0,30}?(\d\.\d{1,2})\s*V\b", prose, re.I)):
        add("cap.cell_voltage", float(cv[1] or cv[2]), cv[0], "FAQ / description")
    pt = P.passthrough(prose)
    if pt is not None:
        i = re.search(r"pass-?through", prose, re.I)
        add("in.passthrough", pt, prose[max(0, i.start() - 100):i.start() + 120] if i else prose[:200], "FAQ / description")
    d = P.display(title + " " + prose)
    add("phys.display", d, title if P.display(title) else prose[:200], "title / description")
    ch = P.chemistry(prose)
    if ch:
        i = re.search(r"lifepo4|semi-?solid|polymer|lithium|li-?ion", prose, re.I)
        add("bat.chemistry", ch, prose[max(0, i.start() - 60):i.start() + 80], "FAQ / description")
    rh, lit = P.recharge_h(prose)
    add("in.recharge_time_h", rh, lit, "FAQ / description")
    if re.search(r"TSA|airline|carry-on|airplane|on a plane|flight", prose, re.I) and (wv := next((c["value"] for c in pr.claims if c["key"] == "cap.energy_wh" and c["status"] == "known"), None)):
        add("cap.under_100wh", wv < 100, f"rated {wv} Wh (stated); airline limit 100 Wh", "derived from cap.energy_wh")
    if vs and vs[0].get("price"):
        L.add(pr, ADAPTER, snap, "id.msrp_us", float(vs[0]["price"]), f"${vs[0]['price']} ({vs[0]['sku']}) at fetch", "model_code", model, "variant price")
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "variants": len(vs), "unmapped": unmapped}
    return pr


if __name__ == "__main__":
    _run.main(AnkerPowerbanks())
