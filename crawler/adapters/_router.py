"""Shared pure parsers for the Wi-Fi router adapters (tplink_routers, netgear_routers, asus_routers). No network.

Keys follow research/routers/spec-profile.yaml. A value is only returned when the source text states it; everything else stays None
(absent = unknown, never invented). `raw` is kept by the caller. Per-band figures come from text segments that START at a band marker
('2.4 GHz', '5GHz', '6 GHz'), so a class number such as AX5400 never becomes a per-band rate.
"""
import html, re

SEG = re.compile(r"(?=(?<![\d.])(?:2\.4|5|6)\s*G\s?Hz)")
RATE = re.compile(r"(\d[\d,]*\.?\d*)\s*(Mbps|Gbps)", re.I)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def generation(t):
    t = t or ""
    if re.search(r"wi-?fi\s*7|802\.11be|\bBE\d{3,5}\b", t, re.I):
        return "wifi7"
    if re.search(r"wi-?fi\s*6\s*e|802\.11axe|\bAXE\d{3,5}\b|\bGT-AXE|\bGT-AX11000 Pro", t, re.I):
        return "wifi6e"
    if re.search(r"wi-?fi\s*6\b|802\.11ax|\bAX\d{3,5}\b", t, re.I):
        return "wifi6"
    if re.search(r"wi-?fi\s*5\b|802\.11ac|\bAC\d{3,5}\b", t, re.I):
        return "wifi5"
    return None


def marketing_class(t):
    m = re.search(r"\b(AXE|AX|BE|AC)\s?-?(\d{3,5})\b", t or "")
    return m[1] + m[2] if m else None


def bands(t):
    """-> int radios from 'Dual-Band|Tri-Band|Quad-Band' words."""
    m = re.search(r"\b(dual|tri|quad)[- ]?band", t or "", re.I)
    return {"dual": 2, "tri": 3, "quad": 4}[m[1].lower()] if m else None


def per_band(t):
    """-> {'24': {rate, streams, width}, '5': .., '5_2': .., '6': ..} from segments starting at a band marker."""
    out, n5 = {}, 0
    for seg in SEG.split(t or ""):
        m = re.match(r"(2\.4|5|6)\s*G\s?Hz(?:\s*-\s*([12]))?", seg)
        if not m:
            continue
        b = {"2.4": "24", "5": "5", "6": "6"}[m[1]]
        if b == "5":
            n5 += 1
            idx = int(m[2]) if m[2] else n5
            b = "5" if idx == 1 else "5_2" if idx == 2 else None
            if b is None or b in out:
                continue
        d = out.setdefault(b, {})
        r = RATE.search(seg)
        if r and "rate" not in d:
            v = float(r[1].replace(",", "")) * (1000 if r[2].lower() == "gbps" else 1)
            d["rate"] = int(v) if v == int(v) else v
        s = re.search(r"\b(\d)\s*[x×]\s*(\d)\b", seg)
        if s and s[1] == s[2] and "streams" not in d:
            d["streams"] = int(s[1])
        w = re.findall(r"((?:\d+/)*\d+)\s*MHz", seg) + [x for x in re.findall(r"(?:HE|EHT|VHT)(\d{2,3})\b", seg)]
        if w and "width" not in d:
            d["width"] = max(int(x) for ws in w for x in ws.split("/"))
    return out


def memory(t):
    """'256 MB Flash and 1 GB RAM' / '128MB flash and 512MB RAM' -> (flash_mb, ram_mb) where stated."""
    fl = ra = None
    for m in re.finditer(r"(\d[\d.]*)\s*(MB|GB)\s*(flash|ram|nand|ddr\d?)", t or "", re.I):
        v = float(m[1]) * (1024 if m[2].upper() == "GB" else 1)
        v = int(v)
        if m[3].lower() == "flash" or m[3].lower() == "nand":
            fl = fl or v
        else:
            ra = ra or v
    for m in re.finditer(r"(flash|ram)[^\d]{0,12}(\d[\d.]*)\s*(MB|GB)\b", t or "", re.I):
        v = int(float(m[2]) * (1024 if m[3].upper() == "GB" else 1))
        if m[1].lower() == "flash":
            fl = fl or v
        else:
            ra = ra or v
    return fl, ra


def cpu(t):
    cores = {"single": 1, "dual": 2, "triple": 3, "quad": 4, "hexa": 6, "octa": 8}
    m = re.search(r"\b(single|dual|triple|quad|hexa|octa)[- ]core", t or "", re.I)
    g = re.search(r"(\d(?:\.\d+)?)\s*GHz", t or "", re.I)
    return (cores[m[1].lower()] if m else None, float(g[1]) if g else None)


def usb(t):
    """-> (count, standard enum) from '1× USB 3.0 Port', 'One (1) USB 3.0 ports', 'USB 3.2 Gen1 x1, 2.0 x1'."""
    t = t or ""
    if re.search(r"\bno usb\b|^\s*none\s*$", t, re.I):
        return 0, None
    nums = []
    for part in re.split(r"[,|;]", t):
        m = re.search(r"(\d+)\s*[×x]\s*USB|\((\d)\)\s*USB|USB[^×x\d]{0,24}\d(?:\.\d)?(?:\s*Gen\s*\d)?\s*[×x]\s*(\d+)|\b(one|two|three)\b[^|]{0,6}USB", part, re.I)
        if not m and nums:
            m2 = re.match(r"\s*\d\.\d\s*[×x]\s*(\d+)", part)
            if m2:
                nums.append(int(m2[1]))
                continue
        if m:
            nums.append(int(next(g for g in m.groups()[:3] if g)) if any(m.groups()[:3]) else {"one": 1, "two": 2, "three": 3}[m[4].lower()])
    cnt = sum(nums) if nums else None
    std = None
    if re.search(r"USB\s*3\.2\s*Gen\s*2|USB\s*3\.1\s*Gen\s*2|10\s*Gbps", t, re.I):
        std = "usb_3_2_gen2"
    elif re.search(r"USB\s*3\.2\s*Gen\s*1|USB\s*3\.1\s*Gen\s*1", t, re.I):
        std = "usb_3_2_gen1"
    elif re.search(r"USB\s*3\.0|USB\s*3\b", t, re.I):
        std = "usb_3_0"
    elif re.search(r"USB\s*2\.0", t, re.I):
        std = "usb_2_0"
    return cnt, std


