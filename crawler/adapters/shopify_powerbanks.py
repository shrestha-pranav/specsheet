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

VERSION = 5       # v5 (A2 preset fill, UGREEN only): per-port "USB-C1 Output:" rows and the per-port Supported Protocol block (pd.pps true; false only from a complete per-port enumeration); v4: r7 shared _powerbank (labelled Wh pairs keep both with energy_basis, case-insensitive Wh); v3: r6 a repeated identical port row is one port (_powerbank.port_segments); v2: review 3 (all-port totals, capacity bases, rated load, page/label identity conflicts)
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

    def handle_model(self, handle):         # brands whose handles name a model token (INIU p41-e1, UGREEN 35340); CUKTECH handles name the line
        return None

    def sku_model(self, sku):
        return None


class IniuPowerbanks(_Shop):
    id, source_id, base, brand, marker = "iniu_powerbanks", "iniu-us-powerbanks", "https://iniushop.com", "iniu", r"Tech Specs|\bSPECS\b"

    def handle_model(self, handle):
        h = re.search(r"(?:^|-)(bi-b\d{2}|b\d{2}|p\d{2,3}l?(?:-[ep]\d)?)(?:-|$)", handle)
        return h[1].upper() if h else None

    def sku_model(self, sku):
        m = re.match(r"D01-([A-Z]{1,3}\d{1,3}L?(?:-[EP]\d)?)(?:-|$)", (sku or "").upper())
        return m[1] if m else None

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

    def handle_model(self, handle):
        h = re.search(r"(?:^|-)(\d{5}A?)(?:-|$)", handle)
        return h[1] if h else None

    def sku_model(self, sku):
        m = re.fullmatch(r"(\d{5}A?)", (sku or "").strip().upper())
        return m[1] if m else None


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


def _mk(x):
    return re.sub(r"[^A-Z0-9]", "", re.sub(r"(?i)^BI-", "", x or "").upper())


def identity_check(ad, model, printed, handle, prod):
    """Page vs label corroboration (review 3, fix 2). -> (conflict dict or None, foreign SKUs). Conflicts (severity: lower = weaker):
      1 sku_disagrees     every variant SKU that names a model names another one (INIU P41 page: SKUs D01-P41-E2-*; qi2 page P73-E1 vs P76-P1)
      2 bundle_skus       every variant SKU is a '+' bundle (UGREEN 35524+70427P)
      2 edition_suffix    the printed label carries an edition suffix the model drops (UGREEN 75982SR -> 75982)
      3 handle_disagrees  the handle names another model token (INIU iniu-p41-e1-... prints 'P41')
    The importer quarantines a conflicted observation when its model already exists from a corroborated page, else keeps it and lists it in
    identity_conflicts; existing public ids never move. SKUs naming a different model on a corroborated page are dropped as aliases (foreign)."""
    hm = ad.handle_model(handle)
    toks = {}
    for v in prod.get("variants") or []:
        t = ad.sku_model(v.get("sku"))
        if t:
            toks[v["sku"].strip().upper()] = t
    skus = [(v.get("sku") or "").strip() for v in prod.get("variants") or [] if (v.get("sku") or "").strip()]
    pt = re.match(r"\s*([A-Z0-9][A-Z0-9-]*)", (printed or "").upper())
    pt = pt[1] if pt else None
    c = None
    if hm and _mk(hm) != _mk(model):
        c = {"reason": "handle_disagrees", "severity": 3, "handle_token": hm}
    elif pt and ad.brand == "ugreen" and re.fullmatch(r"\d{5}A?SR", pt):
        c = {"reason": "edition_suffix", "severity": 2, "printed": pt}
    elif skus and all("+" in x for x in skus):
        c = {"reason": "bundle_skus", "severity": 2, "skus": skus[:6]}
    elif toks and not any(_mk(t) == _mk(model) for t in toks.values()) and not re.fullmatch(r"PB\d{3}", model):   # UGREEN PB label model + item numbers = the wanted mapping
        c = {"reason": "sku_disagrees", "severity": 1, "sku_tokens": sorted(set(toks.values()))}
    if c:
        c.update(model=model, printed=(printed or "")[:40], handle=handle)
    foreign = sorted(s for s, t in toks.items() if _mk(t) != _mk(model)) if not c and ad.brand == "iniu" else []    # UGREEN colour item numbers stay aliases
    return c, foreign


UG_OUT = re.compile(r"(USB-[AC]\d?(?:/C\d)?)\s*Output\s*:\s*")
UG_PORTNAME = r"(?:USB-[AC]\d?(?:\s*/\s*C\d)?(?:\s*/\s*C-Cab(?:el|le))?|Wire?less(?: charging)?)"


