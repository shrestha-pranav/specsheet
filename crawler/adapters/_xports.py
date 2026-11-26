"""Pure parser (A2-lap r8): the maker's own laptop port list -> per-port USB-C facts for ASUS, Dell and Microsoft Surface, in the same
output model as _lports.ports (Lenovo PSREF): {"usbc_list": [...], "tb_usb4": str, "video_out": str, "charge_port": str,
"segments": {key: [segment idx]}} with only stated keys, or {} when the list is not fully understood.

A segment is one port group the maker prints ('2x Thunderbolt 4 with support for DisplayPort / power delivery (data speed up to 40Gbps)',
Dell '2x USB Type-C with Thunderbolt 4 (40 Gbps) - supporting USB4, DisplayPort 2.1 and Power Delivery'). Rules (as _lports):
  - every fact comes from the segment that states it; '2x' -> two items with that segment's facts; never pooled across segments;
  - protocol = the segment's printed USB / Thunderbolt name; usb_gbps only from one printed 'N Gbps' figure ('80/120 Gbps' -> none);
    dp_alt only when the segment names DisplayPort ('support display' is not DisplayPort); pd_in_w only from a printed input/charging
    wattage; a bare 'power delivery' (direction and W unstated) sets nothing;
  - tb_usb4 = highest Thunderbolt 5 > Thunderbolt 4 > USB4 printed on a USB-C segment (affirmative only);
  - video_out = the dedicated HDMI / DisplayPort segments, literal;
  - charge_port: 'barrel power port' -> barrel; 'Surface Connect' -> proprietary; a dedicated power port of unstated shape ('DC-in',
    'power-adapter port') -> dedicated (r9: only when the maker's list names such a port; never from the absence of USB-C charging); usb-c only when a USB-C segment itself states charging (or a
    charging line names USB-C as the only charge path); two different stated charge paths -> nothing;
  - any unknown segment, hedge ('Up to 2x', 'OR', 'only for computers with', 'available on select'), or platform/config condition
    ('AMD Ryzen 200 Series:') that governs a port -> {} (the adapter keeps its literal claim).
"""
import re

TB = re.compile(r"\bThunderbolt\W{0,3}\s*(\d)(?:\.0)?\b", re.I)
USB4 = re.compile(r"\bUSB\s?4(?:\.0)?\b", re.I)
USBC = re.compile(r"\bType[‑ -]?C(?:\b|(?=with))|\bUSB[‑-]C\b|\bThunderbolt\b|\bUSB\s?4\b", re.I)
GBPS = re.compile(r"(\d+(?:/\d+)?)\s*Gbps", re.I)
DP = re.compile(r"\b(?:DisplayPort|DP)\b(?:\s*Alt Mode)?\s*(\d\.\d[a-z]?)?", re.I)
RANKS = {"Thunderbolt 5": 3, "Thunderbolt 4": 2, "USB4": 1}
HEDGE = re.compile(r"^up[- ]to\b|\bOR\b|only for computers|available on select|on select (?:models|configurations)|selected models only|"
                   r"varies by|depending on|optional", re.I)
OTHER = re.compile(r"^(?:Type[‑ -]?A\b|USB[ \d.()GenMbps]*Type[‑ -]?A\b|USB(?: \d\.\d)?(?: Gen \d(?:x\d)?)? Type[‑-]?A|USB Type[‑-]?A|USB \d\.\d(?: Gen \d)?(?: \(\d+ ?[GM]bps\))?(?: Type-A)? ports?|"
                   r"USB 2\.0|USB-A|3\.5\s?mm|3\.5-mm|.*\b(?:audio|headset|headphone|microphone)\b|RJ ?45|.*\bLAN\b|.*Ethernet|.*card reader|"
                   r"(?:MicroSD|SD|microSDXC|MicroSDXC)\b|NanoSIM|Nano-?SIM|.*smart card|Kensington|.*lock slot|.*wedge lock|Wedge|Security|"
                   r"Support XG Mobile|XG Mobile|ROG XG|.*Dock\b.*support|Surface Thunderbolt|Fingerprint|Optical|.*fiber)", re.I)
VIDEO = re.compile(r"^(?:HDMI|DisplayPort|Mini DisplayPort|mini-DP|VGA)\b", re.I)
POWER = re.compile(r"\bDC[- ]in\b|power[- ]adapter port|\bpower (?:jack|port|connector)\b|\bbarrel\b|Surface Connect\b", re.I)


