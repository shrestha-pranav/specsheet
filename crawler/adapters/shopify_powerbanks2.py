#!/usr/bin/env python3
"""Shopify-store power-bank adapters, round 2 (contract ARCHITECTURE 15.5), category power-banks: EcoFlow (us.ecoflow.com), SHARGE (sharge.com),
KUXIU (kuxiu.com), mophie (www.mophie.com). One module, one class per source. Separate module so the audited
shopify_powerbanks@1 fingerprint (claim/mfr-power-banks-structured@2) does not move; fetch is inherited from shopify_powerbanks._Shop unchanged.

discover : {base}/products.json (public Shopify catalogue, robots allow /products) -> per-brand predicate (power banks only; bundles, gift sets,
           '+' combos, refurbished, power stations, licensed/limited skins dropped). One Ref per handle.
fetch    : product page HTML + /products/<handle>.json in one gzip JSON blob (shopify_powerbanks._Shop.fetch).
parse    : pure. Labelled spec rows from the theme's spec markup (HTML label/value pairs, never prose):
           EcoFlow  'pdp-specs-title' / 'pdp-specs-content' under an h2 'Specs - <product name>'. The block is read ONLY when that name equals the
                    page title (normalised): EcoFlow copies spec sections between sibling pages (the 25K 170W page carries the 25K 170W
                    '100W Built-In and Retractable Cables' table), so a mismatch is an absence, not a guess.
           SHARGE   accordion 'heading' span / 'details__content' (Product Name, Product Model, Battery Capacity, Rated Battery Capacity, Input, Output...).
           KUXIU    metafield grid h6 label / p value (Model, Battery Type, Battery Capacity, Rated Capacity, USB-C Output/Input, Wireless Output...).
           mophie   'pdp-spec__label' / 'pdp-spec__value' (Weight, Dimensions, Output, Battery, Input...).
Identity : EcoFlow   no model number printed; the manufacturer SKU stem shared by the page's EF- variant SKUs (EF-RAPID25K140W from
                     EF-RAPID25K140W-S-US / -G-US / -B-US: colour + region suffix stripped, same rule as Anker's 5-char stem). >1 stem = absence.
           SHARGE    'Product Model' row (P3).          KUXIU 'Model' row (S4).
           mophie    no model printed; the page's single 9-digit mophie part number (JSON-LD sku / variant SKU, 401109564). Pages with several part
                     numbers (capacity selectors) are absences; licensed/limited skins (LMTD, MLB, Red Bull, Gallery, Signature) are not discovered.
Not built: Baseus (www.baseus.com, 58 power-bank pages probed 2026-11-23): electrical specs are images; the body_html 'Specs' block is an
           Amazon-attribute template ('Voltage: volts'); newer lines print only a colour SKU (E0028H03) with the model (FC41) in the title.
Traps    : KUXIU 'Total Cell Capacity 10000mAh -5000mAh 7.7VDC (38.5Wh)' = a 2S pack: a series voltage >= 5 V in the cell blocks cap.cell_mah (the
           Anker A1657 rule); the printed Wh is kept. SHARGE 'Battery Capacity 10,000mAh (5V⎓3A)' carries a 5 V basis in brackets next to the
           cell figure; it is read as cell mAh (the rated 5 V figure is its own 'Rated Battery Capacity' row). Inches/lbs/oz are converted to
           the profile units (mm, g) with the literal kept in value_raw.
"""
import gzip, html, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _powerbank as P
import _run
import shopify_powerbanks as S

VERSION = 2       # v2: review 3 (two unlabelled figures unresolved, 5 V capacity basis, rated load conditions)
DELAY = 1.0


def txt(s):
    return P.clean(re.sub(r"<br\s*/?>|</p>\s*<p[^>]*>", " ; ", s or "")).replace("～", "~").replace("＝", "=").replace("，", ", ")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", html.unescape(s or "").lower())


def grams(s):
    g = P.grams(s)
    if g is not None:
        return g
    m = re.search(r"(\d*\.?\d+)\s*(?:lbs?|pounds?)\b", s or "", re.I)
    return round(float(m[1]) * 453.592, 1) if m else None


def dims(s):
    d = P.dims_mm(s)
    if d:
        return d
    t = (s or "").replace("×", "x").replace("*", "x")
    m = re.search(r"(\d*\.?\d+)\s*(?:L\s*)?(?:in\b|\")?\s*x\s*(\d*\.?\d+)\s*(?:W\s*)?(?:in\b|\")?\s*x\s*(\d*\.?\d+)\s*(?:H\s*)?(?:inches|inch|in\b|\")", t, re.I)
    if m:
        return {"w": round(float(m[1]) * 25.4, 1), "d": round(float(m[2]) * 25.4, 1), "h": round(float(m[3]) * 25.4, 1), "unit": "mm"}
    return None


