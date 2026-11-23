"""Shared pure parsers for the power-bank adapters (anker_powerbanks, belkin_powerbanks, shopify_powerbanks). No network.

PDO model reused from the GaN-charger pilot (data/gan-chargers/*.json: pd_fixed_pdos "5V3A 9V3A 15V2A 20V1.5A", pps_ranges "3.3-11V 3A"):
fixed PDOs and PPS/variable ranges are kept as normalised literal strings, one port per entry of `out.ports`.
"""
import html, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C  # noqa: E402  (claim builder for unresolved preview claims only)

SEP = r"\s*(?:⎓|=|/|:|\s)?\s*"
NUM = r"(\d+(?:\.\d+)?)"
RANGE = re.compile(NUM + r"\s*(?:-|–|~|to)\s*" + NUM + r"\s*V" + SEP + NUM + r"\s*A\b", re.I)
FIXED = re.compile(r"(?<![\d.\-–~])" + NUM + r"\s*V" + SEP + NUM + r"\s*A\b", re.I)
MAXW = re.compile(r"(?:\(?\s*" + NUM + r"\s*W\s*\(?\s*Max\b|Max\.?\s*(?:total\s*)?" + NUM + r"\s*W\b|up to\s*" + NUM + r"\s*W\b)", re.I)


def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").replace("：", ":").replace("（", "(").replace("）", ")").replace("、", " / ")
    return re.sub(r"\s+", " ", s).strip()


def fnum(x):
    v = float(x)
    return int(v) if v == int(v) else v


def pdos(text):
    """-> (fixed 'XVYA ...', pps 'a-bV cA; ...', printed max W or None, highest fixed V or None). Ranges are removed before fixed PDOs are read.
    The wattage is only a printed W figure ('(100W Max)', '22.5W'); it is never computed from the highest PDO (19.98 W from 9V2.22A is not a spec)."""
    t = clean(text)
    rng = [(fnum(a), fnum(b), fnum(c)) for a, b, c in RANGE.findall(t)]
    rest = RANGE.sub(" ", t)
    fx = [(fnum(v), fnum(a)) for v, a in FIXED.findall(rest) if 3 <= float(v) <= 48 and float(a) <= 10]
    mw = [fnum(next(x for x in m if x)) for m in MAXW.findall(t)] or [fnum(x) for x in re.findall(r"(?<![\d.])" + NUM + r"\s*W\b(?!h)", rest)]
    fixed = " ".join(f"{v}V{a}A" for v, a in dict.fromkeys(fx))
    pps = "; ".join(f"{a}-{b}V {c}A" for a, b, c in dict.fromkeys(rng))
    return fixed, pps, (max(mw) if mw else None), (max(v for v, _ in fx) if fx else None)    # W only as printed, never V x A


def mah(text):
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*(?:mAh|milliamp[ _]hours?)", text or "", re.I)
    return int(m[1].replace(",", "")) if m else None


def wh(text):
    m = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*Wh\b", text or "")
    return fnum(m[1]) if m else None


class Unresolved:
    """A labelled cell that names the spec but does not establish a trusted value (review 3): emitted by unresolved() as a status-unknown claim
    with the literal in `raw` and the reason in `quote`. No policy accepts status unknown, so it is preview evidence, never a number."""
    __slots__ = ("reason",)

    def __init__(self, reason):
        self.reason = reason

    def __bool__(self):
        return False

    def __repr__(self):
        return f"Unresolved({self.reason!r})"


def unresolved(pr, adapter, snap, key, raw, label, model, reason):
    pr.claims.append(C.claim(model, key, None, None, raw if isinstance(raw, str) else " | ".join(raw), "s1", adapter, "adapter", snap.fetched_at,
                             locator={"model_code": model, "label": label}, quote=reason, status="unknown"))


