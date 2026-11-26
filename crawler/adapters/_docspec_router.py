"""Pure spec-table parser for router datasheets / spec sheets, r6 (2026-11-25): docspec-router@2. No network, deterministic, text layer only.

@1 cell rules are kept (one widening: a slash list '802.11a/b/g/n/ac/ax' reads its highest token). @2 adds three layouts seen in the
126 stored router documents (A2 r5 hosts):
  1. NETGEAR "Technical Specifications" bullet prose: column-aware bullet items ('•' parent, '-' children, wrapped continuation lines at
     the item's text column). Only items that open with an explicit key phrase are read:
       'WiFi 7 BE9300 Router Tri-band WiFi' / 'BE3600 Router Dual-Band WiFi' / 'WiFi 6 (802.11ax) dual band WiFi (AX1800)'
                                                                     -> wifi.generation (+ band word -> wifi.band_count)
       'Tri-band with 6 streams of WiFi' / 'Simultaneous Tri-band WiFi'           -> wifi.band_count (the maker's word)
       '- 6 GHz (2x2)' / '- 5 GHz-1 (4x4)' / '- Radio 3: IEEE 802.11a/n/ac/ax 6GHz' -> wifi.has_6ghz on a 6 GHz radio row; Radio rows also give
                                                                                    wifi.generation from the highest standard (all rows read)
       '- (1) 2.5 Gbps internet port', '- One (1) 10 Gig internet WAN port'         -> port.wan_speed_mbps
       '- (2) 2.5 Gbps Ethernet LAN ports' + '- (2) 10/100/1000 Mbps ... LAN ports' -> port.lan_count (sum) / port.lan_max_mbps
       '(5) 10/100/1000 Mbps Gigabit Ethernet ports' + '- 1 WAN & 4 LAN'            -> WAN + LAN split of one speed (counts must add up)
       'Powerful quad-core 2.0 GHz processor' (alone or under a 'Processor' parent)  -> hw.cpu_cores / hw.cpu_ghz
     Items under a parent naming Satellite(s) / (each) are a different unit of a kit and are never read. A port group holding a
     port-looking line that does not parse reads no LAN facts (no partial counts).
  2. In-cell sub-labels (GL.iNet): 'WAN Port: 1 x 2.5G Port (10/100/1000/2500Mbps)', 'LAN Port: ...', band rows
     '5GHz: 802.11a/n/ac/ax/be, 2882Mbps' (radio rows, as above); 'Ethernet Port  1 x 2.5G WAN, 1 x 2.5G LAN'; CPU cell
     'Qualcomm Quad-core @1.1GHz' (hw.soc_vendor only when the cell opens with the vendor word; cores; clock only with a core count).
  3. Ubiquiti label/value cells with continuation lines (a following line whose first segment sits at the value column continues the cell):
     'Networking interface  LAN: (4) GbE RJ45 ports / WAN: (1) GbE RJ45 port', '(8) LAN: GbE RJ45 ports', 'WiFi standards  802.11a/b/g /
     WiFi 4/WiFi 5/WiFi 6', 'Processor  Dual-core Arm Cortex A53 at 1.35 GHz', radio sub-rows 'MIMO  6 GHz  2x2' -> has_6ghz.
  Product heading (NETGEAR TS page title, one whole segment in the first lines of a page): 'Whole Home Tri-band Mesh WiFi 7 System',
  'Nighthawk WiFi 7 Tri-Band Router' -> wifi.generation (+ band word).

Every fact carries `row`: the full text of the item / cell group it was read from. docspec-attach-r3@2 uses it on multi-model sheets
(row-scoped binding). Facts are per group; T.single then drops any key whose groups disagree (UDM-Pro RJ45 WAN 1G vs SFP+ WAN 10G reads
no WAN speed). Affirmative only: no false / zero from silence; 802.11ax + 6 GHz is never promoted to 6E; an AX class code alone sets nothing.
"""
import re

import _docspec_tv as T

VERSION = 2
NAME = "docspec-router"

