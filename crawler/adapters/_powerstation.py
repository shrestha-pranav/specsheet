"""Shared pure parsers for the portable power station adapters (shopify_powerstations, ankersolix_stations). No network.

emit_rows(pr, adapter, snap, model, rows, block) maps ONE labelled spec block ({label: value}; labels may carry a 'SECTION / ' prefix) to model
claims and returns the rows it did not map (fingerprints.unmapped). Review-3 rules applied from the start:
- no keyword enums from prose: waveform, chemistry, UPS, expandability and certifications come only from their own labelled rows, and an
  affirmative phrase is required (a negated or dash cell is nothing, never `false`; `false` only from a labelled row whose whole value is 'No');
- totals only with explicit membership: the AC inverter rating is taken from the AC row tagged total/rated (or the block's single AC row with a
  single W figure); a 'N x W' or 'N ports, W Max' figure with N > 1 is neither a per-port nor a total figure; no cross-port total is ever summed;
  solar input total only from one figure not multiplied per port ('500W Max*2' -> per-port only) or an explicit 'Double to .. W' combination;
- capacity bases separate: rated pack energy (cap.energy_wh), usable energy (cap.usable_wh, only when labelled usable/available), pack voltage
  and Ah are distinct keys; Wh is never computed from Ah x V; two different Wh figures in one cell are unresolved;
- every basis stays on the claim: cycle life carries retention_pct (none printed -> unresolved), recharge time charge_to_pct (none printed ->
  unresolved) and charger_w, UPS switchover backup_mode, solar voltage window voltage_basis, AC input ac_charge_mode.
r5 (A2-mon 2026-11-25): chemistry() reads 'LiFePO\u2084' (subscript 4); ups_prose() = the coordinator's UPS-prose ruling (see its docstring),
  the one exception to 'no UPS from prose'.
"""
import html, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _powerbank as P  # noqa: E402

U = P.Unresolved
WRX = re.compile(r"(?<![\d.,])(\d{1,2},\d{3}(?:\.\d+)?|\d+(?:\.\d+)?)\s*(k?)W\b(?!h)", re.I)
NEG = re.compile(r"\b(not|no|non|without|pending|in progress|applying|n/a)\b", re.I)


def txt(s):
    return P.clean(re.sub(r"<br\s*/?>|</p>\s*<p[^>]*>|</li>\s*<li[^>]*>", " ; ", s or ""))


def num(x):
    return P.fnum(str(x).replace(",", ""))


def watts(s):
    return [num(a) * (1000 if k else 1) for a, k in WRX.findall(s or "")]


def dash(v):
    return not v or re.fullmatch(r"\s*(-|–|—|/|n/?a|none)?\s*", v, re.I) is not None


def whs(s):
    out = []
    for a, k in re.findall(r"(?<![\d.,])(\d{1,2},\d{3}(?:\.\d+)?|\d+(?:\.\d+)?)\s*(k?)Wh\b", s or "", re.I):
        out.append(num(a) * (1000 if k else 1))
    return list(dict.fromkeys(P.fnum(x) for x in out))


def kg(s):
    t = s or ""
    t = re.sub(r"\s*(?:±|\+/?-?)\s*\d+(?:\.\d+)?\s*(?=kg|lb)", " ", t)           # '33.7±0.6kg' -> '33.7 kg' (the tolerance is not the weight)
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", t, re.I)
    if m:
        return P.fnum(m[1])
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\b", t, re.I)
    return round(float(m[1]) * 0.45359237, 2) if m else None


def dims(s):
    t = (s or "").replace("×", "x").replace("*", "x").replace("”", '"').replace("″", '"')
    for unit, f in (("mm", 1), ("cm", 10), ("in", 25.4)):
        u = r"(?:mm)" if unit == "mm" else r"(?:cm)" if unit == "cm" else r"(?:in\b|inch(?:es)?|\")"
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:" + u + r")?\s*[a-z]?\s*x\s*(\d+(?:\.\d+)?)\s*(?:" + u + r")?\s*[a-z]?\s*x\s*(\d+(?:\.\d+)?)\s*[a-z]?\s*" + u, t, re.I)
        if m:
            return {"w": round(float(m[1]) * f, 1), "d": round(float(m[2]) * f, 1), "h": round(float(m[3]) * f, 1), "unit": "mm"}
    return None


