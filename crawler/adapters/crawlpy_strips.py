#!/usr/bin/env python3
"""Power strips from the crawl.py v0 stores (A2 round 3): anker, belkin, ugreen, baseus, byjasco (GE/Philips), furman, austere.

Source = raw/<slug>/products/<key>/{extract.json, feed.json (Shopify), http.json, page.html.gz}. These stores have no snapshot log, so this
module is a *reader*: iter_legacy(source_id) yields (snapshot-record-like dict, ParseResult dict, extra) exactly like registry.iter_observations
and never writes to raw/.  The "snapshot" is the sha256 crawl.py recorded for the page body (extract.json["sha256"]).

classify : title/type/tags gate -> strip / surge / tap / power-centre or excluded WITH a reason (counts: `python3 -I crawlpy_strips.py`).
identity : model = manufacturer model number (Belkin sku minus a colour suffix, Anker A####, first Shopify variant SKU for the rest);
           other variants (colours) become `mfr_sku` identifiers with package_level=configuration and `variant`, which import.py turns
           into configuration entities (identity.md rule 3). GTINs ride with the variant they were printed for.
claims   : profile keys only, each with locator + quote from the page text (title / JSON-LD description / bullets / spec rows / feed body /
           Belkin 'Technical Specifications' block). Retail copy is `kind: official` (manufacturer storefront); `type.kind` is `derived`.
           Two different joule figures on one page (Belkin 3,940 vs 3780J) are two claims -> resolves to `conflicted`, never silently picked.
"""
import collections, gzip, hashlib, html, json, re, sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C  # noqa: E402

ROOT = C.ROOT
ID, VERSION = "crawlpy-strips", 1
ADAPTER = f"{ID}@{VERSION}"

BRAND = {"byjasco": "jasco"}   # entity-id prefix; the storefront slug is not the brand
NEG = re.compile(r"smart plug|smart outlet|smart switch|in-wall|in wall|tape light|light strip|led |lamp|puck|battery|wireless charg|qi2|qi 2|magsafe|"
                 r"car charger|dash|power bank|earbud|dock\b|hub\b|timer|cable\b|cord reel|\bfan\b|heater|thermostat|doorbell|camera|speaker|"
                 r"flashlight|night ?light|sensor|dimmer|remote|z-wave|wi-?fi|matter", re.I)
POS = re.compile(r"surge|power strip|powerstrip|power-strip|\bpower tap|wall tap|tap adapter|outlet strip|power center|power conditioner|conditioner|"
                 r"sequenc|power distribut|power cube|\d+\s*-?\s*outlet|\d+\s*ac\b|\bac outlets?\b|charging station|desktop charg", re.I)
SMART = re.compile(r"smart (power )?strip|wi-?fi.*strip|matter.*strip", re.I)
COLOR = re.compile(r"^(.*?)[-_ ]?(BLK|WHT|BK|WH|CW|GY|BG|BL|RD|CH)$", re.I)