GEN_RANK = {"wifi4": 4, "wifi5": 5, "wifi6": 6, "wifi6e": 6.5, "wifi7": 7}
GEN = {"7": "wifi7", "6e": "wifi6e", "6": "wifi6", "5": "wifi5"}
TOK = {"n": "wifi4", "ac": "wifi5", "ax": "wifi6", "be": "wifi7"}
NB = {"dual": 2, "tri": 3, "quad": 4}
NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
CORES = {"single": 1, "dual": 2, "tri": 3, "triple": 3, "quad": 4, "hexa": 6, "six": 6, "octa": 8, "eight": 8}
BAND = r"(Dual|Tri|Quad)[- ]?band"
BUL = re.compile(r"^[•●▪\-–]\s")
SAT = re.compile(r"(?i)\bsatellites?\b|\bextenders?\b|\(each\)")
CPU_ITEM = re.compile(r"(?i)^Powerful\s+\S+[- ]core\s+[\d.]+\s*GHz\s+processor$")
HEADING = re.compile(r"(?i)^(?:(?:Nighthawk|Orbi)(?:\s+\d{3}\s+Series)?\s+)?(?:Whole\s+Home\s+)?(?:(?P<b1>Dual|Tri|Quad)[- ]?band\s+)?(?:Mesh\s+)?WiFi\s*(?P<g>7|6E|6|5)"
                     r"\s+(?:(?P<b2>Dual|Tri|Quad)[- ]?band\s+)?(?:Mesh\s+)?(?:WiFi\s+)?(?:Router|System|Satellite|Add-on\s+Satellite)s?(?:\s+[–-](?:\s+.*)?)?$")


# ------------------------------------------------------------------------------------------------------------------------- @1 cell rules
def _std_list(v):
    best = None
    for m in re.finditer(r"(?i)802\.11\s*([a-z]{1,2}(?:\s*/\s*[a-z]{1,2})+)\b", v):
        for t in re.split(r"\s*/\s*", m[1].lower()):
            g = TOK.get(t)
            if g and (best is None or GEN_RANK[g] > GEN_RANK[best]):
                best = g
    return best


def _gen(v):
    if re.search(r"(?i)wi-?fi\s*7\b|802\.11\s*be\b", v):
        return {"wifi.generation": "wifi7"}
    if re.search(r"(?i)wi-?fi\s*6E\b", v):
        return {"wifi.generation": "wifi6e"}
    if re.search(r"(?i)wi-?fi\s*6\b|802\.11\s*ax\b", v):
        return {} if re.search(r"(?i)6\s*GHz", v) else {"wifi.generation": "wifi6"}
    if re.search(r"(?i)wi-?fi\s*5\b|802\.11\s*ac\b", v):
        return {"wifi.generation": "wifi5"}
    g = _std_list(v)        # @2: slash list -> highest token (same 6 GHz guard)
    if g and not (g == "wifi6" and re.search(r"(?i)6\s*GHz", v)):
        return {"wifi.generation": g}
    return {}


def _bands(v):
    out = {}
    m = re.search(r"(?i)\b(dual|tri|quad)[- ]band\b", v)
    if m:
        out["wifi.band_count"] = NB[m[1].lower()]
    if re.search(r"(?i)\b6\s*GHz\b", v):
        out["wifi.has_6ghz"] = True
    return out


def _lan(v):
    m = re.match(r"(?i)^\s*(\d)\s*(?:x\s*)?(?:\(|[0-9.]+\s*G|Gigabit|10/100|Ethernet|LAN|RJ-?45|ports?\b)", v)
    return {"port.lan_count": int(m[1])} if m else {}


def _wan(v):
    if re.search(r"(?i)\band\b|\+|,|/\s*\d+(?:\.\d)?\s*G", v):
        return {}               # two ports / combo cells: not one speed
    if re.search(r"(?i)\b10\s*/\s*100\s*/\s*1000\b", v):
        return {"port.wan_speed_mbps": 1000}
    m = re.search(r"(?i)\b(\d{1,2}(?:\.\d)?)\s*(?:G\b|Gbps|Gigabit|GbE)", v)
    if m:
        return {"port.wan_speed_mbps": int(float(m[1]) * 1000)}
    if re.search(r"(?i)\bGigabit\b", v):
        return {"port.wan_speed_mbps": 1000}
    return {}