def chemistry(s):
    t = (s or "").lower()
    if re.search(r"lifepo[4\u2084]|\blfp\b|lithium iron phosphate", t):      # 'LiFePO\u2084' (subscript four, BLUETTI rows) is the same word
        return "lfp"
    if re.search(r"\bnmc\b|ternary|nickel manganese", t):
        return "nmc"
    if re.search(r"sodium|\bna-?ion\b", t):
        return "sodium_ion"
    if re.search(r"semi-?solid", t):
        return "semi_solid"
    if re.search(r"lithium-?ion|li-?ion", t):
        return "li_ion"
    return None


def port_groups(s):
    """'(1x) 30W Max, ... (1x) 100W Max' / '1x 15W; 2x 140W' / '2 ports, 140W Max' / '1 x100W' -> [(count, W or None, per_port_known)]."""
    t = re.sub(r"(?i)\(\s*x\s*(\d)\s*\)\s*:?", r" \1x ", (s or "").replace("×", "x"))
    t = re.sub(r"(?i)(?:^|(?<=; ))(?:usb-?[ac]|type-?c|car|dc)\s*\d\s*:", " 1x ", t)       # 'USB-C1: ...; USB-C2: ...' = one port each
    gs = []
    for m in re.finditer(r"\(?\b(\d)\s*x\)?\s*(?:[A-Za-z][\w-]*\d?\s*:\s*)?([^;()]*?)(?=\(?\b\d\s*x\b|;|$)", t, re.I):
        n, body = int(m[1]), m[2]
        each = re.search(r"(?i)(\d+(?:\.\d+)?)\s*W\s*(?:max\.?\s*)?(?:each|per port)", body)
        tot = re.search(r"(?i)\btotal\b|in total|shared|combined", body)
        w = watts(re.sub(r"(?i)\d+(?:\.\d+)?\s*W\s*(?:in )?total|total\s*\d+(?:\.\d+)?\s*W", "", body))
        if each:
            gs.append((n, num(each[1]), True))
        else:
            gs.append((n, max(w) if w else None, n == 1 and not tot))
    if not gs:
        m = re.search(r"(?i)\b(\d)\s*ports?\b", t)
        w = watts(t)
        each = re.search(r"(?i)(\d+(?:\.\d+)?)\s*W\s*(?:max\.?\s*)?(?:each|per port)", t)
        if m:
            gs.append((int(m[1]), num(each[1]) if each else (max(w) if w else None), int(m[1]) == 1 or bool(each)))
        elif w:
            gs.append((None, max(w), len(set(w)) == 1 and not re.search(r"(?i)total|shared", t)))
    return gs


def solar_window(s):
    rs = [(float(a), float(b)) for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*V?\s*(?:-|–|~|to)\s*(\d+(?:\.\d+)?)\s*V(?:DC|oc)?\b", s or "", re.I)
          if 5 <= float(a) < float(b) <= 600]
    if not rs:
        return None, None
    basis = "voc" if re.search(r"(?i)\bvoc\b|open[- ]circuit", s) else "operating" if re.search(r"(?i)working|operating|mppt (voltage )?range", s) else "unstated"
    return {"min": P.fnum(min(a for a, _ in rs)), "max": P.fnum(max(b for _, b in rs))}, basis


def hours(s):
    t = (s or "").replace("≈", "").replace("~", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|min(?:ute)?s?)", t, re.I)
    if m:
        f = 60 if m[3].lower().startswith("min") else 1
        return {"min": round(float(m[1]) / f, 2), "max": round(float(m[2]) / f, 2)}
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|min(?:ute)?s?)", t, re.I)
    if m:
        f = 60 if m[2].lower().startswith("min") else 1
        v = round(float(m[1]) / f, 2)
        return {"min": v, "max": v}
    return None