def _dash(s):
    return re.sub(r"\s+", " ", s.replace("‑", "-").replace("–", "-").replace("™", "").replace("®", "")).strip(" ,;*")


def _count(s):
    m = re.match(r"^\(?(\d+)\)?\s*(?:x|×)?\s+(.*)$", s, re.S)
    return (int(m.group(1)), m.group(2)) if m else (1, s)


def _protocol(body):
    t = TB.search(body)
    if t:
        return f"Thunderbolt {t.group(1)}"
    if USB4.search(body):
        return "USB4"
    m = re.search(r"\bUSB(?: Type-C|-C)?\s+(\d\.\d(?: Gen \d(?:x\d)?)?)", body)
    if m:
        return "USB " + m.group(1)
    m = re.search(r"\bUSB-C\s*/\s*USB (\d\.\d(?: Gen \d)?)", body)
    return "USB " + m.group(1) if m else None


def _usbc(body, extra=""):
    """One USB-C segment (count removed) + an optional attributed continuation ('with support for: Charging | DisplayPort 1.4a') -> item."""
    text = body + (" " + extra if extra else "")
    item = {}
    p = _protocol(body)
    if p is None:
        return None
    item["protocol"] = p
    g = {x for x in GBPS.findall(text)}
    if len(g) == 1 and "/" not in next(iter(g)):
        item["usb_gbps"] = int(next(iter(g)))
    dps = {(d or "") for d in DP.findall(text)}
    if len(dps) > 1:
        return None
    if dps:
        v = dps.pop()
        item["dp_alt"] = f"DisplayPort {v}" if v else "DisplayPort"
    w = re.search(r"(\d+)\s*W\s+(?:charging|input)", text, re.I)
    if w:
        item["pd_in_w"] = {"max": int(w.group(1))}
    return item


def _charging(text):
    return bool(re.search(r"\bcharging\b", text, re.I))


def _tb(body):
    t = TB.search(body)
    name = f"Thunderbolt {t.group(1)}" if t else ("USB4" if USB4.search(body) else None)
    return name if name in RANKS else None


def _assemble(segs):
    """segs: list of (idx, kind, n, item_or_text, flags). -> output dict."""
    usbc, video, at, tb = [], [], {}, None
    charge, clash, usbc_charge = None, False, False
    for i, kind, n, x, fl in segs:
        if kind == "usbc":
            usbc += [dict(x) for _ in range(n)]
            at.setdefault("usbc_list", []).append(i)
            if fl.get("charging"):
                usbc_charge = True
                at.setdefault("_usbc_charge", []).append(i)
            name = fl.get("tb")
            if name and (tb is None or RANKS[name] > RANKS[tb]):
                tb, at["tb_usb4"] = name, [i]
        elif kind == "video":
            video.append(x)
            at.setdefault("video_out", []).append(i)
        elif kind == "power":
            if charge not in (None, x):
                clash = True
            charge = x
            at.setdefault("charge_port", []).append(i)
        elif kind == "charge_paths":                       # 'Fast charging through Surface Connect or USB-C'
            if len(x) > 1:
                clash = True
            elif x == ["usb-c"]:
                usbc_charge = True
                at.setdefault("_usbc_charge", []).append(i)
    out = {}
    if usbc:
        out["usbc_list"] = usbc
    if tb:
        out["tb_usb4"] = tb
    if video:
        out["video_out"] = "; ".join(video)
    if not clash:
        if charge is None and usbc_charge:
            charge = "usb-c"
            at["charge_port"] = at.get("_usbc_charge", [])
        elif charge is not None and usbc_charge:          # dedicated connector AND USB-C charging both stated: both are real charge paths (list)
            charge = sorted({charge, "usb-c"})
            at["charge_port"] = at.get("charge_port", []) + at.get("_usbc_charge", [])
        if charge:
            out["charge_port"] = charge
    if out:
        out["segments"] = {k: v for k, v in at.items() if k in out}
    return out