def ugreen_outputs(blk):
    """UGREEN 'USB-C1 Output: ... 100W Max USB-C2 Output: ... USB-A Output: ...' (one labelled row per port; the shared label split eats the
    port names) -> 'USB-C1: ...; USB-C2: ...; USB-A: ...' for ports_from, or None. Only the first block, only when >= 2 port rows."""
    ms = [m for m in UG_OUT.finditer(blk) if not re.match(r"(?i)protocol", blk[m.end():m.end() + 9])]
    if len(ms) < 2:
        return None
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(blk)
        seg = re.split(r"\s(?:USB-[AC]\d?(?:/C\d)?\s+)?(?:Input|Total|Ports|Dimensions|Weight|Protocols?|Capacity|Indicator)\b", blk[m.end():end])[0]
        out.append(f"{m[1]}: {seg.strip(' ;,')}")
    return "; ".join(out)


def ugreen_protocols(blk):
    """UGREEN per-port protocol lists -> [(port name, protocol list)] for OUTPUT ports, plus the literal. Two printed layouts:
    'Support Protocol Input:USB-C1:PD3.0/... Output:USB-C1:PD3.0/PD2.0/PPS/... USB-C2:PD3.0/... USB-A:SCP/...' and
    'USB-C1/C2 Output Protocols: PD3.0/PD2.0/PPS/... USB-A Output Protocols: SCP/...'. Wireless entries are dropped (not a wired port)."""
    m = re.search(r"Support(?:ed)? Protocols?\s*:?\s*(?:Input(?: port)?\s*:.*?)?Output(?: port)?\s*:\s*(.*?)(?=\s(?:Wire?less charging\s*:|Learn More|Ports?\b|Dimensions|Weight|Display|Battery|Rated|Product)|$)", blk, re.S)
    if m:
        body, lit = m[1], m[0]
        heads = list(re.finditer(r"(" + UG_PORTNAME + r")\s*:\s*", body))
        ents = [(h[1], body[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(body)].strip(" ;,")) for i, h in enumerate(heads)]
    else:
        ents = [(x[1], x[2].strip()) for x in re.finditer(r"(USB-[AC]\d?(?:/C\d)?)\s*Output Protocols?\s*:\s*(.*?)(?=\s(?:USB-[AC]\d?(?:/C\d)?\s*Output Protocols?|Compatib|Learn More|Ports?\b|Dimensions)|$)", blk, re.S)]
        lit = " ; ".join(f"{a}: {b}" for a, b in ents)
    ents = [(n, v) for n, v in ents if not re.match(r"(?i)wire?less", n)]
    return ents, lit