def emit_rows(pr, adapter, snap, model, rows, block):
    def E(k, v, raw, lab, cond=None, quote=None):
        P.emit(pr, adapter, snap, k, v, raw, lab, model, cond, quote)

    left, ports, ac_rows, solar_tot, windows = {}, [], [], [], []
    volts = set()
    for lab, val in rows.items():
        l, v = lab.lower(), (val or "").strip()
        sec = l.rsplit(" / ", 1)[0] if " / " in l else ""
        tail = l.rsplit(" / ", 1)[-1]
        if dash(v):
            continue
        inp = bool(re.search(r"\binput\b|charg", sec)) and not re.search(r"output", sec)
        # ---- capacity ---------------------------------------------------------------------------------------------------------
        if re.search(r"(^|/ )((battery pack|battery|pack|total|rated) )?capacity$", l) and not re.search(r"solar|expan|extra|charging time", l):
            ws = whs(v)
            key = "cap.usable_wh" if re.search(r"usable|available", tail) else "cap.energy_wh"
            if len(ws) == 1:
                E(key, ws[0], v, lab)
            elif ws:
                E(key, U(f"{len(ws)} Wh figures ({' / '.join(map(str, ws))}) in one capacity cell"), v, lab)
            vs = {P.fnum(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*V(?:DC)?\b", v) if 5 < float(x) < 1000}
            if len(vs) == 1:
                E("cap.pack_voltage_v", vs.pop(), v, lab)
            ahs = {P.fnum(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*Ah\b", v)}
            if len(ahs) == 1:
                E("cap.pack_ah", ahs.pop(), v, lab)
            continue
        if re.search(r"usable (capacity|energy)|available (capacity|energy)", l):
            ws = whs(v)
            E("cap.usable_wh", ws[0] if len(ws) == 1 else (U("several Wh figures") if ws else None), v, lab)
            continue
        # ---- expansion --------------------------------------------------------------------------------------------------------
        if re.search(r"extra battery|expan|chainable|expandab|scalab", l) and "expansion module" not in l and not re.search(r"\bkw\b|\d\s*kw$", v.lower()):
            ws = whs(v)
            if re.search(r"capacity|max", tail) and ws:
                nb = re.search(r"\(\s*(\d+)\s*[x×]", v)
                E("exp.max_wh", ws[0] if len(ws) == 1 else U("several expanded-capacity figures (configurations)"), v, lab,
                  {"extra_batteries": int(nb[1])} if nb and len(ws) == 1 else None)
            if re.fullmatch(r"(?i)no\.?|not (expandable|supported)\.?", v):
                E("exp.expandable", False, v, lab, quote="labelled row says No")
            elif re.fullmatch(r"(?i)yes\.?", v) or (re.search(r"(?i)supports?|compatible|with|up to|\d\s*[x×]", v) and not NEG.search(v[:20])):
                E("exp.expandable", True, v, lab)
            W_ = r"(?:[A-Z]{2,}[A-Za-z0-9]*|\d+[A-Za-z]*|Max|Pro|Plus|Ultra|Mini|Smart)"
            names = sorted({m[1] + " Extra Battery" for m in re.finditer(r"\b(" + W_ + r"(?: " + W_ + r"){0,4}) Extra Batter(?:y|ies)\b", v)} |
                           set(re.findall(r"\b(?:BP|B)\d{3,4}[A-Z]{0,2}\b", v)) | set(re.findall(r"\bTank(?: PRO \d+)?\b", v)))
            names = {re.sub(r"^(?:Smart )", "", n) for n in names}
            names = sorted(names)
            if names:
                E("exp.batteries", names, v, lab)
            m = re.search(r"(?i)up to\s*(\d+|one|two|three|four|five|six)\b(?=[^;]{0,60}batter)", v) or (re.search(r"^(\d+)\b", v) if "quantity" in tail else None)
            if m:
                n_ = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}.get(m[1].lower(), None) or int(m[1])
                E("exp.max_batteries", n_, v, lab)
            continue
        # ---- AC output --------------------------------------------------------------------------------------------------------
        if not inp and (re.search(r"output", sec) and re.match(r"(\(?\d+x\)? )?(120v )?ac\b", tail) or re.search(r"\bac\b.*(output|outlet)|^(output / )?(\d+x )?ac\b(?!.*input)|ac rated (output|power)|surge|x-?boost|lifting|max device|inverter type|waveform|^ac$|/ ac$|/ \d+x ac$", l)) \
                and not re.search(r"input|charging|bypass", tail):
            vs = [float(x) for pair in re.findall(r"(\d{3})(?:\s*/\s*(\d{3}))?\s*V(?:AC)?\b", v + " " + tail) for x in pair if x and 100 <= float(x) <= 250]
            volts.update(P.fnum(x) for x in vs)
            if re.search(r"pure sine", v + " " + l, re.I) and not re.search(r"(not|non)[- ]pure", v, re.I):
                E("out.ac_waveform", "pure_sine", v, lab)
            elif re.search(r"modified sine", v, re.I) and not re.search(r"pure sine", v, re.I):
                E("out.ac_waveform", "modified_sine", v, lab)
            if re.search(r"inverter type|waveform", l):
                continue
            body = v
            if "surge" in tail or "peak" in tail:
                w = watts(body)
                E("out.ac_surge_w", w[0] if len(set(w)) == 1 else (U("several surge figures") if w else None), v, lab)
                continue
            if re.search(r"x-?boost|lifting|max device|boost", tail):
                w = watts(body)
                E("out.ac_boost_w", w[0] if len(set(w)) == 1 else (U("several boost figures") if w else None), v, lab,
                  quote="resistive-load boost mode (X-Boost / Power Lifting), not the continuous inverter rating")
                continue
            sg = re.search(r"(?i)(?:surge|peak)\D{0,14}?(\d{1,2},\d{3}|\d+)\s*(k?)W\b|(\d{1,2},\d{3}|\d+)\s*(k?)W\s*(?:surge|peak)", body)
            if sg:
                E("out.ac_surge_w", num(sg[1] or sg[3]) * (1000 if (sg[2] or sg[4]) else 1), v, lab)
                body = body.replace(sg[0], " ")
            bs = re.search(r"(?i)(?:x-?boost|power lifting|lifting|boost|heating)\D{0,20}?(\d{1,2},\d{3}|\d+)\s*W\b|(\d{1,2},\d{3}|\d+)\s*W\s*(?:with|in)\s*(?:x-?boost|power lifting|lifting)", body)
            if bs:
                E("out.ac_boost_w", num(bs[1] or bs[2]), v, lab, quote="resistive-load boost mode, not the continuous inverter rating")
                body = body.replace(bs[0], " ")
            gs_ = [int(x) for x in re.findall(r"(?i)\(?\b(\d{1,2})\s*(?:x|×)\)?\s*(?=\d{3}\s*V|nema|ac\b|outlet|\()", body)]
            n = re.search(r"(?i)\b(\d{1,2})\s*(?:ac )?outlets?\b", body) or re.search(r"(?i)(?:^|/ )\(?(\d)\s*x\)?\s*(?:120v )?ac\b", l)
            cnt = sum(gs_) if gs_ else (int(n[1]) if n else None)
            ac_rows.append((lab, v, body, cnt))
            continue
        # ---- DC / USB outputs -------------------------------------------------------------------------------------------------
        if not inp and re.search(r"usb|type-?c|car (power )?(output|port|outlet)|cigarette|car auxiliary|12v (dc )?(outlets?|car|high power)|car port|auxiliary|dc ?5521|dc output|dc outlets?|"
                                 r"6mm|anderson|high power port|wireless charg|wireless output", l) and not re.search(r"input|button|charging time|connection", tail):
            name = lab.rsplit(" / ", 1)[-1]
            if re.search(r"total|combined", tail):
                left[lab] = v                 # a combined figure is not a port (and no cross-port total is published)
                continue
            lead = re.match(r"\(?(\d)\s*x\)?\s*", name, re.I)
            text = f"{lead[1]}x {v}" if lead else v
            typ = "wireless" if "wireless" in l else "usb_c" if re.search(r"usb-?c|type-?c", l) else "usb_a" if re.search(r"usb-?a\b|usb a\b", l) else \
                "car" if re.search(r"car|cigarette|auxiliary", l) else "dc"
            gs = port_groups(text)
            if typ == "wireless":
                w = watts(v)
                E("out.wireless_w", max(w) if w and max(w) <= 30 else None, v, lab)
            single = bool(re.search(r"\bport\b|\boutlet\b", name, re.I)) and not re.search(r"\bports\b|\boutlets\b|\+", name, re.I)
            if gs and single and len(gs) == 1 and gs[0][0] is None:
                gs = [(1, gs[0][1], True)]            # 'USB-C port (output): 18W max': the label names one port
            if not gs:
                gs = [(1 if typ in ("car", "wireless") or single else None, None, True)]
            for c, w, known in gs:
                ports.append({"name": name, "type": typ, "count": c, "max_w": w if known else None, "raw": v[:120], "_amb": (w if not known else None)})
            continue
        # ---- inputs -----------------------------------------------------------------------------------------------------------
        if re.search(r"charging time|recharge time|charge time|charge times", l):
            ch = "solar" if re.search(r"solar|panel|pv", tail) else "car" if re.search(r"car|12v|vehicle|alternator", tail) else \
                "ac" if re.search(r"\bac\b|wall|adapter|power supply|turbo|cable", tail) else None
            hm = re.search(r"solar charging \((\d+)\s*w (?:actual )?input max\)", l)
            if hm:
                solar_tot.append((lab, v, num(hm[1]), "labelled 'Solar Charging (N W Actual Input Max)' heading"))
            if not ch or not hours(v):
                left[lab] = v
                continue
            cw = watts(tail)
            PCT = r"(\d{1,3})\s*%?\s*(?:-|–|to)\s*(\d{2,3})\s*%"
            for i, seg in enumerate(x for x in re.split(r"\s*;\s*", v) if x.strip()):
                h = hours(seg)
                if not h:
                    continue
                own = re.match(r"\s*" + PCT, seg)
                pct = own or (re.search(PCT, l) if i == 0 else None) or (re.search(PCT, seg) if i == 0 and not re.search(PCT + r"\s*:", seg) else None)
                cond = {"charge_to_pct": int(pct[2]), "charger": P.clean(lab.rsplit(" / ", 1)[-1])[:60]} if pct else None
                E(f"in.recharge_{ch}_h", h if pct else U("recharge time printed without its charge range (0-100 % vs 0-80 %)"), seg, lab, cond)
            continue
        if (re.search(r"\bac (charging|input|power input)|charge mode ac input|wall charg", l) or (inp and re.match(r"ac\b", tail))) and not re.search(r"voltage|bypass|current", tail):
            parts = [p for p in re.split(r"\s*;\s*", v) if watts(p)]
            for p in parts or [v]:
                w = watts(p)
                mode = re.search(r"(?i)turbo|ultra[- ]fast|fast|standard|normal|silent|quiet|low speed", p + " " + tail)
                cond = {"ac_charge_mode": re.sub(r"[- ]", "_", mode[0].lower())} if mode and (len(parts) > 1 or re.search(r"mode|fast|low speed|turbo", tail)) else None
                E("in.ac_w", (w[0] if len(set(w)) == 1 else U("several AC input figures")) if w else None, v, lab, cond)
            continue
        if (re.search(r"solar (charging|input)|mppt|pv input|(^|/ )dc input$|8mm|high pv|low pv|xt60", l) or (inp and "solar" in tail)) and not re.search(r"time|cable", tail):
            if re.search(r"total|combined", tail):
                w = watts(v)
                if len(set(w)) == 1:
                    solar_tot.append((lab, v, w[0], "EXPLICIT labelled total/combined solar input row"))
                continue
            win, basis = solar_window(v)
            if win:
                windows.append((lab, v, win, basis))
            pp = re.search(r"(?i)(\d{2,4})\s*W\s*(?:max\.?)?\s*[*x×]\s*(\d)\b", v) or re.search(r"(?i)\b(\d)\s*[x×]\s*(\d{2,4})\s*W", v)
            dbl = re.search(r"(?i)double to[^;]*?(\d{2,4})\s*W", v) or re.search(r"(?i)dual[- ]ports?\s*(\d{1,2},\d{3}|\d{2,4})\s*W", v) or \
                re.search(r"(?i)(\d{1,2},\d{3}|\d{2,4})\s*W\s*(?:in )?total", v)
            cnt = re.search(r"(?i)\(?\b(\d)\s*(?:x\)|ports?\b)", v)
            if dbl:
                solar_tot.append((lab, v, num(dbl[1]), "explicit combined figure ('total' / 'dual port' / 'Double to')"))
            elif pp:
                a, b = pp.groups()
                w, n = (num(a), int(b)) if int(a) > 9 else (num(b), int(a))
                E("in.solar_port_w", w, v, lab, quote=f"per-port figure x {n}: the combined solar maximum is not printed")
                E("in.solar_ports", n, v, lab)
                solar_tot.append((lab, v, U(f"per-port figure x {n}; combined maximum not printed"), None))
            else:
                w = watts(v)
                if len(set(w)) == 1 and not (cnt and int(cnt[1]) > 1 and not re.search(r"(?i)total|combined", v)):
                    solar_tot.append((lab, v, w[0], "single solar-input figure for the row"))
                elif w:
                    solar_tot.append((lab, v, U("solar figure is per port or several figures; combined maximum not printed"), None))
            continue
        if re.search(r"car (charging|input)|car adapter|12v car", l) and not re.search(r"time", tail):
            w = watts(v)
            if w:
                E("in.car_w", w[0] if len(set(w)) == 1 and w[0] <= 400 else U("figure above a 12 V socket input (accessory/alternator rate) or several figures"), v, lab)
            continue
        if re.search(r"max(imum)? input|ac ?\+ ?solar|dual charging|ac \+ pv", l):
            w = watts(v)
            E("in.max_w", w[0] if len(set(w)) == 1 else (U("several figures") if w else None), v, lab)
            continue
        # ---- battery / backup / general ---------------------------------------------------------------------------------------
        if re.search(r"chemistry|battery type|cell type|^battery info / type$|battery / type$", l):
            E("bat.chemistry", chemistry(v), v, lab)
            continue
        if re.search(r"cycle|lifespan", l):
            m = re.search(r"(\d{1,2},\d{3}|\d{3,5})\s*\+?\s*(?:cycles|times)?", v)
            ret = re.search(r"(\d{2})\s*\+?\s*%", v) or re.search(r"(\d{2})\s*\+?\s*%", tail)
            if m:
                E("bat.cycle_life", int(num(m[1])) if ret else U("cycle count printed without the retention it is rated to"), v, lab,
                  {"retention_pct": int(ret[1])} if ret else None)
            continue
        if re.search(r"\bups\b|\beps\b|\baps\b|switch(over|ing)? time|power switching", l):
            m = re.search(r"(\d+(?:\.\d+)?)\s*ms\b", v)
            both = l + " " + v
            mode = "eps" if re.search(r"\beps\b", both, re.I) and not re.search(r"\bups\b", both, re.I) else \
                "aps" if re.search(r"\baps\b|automatic power switching", both, re.I) else "ups"
            if m:
                E("ups.switchover_ms", P.fnum(m[1]), v, lab, {"backup_mode": mode})
            if (m or re.fullmatch(r"(?i)yes\.?", v)) and not NEG.search(v):
                E("ups.supported", True, v, lab, {"backup_mode": mode})
            continue
        if re.search(r"pass-?through", l):
            if re.fullmatch(r"(?i)yes\.?|supported", v):
                E("in.passthrough", True, v, lab)
            continue
        if re.search(r"weight", l) and not re.search(r"package|gross|shipping|lithium content|cart|with |only|accessor|panel", l):
            if re.search(r"\(lbs?\)", l) and any(re.search(r"weight.*\(kg\)", k, re.I) for k in rows):
                continue                      # 'Net weight (lbs)' next to 'Net weight (kg)': the metric row is the figure, no rounding conflict
            E("phys.weight", kg(v), v, lab)
            continue
        if re.search(r"dimension|^size$|/ size$", l) and not re.search(r"package|folded|unfolded", l):
            E("phys.dimensions", dims(v), v, lab)
            continue
        if re.search(r"certif|\bcerts?\b|compliance|safety standard", l):
            marks = [x.strip() for x in re.split(r"[,;/]|\band\b", v) if x.strip() and len(x.strip()) < 40]
            if marks:
                E("cert.marks", marks, v, lab)
            for std, key in (("2743", "cert.ul2743"), ("9540", "cert.ul9540")):
                m = re.search(r"UL\s*-?\s*" + std, v)
                if m and not NEG.search(v[max(0, m.start() - 25): m.end() + 10]):
                    E(key, True, v, lab, quote=f"certification row lists UL {std}")
            continue
        if re.search(r"warranty", l):
            m = re.fullmatch(r"(?i)\s*(\d+)\s*(?:-|\s)?years?(?: (?:limited )?warranty)?\.?\s*", v)
            E("gen.warranty_years", int(m[1]) if m else (U("warranty printed as base + extension or with conditions") if re.search(r"\d", v) else None), v, lab)
            continue
        if re.search(r"self[- ]?consumption|no[- ]load|idle|standby (power|consumption)", l):
            w = watts(v)
            mode = "ac_on" if re.search(r"\bac\b", l + " " + v, re.I) else "standby" if "standby" in l else "unstated"
            E("idle.draw_w", w[0] if len(set(w)) == 1 else (U("several idle figures") if w else None), v, lab, {"idle_mode": mode})
            continue
        if re.search(r"wireless connection|connectivity|^connection", l):
            c = [x for x, rx in (("wifi", r"wi-?fi"), ("bluetooth", r"bluetooth"), ("cellular", r"4g|lte|cellular")) if re.search(rx, v, re.I)]
            if c:
                E("conn.wireless", c, v, lab)
            continue
        left[lab] = v
    # ---- AC inverter rating: explicit membership --------------------------------------------------------------------------------
    acraw = " | ".join(v for _, v, _, _ in ac_rows)[:300]
    if volts:
        E("out.ac_voltage", "/".join(f"{x}V" for x in sorted(volts)), acraw or "AC rows", "AC rows")
    cnts = [c for _, _, _, c in ac_rows if c]
    if cnts:
        uncounted = [r for r in ac_rows if not r[3] and re.search(r"(?i)nema|outlets?\b", r[1])]
        E("out.ac_outlets", sum(cnts) if not uncounted else U("outlet count not printed on every AC outlet row"),
          acraw, " + ".join(l for l, _, _, _ in ac_rows))
    tagged = [(l, v, watts(b)) for l, v, b, _ in ac_rows if re.search(r"(?i)total|rated|continuous", l + " " + b) and watts(b)]
    seen = {(a, b2) for a, b2, _ in tagged}
    untag = [(l, v, watts(b)) for l, v, b, _ in ac_rows if watts(b) and (l, v) not in seen]
    if tagged:
        vals = {w[0] for _, _, w in tagged}
        E("out.ac_continuous_w", vals.pop() if len(vals) == 1 else U("several tagged AC ratings"), " | ".join(v for _, v, _ in tagged),
          " + ".join(l for l, _, _ in tagged), quote="AC inverter rating shared by all AC outlets (row tagged total/rated)")
    elif len(untag) == 1 and len(set(untag[0][2])) == 1 and len([r for r in ac_rows if watts(r[2])]) == 1:
        E("out.ac_continuous_w", untag[0][2][0], untag[0][1], untag[0][0], quote="the block's only AC row with a W figure, a single figure")
    elif untag:
        E("out.ac_continuous_w", U("several AC W figures; which one is the inverter total is not printed"), " | ".join(v for _, v, _ in untag), "AC rows")
    # ---- ports: counts + best single port ---------------------------------------------------------------------------------------
    for typ, kc, kw in (("usb_c", "out.usb_c_count", "out.usb_c_max_w"), ("usb_a", "out.usb_a_count", None), ("car", None, "out.car_w")):
        ps = [p for p in ports if p["type"] == typ]
        if not ps:
            continue
        raw = " | ".join(dict.fromkeys(p["raw"] for p in ps))
        lab = " + ".join(dict.fromkeys(p["name"] for p in ps))
        if kc:
            E(kc, sum(p["count"] for p in ps) if all(p["count"] for p in ps) else U("port count not printed for every row"), raw, lab)
        if kw:
            known = [p["max_w"] for p in ps if p["max_w"]]
            amb = [p["_amb"] for p in ps if p["_amb"]]
            if known and not any(a > max(known) for a in amb):
                E(kw, max(known), raw, lab, quote="best single port: figure printed for one port")
            elif amb:
                E(kw, U("'N x W' / 'N ports, W Max' with N > 1: per-port or shared is not printed"), raw, lab)
    if ports:
        E("out.ports", [{k: p[k] for k in ("name", "type", "count", "max_w")} for p in ports], " | ".join(dict.fromkeys(p["raw"] for p in ports))[:300], "output port rows")
    for lab, v, win, basis in windows:          # one window per solar port; several ports -> each claim names its port (no merged window)
        E("in.solar_voltage", win, v, lab, {"voltage_basis": basis, **({"port": P.clean(lab.rsplit(" / ", 1)[-1])[:60]} if len(windows) > 1 else {})})
    # ---- solar total --------------------------------------------------------------------------------------------------------------
    expl = [s for s in solar_tot if s[3] and s[3].startswith("EXPLICIT")]
    if expl:
        solar_tot = expl
    good = [s for s in solar_tot if not isinstance(s[2], U)]
    if good and len(good) == len(solar_tot) and len({s[2] for s in good}) == 1:
        E("in.solar_w", good[0][2], good[0][1], good[0][0], quote=good[0][3] if len(good) == 1 else f"{good[0][3]} (same figure on {len(good)} rows)")
    elif solar_tot:
        bad = next((s[2] for s in solar_tot if isinstance(s[2], U)), None)
        E("in.solar_w", U("several solar inputs; their combined maximum is not printed" if len(solar_tot) > 1 and bad is None else bad.reason if bad is not None else "?"),
          " | ".join(s[1] for s in solar_tot)[:300], " + ".join(s[0] for s in solar_tot))
    return left


# ---- coordinator ruling r5 (A1, 2026-11-25): ups.switchover_ms from maker prose ----------------------------------------------------------------
# Allowed ONLY when (a) the page is single-SKU (the caller has resolved exactly one model and the page is not a package), (b) the sentence is in
# the maker's own product description (spec/feature copy; text inside <table> = comparison tables is dropped, and a sentence naming another
# model is skipped), (c) the sentence states a number + ms AND 'UPS' / 'switchover' / 'switch time'. '<' / '\u2264' / 'sub-' / 'under' /
# 'within' / 'less than' -> the value is an upper bound: published as 'up to N' (normalize.py qualifier up_to). EPS-only sentences, 'auto-switch'
# without UPS, 'power transition' and sentences with two different ms figures -> nothing.
UPS_WORD = re.compile(r"\bUPS\b|switch-?over|switch(?:ing)? time", re.I)
UPS_MS = re.compile(r"(?:(<|\u2264|&lt;|\bsub-?|\bunder\s+|\bwithin\s+|\bless than\s+|\bin under\s+)\s*)?(?<![\d.])(\d+(?:\.\d+)?)\s*-?\s*ms\b", re.I)
MODEL_TOKEN = re.compile(r"\b(?:[A-Z]{1,4}\d{2,5}[A-Z]{0,3}|(?:Explorer|HomePower|Elite|Premium|Yeti|DELTA|RIVER)\s\d{2,5}[A-Za-z]*)\b")


def ups_prose(body_html, own_names=()):
    """-> (value, sentence) or (None, None). value = number (stated exactly) or 'up to N' (upper bound)."""
    if not body_html:
        return None, None
    t = re.sub(r"(?is)<table.*?</table>|<script.*?</script>|<style.*?</style>", " ", body_html)
    t = re.sub(r"(?i)<br\s*/?>|</(?:p|li|h\d|div|ul)>|<li[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    own = {re.sub(r"[^a-z0-9]", "", n.lower()) for n in own_names if n}
    hits = {}
    for sent in (x for blk in t.split("\n") for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\s*\u2022\s*", re.sub(r"\s+", " ", blk))):
        sent = sent.strip()
        if not sent or not UPS_WORD.search(sent) or re.search(r"\bEPS\b", sent) and not re.search(r"\bUPS\b", sent):
            continue
        ms = UPS_MS.findall(sent)
        if len({x[1] for x in ms}) != 1:
            continue
        others = {re.sub(r"[^a-z0-9]", "", m.lower()) for m in MODEL_TOKEN.findall(sent)} - own
        if others and not any(o in n or n in o for o in others for n in own):
            continue                                    # the sentence names another model: comparison copy, not this SKU's statement
        bound, n = ms[0]
        v = P.fnum(n)
        hits.setdefault(f"up to {n}" if bound else v, sent[:300])
    if len(hits) != 1:
        return None, None
    (v, sent), = hits.items()
    return v, sent


def emit_ups_prose(pr, adapter, snap, model, body_html, own_names=()):
    """Caller contract: one resolved model, not a package page. Only when no labelled row already wrote ups.switchover_ms."""
    if any(c["key"] == "ups.switchover_ms" for c in pr.claims):
        return
    v, sent = ups_prose(body_html, (model,) + tuple(own_names))
    if v is not None:
        P.emit(pr, adapter, snap, "ups.switchover_ms", v, sent, "product description (UPS prose ruling r5)", model, {"backup_mode": "ups"},
               quote=sent)