def txt(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def num(x):
    x = x.replace(",", "")
    v = float(x)
    return int(v) if v == int(v) else round(v, 3)


# ----------------------------------------------------------------------------- store readers
def _jl(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def products(source_id):
    base = ROOT / "raw" / source_id / "products"
    for d in sorted(base.iterdir()) if base.exists() else []:
        e = _jl(d / "extract.json")
        if e:
            yield d, d.name, e, _jl(d / "feed.json"), _jl(d / "http.json") or {}


def page_text(d):
    p = d / "page.html.gz"
    if not p.exists():
        return ""
    t = gzip.open(p, "rt", errors="replace").read()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    return txt(t)


# ----------------------------------------------------------------------------- classification
def gate(source_id, key, e, f):
    """-> (ok, reason). Reasons for exclusion are stable strings so the report can count them."""
    jl = (e.get("jsonld_products") or [{}])[0] or {}
    title = (f or {}).get("title") or jl.get("name") or e.get("title") or ""
    ptype = (f or {}).get("product_type") or ""
    tags = " ".join((f or {}).get("tags") or []) if isinstance((f or {}).get("tags"), list) else str((f or {}).get("tags") or "")
    desc = jl.get("description") or ""
    head = f"{title} {ptype}"
    if source_id == "furman":
        if re.search(r"(^|-)e(-|$)", key) or re.search(r"230V|220V|240V|\b[0-9]+A?\s*\(.*\bE\b.*\)|\bE I\b|\bE\)|220-240V", title):
            return False, "non-US voltage (230V/220-240V)"
        if ptype in ("Power Conditioners", "Sequencers", "Surge Protectors", "Direct Plug Ins") or re.search(r"distribut|surge|strip|power center", title, re.I):
            return (False, "cable/accessory") if re.search(r"cable|cord|extension", title, re.I) else (True, "")
        return False, f"furman product_type {ptype or '-'}"
    if source_id == "anker":
        if key.startswith("bundle") or len(re.findall(r"\ba\d{4}", key)) > 1 or re.search(r"\bbundle\b|\band Anker\b", title, re.I):
            return False, "bundle (two model numbers)"
        body = " ".join(e.get("bullets") or []) + " " + desc
        if re.search(r"wireless|qi2|magsafe|car charger", title, re.I):
            return False, "wireless/car charger"
        if re.search(r"power strip|surge|charging station|extension", title, re.I) and re.search(r"\bAC (outlets?|ports?)\b|\d\s*AC\b|AC Outlets\s*\d", body, re.I):
            return True, ""
        return False, "no AC outlets (charger / dock)"
    if source_id == "belkin":
        n = f"{jl.get('name') or ''} {desc}"
        if not jl:
            return False, "no JSON-LD product"
        if re.search(r"\b\d+\s*-?(outlet|OT|OUT|OUTLT)|surge|power strip|power cube|\bAC\b.*outlet|\d+AC\b", n, re.I) and not re.search(r"wireless|magnetic|dock|hub|battery|power bank|car ", n, re.I):
            return True, ""
        return False, "not a strip (Belkin accessory)"
    if source_id == "baseus":
        if re.search(r"power bank", title, re.I):
            return False, "power bank"
        if ptype == "Power Strips" or re.search(r"power strip|\d+AC\b", title, re.I):
            if re.search(r"\d+\s*AC\b|AC outlets?|power strip", title, re.I):
                return True, ""
            return False, "no AC outlet in title (USB charging station)"
        return False, f"baseus product_type {ptype or '-'}"
    if source_id == "ugreen":
        if re.search(r"power strip|surge|\bAC outlets?\b|\d+\s*-?\s*AC\b|outlet strip", title, re.I) and not re.search(r"car charger|wireless|dock\b|hub\b", title, re.I):
            return True, ""
        return False, "USB charger / dock (no AC outlets in title)"
    if source_id == "austere":
        return (True, "") if re.search(r"surge|outlet", title, re.I) else (False, "not a strip")
    if source_id == "byjasco":
        if NEG.search(title):
            return False, "smart/lighting/battery/in-wall (not a power strip)"
        if re.search(r"extension cord", title, re.I) and not re.search(r"surge|strip|power center", title, re.I):
            return False, "extension cord without strip/surge in title"
        if re.search(r"surge|power strip|power center|\btap\b|\d+\s*-?\s*outlets?|\d+\s*ac\b|\bac tap|power cube|\boutlet (adapter|expander)", title, re.I):
            return True, ""
        return False, "not a strip (Jasco accessory)"
    return False, "unknown source"


def kind(title, desc, claims_keys, usb):
    t = title
    if SMART.search(t):
        return "smart_strip"
    if re.search(r"conditioner|sequenc|power center|distributor", t, re.I):
        return "power_center"
    if re.search(r"wall tap|tap adapter|wall mount|wall-mount|surge tap|wall charger|\btap\b|cube", t, re.I) and not re.search(r"strip", title, re.I):
        return "wall_tap"
    if "surge.joules" in claims_keys or "type.ul1449_listed" in claims_keys or re.search(r"surge", title, re.I):
        return "surge_protector"
    if usb:
        return "usb_strip"
    return "plain_power_strip"


# ----------------------------------------------------------------------------- identity
def identity(source_id, key, e, f, jl):
    """-> (model, [variant dicts {sku, gtin, color}], alias_titles)"""
    title = (f or {}).get("title") or jl.get("name") or e.get("title", "").split(" | ")[0]
    if source_id == "belkin":
        sku = (jl.get("sku") or key.upper()).strip()
        m = COLOR.match(sku)
        # colour suffix after the 'tt' packaging code (BSV300ttCW) or after the cord code (BE106000-04-BLK); never strip into the family number
        base, col = (m.group(1).rstrip("-"), m.group(2).upper()) if m and len(m.group(1)) >= 6 and re.search(r"(tt|[-_]\d+[A-Z]?|\d)$", m.group(1), re.I) and (m.group(1).lower().endswith("tt") or "-" in m.group(1) or re.search(r"\d$", m.group(1))) else (sku, None)
        gt = jl.get("gtin12") or jl.get("gtin13") or jl.get("gtin")
        return base, ([{"sku": sku, "gtin": gt, "color": col}] if col else [{"sku": None, "gtin": gt, "color": None}]), []
    if source_id == "anker":
        model = key.split("-")[0].upper()
        sku = (jl.get("sku") or "").upper()
        gt = jl.get("gtin") or jl.get("gtin13")
        v = [{"sku": sku if sku and sku != model else None, "gtin": gt, "color": None}]
        return model, v, []
    if source_id in ("ugreen", "baseus", "byjasco", "furman", "austere"):
        vs = (f or {}).get("variants") or []
        skus = [(v.get("sku") or "").strip() for v in vs if (v.get("sku") or "").strip()]
        model = skus[0] if skus else (jl.get("sku") or key)
        out = []
        for v in vs:
            s = (v.get("sku") or "").strip()
            if s and s != model:
                out.append({"sku": s, "gtin": v.get("barcode"), "color": (v.get("title") if v.get("title") not in (None, "Default Title") else None)})
        if not out:
            out = [{"sku": None, "gtin": (vs[0].get("barcode") if vs else None), "color": None}]
        return model, out, []
    return key, [], []


# ----------------------------------------------------------------------------- claim extraction
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12}


class Collector:
    def __init__(self, model, observed):
        self.model, self.observed, self.claims, self.seen, self.absences = model, observed, [], set(), []

    def add(self, key, value, unit, raw, where, quote, kind="official", status="known"):
        sig = (key, json.dumps(value, sort_keys=True))
        if sig in self.seen:
            return
        self.seen.add(sig)
        stage = "jsonld" if where.startswith("jsonld") else "table" if where in ("spec_table", "belkin.tech") else "adapter"
        c = C.claim(self.model, key, value, unit, raw, "s1", ADAPTER, stage, self.observed, {"where": where}, quote)
        c["kind"] = kind
        self.claims.append(c)

    def has(self, key):
        return any(c["key"] == key for c in self.claims)


def extract_claims(col, parts, title, ptype=""):
    """parts: ordered [(where, text)]; earlier = more authoritative. First hit per key is kept, except joules, where distinct values all stay."""
    def first(rx, flags=re.I):
        for where, t in parts:
            m = re.search(rx, t, flags)
            if m:
                s = max(0, m.start() - 40)
                return m, where, t[s:m.end() + 40]
        return None, None, None

    # joules: all distinct stated values (a page that contradicts itself is a conflict, not a pick)
    seen_j = []
    for where, t in parts:
        for m in re.finditer(r"(?<![\d.])(\d{1,2},?\d{3}|\d{3})\s*(?:J(?:LS)?\b|joules?\b)", t, re.I):
            v = num(m.group(1))
            if 100 <= v <= 20000 and v not in seen_j:
                seen_j.append(v)
                col.add("surge.joules", v, "J", m.group(0), where, t[max(0, m.start() - 30):m.end() + 30])
    m, w, q = first(r"(?<![\d.A-Za-z])(\d{1,2})\s*-?\s*(?:AC\s+)?(?:outlets?|OT\b|OUT\b|OUTLT)")
    if not m:
        m, w, q = first(r"(?<![\d.A-Za-z])(\d{1,2})\s*AC\b(?!\s*adapter)")
    if not m:
        m, w, q = first(r"AC Outlets\s*(\d{1,2})")
    if not m:
        m, w, q = first(r"(" + "|".join(WORDNUM) + r")[- ]outlet", re.I)
        if m:
            m = type("M", (), {"group": lambda s, i=0, mm=m: str(WORDNUM[mm.group(1).lower()]) if i == 1 else mm.group(0)})()
    if m:
        col.add("outlets.count", int(m.group(1)), None, m.group(0), w, q)
    # USB ports {a, c}
    a = c = None
    m, w, q = first(r"(\d)\s*U\b(?=[+ /])")            # Baseus "1U+3C" code in the title
    mc, _, _ = first(r"(\d)\s*C\b(?=[+ /,]|\s*\d+W)")
    if m and mc and re.search(r"\d+AC", title):
        a, c = int(m.group(1)), int(mc.group(1))
    else:
        ma, w1, q1 = first(r"(\d)\s*(?:x\s*)?USB[- ]?A\b|USB-?A Ports?\s*(\d)")
        mc2, w2, q2 = first(r"(\d)\s*(?:x\s*)?USB[- ]?C\b|USB-?C Ports?\s*(\d)")
        if ma:
            a = int(ma.group(1) or ma.group(2)); w, q = w1, q1
        if mc2:
            c = int(mc2.group(1) or mc2.group(2)); w, q = (w2, q2) if not ma else (w, q)
        if a is None and c is None:
            mu, w, q = first(r"(\d)\s*-?\s*USB\b(?!-?[AC])")
            if mu:
                a, c = int(mu.group(1)), None
    if a is not None or c is not None:
        col.add("usb.ports", {k: v for k, v in (("a", a), ("c", c)) if v is not None}, None, (q or "")[:80], w, q)
    # cord
    for where, t in parts:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-?\s*(?:ft\.?|foot|feet)|')\s*(?:power |braided |extended |long |extension |tether(?:ed)? |AC )*(?:cord|cable|tether|power cord|lead)\b", t, re.I) or \
            re.search(r"(?:cord|cable)[^.,;]{0,25}?(\d+(?:\.\d+)?)\s*(?:ft\.?|foot|feet)\b", t, re.I) or \
            re.search(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:ft\b\.?|foot\b|feet\b|')(?=[,.\s]|$)", t, re.I) if where in ("title", "jsonld.description") else None
        if m and 0.2 <= float(m.group(1)) <= 50:
            col.add("cord.length_ft", num(m.group(1)), "ft", m.group(0), where, t[max(0, m.start() - 20):m.end() + 20])
            break
    m, w, q = first(r"(\d+(?:\.\d+)?)\s*m\b(?:\s*\(\d+\s*ft\))?\s*(?:power )?cord|cord length[^0-9]{0,20}(\d+(?:\.\d+)?)\s*m\b")
    if m and not col.has("cord.length_ft"):
        mm = float(m.group(1) or m.group(2))
        col.add("cord.length_ft", round(mm * 3.28084, 1), "ft", m.group(0), w, q)
    # electrical rating
    m, w, q = first(r"(\d{2})\s*A\b[ /,]*(?:\(?125\s*V|120\s*V)[ /,]*(?:60\s*Hz)?[ /,]*(\d{3,4})\s*W|125\s*V\s*~?\s*60\s*Hz\s*(\d{2})\s*A\s*(\d{3,4})\s*W|(\d{2})\s*A\s*/\s*125\s*V\s*/\s*(\d{3,4})\s*W")
    if m:
        g = [x for x in m.groups() if x]
        col.add("load.max_amps", int(g[0]), "A", m.group(0), w, q)
        col.add("load.max_watts", int(g[1]), "W", m.group(0), w, q)
        col.add("load.voltage", 125, "V", m.group(0), w, q)
    else:
        m, w, q = first(r"(?<![\d.])(1[0-9]|20)\s*(?:A|amps?)\b(?!\s*port)(?=[^.]{0,40}(?:125|120)\s*V|\s*(?:circuit|breaker|rating))|(?:rated|input)[^.]{0,25}(1[0-9]|20)\s*A\b")
        if m:
            col.add("load.max_amps", int(m.group(1) or m.group(2)), "A", m.group(0), w, q)
    # clamping (Belkin): L-N: 400V, L-G: 500V, N-G: 500V
    m, w, q = first(r"L-N:?\s*(\d{3,4})\s*V,?\s*L-G:?\s*(\d{3,4})\s*V,?\s*N-G:?\s*(\d{3,4})\s*V")
    if m:
        ln, lg, ng = (int(x) for x in m.groups())
        for k, v in (("surge.vpr_ln", ln), ("surge.vpr_lg", lg), ("surge.vpr_ng", ng), ("surge.vpr_max", max(ln, lg, ng))):
            col.add(k, v, "V", m.group(0), w, q)
    m, w, q = first(r"Max\.? Spike Voltage\s*(\d{3,6})\s*V?")
    if m:
        col.add("surge.max_spike_voltage", int(m.group(1)), "V", m.group(0), w, q)
    m, w, q = first(r"(\d{1,3},?\d{3})\s*(?:amps?|A)\b[^.]{0,20}(?:surge current|max(?:imum)? surge)|(?:max(?:imum)? )?surge current[^0-9]{0,15}(\d{1,3},?\d{3})\s*A")
    if m:
        col.add("surge.max_surge_current", num(m.group(1) or m.group(2)), "A", m.group(0), w, q)
    if first(r"EMI\s*/?\s*RFI")[0]:
        col.add("surge.emi_rfi", True, None, "EMI/RFI", *first(r"EMI\s*/?\s*RFI")[1:])
    # data lines
    dl = []
    for t_, rx in (("coax", r"coax|cable/satellite|cable & satellite|satellite|\bRG6"), ("ethernet", r"ethernet|RJ-?45"), ("phone_dsl", r"RJ-?11|telephone|phone line|modem|\bDSL\b|(?-i:\bTEL\b)|\bfax\b")):
        for where, t in parts:
            if re.search(rx, t, re.I) and re.search(r"protect|TEL\b|RJ|COAX|surge", t, re.I) and where in ("title", "jsonld.description", "belkin.tech"):
                dl.append(t_); break
    if dl:
        col.add("surge.dataline", dl, None, ",".join(dl), "title/description", title)
    # certification
    for where, t in parts:
        if re.search(r"UL\s?1449", t):
            col.add("type.ul1449_listed", True, None, "UL 1449", where, t[max(0, re.search(r"UL\s?1449", t).start() - 30):][:90]); break
    for where, t in parts:
        if re.search(r"UL\s?1363", t):
            col.add("type.ul1363_listed", True, None, "UL 1363", where, t[max(0, re.search(r"UL\s?1363", t).start() - 30):][:90]); break
    marks = [mk for mk, rx in (("UL", r"\bUL\b(?!\s*\w*\s*(?:recognized))|\bcUL\b"), ("ETL", r"\bETL\b"), ("CSA", r"\bCSA\b")) if any(re.search(rx, t) for _, t in parts)]
    if marks:
        col.add("cert.listing_mark", marks, None, ",".join(marks), "page text", ",".join(marks))
    # CEW (US dollars): "$300,000 CEW/Connected Equipment Warranty", or Belkin code "$15k"
    m, w, q = first(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)\s*(k\b)?\s*(?:CEW|connected equipment|CEG|guarantee|insurance|warranty)|(?:CEW|connected equipment[^$]{0,30})\s*\$\s?(\d{1,3}(?:,\d{3})+)")
    if m:
        v = num(m.group(1) or m.group(3))
        col.add("cert.cew_usd", v * 1000 if m.group(2) else v, "USD", m.group(0), w, q)
    else:
        m, w, q = first(r"(?<![\w.])\$?(\d{2,3})\s?k\b(?!\s*H)", 0)
        if m and w == "jsonld.description":
            col.add("cert.cew_usd", int(m.group(1)) * 1000, "USD", m.group(0), w, q)
    m, w, q = first(r"(lifetime(?: limited)?|\d+[- ]year(?: limited)?|\d+[- ]month)\s*(?:product )?(?:warranty|guarantee)|(?:warranty|guarantee)[: ]+(lifetime|\d+[- ]years?)")
    if m:
        col.add("cert.warranty_years", (m.group(1) or m.group(2)).strip().capitalize(), None, m.group(0), w, q)
    # plug / outlets / mounting
    m, w, q = first(r"\b(?:flat plug|ultra[- ]flat|flat[- ]plug)\b|\b45\s*°?\s*flat|STRT\b|right[- ]angle(?:d)? plug|angled plug|\bRTANG\w*|rotating plug|swivel plug|pivot[- ]plug|\b360\b", 0)
    if m:
        s = m.group(0).lower()
        v = "flat" if "flat" in s else "straight" if s == "strt" else "pivot" if ("pivot" in s or "rotating" in s or "360" in s or "swivel" in s) else "right_angle"
        col.add("cord.plug_style", v, None, m.group(0), w, q)
    if first(r"swivel outlets?|rotating outlets?|rotatable outlets?|pivot outlets?")[0]:
        col.add("outlets.rotating", True, None, "swivel/rotating outlets", *first(r"swivel outlets?|rotating outlets?|rotatable outlets?|pivot outlets?")[1:])
    if first(r"master switch|on/off switch|illuminated switch|lighted switch")[0]:
        col.add("outlets.switch", "master", None, "switch", *first(r"master switch|on/off switch|illuminated switch|lighted switch")[1:])
    if first(r"safety covers?|shutter")[0]:
        col.add("outlets.covers", True, None, "covers", *first(r"safety covers?|shutter")[1:])
    if first(r"\bmetal (?:housing|case|enclosure|surge|power|strip)|\bmetal\b", 0)[0] and re.search(r"\bmetal\b", title, re.I):
        col.add("phys.material", "metal", None, "metal", "title", title)
    if first(r"keyhole|wall[- ]mountable|mount holes|wall mount", 0)[0]:
        col.add("phys.mounting", ["keyhole"] if re.search(r"keyhole|mount holes", " ".join(t for _, t in parts), re.I) else ["wall_bracket"], None, "mounting", *first(r"keyhole|wall[- ]mountable|mount holes|wall mount", 0)[1:])
    # weight
    m, w, q = first(r"(?:item |net |product )?weight[: ]+(\d+(?:\.\d+)?)\s*(oz|ounces?|lbs?|pounds?|g|kg)\b")
    if m:
        v = float(m.group(1)); u = m.group(2).lower()
        lb = v / 16 if u.startswith(("oz", "ounce")) else v / 453.592 if u == "g" else v * 2.20462 if u == "kg" else v
        col.add("phys.weight_lb", round(lb, 3), "lb", m.group(0), w, q)
    # USB charging power (Baseus title "... 67W", Anker "(140W)") and protocols
    if col.has("usb.ports"):
        m, w, q = first(r"(?:Total|Max)(?: USB)?(?: Output)?[: ]+(\d{2,3})\s*W|(?<![\w.])(\d{2,3})\s*W\b(?!\s*max\b)")
        if m and w == "title":
            col.add("usb.total_w", int(m.group(1) or m.group(2)), "W", m.group(0), w, q)
        pd = [p for p, rx in (("PD", r"\bPD\b|power delivery"), ("PPS", r"\bPPS\b"), ("QC", r"\bQC\b|quick charge")) if any(re.search(rx, t, re.I) for _, t in parts)]
        if pd:
            col.add("usb.pd", pd, None, ",".join(pd), "page text", ",".join(pd))