def _classify(i, s, side=None, hedged=False):
    """One segment string -> (idx, kind, n, payload, flags) or None if not understood."""
    s = _dash(s)
    if not s:
        return (i, "skip", 0, None, {})
    if s.startswith("*") or re.match(r"^(?:Note:|This feature|MicroSD card reader is available)", s, re.I):
        return (i, "skip", 0, None, {})                   # footnote line
    if re.search(r"(?:Series|processors?|models?|editions?|configurations?)\s*:\s*$", s, re.I):
        return None                                       # platform / config condition header
    if not hedged and HEDGE.search(s):                    # a hedged port group: fine only when it carries none of our facts (USB-A count)
        c = _classify(i, re.sub(r"^up[- ]to\s+", "", s, flags=re.I).replace(" OR ", " "), side, True)
        return c if c is not None and c[1] == "skip" and not USBC.search(s) and not VIDEO.search(s) and not POWER.search(s) else None
    n, body = _count(s)
    if re.search(r"Kensington|lock supported", body, re.I):
        return (i, "skip", 0, None, {})
    if POWER.search(body) and not USBC.search(body):
        kind = "barrel" if re.search(r"\bbarrel\b", body, re.I) else ("proprietary" if re.search(r"Surface Connect", body, re.I) else "dedicated")
        return (i, "power", n, kind, {})
    if USBC.search(body):
        it = _usbc(body)
        if it is None:
            return None
        if side:
            it["side"] = side
        return (i, "usbc", n, it, {"charging": _charging(body), "tb": _tb(body)})
    if VIDEO.match(body):
        return (i, "video", n, s, {})
    if OTHER.match(body):
        return (i, "skip", 0, None, {})
    return None


def _split_asus(cell):
    """ASUS I/O Ports cell -> port-group segments: a new group starts at each 'Nx ' count (commas inside a group are kept)."""
    t = re.sub(r"\bUp to\s+(?=\d+x\s)", "Up-to ", cell.replace("\\n", "\n"), flags=re.I)
    parts = [p for p in re.split(r"(?:,\s*|(?<!Up-to)\s+|^)(?=(?:Up-to )?\d+x\s)", t) if p and p.strip(" ,\n")]
    segs = []
    for p in parts:
        p = p.strip(" ,\n")
        tail = re.split(r",\s*(?=Support XG|Micro ?SD|Smart card|This feature)|\n", p, flags=re.I)
        segs += [x for x in tail if x.strip()]
    return segs


def asus(cell):
    """ASUS techspec 'I/O Ports' cell (one option) or ROG JSON-LD 'I/O Ports' value -> ports dict or {}."""
    if not isinstance(cell, str) or not cell.strip():
        return {}
    segs = []
    for i, s in enumerate(_split_asus(cell)):
        if re.match(r"^\s*(?:This feature|MicroSD card reader is available)", s, re.I):
            continue
        c = _classify(i, s)
        if c is None:
            return {}
        segs.append(c)
    return _assemble(segs)


def asus_options(opts):
    """Several options in one model-code cell: the result only when every option gives the same non-empty result."""
    rs = [asus(o) for o in opts]
    if not rs or any(not r for r in rs):
        return {}
    first = {k: v for k, v in rs[0].items() if k != "segments"}
    return rs[0] if all({k: v for k, v in r.items() if k != "segments"} == first for r in rs) else {}


def dell(lines):
    """Dell Tech Specs 'Ports' list (one item per line) -> ports dict or {}. 'Left Side Ports' / 'Right side' headers give the side."""
    if not isinstance(lines, list):
        lines = [lines] if isinstance(lines, str) else []
    segs, side = [], None
    for i, s in enumerate(lines):
        d = _dash(s)
        if not d or d.startswith("*") or s.strip().startswith("*"):
            continue
        h = re.match(r"^(Left|Right|Rear|Back)[- ]side(?: ports)?:?$|^(Left|Right|Rear|Back) ports:?$", d, re.I)
        if h:
            side = (h.group(1) or h.group(2)).lower().replace("back", "rear")
            continue
        if re.search(r"ports?\s.*\d\s?(?:USB|HDMI).*ports?", d) and len(re.findall(r"(?:^|\s)\d+\s+(?:x\s+)?(?:USB|HDMI|Thunderbolt)", d)) > 1:
            return {}                                       # two port groups run together in one line
        if re.match(r"^\(?\d+\)?\s*(?:x\s+)?USB\b", d) and not USBC.search(d) and not HEDGE.search(d):
            segs.append((i, "skip", 0, None, {}))           # Dell names Type-C explicitly; a bare 'USB 3.2 Gen 1 (5 Gbps) port' is Type-A
            continue
        c = _classify(i, d, side)
        if c is None:
            return {}
        segs.append(c)
    return _assemble(segs)