RULES = [
    (r"(?:Wi-?Fi|Wireless)(?:\s+(?:Standards?|Technology|Protocol))?", lambda v: dict(_gen(v), **{k: x for k, x in _bands(v).items() if k == "wifi.has_6ghz"})),
    (r"(?:Wireless\s+|Wi-?Fi\s+)?(?:Bands?|Frequency(?:\s+Bands?)?|Radios?)", _bands),
    (r"(?:Ethernet\s+)?LAN(?:\s+Ports?)?", _lan),
    (r"(?:WAN|Internet)(?:\s+Port)?", _wan),
]


# ------------------------------------------------------------------------------------------------------------------------ @2 helpers
def segs(line):
    """[(column, text)] of one layout line, split at runs of 3+ spaces (tabs expanded)."""
    line = line.expandtabs(8)
    out = []
    for m in re.finditer(r"\S(?:.*?\S)?(?=\s{3,}|\s*$)", line):
        if out and re.fullmatch(r"[•●▪\-–]", out[-1][1]):
            out[-1] = (out[-1][0], out[-1][1] + "   " + m[0].strip())          # a lone bullet marker ('-\tRadio 4: ...') owns the next segment
        else:
            out.append((m.start(), m[0].strip()))
    return out


def clean(t):
    t = re.sub(r"(?<=[A-Za-z][a-z])\d{1,2}\b", "", t)          # footnote digits glued to a word: 'WiFi1', 'GHz3', 'Gbps1' (never 'RBE773')
    t = re.sub(r"[†‡∞*]+|[\x00-\x08\x0b-\x1f]", "", t)          # footnote marks, stray control bytes ('\x07Radio 1: ...')
    return " ".join(t.replace("®", "").replace("™", "").split())


def speed(t):
    """Fastest speed (Mbps) printed in one port statement; None when none."""
    best = None
    for m in re.finditer(r"(?i)\b(\d{2,5}(?:/\d{2,5})+)\s*Mbps", t):
        best = max(best or 0, max(int(x) for x in m[1].split("/")))
    for m in re.finditer(r"(?i)(?<![\d/])(\d{1,2}(?:\.\d)?)\s*(?:Gbps|Gig(?:abit)?\b|GbE|G\b)", t):
        best = max(best or 0, int(float(m[1]) * 1000))
    for m in re.finditer(r"(?i)(?<![\d/])(\d{3,5})\s*Mbps", t):
        best = max(best or 0, int(m[1]))
    if best is None and re.search(r"(?i)\bGigabit\b|\bGbE\b", t):
        best = 1000
    return best


def count(t):
    m = re.match(r"(?i)^(?:(one|two|three|four|five|six|seven|eight)\s+)?\((\d{1,2})\)\s*", t)
    if m:
        if m[1] and NUM[m[1].lower()] != int(m[2]):
            return None, t
        return int(m[2]), t[m.end():]
    m = re.match(r"(?i)^(\d{1,2})\s*x\s*", t)
    return (int(m[1]), t[m.end():]) if m else (None, t)


def cpu(t):
    out = {}
    m = re.search(r"(?i)\b(single|dual|tri|triple|quad|hexa|six|octa|eight)[- ]core\b", t)
    g = re.search(r"(?i)(?<![\d.])(\d(?:\.\d{1,2})?)\s*GHz\b", t)
    if m:
        out["hw.cpu_cores"] = CORES[m[1].lower()]
        if g:
            out["hw.cpu_ghz"] = float(g[1])
    v = re.match(r"(?i)^(qualcomm|broadcom|mediatek|realtek|marvell)\b", t)
    if v:
        out["hw.soc_vendor"] = v[1].lower()
    return out


def port_item(t):
    """One port statement -> (role, count, speed) or None. role: wan / lan / combo / ports (no role printed)."""
    n, rest = count(t)
    if n is None:
        return None
    if re.search(r"(?i)\bUSB\b", rest):
        return None
    if re.search(r"(?i)WAN\s*/\s*LAN|LAN\s*/\s*WAN|internet\s*/\s*LAN", rest):
        return ("combo", n, speed(rest))
    wan = re.search(r"(?i)\b(?:WAN|internet)\b", rest)
    lan = re.search(r"(?i)\bLAN\b", rest)
    if wan and lan:
        return None
    if wan:
        return ("wan", n, speed(rest))
    if lan:
        return ("lan", n, speed(rest))
    if re.search(r"(?i)\bports?\b", rest):
        return ("ports", n, speed(rest))
    return None