class _Shop2(S._Shop):
    host = None

    def keep(self, p):
        return False

    def discover(self, checkpoint, net):
        refs, page, n = [], 1, 0
        while page <= 10:
            r = net.get(f"{self.base}/products.json?limit=250&page={page}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery(refs, False, f"products.json page {page}: {getattr(r, 'status_code', r)}", {"page": page})
            ps = r.json().get("products") or []
            if not ps:
                break
            n += len(ps)
            for p in ps:
                if self.keep(p):
                    refs.append(C.Ref(self.source_id, p["handle"], f"{self.base}/products/{p['handle']}", {"title": p.get("title")}))
            page += 1
        return C.Discovery(refs, True, None, {"catalogue": n, "products": len(refs)})

    def parse(self, snap, blobs, profile):
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        return parse2(self, snap, d["page"], d.get("product") or {})

    def rows(self, page, prod, title):
        return {}, None          # -> ({label: value}, reason-if-unusable)

    def model(self, rows, prod, page):
        return None


BUNDLE = re.compile(r"bundle|\+|combo|2-pack|gift set|\bduo\b|refurb|kit\b|travel case|solar panel|power station", re.I)


class EcoflowPowerbanks(_Shop2):
    id, source_id, base, brand = "ecoflow_powerbanks", "ecoflow-us-powerbanks", "https://us.ecoflow.com", "ecoflow"

    def keep(self, p):
        t = p.get("title") or ""
        return bool(re.search(r"power bank", t, re.I)) and not BUNDLE.search(t) and not BUNDLE.search(p.get("product_type") or "")

    def rows(self, page, prod, title):
        m = re.search(r"<h2>\s*(?:Specs|Specifications|Tech Specs)\s*(?:-\s*(.*?))?</h2>(.*?)</section>", page, re.S)
        if not m:
            return {}, "no pdp-specs section"
        if m[1] and norm(m[1]) != norm(title):
            return {}, f"spec section names another product: {P.clean(m[1])[:80]}"
        out = {}
        for lab, val in re.findall(r'pdp-specs-title">(.*?)</p>.*?pdp-specs-content">(.*?)</div>', m[2], re.S):
            out.setdefault(P.clean(lab), txt(val))
        if not m[1]:                       # unnamed block: accept only if it agrees with every mAh / W figure in the page title
            blk = " ".join(out.values()).replace(",", "")
            t = title.replace(",", "")
            figs = re.findall(r"(\d+(?:\.\d+)?)\s*(mAh|W)\b", t) + [(str(int(k) * 1000), "mAh") for k in re.findall(r"\b(\d{1,2})K\b", t)]
            if not figs or any(not re.search(r"(?<![\d.])" + re.escape(n) + r"\s*" + u + r"\b", blk) for n, u in figs):
                return {}, "unnamed spec section disagrees with the title figures"
        return out, None

    def model(self, rows, prod, page):
        stems = set()
        for v in prod.get("variants") or []:
            s = (v.get("sku") or "").strip().upper()
            if not s.startswith("EF-"):
                continue                      # accessory/bundle variants (RP20K-C100, RP27K-STATION320W)
            s = re.sub(r"-(US|USAMZ)$", "", s)
            s = re.sub(r"-(B|W|DG|L|BLU|S|G|GR|BK|WH)$", "", s)
            stems.add(s)
        return stems.pop() if len(stems) == 1 else None


class ShargePowerbanks(_Shop2):
    id, source_id, base, brand = "sharge_powerbanks", "sharge-us-powerbanks", "https://sharge.com", "sharge"

    def keep(self, p):
        t = p.get("title") or ""
        return p.get("product_type") == "Power Bank" and not BUNDLE.search(t) and not BUNDLE.search(p["handle"])

    def rows(self, page, prod, title):
        out = {}
        for lab, val in re.findall(r'<span class="heading[^"]*">([^<]{2,60})</span>.*?<div class="details__content[^"]*">\s*<div class="specification[^"]*">(.*?)</div>\s*</div>\s*</details>', page, re.S):
            out.setdefault(P.clean(lab), txt(val))
        if re.search(r"\d+K\s*/\s*\d+K", title, re.I):
            return {}, "page sells two capacities (two models, one spec block)"
        return out, (None if self._mlab(out) else "no model row")

    @staticmethod
    def _mlab(rows):
        return next((v for k, v in rows.items() if re.fullmatch(r"(?i)(product |prodcut )?model", k)), None)

    def model(self, rows, prod, page):
        m = re.match(r"^[A-Z0-9][A-Za-z0-9-]{1,15}$", (self._mlab(rows) or "").strip())     # 'M6/M7', 'P7 / P7U' = two models -> None
        return m[0] if m else None


class KuxiuPowerbanks(_Shop2):
    id, source_id, base, brand = "kuxiu_powerbanks", "kuxiu-us-powerbanks", "https://kuxiu.com", "kuxiu"

    def keep(self, p):
        t = p.get("title") or ""
        return bool(re.search(r"power bank", t, re.I)) and not BUNDLE.search(t)

    def rows(self, page, prod, title):
        out = {}
        for lab, val in re.findall(r'<h6[^>]*>(.*?)</h6>\s*<p>(.*?)</p>', page, re.S):
            l = P.clean(lab).rstrip(":")
            out.setdefault(l, txt(val).lstrip("- ").replace(" ; -", " ;"))
        return out, (None if "Model" in out else "no 'Model' row")

    def model(self, rows, prod, page):
        m = re.match(r"^[A-Z][A-Za-z0-9]{0,4}(?:\s?(?:Ultra|Pro|Max))?$", (rows.get("Model") or "").strip())
        return m[0] if m else None


class MophiePowerbanks(_Shop2):
    id, source_id, base, brand = "mophie_powerbanks", "mophie-us-powerbanks", "https://www.mophie.com", "mophie"
    SKIN = re.compile(r"\||red bull|gallery edition|signature series|^lmtd|mlb|\bsst\b", re.I)

    def keep(self, p):
        t = p.get("title") or ""
        return p.get("product_type") == "Power Banks" and not BUNDLE.search(t) and not self.SKIN.search(t) and not self.SKIN.search(p["handle"])

    def rows(self, page, prod, title):
        out = {}
        page = re.sub(r"<style.*?</style>|<script.*?</script>", " ", page, flags=re.S)
        for lab, val in re.findall(r'<span class="pdp-spec__label[^>]*>(.*?)</span>\s*<span class="pdp-spec__value[^>]*>(.*?)</span>', page, re.S):
            l = P.clean(lab)
            out.setdefault(l, re.sub(r"^" + re.escape(l) + r"\s*:\s*", "", txt(val), flags=re.I))
        return out, (None if out else "no Technical Specifications rows")

    def model(self, rows, prod, page):
        ns = {(v.get("sku") or "").strip() for v in prod.get("variants") or []}
        return ns.pop() if len(ns) == 1 and re.fullmatch(r"40\d{7}", next(iter(ns))) else None


def _first(rows, *pats):
    for lab, v in rows.items():
        if any(re.search(p, lab, re.I) for p in pats):
            return lab, v
    return None, None


def port_list(lit):
    """'USB-C1/C2: 5V⎓3A ... PD 45W ; USB-A: ... ; Wireless Charging: 5W/15W(MAX) ; C1+A: 140W+20W' -> (ports, simultaneous literal).
    One segment per ';' with a 'name:' head (a head-only segment is joined to the next); '+' names are combinations, not ports."""
    segs, carry = [], ""
    lit = re.sub(r"(\d+(?:\.\d+)?)\s*V\s*[~-]\s*(?=\d)", r"\1~", lit)        # '5V~11V⎓4.05A' -> '5~11V⎓4.05A' (the shared RANGE form)
    for x in [y.strip() for y in lit.split(";")]:
        if not x:
            continue
        x = (carry + " " + x).strip() if carry else x
        carry = ""
        if re.fullmatch(r"[^:]{1,60}:", x) or (":" not in x and not re.search(r"\d\s*[VW]", x)):
            carry = x
            continue
        segs.append(x)
    ports, combos = [], []
    for x in segs:
        name, _, val = x.partition(":") if re.match(r"^[^:\d][^:]{0,60}:", x) else ("", "", x)
        name = re.sub(r"\s*(cable|port)s?\s*$|\s*(build|built)-?in cable", "", name.strip(), flags=re.I).strip() or "Output"
        if re.search(r"\+|total", name, re.I):
            combos.append(f"{name}: {val.strip()}"[:120])
            continue
        fx, pps, mw, _ = P.pdos(val)
        if re.fullmatch(r"(?i)pps", name) and ports:                        # 'PPS: 5~11V⎓4.05A/...' continues the previous port
            ports[-1]["pps"] = "; ".join(x for x in (ports[-1]["pps"], pps) if x) or None
            ports[-1]["max_w"] = ports[-1]["max_w"] or mw
            continue
        pt = "wireless" if re.search(r"(?i)wir?e?less|\bqi\b", name) else P.port_type(name)
        if pt == "wireless":
            ws = [float(w) for w in re.findall(P.NUM + r"\s*W\b", val)]
            mw, fx, pps = (P.fnum(max(ws)) if ws and max(ws) <= 30 else None), "", ""
        ports.append({"name": name, "type": pt, "direction": "out", "max_w": mw, "fixed_pdos": fx or None, "pps": pps or None})
    return ports, "; ".join(combos) or None


def parse2(ad, snap, page, prod):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [L.source(snap, f"{ad.brand.upper()} US store page {key}")]
    title = P.clean(prod.get("title")) or snap.ref.hints.get("title") or key
    rows, why = ad.rows(page, prod, title)
    model = ad.model(rows, prod, page)
    pr.fingerprints = {"raw": snap.snapshot, "labels": list(rows), "title": title}
    if not model:
        pr.absences.append({"key": "*", "reason": "no model number (printed row / manufacturer SKU) for this page", "source": "s1"})
        return pr
    pr.identifiers.append(L.ident("mfr_model", model, "model", ad.brand))
    pr.aliases.append({"text": title, "kind": "marketing_name"})
    for v in prod.get("variants") or []:
        s = (v.get("sku") or "").strip()
        if s and s.upper() != model.upper():
            pr.identifiers.append(L.ident("mfr_sku", s.upper(), "configuration", ad.brand, role="alias", variant=v.get("title")))
        if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"])):
            pr.identifiers.append(L.ident("gtin", str(v["barcode"]), "package", "GS1", role="alias"))
    if why:
        pr.absences.append({"key": "*", "reason": why, "source": "s1"})
        return pr

    def add(k, val, raw, label, cond=None, quote=None):
        P.emit(pr, ad.adapter, snap, k, val, raw, label, model, cond, quote)

    lab, cap = _first(rows, r"^(total |battery |power )?(cell )?capacity$", r"^battery$", r"^battery capacity")
    if cap:
        series = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*V(?:DC)?\b(?!\s*⎓)", cap) if 5 <= float(x) <= 30 and not re.search(r"\(\s*5V", cap)]
        mahs = [int(x.replace(",", "")) for x in re.findall(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*mAh", cap, re.I)]
        whs = [P.fnum(x) for x in re.findall(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*Wh\b", cap)]
        if re.search(r"\b\d+K\s*:", cap):
            mahs = whs = []                       # '5K: ... ; 10K: ...' = two models in one cell
        if not series and mahs:
            if re.search(r"\(\s*5\s*V", cap):               # SHARGE '10,000mAh (5V⎓3A)': a 5 V output basis on the capacity row contradicts a cell figure
                add("cap.cell_mah", P.Unresolved("capacity printed with a 5 V output basis: cell vs rated basis contradictory"), cap, lab)
            elif len(set(mahs)) > 1:                            # '10000mAh / 9800mAh': which is typical / rated is not printed -> no pick (review 3)
                add("cap.cell_mah", P.Unresolved(f"{len(set(mahs))} mAh figures without a typical/rated label"), cap, lab)
            else:
                add("cap.cell_mah", mahs[0], cap, lab)
        add("cap.energy_wh", P.energy(cap) if whs else None, cap, lab)
        vm = re.search(r"(\d\.\d{1,2})\s*V\b", cap)
        add("cap.cell_voltage", float(vm[1]) if vm and float(vm[1]) < 5 else None, cap, lab)
    lab, rc = _first(rows, r"^rated (battery )?capacity")
    if rc:
        b = re.search(r"\(([^)]*\d[^)]*)\)", rc)
        n, cond = P.rated(rc)
        if n is not None and b:
            add("cap.rated_mah", n, rc, lab, cond)                   # value + {rated_voltage_v, rated_current_a}: the load stays with the figure
            add("cap.rated_basis", b[1].strip(), rc, lab)
    lab, tot = _first(rows, r"to(?:ta|at)l output")
    if tot and (m := re.search(P.NUM + r"\s*W\b", tot)):
        add("out.max_total_w", P.fnum(m[1]), tot, lab, quote=f"all-ports output: the maker's labelled '{lab}' row")
    lab, so = _first(rows, r"^single output$")
    if so:                                                                      # EcoFlow 'C1/C2: 140W ; A: 33W'
        ws = [P.fnum(x) for x in re.findall(P.NUM + r"\s*W\b", so)]
        add("out.max_single_port_w", max(ws) if ws else None, so, lab)
    if ad.brand == "mophie" and (o := rows.get("Output")):          # '3 USB-C Ports - 45W': per-port or total not stated (Belkin 'Wattage' rule)
        ws = re.findall(P.NUM + r"\s*W\b", o)
        add("out.max_output_w", P.fnum(ws[0]) if len(set(ws)) == 1 else None, o, "Output")
        rows = {k: v for k, v in rows.items() if k != "Output"}
    outs = [(l, v) for l, v in rows.items() if re.search(r"(^|usb-?[ac][\d/c]* |single-port |power )output$|^output$|^output \(power bank mode\)$", l, re.I)]
    if outs and not any(re.search(r"\b\d+K\s*:", v) for _, v in outs):
        lit = " ; ".join(f"{re.sub(r'(?i)\s*output.*$', '', l)}: {v}" if re.match(r"(?i)usb", l) else v for l, v in outs)
        ports, combo = port_list(lit)
        if ports and any(p["fixed_pdos"] for p in ports):
            add("out.ports", ports, lit, " + ".join(l for l, _ in outs))
            add("out.simultaneous", combo, lit, "Output")
            single = [p["max_w"] for p in ports if p["max_w"] and p["type"] != "wireless"]
            if not so:
                add("out.max_single_port_w", max(single) if single else None, lit, "Output")
            vmax = [P.pdos(p["fixed_pdos"] or "")[3] for p in ports]
            add("pd.max_fixed_voltage", max([x for x in vmax if x] or [0]) or None, lit, "Output")
            if any(p["pps"] for p in ports):
                add("pd.pps", True, lit, "Output")
            wl = [p["max_w"] for p in ports if p["type"] == "wireless" and p["max_w"]]
            if wl and not _first(rows, r"^wireless output")[1]:
                add("out.wireless_w", max(wl), lit, "Output (Wireless Charging)")
    lab, mp = _first(rows, r"^multi-port output$")
    cl = [(l, v) for l, v in rows.items() if re.search(r"\+.*output$", l, re.I)]
    if cl and not mp:
        lab, mp = "USB-* + * Output rows", " ; ".join(f"{re.sub(r'(?i)\s*output$', '', l)}: {v}" for l, v in cl)
    if mp:
        add("out.simultaneous", mp, mp, lab)
    lab, wo = _first(rows, r"^wireless output")
    if wo:
        ws = [float(x) for x in re.findall(P.NUM + r"\s*W\b", wo)]
        add("out.wireless_w", P.fnum(max(ws)) if ws and max(ws) <= 30 else None, wo, lab)
    ins = [(l, v) for l, v in rows.items() if re.fullmatch(r"(?i)(usb-?c\d? )?input", l)]
    lab, inp = (" + ".join(l for l, _ in ins), " ; ".join(v for _, v in ins)) if ins else (None, None)
    if inp:
        fx, pps, mw, _ = P.pdos(inp)
        add("in.max_w", mw, inp, lab)
        add("in.pdos", fx or None, inp, lab)
    lab, pro = _first(rows, r"protocols?$")
    if pro:
        add("pd.protocols", sorted({x.strip() for x in re.split(r"[/,;]", pro) if x.strip() and len(x.strip()) < 20}), pro, lab)
        if re.search(r"\bPPS\b", pro):
            add("pd.pps", True, pro, lab)
    lab, w = _first(rows, r"weight$")
    if w and not re.search(r"package|gross", lab, re.I):
        add("phys.weight", grams(w), w, lab)
    lab, dm = _first(rows, r"dimensions?$")
    if dm:
        add("phys.dimensions", dims(dm), dm, lab)
    lab, bt = _first(rows, r"^battery (type|cell)", r"^cell type")
    if bt:
        add("bat.chemistry", P.chemistry(bt), bt, lab)
    lab, dp = _first(rows, r"display$")
    if dp and not re.fullmatch(r"(?i)no|none|-", dp.strip()):
        add("phys.display", P.display(dp) or ("smart_display" if re.search(r"TFT|smart", dp, re.I) else "digital_percent" if re.search(r"digital|LED|dot", dp, re.I) else None), dp, lab)
    pr.fingerprints["unmapped"] = {k: v[:80] for k, v in rows.items() if not re.search(
        r"capacity|output|input|protocol|weight|dimension|battery|display|model|name", k, re.I)}
    return pr


CLASSES = (EcoflowPowerbanks, ShargePowerbanks, KuxiuPowerbanks, MophiePowerbanks)

if __name__ == "__main__":
    which = {c.source_id: c for c in CLASSES}
    if len(sys.argv) < 2 or sys.argv[1] not in which:
        raise SystemExit("usage: shopify_powerbanks2.py <" + "|".join(which) + "> discover|fetch|parse|run")
    _run.main(which[sys.argv.pop(1)]())