def surface(lines):
    """Microsoft Learn Surface 'Ports and charging' list -> ports dict or {}. Sub-item lines after a 'ports with support for:' / 'supporting:'
    line are attributed to those USB-C ports; 'All USB-C ports support ...' is attributed to every USB-C port. A page split into sections
    ('13.8-inch:' / '15-inch:') is accepted only when every section gives the same result; a section 'only' for some models must not carry
    USB-C, video or charging lines."""
    if not isinstance(lines, list):
        return {}
    secs, cur, cond = [], [], False
    for i, s in enumerate(lines):
        d = _dash(s)
        if re.search(r"(?:-inch|\"|models?|only|Additional for .*)\s*:?\s*$", d) and not re.match(r"^\d+\s*(?:x|×)\s", d) \
                and not USBC.search(d) and not VIDEO.match(d):
            if cur:
                secs.append((cond, cur))
            cur, cond = [], bool(re.search(r"\bonly\b|Additional for", d, re.I))
            continue
        cur.append((i, d))
    if cur:
        secs.append((cond, cur))
    results = []
    for cond, sec in secs:
        r = _surface_section(sec)
        if r is None:
            return {}
        if cond:
            if r:
                return {}
            continue
        results.append(r)
    if not results:
        return {}
    strip = lambda r: {k: v for k, v in r.items() if k != "segments"}
    return results[0] if all(strip(r) == strip(results[0]) for r in results) else {}


def _surface_section(sec):
    segs, k = [], 0
    while k < len(sec):
        i, d = sec[k]
        k += 1
        n, body = _count(d)
        if re.match(r"^All USB-C ports support\b", d, re.I):
            for idx, kind, n0, it, fl in segs:
                if kind == "usbc":
                    add = _usbc("USB4 " if it["protocol"] == "USB4" else it["protocol"], d) or {}
                    it.update({x: y for x, y in add.items() if x != "protocol"})
                    if _charging(d):
                        fl["charging"] = True
            continue
        if USBC.search(body) and re.match(r"^\d+\s*(?:x|×)\s", d):
            extra = ""
            if re.search(r"(?:with support for|supporting):?\s*$", body, re.I):
                subs = []
                while k < len(sec) and re.match(r"^(Charging|Data transfer|DisplayPort[^,]*)$", sec[k][1], re.I):
                    subs.append(sec[k][1]); k += 1
                extra = " ".join(subs)
            it = _usbc(body, extra)
            if it is None:
                return None
            segs.append((i, "usbc", n, it, {"charging": _charging(body + " " + extra), "tb": _tb(body)}))
            continue
        if re.search(r"charging|charger|power supply", d, re.I) and not re.match(r"^\d+\s*(?:x|×)\s", d):
            paths = []
            if re.search(r"Surface Connect", d):
                paths.append("proprietary")
            if re.search(r"USB-C", d):
                paths.append("usb-c")
            if re.search(r"Surface Power Supply", d) and "proprietary" not in paths:
                pass                                           # Laptop Ultra: the Surface Power Supply plugs into a USB-C port (no other port listed)
            segs.append((i, "charge_paths", 0, paths, {}))
            continue
        if re.match(r"^Surface Connect port$", d, re.I):
            segs.append((i, "power", 1, "proprietary", {}))
            continue
        if re.match(r"^(?:DisplayPort[^,]*with support for|Support for up to)", d, re.I):
            continue                                          # monitor-support line not attributed to a port: no dp_alt, not a port
        if VIDEO.match(d):
            segs.append((i, "video", 1, d, {}))
            continue
        if re.match(r"^(?:USB-A\b|3\.5|MicroSD|SD card|NanoSIM|Integrated smart card|Surface Thunderbolt|Surface .*Dock)", d, re.I):
            continue
        return None
    return _assemble(segs)


PORT_KEYS = {"usbc_list": "port.usbc_list", "tb_usb4": "port.tb_usb4", "video_out": "port.video_out", "charge_port": "port.charge_port"}


def replace_claims(pr, C, c, p, entity):
    """Swap one literal port.usbc_list claim c for the structured claims of p (same entity, raw, source, extractor, locator + segments).
    Like lenovo_psref@4: only when p has a usbc_list; otherwise the literal claim stays untouched. -> True when replaced."""
    if "usbc_list" not in p:
        return False
    i = pr.claims.index(c)
    new = [C.claim(entity, key, p[f], None, c["raw"], c["source"], c["method"]["extractor"], c["method"]["stage"], c["observed_at"],
                   locator=dict(c.get("locator") or {}, segments=p["segments"][f])) for f, key in PORT_KEYS.items() if f in p]
    pr.claims[i:i + 1] = new
    return True