def port_facts(items):
    """Port statements of ONE group (a bullet block / a cell) -> facts. Fails closed on anything partial."""
    out = {}
    wans = [x for x in items if x and x[0] == "wan"]
    lans = [x for x in items if x and x[0] == "lan"]
    bad = any(x is None or x[0] == "combo" for x in items)
    if len(wans) == 1 and wans[0][1] == 1 and wans[0][2]:
        out["port.wan_speed_mbps"] = wans[0][2]
    if lans and not bad:
        out["port.lan_count"] = sum(x[1] for x in lans)
        if all(x[2] for x in lans):
            out["port.lan_max_mbps"] = max(x[2] for x in lans)
    return out


def items(lines):
    """Column-aware bullet items: [(col, marker, text, parent_text)], wrapped continuation lines joined."""
    rows = [segs(ln) for ln in lines]
    out, parents = [], {}
    for i, row in enumerate(rows):
        for col, s in row:
            m = re.match(r"^([•●▪\-–])\s+(\S.*)$", s)
            if not m:
                continue
            tcol = col + (len(s) - len(m[2]))
            text = [m[2]]
            for nxt in rows[i + 1:i + 4]:
                cont = [x for c, x in nxt if abs(c - tcol) <= 1 and not BUL.match(x)]
                if not cont or any(abs(c - col) <= 1 and BUL.match(x) for c, x in nxt):
                    break
                text.append(cont[0])
            t = clean(" ".join(text))
            if m[1] in "•●▪":
                parents = {c: p for c, p in parents.items() if abs(c - col) > 1}
                parents[col] = t
                out.append((col, "•", t, None))
            else:
                par = next((parents[c] for c in sorted(parents, reverse=True) if col - 8 <= c < col), None)   # children sit ~4 cols in
                out.append((col, "-", t, par))
    return out


def _f(k, v, row, page):
    q = " ".join(str(row).split())
    return {"key": k, "value": v, "raw": q[:200], "quote": q[:200], "page": page, "ocr": False, "ocr_conf": None, "row": q}


def _radio(std, band, row, page):
    s = std.lower().replace("802.11", "")
    return _f("radio", [_std_list(std) or TOK.get(s), band], row, page)