def _speed(tok):
    tok = tok.lower().replace(" ", "")
    if tok in ("gigabit", "1g", "1gbps", "1000"):
        return 1000
    m = re.match(r"(\d+(?:\.\d+)?)g(?:bps|bit)?$", tok)
    if m:
        return int(float(m[1]) * 1000)
    m = re.match(r"(\d+)(?:mbps)?$", tok)
    return int(m[1]) if m else None


def ports(lines):
    """-> dict wan_mbps, lan_count, lan_max, multigig, wan_lan_cfg from stated port lines (TP-Link '4× Gigabit LAN Ports', '2× 2.5 Gbps ... WAN/LAN',
    NETGEAR '(1 WAN & 4 LAN)', ASUS 'RJ45 for 10/100/1000 BaseT for WAN x 1'). Only what is explicit."""
    wan, lan, lanmax, mg, cfg = [], 0, 0, 0, False
    seen_lan = False
    for l in lines:
        if re.search(r"WAN/LAN|LAN/WAN", l, re.I) and re.search(r"(\d+(?:\.\d+)?)\s*G", l):
            m = re.search(r"(\d+)\s*[×x]\s*(\d+(?:\.\d+)?)\s*G", l)
            if m:
                sp = int(float(m[2]) * 1000)
                wan.append(sp)
                cfg = True
                if sp >= 2500:
                    mg += int(m[1])
            continue
        m = re.search(r"(\d+)\s*[×x]\s*(Gigabit|\d+(?:\.\d+)?\s*G(?:bps|bit)?)\s*(?:Ethernet\s*)?(WAN|LAN)\b", l, re.I)
        if m:
            sp, c = _speed(m[2]), int(m[1])
            if m[3].upper() == "WAN":
                wan.append(sp)
            else:
                lan += c; seen_lan = True; lanmax = max(lanmax, sp or 0)
            if sp and sp >= 2500:
                mg += c
            continue
        m = re.search(r"\((\d+)\s*WAN\s*(?:&|and|\+)\s*(\d+)\s*LAN\)", l, re.I)
        if m:
            toks = {float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*G(?:bps|igabit|b)?\b", l)} or ({1.0} if re.search(r"10/100/1000|Gigabit", l) else set())
            if len(toks) != 1 or (toks != {1.0} and re.search(r"(?<!\d )(?<!\d)Gigabit", l)):
                continue            # mixed or unstated speeds: the sentence cannot give a per-port speed
            sp = int(next(iter(toks)) * 1000)
            wan.append(sp); lan += int(m[2]); seen_lan = True; lanmax = max(lanmax, sp)
            if sp >= 2500:
                mg += int(m[1]) + int(m[2])
            continue
        m = re.search(r"RJ45 for (.*?)\s*BaseT for (WAN|LAN)\s*x\s*(\d+)", l, re.I)
        if m:
            vals = []
            for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(G|M)?(?:bps)?", m[1]):
                vals.append(float(num) * 1000 if unit.upper() == "G" else float(num))
            if re.search(r"Gigabits?", m[1], re.I):
                vals.append(1000)
            sp = int(max(vals)) if vals else None
            if m[2].upper() == "WAN":
                wan.append(sp)
            else:
                lan += int(m[3]); seen_lan = True; lanmax = max(lanmax, sp or 0)
            if sp and sp >= 2500:
                mg += int(m[3])
    return {"wan_mbps": max([w for w in wan if w], default=None), "lan_count": lan if seen_lan else None, "lan_max": lanmax or None,
            "multigig": mg or None, "wan_lan_cfg": True if cfg else None}


def vpn(t, role):
    out = []
    for pat, v in ((r"open\s*vpn", "openvpn"), (r"wire\s*guard", "wireguard"), (r"pptp", "pptp"), (r"l2tp", "l2tp_ipsec"), (r"ipsec", "ipsec")):
        if re.search(pat, t or "", re.I) and v not in out:
            out.append(v)
    return out


def mesh_systems(t):
    out = []
    for pat, v in ((r"easy\s*mesh", "easymesh"), (r"ai\s*mesh", "aimesh"), (r"one\s*mesh", "onemesh")):
        if re.search(pat, t or "", re.I):
            out.append(v)
    return out


def dims_mm(t):
    m = re.search(r"\(?\s*(\d+(?:\.\d+)?)\s*[×xX]\s*(\d+(?:\.\d+)?)\s*[×xX]\s*(\d+(?:\.\d+)?)\s*mm", t or "")
    return {"length": float(m[1]), "width": float(m[2]), "height": float(m[3])} if m else None


def usd(t):
    m = re.search(r"([\d,]+\.\d{2})", t or "")
    return float(m[1].replace(",", "")) if m else None