def build(source_id, key, d, e, f, h):
    jl = (e.get("jsonld_products") or [{}])[0] or {}
    ok, why = gate(source_id, key, e, f)
    if not ok:
        return None, why
    title = txt((f or {}).get("title") or jl.get("name") or e.get("title", "").split(" | ")[0])
    ptype = (f or {}).get("product_type") or ""
    desc = jl.get("description") or ""
    model, variants, _ = identity(source_id, key, e, f, jl)
    observed = h.get("fetched_at") or ""
    snap = "sha256:" + (e.get("sha256") or hashlib.sha256(key.encode()).hexdigest())
    parts = [("title", title), ("jsonld.description", desc)]
    if source_id == "belkin":
        pt = page_text(d)
        i = pt.find("Technical Specifications")
        j = pt.find("Warranty and Support", i)
        if i >= 0:
            parts.append(("belkin.tech", pt[i:j if j > i else i + 1200]))
        k = pt.find("At a Glance")
        if k >= 0:
            parts.append(("page.text", pt[k:k + 1500]))
    body = txt((f or {}).get("body_html")) if f else ""
    bullets = e.get("bullets") or []
    if source_id == "anker":
        parts.append(("bullets", " ; ".join(b for b in bullets if re.search(r"\d", b))[:3000]))
        parts.append(("meta.description", (e.get("meta") or {}).get("description") or ""))
    rows = []
    for tb in e.get("spec_tables") or []:
        for r in tb:
            if len(r) == 2 and r[0]:
                rows.append(f"{r[0].strip(' :：')}: {r[1]}")
    if rows:
        parts.append(("spec_table", " ; ".join(rows)[:2500]))
    if body:
        parts.append(("body", body[:3500]))
    parts = [(w, t) for w, t in parts if t]
    col = Collector(model, observed)
    extract_claims(col, parts, title, ptype)
    usb = col.has("usb.ports")
    kd = kind(title, desc, {c["key"] for c in col.claims}, usb)
    col.add("type.kind", kd, None, kd, "derived", f"{title}", kind="derived")
    pr = C.ParseResult()
    variant_info = {}
    url = e.get("url") or h.get("url")
    pr.sources = [{"id": "s1", "url": url, "label": f"{source_id} product page", "source_id": f"{source_id}-crawl", "tier": "manufacturer",
                   "retrieved_at": observed, "snapshot": snap}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": BRAND.get(source_id, source_id), "market": "US"})
    for v in variants:
        if v["sku"]:
            pr.identifiers.append({"scheme": "mfr_sku", "value": v["sku"], "value_raw": v["sku"], "issuer": BRAND.get(source_id, source_id), "market": "US",
                                   "package_level": "configuration", "role": "key"})
            if v["color"]:
                variant_info[v["sku"]] = {"axis": "color", "value": v["color"], "parent": model}
        g = re.sub(r"\D", "", str(v.get("gtin") or ""))
        if len(g) in (8, 12, 13, 14):
            pr.identifiers.append({"scheme": "gtin", "value": g.zfill(14), "value_raw": str(v["gtin"]), "issuer": "GS1", "market": None})
    pr.aliases.append({"text": title, "kind": "marketing_name", "source": "s1", "observed_at": observed})
    pr.claims = col.claims
    if not col.has("surge.joules") and kd == "surge_protector":
        pr.absences.append({"key": "surge.joules", "reason": "no joule rating in the storefront copy", "source": "s1", "status": "not_published"})
    pr.fingerprints = {"raw": snap, "model": model, "title": title, "product_type": ptype, "kind": kd, "variants": variant_info}
    if source_id == "belkin" and any(v["color"] for v in variants):
        pr.fingerprints["claims_on"] = "configuration"     # a colour has its own page: its claims belong to the configuration (identity rule 3)
    rec = {"snapshot": snap, "ref": key, "url": url, "final_url": h.get("final_url") or url, "status": 200, "fetched_at": observed,
           "adapter": ADAPTER, "blob": f"products/{key}/page.html.gz"}
    return (rec, asdict(pr), {}), ""


def iter_legacy(source_id):
    for d, key, e, f, h in products(source_id):
        out, why = build(source_id, key, d, e, f, h)
        if out is not None:
            yield out


if __name__ == "__main__":      # classification report: kept / excluded-by-reason per source
    tot = {}
    for sid in ("anker", "belkin", "ugreen", "baseus", "byjasco", "furman", "austere"):
        kept, ex = 0, collections.Counter()
        for d, key, e, f, h in products(sid):
            ok, why = gate(sid, key, e, f)
            if ok:
                kept += 1
            else:
                ex[why] += 1
        print(sid, "kept", kept, "excluded", dict(ex))