def bullets(page):
    out, its, groups, n = [], items(page["text"].splitlines()), {}, page["n"]
    for idx, (col, mk, t, par) in enumerate(its):
        if mk == "•":
            m = re.match(r"(?i)^(?:(?:Nighthawk|Orbi)\s+)?WiFi\s*(7|6E|6|5)\s+(?:\((802\.11\s*[a-z]{2})\)\s+)?(?:(BE|AXE|AX|AC)\d{3,5}\s+)?"
                         rf"(?:Router\s+)?(?:Simultaneous\s+)?(?:{BAND})?", t)
            if m and (m[2] or m[3] or m[4]):
                g = GEN[m[1].lower()]
                cls = {"BE": "wifi7", "AXE": "wifi6e", "AX": "wifi6", "AC": "wifi5"}.get((m[3] or "").upper())
                std = TOK.get((m[2] or "").lower().replace("802.11", "").strip())
                if cls in (None, g) and (std in (None, g) or (g == "wifi6e" and std == "wifi6")):
                    out.append(_f("wifi.generation", g, t, n))
                    if g == "wifi6e":
                        out.append(_f("wifi.has_6ghz", True, t, n))
                    if m[4]:
                        out.append(_f("wifi.band_count", NB[m[4].lower()], t, n))
                continue
            m = re.match(rf"(?i)^(BE|AXE)\d{{3,5}}\s+Router\s+{BAND}\s+WiFi$", t)
            if m:
                out.append(_f("wifi.generation", {"BE": "wifi7", "AXE": "wifi6e"}[m[1].upper()], t, n))
                out.append(_f("wifi.band_count", NB[m[2].lower()], t, n))
                if m[1].upper() == "AXE":
                    out.append(_f("wifi.has_6ghz", True, t, n))
                continue
            m = re.match(rf"(?i)^(?:Simultaneous\s+{BAND}(?:\s+WiFi)?|{BAND}\s+with\s+\d{{1,2}}\s+streams\s+of\s+WiFi)$", t)
            if m:
                out.append(_f("wifi.band_count", NB[(m[1] or m[2]).lower()], t, n))
                continue
            if CPU_ITEM.match(t):
                out += [_f(k, v, t, n) for k, v in cpu(t).items()]
                continue
            pi = port_item(t)
            if pi is not None:
                groups.setdefault(idx, [t, []])[1].append(pi)
            continue
        if par is None:
            continue
        m = re.match(r"(?i)^(?:Radio\s+\d\s*:\s*)?(2\.4|5|6)\s*GHz(?:-\d)?\s*\(\d\s*x\s*\d\)", t) or \
            (re.fullmatch(r"(?i)(2\.4|5|6)\s*GHz(?:-\d)?", t) if re.search(rf"(?i){BAND}|streams", par) else None)   # bare band row under a band item
        if m:
            if m[1] == "6":
                out.append(_f("wifi.has_6ghz", True, t, n))
            continue
        m = re.match(r"(?i)^Radio\s+\d\s*:\s*IEEE\s+(802\.11[a-z/]+),?\s*(2\.4|5|6)\s*GHz\b", t)
        if m:
            out.append(_radio(m[1], m[2], t, n))
            continue
        if SAT.search(par):
            continue
        if CPU_ITEM.match(t) and re.match(r"(?i)^Processor\b", par):
            out += [_f(k, v, t, n) for k, v in cpu(t).items()]
            continue
        pidx = max((j for j in range(idx) if its[j][1] == "•" and its[j][2] == par), default=None)
        if pidx is None or not re.search(r"(?i)\bports?\b", par):
            continue
        g = groups.setdefault(pidx, [par, []])
        m = re.match(r"(?i)^(\d)\s+WAN\s*&\s*(\d)\s+LAN$", t)
        if m:
            g[1].append(("split", int(m[1]), int(m[2])))
            continue
        pi = port_item(t)
        if pi is None and re.search(r"(?i)\b(?:LAN|WAN|internet|Ethernet)\b", t) and not re.search(r"(?i)\bUSB\b", t):
            g[1].append(None)                                   # a port-looking line we cannot read: the group reads no LAN facts
        elif pi is not None:
            g[1].append(pi)
    for head, its_ in groups.values():
        split = [x for x in its_ if x and x[0] == "split"]
        rest = [x for x in its_ if not (x and x[0] in ("split", "ports"))]
        if split:
            ports = [x for x in its_ if x and x[0] == "ports"]
            if len(split) != 1 or len(ports) != 1 or ports[0][1] != split[0][1] + split[0][2] or not ports[0][2] or rest:
                continue
            rest = [("wan", split[0][1], ports[0][2]), ("lan", split[0][2], ports[0][2])]
        row = head + " | " + " | ".join(str(x) for x in its_)
        out += [_f(k, v, row, n) for k, v in port_facts(rest).items()]
    return out


PORT_CELL = re.compile(r"(?i)(?:Networking|Ethernet|SFP\+?)\s+(?:interface|Ports?)|Ethernet\s+Ports?|Interfaces?")