def ugreen_pps(rows, blk, ports):
    """-> (value, literal, conditions) or None. True when an output port's protocol list names PPS (or a USB-C port prints a PPS range).
    False ONLY by complete enumeration (A1 ruling 2026-11-24): the spec block prints the port inventory ('Ports USB-A*1 USB-C*2'), every output
    port of that inventory has its own protocol list, no list is open-ended ('etc.'), and none names PPS. Otherwise nothing."""
    ents, lit = ugreen_protocols(blk)
    if any(re.search(r"\bPPS\b", v) and not re.match(r"(?i)usb-a", n) for n, v in ents) or any(p["pps"] and p["type"] in ("usb_c", "cable_c") for p in ports):
        return True, lit or (rows.get("Output") or ""), None
    inv = rows.get("Ports") or ""
    nc = re.search(r"USB-C\s*\*\s*(\d)", inv)
    na = re.search(r"USB-A\s*\*\s*(\d)", inv)
    if not ents or not (nc or na) or re.search(r"(?i)\betc\b|\bPPS\b", lit) or re.search(r"(?i)\binput\b", re.sub(r"(?i)^.*?Output", "", lit)):
        return None
    want = {f"C{i}" for i in range(1, int(nc[1]) + 1)} if nc else set()
    want |= {f"A{i}" for i in range(1, int(na[1]) + 1)} if na else set()
    got = set()
    for n, _ in ents:
        u = n.upper().replace(" ", "")
        for kind in "CA":
            cnt = len([w for w in want if w[0] == kind])
            if not u.startswith(f"USB-{kind}"):
                continue
            nums = re.findall(r"(?:^USB-" + kind + r"|/" + kind + r")(\d)", u)
            if nums:
                got |= {kind + x for x in nums}
            elif cnt == 1:
                got.add(kind + "1")
            else:
                return None                       # 'USB-C: ...' on a two-C-port bank: which port is not stated
    if not want or got != want:
        return None
    return False, lit, {"basis": "complete_enumeration"}


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
    printed = rows.get("Product Model") or rows.get("Model") or rows.get("SKU") or rows.get("Sku")
    conflict, foreign = identity_check(ad, model, printed, key, prod)
    pr.identifiers.append(L.ident("mfr_model", model, "model", ad.brand))
    pr.aliases.append({"text": title, "kind": "marketing_name"})
    colors = []
    for v in prod.get("variants") or []:
        if v.get("sku") and v["sku"].upper() != model.upper() and v["sku"].strip().upper() not in foreign:
            pr.identifiers.append(L.ident("mfr_sku", v["sku"].upper(), "configuration", ad.brand, role="alias", variant=v.get("title")))
        if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"])):
            pr.identifiers.append(L.ident("gtin", str(v["barcode"]), "package", "GS1", role="alias"))
    for o in prod.get("options") or []:
        if o.get("name", "").lower() in ("color", "colour"):
            colors += [x for x in o.get("values") or [] if x.lower() != "default title"]

    def add(k, val, raw, label, cond=None, quote=None):
        P.emit(pr, ad.adapter, snap, k, val, raw, label, model, cond, quote)

    add("gen.form_factor", P.form_factor(title), title, "title (derived)")
    add("gen.color", colors, " | ".join(colors), "variant option Color")
    cap = rows.get("Total Capacity") or rows.get("Power Capacity") or rows.get("Battery Capacity")
    if cap:
        vm = re.search(r"/\s*(\d\.\d{1,2})\s*V\b", cap)
        five = re.search(r"\(\s*5\s*V", cap)
        add("cap.cell_mah", P.Unresolved("capacity printed with a 5 V output basis: cell vs rated basis contradictory") if five and P.mah(cap) else P.mah(cap), cap, "Capacity")
        add("cap.cell_voltage", float(vm[1]) if vm else None, cap, "Capacity")
        add("cap.energy_wh", P.energy(cap), cap, "Capacity")
    if (cc := rows.get("Cell Capacity")):
        add("cap.energy_wh", P.energy(cc), cc, "Cell Capacity")
        vm = re.search(r"(\d+(?:\.\d+)?)\s*V\b", cc)
        if vm and float(vm[1]) < 5:
            add("cap.cell_voltage", float(vm[1]), cc, "Cell Capacity")
    if (rc := rows.get("Rated Capacity")):
        n, cond = P.rated(rc)
        add("cap.rated_mah", n, rc, "Rated Capacity", cond)       # never backfills cap.cell_mah (CUKTECH 'Rated Capacity 20000mAh' without basis)
        b = re.search(r"\(([^)]*)\)", rc)
        if cond:
            add("cap.rated_basis", b[1].strip() if b else None, rc, "Rated Capacity")
    out = rows.get("Output") or ""
    if ad.brand == "ugreen" and (uo := ugreen_outputs(blk)):
        out = uo
    if out:
        ports, combo, total, toks = P.ports_from(out, "out")
        tot = rows.get("Total Output")
        if tot and re.search(P.NUM + r"\s*W", tot):
            total, toks = P.fnum(re.search(P.NUM + r"\s*W", tot)[1]), None
            add("out.max_total_w", total, tot, "Total Output", quote="all-ports output: the maker's labelled 'Total Output' row")
        else:
            add("out.max_total_w", total, out, "Output", quote=("all-ports output: " + " + ".join(toks)) if toks else None)
        add("out.ports", ports, out, "Output")
        add("out.simultaneous", combo, out, "Output")
        single = [p["max_w"] for p in ports if p["max_w"] and p["type"] != "wireless"]
        add("out.max_single_port_w", max(single) if single else None, out, "Output")
        up = ugreen_pps(rows, blk, ports) if ad.brand == "ugreen" else None
        if up:
            add("pd.pps", up[0], up[1], "Supported Protocol (per output port)", up[2],
                quote="every output port of the printed inventory lists its protocols; none names PPS" if up[0] is False else None)
        else:
            add("pd.pps", True if any(p["pps"] and p["type"] in ("usb_c", "cable_c", None) for p in ports) or re.search(r"\bPPS\b", rows.get("Supported Protocol", "") + rows.get("Protocols", "")) else None, out, "Output")
        vmax = [P.pdos(p["fixed_pdos"] or "")[3] for p in ports]
        add("pd.max_fixed_voltage", max([x for x in vmax if x] or [0]) or None, out, "Output")
    inp = rows.get("Input") or ""
    if inp:
        fx, pps, mw, _ = P.pdos(inp)
        ip = P.ports_from(inp, "in")[0]
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
    if conflict:
        pr.fingerprints["identity_conflict"] = conflict
    if foreign:
        pr.fingerprints["foreign_skus"] = foreign
    if (mp := rows.get("Multi-port")):
        add("out.simultaneous", mp, mp, "Multi-port")
    return pr


if __name__ == "__main__":
    which = {c.source_id: c for c in (IniuPowerbanks, CuktechPowerbanks, UgreenPowerbanks)}
    src = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in which else "iniu-us-powerbanks"
    _run.main(which[src]())
