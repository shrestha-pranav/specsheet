"""Shared pure parsers for the power-bank adapters (anker_powerbanks, belkin_powerbanks, shopify_powerbanks). No network.

PDO model reused from the GaN-charger pilot (data/gan-chargers/*.json: pd_fixed_pdos "5V3A 9V3A 15V2A 20V1.5A", pps_ranges "3.3-11V 3A"):
fixed PDOs and PPS/variable ranges are kept as normalised literal strings, one port per entry of `out.ports`.
"""
import html, re

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


PORTSEG = re.compile(r"(?:(Total\s*\([^)]*\)|(?:OUT|IN)\d(?:\s*[/&+]\s*(?:OUT|IN)?\d)*(?:\s*\((?:Type-|USB-)[^)]*\))?)\s*[:：]?|("
                     r"USB[- ]?C\d?(?:\s*/\s*(?:USB[- ]?)?C\d?)?(?:\s*/\s*C-?Cab\w*)?(?:\s*\+\s*USB[- ]?[AC]\d?)*|USB[- ]?A\d?(?:\s*&\s*Type-C\d)*|"
                     r"Type-C\d?|Built-?in (?:USB-C )?Cable|C-?Cable|Wireless(?: Charging| Output)?|Magnetic(?: Wireless)?)\s*(?:Output|Input)?\s*[:：])", re.I)


def port_segments(text):
    """'OUT1/OUT2: 5V⎓3A ... 45W(Max); OUT3: ...; OUT1+OUT2: 15W(Max)' -> [(name, text, is_combo)]."""
    t = clean(text)
    ms = list(PORTSEG.finditer(t))
    out = []
    for i, m in enumerate(ms):
        seg = t[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(t)].strip(" ;,")
        name = re.sub(r"\s*(?:Output|Input)?\s*[:：]?$", "", m.group(0).strip(), flags=re.I).strip()
        combo = bool(re.search(r"\+|total", name, re.I)) or name.count("&") >= 2     # 'OUT1&OUT2:' = each of two ports; 'A1 & C1 & C2:' = all ports
        out.append((name, seg, combo))
    return out


def ports_from(text, direction="out"):
    """-> (ports list, simultaneous literal, total W or None)."""
    ports, combos, total, best = [], [], None, 0
    for name, seg, combo in port_segments(text):
        fx, pps, mw, _ = pdos(seg)
        if combo and not MAXW.search(seg) and re.search(NUM + r"\s*W\s*\+\s*" + NUM + r"\s*W", seg):
            mw = fnum(sum(float(x) for x in re.findall(NUM + r"\s*W\b", seg.split("(")[0])))     # '65W+15W (Total)' = 80 W
        if combo:
            combos.append(f"{name}: {seg}"[:120])
            n = 99 if re.match(r"total", name, re.I) else name.count("+") + name.count("&") + 1
            if mw and (total is None or n > best or (n == best and mw > total)):
                total, best = mw, n      # the combination with the most ports = 'all ports at once' (detail stays in `simultaneous`)
            continue
        ports.append({"name": name, "type": port_type(name), "direction": direction, "max_w": mw, "fixed_pdos": fx or None, "pps": pps or None})
    return ports, "; ".join(combos) or None, total