def cells(page):
    """Label/value cells with continuation, plus in-cell sub-labels. -> facts."""
    out, n = [], page["n"]
    rows = [segs(ln) for ln in page["text"].splitlines()]
    for i, row in enumerate(rows):
        for j, (col, s) in enumerate(row):
            s = clean(s)
            m = re.match(r"(?i)^(WAN|LAN)\s*Ports?\s*:\s*(.+)$", s)                       # GL.iNet 'WAN Port: 1 x 2.5G Port (...)'
            if m:
                c, rest = count(m[2])
                if c and speed(rest):
                    out += [_f(a, b, s, n) for a, b in port_facts([(m[1].lower(), c, speed(rest))]).items()]
                continue
            m = re.match(r"(?i)^(2\.4|5|6)\s*GHz(?:-\d)?\s*:\s*(802\.11[a-z/]+)", s)          # GL.iNet '5GHz: 802.11a/n/ac/ax/be, 2882Mbps'
            if m:
                out.append(_radio(m[2], m[1], s, n))
                continue
            if j + 1 >= len(row):
                continue
            lab, (vcol, val) = s, row[j + 1]
            group = [clean(val)]
            radio_tab = re.fullmatch(r"(?i)MIMO|Max\.?\s+TX\s+power|Throughput\s+rate|Antenna\s+gain", lab)
            blank = 0
            for nxt in rows[i + 1:i + 12]:
                if not nxt:
                    blank += 1
                    if blank > 1:
                        break
                    continue                                   # Ubiquiti sheets interleave one empty line between sub-rows
                blank = 0
                if abs(nxt[0][0] - vcol) > 2:
                    break
                group.append(clean(nxt[0][1]))
                if len(nxt) > 1 and not radio_tab:
                    break
            full = " ".join(group)
            if PORT_CELL.fullmatch(lab):
                its_ = []
                for v in re.split(r"\s*,\s*", ", ".join(group)):
                    v2 = re.sub(r"(?i)^(WAN|LAN)\s*:\s*(\(\d+\))", r"\2 \1", v)          # 'LAN: (4) GbE RJ45 ports'
                    v2 = re.sub(r"(?i)^(\(\d+\))\s*(WAN|LAN)\s*:", r"\1 \2", v2)          # '(8) LAN: GbE RJ45 ports'
                    pi = port_item(v2)
                    its_.append(pi if pi is not None or not re.search(r"(?i)\b(?:LAN|WAN)\b", v2) else None)
                its_ = [x for x in its_ if x is None or x[0] in ("wan", "lan", "combo")]
                if its_:
                    out += [_f(k, v, f"{lab}: {full}", n) for k, v in port_facts(its_).items()]
            elif re.fullmatch(r"(?i)CPU|Processor|SoC|Chipset", lab):
                out += [_f(k, v, f"{lab}: {full}", n) for k, v in cpu(full).items()]
            elif re.fullmatch(r"(?i)Wi-?Fi\s+standards?", lab):
                g = _gen(full)
                if g:
                    out.append(_f("wifi.generation", g["wifi.generation"], f"{lab}: {full}", n))
            elif radio_tab:
                if any(re.fullmatch(r"6\s*GHz", b) for b in group):
                    out.append(_f("wifi.has_6ghz", True, f"{lab}: 6 GHz", n))
    return out


def heading(page):
    out = []
    for line in page["text"].splitlines()[:6]:
        for _, s in segs(line):
            m = HEADING.match(clean(s))
            if m:
                out.append(_f("wifi.generation", GEN[m["g"].lower()], clean(s), page["n"]))
                if m["b1"] or m["b2"]:
                    out.append(_f("wifi.band_count", NB[(m["b1"] or m["b2"]).lower()], clean(s), page["n"]))
    return out


def radios(facts):
    """Radio rows -> has_6ghz (a 6 GHz row) + generation from the highest standard when every row reads one.
    802.11ax with a 6 GHz radio is not promoted to 6E (same rule as @1)."""
    rs = [f for f in facts if f["key"] == "radio"]
    out = [f for f in facts if f["key"] != "radio"]
    six = [f for f in rs if f["value"][1] == "6"]
    if six:
        out.append(dict(six[0], key="wifi.has_6ghz", value=True))
    gens = [f["value"][0] for f in rs if f["value"][0]]
    if rs and len(gens) == len(rs):
        best = max(gens, key=GEN_RANK.get)
        if not (best == "wifi6" and six):
            src = next(f for f in rs if f["value"][0] == best)
            out.append(dict(src, key="wifi.generation", value=best, row=" | ".join(f["row"] for f in rs)))
    return out


def router(doc):
    out = []
    for page in doc.get("pages") or []:
        if page.get("method") != "text_layer":
            continue
        for raw in page.get("text", "").splitlines():
            for lrx, fn in RULES:
                for lab, val, nxt in T.pairs(raw, lrx):
                    got = fn(val)
                    if not got or (nxt is not None and fn(nxt)):
                        continue
                    q = " ".join(raw.split())
                    out += [{"key": k, "value": x, "raw": val[:200], "quote": q[:200], "page": page["n"], "ocr": False, "ocr_conf": None,
                             "row": q} for k, x in got.items()]
        out += bullets(page) + cells(page) + heading(page)
    return T.single(radios(out))
