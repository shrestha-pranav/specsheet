#!/usr/bin/env python3
"""Shopify-store power-bank adapters v1 (contract ARCHITECTURE 15.5), category power-banks: INIU (iniushop.com), CUKTECH (www.cuktech.com),
UGREEN (us.ugreen.com). One module, one class per source.

discover : {base}/products.json?limit=250&page=N (Shopify public catalogue; robots allows /products) -> products whose title says power bank /
           portable charger; bundles ('Bundle', '+', 'combo', '2-pack', gift sets), wireless chargers and power stations dropped. One Ref per handle.
fetch    : product page HTML (spec block lives in theme sections, not in body_html) + {base}/products/<handle>.json (variants: SKU, barcode,
           colour option). Stored together as one gzip JSON blob {"page":..., "product":...}. 2 requests per product, 1 req/s per host.
parse    : pure. The spec block = text after the brand's marker (INIU 'Tech Specs' / 'SPECS', CUKTECH 'SPEC', UGREEN 'Specs' / 'Specifications')
           split on a fixed label list. Model per brand: INIU 'Product Model' (P63-E1); CUKTECH 'Model:' (PB200N); UGREEN 'SKU' item number (25188;
           UGREEN's store prints no other model). Pages without a model in the block fall back to a model token in the handle (INIU b41/p50),
           else are recorded as absences (no model -> no entity). Colour variants = mfr_sku aliases of the one model.
Traps    : UGREEN 'Power Capacity: 20,000mAh/72Wh (14.4V*5000mAh)' = cell mAh at 3.6 V AND a 4S pack figure; only the first mAh is cell mAh.
           CUKTECH 'Cell Capacity: 74Wh/75.5Wh 7.4V' = typical/rated energy of a 2S pack; the lower figure is kept with both in the literal.
           INIU 'Total(OUT1+OUT2+OUT3): 15W' is the all-ports total, not the single-port max. Several INIU pages describe two models (P41 / P41-E1).
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _powerbank as P
import _run

VERSION = 1
CATEGORIES = {"power-banks"}
DELAY = 1.0
PB = re.compile(r"power ?bank|portable charger|battery pack", re.I)
NOT = re.compile(r"bundle|\+|combo|2-pack|2 pack|gift set|kit\b|power station|wireless charger with stand|fan\b|car jump|case\b", re.I)
LABELS = ["Product Model", "Model", "SKU", "Sku", "Category", "Dimensions(mm)", "Product Dimensions", "Dimensions", "Weight(g)", "Item Weight", "Weight",
          "Total Capacity", "Battery Capacity", "Power Capacity", "Rated Capacity", "Cell Capacity", "Battery Type", "Cell Type", "Battery Cell",
          "Supported Protocols", "Supported Protocol", "Support Protocol", "Protocols", "Total Output", "Output", "Input", "Ports", "Indicator", "Display",
          "Wireless Charging", "Wireless Output", "Multi-port", "Product with feature", "Cable Spec", "Compatible Models", "Compatibility List",
          "Compatibility", "Brand", "Marca", "Colour", "Color", "Special Feature", "Special feature", "Operating Temp", "Surge Suppression",
          "Efficiency", "What's in the Box", "Recommended uses for product", "Connector Type", "Compatible Devices"]
STOP = re.compile(r"Compatible Models|Compatibility List|What.s in the Box|Learn More|Customer Reviews|You May Also Like|Reviews|Left New Releases|FAQ\b")
LABRX = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(x) for x in sorted(LABELS, key=len, reverse=True)) + r")\s*[:：]?\s*")


class _Shop:
    id = source_id = base = marker = brand = None
    version, categories = VERSION, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(self.source_id)
        self.adapter = f"{self.id}@{self.version}"

    def discover(self, checkpoint, net):
        refs, page = [], 1
        while page <= 10:
            r = net.get(f"{self.base}/products.json?limit=250&page={page}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery(refs, False, f"products.json page {page}: {getattr(r, 'status_code', r)}", {"page": page})
            ps = r.json().get("products") or []
            if not ps:
                break
            for p in ps:
                t = p.get("title") or ""
                if PB.search(t) and not NOT.search(t) and not NOT.search(p["handle"]):
                    refs.append(C.Ref(self.source_id, p["handle"], f"{self.base}/products/{p['handle']}", {"title": t}))
            page += 1
        return C.Discovery(refs, True, None, {"products": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, self.adapter, ".json.gz")
            return s
        j = net.get(ref.url + ".json", DELAY)
        prod = j.json().get("product") if (hasattr(j, "status_code") and j.status_code == 200) else None
        body = json.dumps({"page": r.text, "product": prod}).encode()
        s = C.Snapshot(self.store.put(gzip.compress(body, 6, mtime=0), ".json.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, self.adapter, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        return parse_shop(self, snap, d["page"], d.get("product") or {})

    def model_from(self, rows, handle):
        return None


class IniuPowerbanks(_Shop):
    id, source_id, base, brand, marker = "iniu_powerbanks", "iniu-us-powerbanks", "https://iniushop.com", "iniu", r"Tech Specs|\bSPECS\b"

    def model_from(self, rows, handle):
        m = rows.get("Product Model") or rows.get("Model")
        if m and re.match(r"^[A-Z]{1,3}-?\d{1,3}[A-Z]?(-[A-Z]\d)?\b", m):
            return re.match(r"^[A-Z]{1,3}-?\d{1,3}[A-Z]?(-[A-Z]\d)?", m)[0]
        h = re.search(r"(?:^|-)(bi-b\d{2}|b\d{2}|p\d{2,3}l?(?:-[ep]\d)?)(?:-|$)", handle)
        return h[1].upper() if h else None


class CuktechPowerbanks(_Shop):
    id, source_id, base, brand, marker = "cuktech_powerbanks", "cuktech-us-powerbanks", "https://www.cuktech.com", "cuktech", r"\bSPEC\b"

    def model_from(self, rows, handle):
        m = rows.get("Model")
        return re.match(r"^[A-Z]{1,3}\d{2,3}[A-Z]{0,3}", m)[0] if m and re.match(r"^[A-Z]{1,3}\d{2,3}[A-Z]{0,3}", m) else None


class UgreenPowerbanks(_Shop):
    id, source_id, base, brand, marker = "ugreen_powerbanks", "ugreen-us-powerbanks", "https://us.ugreen.com", "ugreen", r"\bSpecs\b|\bSpecifications\b"

    def model_from(self, rows, handle):
        m = rows.get("SKU") or rows.get("Sku")
        mm = re.match(r"^(\d{5}A?|PB\d{3})(?:SR)?\b(?!\s*\+)", m or "")     # 75982SR = Honkai Star Rail edition of 75982 (identity.md rule 1)
        return mm[1] if mm else None


def page_text(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    return P.clean(h)


def spec_rows(ad, text):
    """-> (rows {label: value}, block literal). The first marker occurrence that is followed by a known label within 40 chars."""
    for m in re.finditer(ad.marker, text):
        blk = text[m.end(): m.end() + 2500]
        first = LABRX.search(blk)
        if not first or first.start() > 40:
            continue
        stop = STOP.search(blk, first.end())
        blk = blk[first.start(): stop.start() if stop else len(blk)]
        ms = list(LABRX.finditer(blk))
        rows = {}
        for i, x in enumerate(ms):
            v = blk[x.end(): ms[i + 1].start() if i + 1 < len(ms) else len(blk)].strip(" ;,")
            rows.setdefault(x.group(1), v)
        if len(rows) >= 3:
            return rows, blk
    return {}, ""


def parse_shop(ad, snap, page, prod):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [L.source(snap, f"{ad.brand.upper()} US store page {key}")]
    text = page_text(page)
    rows, blk = spec_rows(ad, text)
    title = P.clean(prod.get("title")) or snap.ref.hints.get("title") or key
    model = ad.model_from(rows, key)
    if not model:
        pr.absences.append({"key": "*", "reason": "no model number in the spec block or handle", "source": "s1"})
        pr.fingerprints = {"labels": list(rows), "title": title}
        return pr
    pr.identifiers.append(L.ident("mfr_model", model, "model", ad.brand))
    pr.aliases.append({"text": title, "kind": "marketing_name"})
    colors = []
    for v in prod.get("variants") or []:
        if v.get("sku") and v["sku"].upper() != model.upper():
            pr.identifiers.append(L.ident("mfr_sku", v["sku"].upper(), "configuration", ad.brand, role="alias", variant=v.get("title")))
        if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"])):
            pr.identifiers.append(L.ident("gtin", str(v["barcode"]), "package", "GS1", role="alias"))
    for o in prod.get("options") or []:
        if o.get("name", "").lower() in ("color", "colour"):
            colors += [x for x in o.get("values") or [] if x.lower() != "default title"]

    def add(k, val, raw, label):
        L.add(pr, ad.adapter, snap, k, val, raw, "model_code", model, label)

    add("gen.form_factor", P.form_factor(title), title, "title (derived)")
    add("gen.color", colors, " | ".join(colors), "variant option Color")
    cap = rows.get("Total Capacity") or rows.get("Power Capacity") or rows.get("Battery Capacity")
    if cap:
        vm = re.search(r"/\s*(\d\.\d{1,2})\s*V\b", cap)
        add("cap.cell_mah", P.mah(cap), cap, "Capacity")
        add("cap.cell_voltage", float(vm[1]) if vm else None, cap, "Capacity")
        add("cap.energy_wh", P.wh(cap), cap, "Capacity")
    if (cc := rows.get("Cell Capacity")):
        whs = [P.fnum(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*[Ww]h\b", cc)]
        add("cap.energy_wh", min(whs) if whs else None, cc, "Cell Capacity")
        vm = re.search(r"(\d+(?:\.\d+)?)\s*V\b", cc)
        if vm and float(vm[1]) < 5:
            add("cap.cell_voltage", float(vm[1]), cc, "Cell Capacity")
    if (rc := rows.get("Rated Capacity")):
        n = P.mah(rc)
        if n and re.search(r"\(\s*\d", rc):             # CUKTECH/INIU print the rated (5 V) capacity with its basis in brackets
            add("cap.rated_mah", n, rc, "Rated Capacity")
            b = re.search(r"\(([^)]*)\)", rc)
            add("cap.rated_basis", b[1].strip() if b else None, rc, "Rated Capacity")
        elif n and ad.brand == "cuktech" and not cap:
            add("cap.cell_mah", n, rc, "Rated Capacity (CUKTECH: cell mAh)")
    out = rows.get("Output") or ""
    if out:
        ports, combo, total = P.ports_from(out, "out")
        tot = rows.get("Total Output")
        if tot and re.search(P.NUM + r"\s*W", tot):
            total = P.fnum(re.search(P.NUM + r"\s*W", tot)[1])
        add("out.ports", ports, out, "Output")
        add("out.simultaneous", combo, out, "Output")
        single = [p["max_w"] for p in ports if p["max_w"] and p["type"] != "wireless"]
        add("out.max_single_port_w", max(single) if single else None, out, "Output")
        add("out.max_total_w", total if total is not None else (single[0] if len(ports) == 1 and single else None), out, "Output")
        add("pd.pps", True if any(p["pps"] and p["type"] in ("usb_c", "cable_c", None) for p in ports) or re.search(r"\bPPS\b", rows.get("Supported Protocol", "") + rows.get("Protocols", "")) else None, out, "Output")
        vmax = [P.pdos(p["fixed_pdos"] or "")[3] for p in ports]
        add("pd.max_fixed_voltage", max([x for x in vmax if x] or [0]) or None, out, "Output")
    inp = rows.get("Input") or ""
    if inp:
        fx, pps, mw, _ = P.pdos(inp)
        ip, _, _ = P.ports_from(inp, "in")
        mws = [p["max_w"] for p in ip if p["max_w"]]
        add("in.max_w", max(mws) if mws else mw, inp, "Input")
        add("in.pdos", fx or None, inp, "Input")
    pro = rows.get("Supported Protocol") or rows.get("Supported Protocols") or rows.get("Support Protocol") or rows.get("Protocols")
    if pro:
        add("pd.protocols", sorted({x.strip() for x in re.split(r"[/,]|\betc\.?", re.sub(r"(Input|Output)\s*[:：]|USB-[AC]\d?(/C\d)?\s*:", " ", pro)) if x.strip() and len(x.strip()) < 20}), pro, "Protocols")
    if (w := rows.get("Weight") or rows.get("Weight(g)") or rows.get("Item Weight")):
        add("phys.weight", P.grams(w) if not re.fullmatch(r"\d+(\.\d+)?", w.strip()) else P.fnum(w.strip()), w, "Weight")
    if (dm := rows.get("Dimensions") or rows.get("Dimensions(mm)") or rows.get("Product Dimensions")):
        dd = P.dims_mm(dm) or (lambda m: {"w": P.fnum(float(m[1]) * 10), "d": P.fnum(float(m[2]) * 10), "h": P.fnum(float(m[3]) * 10), "unit": "mm"} if m else None)(
            re.search(P.NUM + r"\s*[x*×]\s*" + P.NUM + r"\s*[x*×]\s*" + P.NUM + r"\s*cm", dm))
        add("phys.dimensions", dd, dm, "Dimensions")
    bt = rows.get("Battery Type") or rows.get("Cell Type") or rows.get("Battery Cell")
    if bt:
        add("bat.chemistry", P.chemistry(bt), bt, "Battery Type")
    disp = rows.get("Indicator") or rows.get("Display") or ""
    add("phys.display", P.display(disp + " " + title) or ("digital_percent" if re.search(r"digital|LED Digital|TFT", disp) else None), disp or title, "Indicator / title")
    std, ww = P.wireless(title + " " + (rows.get("Wireless Charging") or ""))
    if (rows.get("Wireless Charging") or "").strip().upper() in ("N", "NO"):
        std, ww = None, None
    add("out.wireless_standard", std, title, "title")
    add("out.wireless_w", ww, title, "title")
    pt = P.passthrough(text)
    if pt is not None:
        i = re.search(r"pass-?through", text, re.I)
        add("in.passthrough", pt, text[max(0, i.start() - 80):i.start() + 100] if i else "", "page text")
    v0 = next((v for v in prod.get("variants") or [] if v.get("price")), None)
    if v0:
        add("id.msrp_us", float(v0["price"]), f"${v0['price']} ({v0.get('sku')}) at fetch", "variant price")
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "block": blk[:300],
                       "unmapped": {k: v[:100] for k, v in rows.items() if k in ("Multi-port", "Product with feature", "Cable Spec", "Efficiency")}}
    if (mp := rows.get("Multi-port")):
        add("out.simultaneous", mp, mp, "Multi-port")
    return pr


if __name__ == "__main__":
    which = {c.source_id: c for c in (IniuPowerbanks, CuktechPowerbanks, UgreenPowerbanks)}
    src = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in which else "iniu-us-powerbanks"
    _run.main(which[src]())