def emit(pr, adapter, snap, key, value, raw, label, model, conditions=None, quote=None):
    """One model claim: a value, an Unresolved (-> status unknown + reason) or nothing. Conditions/quote are kept on the claim."""
    if isinstance(value, Unresolved):
        return unresolved(pr, adapter, snap, key, raw, label, model, value.reason)
    if value in (None, "", []):
        return
    pr.claims.append(C.claim(model, key, value, None, raw if isinstance(raw, str) else " | ".join(raw), "s1", adapter, "adapter", snap.fetched_at,
                             locator={"model_code": model, "label": label}, quote=quote, conditions=conditions))


def energy(text):
    """Printed Wh. One figure -> it. Several DIFFERENT figures ('74Wh/75.5Wh', '36Wh/ 35.28Wh') -> the one explicitly labelled rated, else
    Unresolved: the profile's cap.energy_wh is the rated energy and an unlabelled pair does not say which is which (review 3)."""
    t = text or ""
    whs = list(dict.fromkeys(fnum(x) for x in re.findall(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*Wh\b", t)))
    if len(whs) <= 1:
        return whs[0] if whs else None
    lab = re.search(r"(?i)rated(?: energy| capacity)?\s*[:：]?\s*(\d{1,3}(?:\.\d+)?)\s*Wh\b|(\d{1,3}(?:\.\d+)?)\s*Wh\s*\(?\s*rated", t)
    if lab:
        return fnum(lab[1] or lab[2])
    return Unresolved(f"{len(whs)} Wh figures ({' / '.join(str(x) for x in whs)}) without a rated/typical label")


def rated(text):
    """'13500mAh(5V/6A)' / '5,800mAh (5V⎓3A)' -> (mAh, {rated_voltage_v, rated_current_a}) : the 5 V rating is inseparable from its load
    (review 3, fix 3). A basis without a current ('(5V)'), with several voltages ('5V/9V/7A typical'), or no basis -> (Unresolved, None)."""
    n = mah(text)
    if not n:
        return None, None
    b = re.search(r"\(([^)]*\d[^)]*)\)", text or "")
    if not b:
        return Unresolved("rated mAh printed without its output basis (voltage and current)"), None
    vs = re.findall(r"(\d+(?:\.\d+)?)\s*V\b", b[1])
    cs = re.findall(r"(\d+(?:\.\d+)?)\s*A\b", b[1])
    if len(set(vs)) != 1 or len(set(cs)) != 1:
        return Unresolved(f"rated basis '{b[1].strip()}' does not name exactly one voltage and one current"), None
    return n, {"rated_voltage_v": fnum(vs[0]), "rated_current_a": fnum(cs[0])}


def grams(text):
    t = text or ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:±\s*\d+(?:\.\d+)?\s*)?g\b", t)
    if m:
        return fnum(m[1])
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:oz|ounces)\b", t, re.I)
    return round(float(m[1]) * 28.3495, 1) if m else None


def dims_mm(text):
    """'156.97 × 53.85 × 49.02 mm' or '0.9in/23mm x 3.2in/80mm x 2.4in/62mm' -> {w,d,h,unit:mm} or None."""
    t = (text or "").replace("×", "x").replace("*", "x")
    m = re.search(NUM + r"\s*x\s*" + NUM + r"\s*x\s*" + NUM + r"\s*mm", t, re.I)
    if m:
        return {"w": fnum(m[1]), "d": fnum(m[2]), "h": fnum(m[3]), "unit": "mm"}
    mm = re.findall(NUM + r"\s*mm", t)
    if len(mm) == 3:
        return {"w": fnum(mm[0]), "d": fnum(mm[1]), "h": fnum(mm[2]), "unit": "mm"}
    return None


def chemistry(text):
    t = (text or "").lower()
    if re.search(r"lifepo4|lithium iron phosphate", t):
        return "lifepo4"
    if re.search(r"semi-?solid", t):
        return "semi_solid"
    if re.search(r"sodium-?ion", t):
        return "sodium_ion"
    if re.search(r"(lithium[- ])?polymer|li-?po\b", t):
        return "li_polymer"
    if re.search(r"lithium-?ion|li-?ion|ternary|18650|21700", t):
        return "li_ion"
    return None


def wireless(text):
    t = text or ""
    if re.search(r"Qi\s*2\.2", t):
        std = "qi2_2"
    elif re.search(r"Qi\s*2\b|Qi2", t):
        std = "qi2"
    elif re.search(r"\bQi\b|wireless charg", t, re.I):
        std = "qi"
    elif re.search(r"magsafe|magnetic", t, re.I):
        std = "magsafe_compatible"
    else:
        return None, None
    m = re.search(r"(?:Qi\s*2(?:\.2)?|wireless|magnetic|MagSafe)[^.;|]{0,30}?(\d{1,2}(?:\.\d)?)\s*W\b", t, re.I) or \
        re.search(r"(\d{1,2}(?:\.\d)?)\s*W\s*(?:Qi|wireless|magnetic|MagSafe)", t, re.I)
    return std, (fnum(m[1]) if m and float(m[1]) <= 30 else None)


def display(text):
    t = (text or "").lower()
    if re.search(r"smart (digital )?display|tft|real-time (smart )?display", t):
        return "smart_display"
    if re.search(r"digital display|lcd|led display|percentage display|% display|digital screen", t):
        return "digital_percent"
    if re.search(r"led (battery )?indicator|indicator lights?|led lights? indicat", t):
        return "led_indicator"
    return None


def form_factor(title):
    t = (title or "").lower()
    if re.search(r"magnetic|maggo|magsafe|qi2|magflow|snapgo|picogo", t):
        return "magnetic"
    if re.search(r"ac plug|foldable plug|3-in-1 power bank|wall charger.*power bank|fusion|plug", t):
        return "ac_plug"
    if re.search(r"laptop|1[0-9]{2}w|2[0-9]{2}w|300w", t):
        return "laptop"
    if re.search(r"rugged|outdoor|solar", t):
        return "rugged"
    if re.search(r"built-?in (usb-c )?cable|integrated cable|retractable", t):
        return "built_in_cable"
    if re.search(r"\bmini\b|nano|pocket|slim|5000\s*mah|5k\b", t):
        return "mini"
    return "standard"


def passthrough(text):
    t = text or ""
    if re.search(r"(does not|doesn't|not) support pass-?through", t, re.I):
        return False
    if re.search(r"pass-?through charging|charge (the power bank and|both) .{0,40}simultaneously", t, re.I):
        return True
    return None


def recharge_h(text):
    """Full recharge time in hours only from 'fully recharge(s|d) in (about) N hours/hrs/minutes' phrasing."""
    m = re.search(r"(?:fully|full)\s+(?:re)?charge[sd]?\b[^.]{0,40}?\b(?:in|within)\s*(?:about|approx\.?|approximately|just|only)?\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|minutes|mins)", text or "", re.I)
    if not m:
        return None, None
    v = float(m[1]) / (60 if m[2].lower().startswith("min") else 1)
    return round(v, 2), m[0]


def port_type(name):
    n = (name or "").lower()
    if "lightning" in n:
        return "cable_lightning"
    if "cable" in n:
        return "cable_c"
    if "usb-a" in n or "usb a" in n or re.search(r"\ba\d?\b", n):
        return "usb_a"
    if "wireless" in n or "magnetic" in n:
        return "wireless"
    if "ac" == n.strip():
        return "ac"
    if re.search(r"usb-?c|type-?c|\bc\d?\b", n):
        return "usb_c"
    return None


_TOK = (r"(?:USB[- ]?[AC]\d?|Type-?C\d?|OUT\s*\d?|IN\s*\d?|Wire?less(?:\s+(?:Out(?:put)?|Charging))?(?:\s*\([^)]*\))?|Magnetic(?:\s+Wireless)?|"
        r"(?:Built-?in\s+)?(?:USB-C\s+)?(?:C-?)?Cab(?:le|el)s?|Ports?)")
PORTSEG = re.compile(r"(?<![\w.])(?:(Total\s*(?:\[[^\]]*\]|\((?:[^()]|\([^()]*\))*\)))\s*[:：]?|((?:OUT|IN)\d(?:\s*[/&+]\s*(?:OUT|IN)?\d)*\s*\((?:Type-|USB-)[^)]*\))\s*[:：]?|("
                     + _TOK + r"(?:\s*(?:[/&+,]|\band\b)?\s*" + _TOK + r")*(?:\s*\((?:Type-|USB-)[^)]*\))?)\s*(?:Output|Input)?\s*[:：])", re.I)


def port_segments(text):
    """'OUT1/OUT2: 5V⎓3A ... 45W(Max); OUT3: ...; OUT1+OUT2: 15W(Max)' -> [(name, text, kind)], kind in port | combo | ambiguous.
    '+' or 'Total' = a combination. '&' means 'each of' ONLY when the same block prints '+' combinations (INIU 'OUT1&OUT2: 45W' next to
    'OUT1+OUT2: 15W'); without that context ('USB-A1 & Type-C1 & Type-C2: 210W') each-port vs all-ports is ambiguous (review 3)."""
    t = clean(text)
    ms = list(PORTSEG.finditer(t))
    raw = []
    for i, m in enumerate(ms):
        seg = t[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(t)].strip(" ;,")
        name = re.sub(r"\s*(?:Output|Input)?\s*[:：]?$", "", m.group(0).strip(), flags=re.I).strip()
        raw.append((name, seg))
    plus_ctx = any("+" in n for n, _ in raw)
    out = []
    for name, seg in raw:
        if re.search(r"\+|^total", name, re.I):
            kind = "combo"
        elif "&" in name and not plus_ctx:
            kind = "ambiguous"
        else:
            kind = "port"
        out.append((name, seg, kind))
    return out


def port_tokens(name):
    """Port name -> physical port tokens. 'OUT1/OUT2' / 'OUT1&OUT2' -> [OUT1, OUT2]; 'USB-C Cable / Port' -> [CABLE, C]; 'USB-C1/C2' -> [C1, C2];
    'Wireless OUT (Phone)' -> [W(PHONE)]; 'OUT3 (USB-A1)' -> [OUT3] (the OUTn number wins when printed)."""
    parts = [x for x in re.split(r"\s*/\s*|\s*&\s*|\s*,\s*|\s+and\s+", re.sub(r"(?i)^combined\s+", "", name or "")) if x.strip()]
    toks, typ = [], None
    for x in parts:
        u = x.upper()
        m = re.search(r"\bOUT\s*(\d)", u)
        if re.search(r"WIRE?LESS|MAGNETIC|\bQI", u):
            q = re.search(r"\(([^)]*)\)", u)
            toks.append("W" + (f"({q[1].strip()})" if q else "")); continue
        if m:
            toks.append("OUT" + m[1]); continue
        if "CABLE" in u or "CABEL" in u:
            toks.append("CABLE"); typ = typ or "C"; continue
        c = re.search(r"(?:USB[- ]?|TYPE-?)?C\s*(\d)\b|^C(\d)\b", u)
        a_ = re.search(r"(?:USB[- ]?)?A\s*(\d)\b|^A(\d)\b", u)
        if c:
            typ = "C"; toks.append("C" + (c[1] or c[2])); continue
        if a_:
            typ = "A"; toks.append("A" + (a_[1] or a_[2])); continue
        if re.search(r"USB[- ]?C|TYPE-?C", u):
            typ = "C"; toks.append("C"); continue
        if re.search(r"USB[- ]?A", u):
            typ = "A"; toks.append("A"); continue
        if re.fullmatch(r"\s*OUT(PUT)?\s*", u):
            toks.append("OUT"); continue
        if re.fullmatch(r"\s*PORTS?\s*", u) and typ:
            toks.append(typ); continue
        toks.append(re.sub(r"[^A-Z0-9]", "", u))
    return toks


ADDITIVE = re.compile(NUM + r"\s*W\s*\+\s*" + NUM + r"\s*W")


def all_port_total(port_names, combos):
    """Shopper-visible 'all ports at once' output (review 3, fix 1). port_names: names of the individual output ports (the physical inventory);
    combos: [(name, segment text)] of printed combinations. -> (W, participating tokens, None) or (None, None, reason).
    Accepted only when a combination's members, each naming exactly one port, cover EVERY port of the inventory and the segment prints the
    figure ('15W(Max)', '10W + 5W = 15W'); a subset ('OUT1+OUT2' when OUT3 exists), an alternative member ('OUT1/OUT2+Wireless'), an unprinted
    sum ('65W+15W (Total)') or disagreeing covering combinations are never a total."""
    inv = {t for n in port_names for t in port_tokens(n)}
    if not combos:
        return None, None, None
    if not inv:
        return None, None, "combination printed but no individual port inventory to check it against"
    found, why = {}, []
    for name, seg in combos:
        inner = re.match(r"(?i)total\s*[\(\[](.*)[\)\]]\s*$", name)
        body = inner[1] if inner else re.sub(r"(?i)^combined\s+|\s*total\s*", "", name)
        members = [m for m in re.split(r"\s*\+\s*|\s*,\s*|\s+and\s+", body) if m.strip()]
        mt = [port_tokens(m) for m in members]
        if not members or any(len(x) != 1 for x in mt):
            why.append(f"'{name}': a member names several alternative ports"); continue
        cover = {x[0] for x in mt}
        if not inv <= cover:
            why.append(f"'{name}' omits {', '.join(sorted(inv - cover))}"); continue
        if ADDITIVE.search(seg) and not re.search(r"=\s*" + NUM + r"\s*W", seg) and not MAXW.search(seg.replace(ADDITIVE.search(seg)[0], " ")):
            why.append(f"'{name}': additive figures, sum not printed"); continue
        eq = re.search(r"=\s*" + NUM + r"\s*W", seg)
        mw = [fnum(next(x for x in m if x)) for m in MAXW.findall(seg)]
        w = fnum(eq[1]) if eq else (max(mw) if mw else None)
        if w is None:
            ws = re.findall(r"(?<![\d.])" + NUM + r"\s*W\b(?!h)", RANGE.sub(" ", clean(seg)))
            w = fnum(ws[0]) if len(set(ws)) == 1 else None
        if w is None:
            why.append(f"'{name}': no single printed W figure"); continue
        found.setdefault(w, sorted(cover))
    if len(found) == 1:
        w, toks = next(iter(found.items()))
        return w, toks, None
    if len(found) > 1:
        return None, None, "combinations covering every port print different totals: " + ", ".join(f"{w} W" for w in sorted(found))
    return None, None, "no printed combination covers every port (" + "; ".join(why)[:200] + ")"


def ports_from(text, direction="out"):
    """-> (ports list, simultaneous literal, total W or Unresolved or None, participating tokens or None). Ports = individual ports only
    (ambiguous '&' segments are neither a port nor a total; they stay in the simultaneous literal)."""
    ports, combos, lit = [], [], []
    for name, seg, kind in port_segments(text):
        fx, pps, mw, _ = pdos(seg)
        if kind != "port":
            lit.append(f"{name}: {seg}"[:120])
            if kind == "combo":
                combos.append((name, seg))
            continue
        ports.append({"name": name, "type": port_type(name), "direction": direction, "max_w": mw, "fixed_pdos": fx or None, "pps": pps or None})
    amb = [n for n, _, k in port_segments(text) if k == "ambiguous"]
    total, toks, why = all_port_total([p["name"] for p in ports], combos)
    if total is None and (why or amb):
        total = Unresolved(why or f"'{amb[0]}': '&' without '+' combinations does not say each-port or all-ports")
    return ports, "; ".join(lit) or None, total, toks
