"""Pure parser: one Lenovo PSREF 'Standard Ports' cell (one MTM row) -> per-port USB-C facts (used by lenovo_psref@4).

The cell enumerates the MTM's ports, one port group per '^|^' segment ('2x Thunderbolt 4, with USB PD 3.1 and DisplayPort 2.1,
140W input / 15W output'). Every fact below is attributed to the segment that states it (locator segment index), never pooled
across ports, and only what the segment states literally is returned:

  port.usbc_list   one item per physical USB-C port ('2x' -> two items): protocol (literal: 'Thunderbolt 4', 'USB4 40Gbps',
                   'USB 10Gbps / USB 3.2 Gen 2', 'charging only'), usb_gbps (only a printed 'NGbps'), pd_in_w (range from 'USB PD 45-65W'
                   or 'NW input'), pd_out_w ('NW output'), dp_alt (the printed 'DisplayPort 2.1' / 'DP 1.4' / 'DisplayPort'). A field the
                   segment does not print is absent (absent = not stated, never 'no'). Emitted only when EVERY segment of the cell is
                   understood (USB-C group or a known non-USB-C port); one unknown segment -> None (the literal claim stays).
  port.tb_usb4     the highest of Thunderbolt 5 > Thunderbolt 4 > USB4 printed on a USB-C segment. Affirmative only: no 'none'.
  port.video_out   the dedicated HDMI / DisplayPort segments, literal, '; '-joined (USB-C DP alt is in usbc_list, not here).
  port.charge_port the dedicated power connector the cell names ('Slim tip (rectangle) power connector' -> proprietary,
                   'Round tip power connector' -> barrel). With no power connector in a fully understood cell, 'usb-c' only when a
                   USB-C segment states an input wattage or 'charging only' (PD input stated); otherwise nothing.
Platform-dependent segments ('DisplayPort 2.1 (Gorgon Point) / DisplayPort 1.4a (Hawk Point)', or a 'Platform:' prefix) are
ambiguous for one MTM: the cell yields nothing.
"""
import re

COUNT = re.compile(r"^(\d+)x\s+(.*)$", re.S)
USBC = re.compile(r"\bUSB-C\b|\bThunderbolt\b|\bUSB4\b|\bType-C\b", re.I)
GBPS = re.compile(r"(\d+)\s*Gbps", re.I)
DP = re.compile(r"\b(DisplayPort|DP)(?:\s+(\d\.\d[a-z]?(?:\s+UHBR\d+)?))?", re.I)
RANGE = re.compile(r"(?:USB\s+)?PD\s+(\d+)\s*-\s*(\d+)\s*W", re.I)
WIN = re.compile(r"(?:(\d+)\s*-\s*)?(\d+)\s*W\s+input", re.I)
WOUT = re.compile(r"(\d+)\s*W\s+output", re.I)
TB = re.compile(r"\bThunderbolt\s+(\d)\b", re.I)
PLATFORM = re.compile(r"\((?:[A-Z][a-z]+ )+(?:Point|Lake|Lake-H|Ridge)\)|^[A-Z][A-Za-z0-9 ,-]*:\s")
OTHER = re.compile(r"^(USB(?: 3\.\d| 2\.0| \d+Gbps)?|USB-A|HDMI|Headphone|Microphone|Ethernet|RJ-45|Card reader|.*power connector|Kensington|"
                   r"Security|Nano|Docking|Smart card|Mini DisplayPort|DisplayPort|VGA|Serial|Side docking|Lenovo|Thunderbolt-?(?:compatible)? dock|"
                   r"SIM|microSD|SD|Optical|e-SATA|Fingerprint|Audio|Microphone|Stereo|Combo|Pogo pin connector)", re.I)
VIDEO = re.compile(r"^(HDMI|DisplayPort|Mini DisplayPort|VGA)\b", re.I)
RANKS = {"Thunderbolt 5": 3, "Thunderbolt 4": 2, "USB4": 1}


def _usbc(body):
    """One USB-C port-group segment body (count prefix removed) -> item dict, or None if ambiguous."""
    head, _, rest = body.partition(",")
    item = {}
    m = re.match(r"^(?:USB-C\s*)?\(([^)]*)\)", head.strip())
    if re.search(r"support charging only", body, re.I):
        item["protocol"] = "charging only"
    elif m:
        item["protocol"] = m.group(1).strip()
    elif re.match(r"^USB-C\s+3\.\d Gen \d", head.strip()):
        item["protocol"] = re.match(r"^USB-C\s+(3\.\d Gen \d)", head.strip()).group(1).join(("USB ", ""))
    else:
        item["protocol"] = re.sub(r"\s*\(.*$", "", head).strip()
    g = GBPS.findall(item["protocol"]) or GBPS.findall(head)
    if len(set(g)) == 1:
        item["usb_gbps"] = int(g[0])
    dps = DP.findall(body)
    if len(dps) > 1:
        return None
    if dps:
        item["dp_alt"] = ("DisplayPort " + dps[0][1]).strip() if dps[0][1] else "DisplayPort"
    r = RANGE.search(body)
    w = WIN.search(body)
    if r:
        item["pd_in_w"] = {"min": int(r.group(1)), "max": int(r.group(2))}
    elif w:
        item["pd_in_w"] = {"min": int(w.group(1)), "max": int(w.group(2))} if w.group(1) else {"max": int(w.group(2))}
    o = WOUT.search(body)
    if o:
        item["pd_out_w"] = int(o.group(1))
    return item


def ports(cell):
    """-> {"usbc_list": [...], "tb_usb4": str, "video_out": str, "charge_port": str, "segments": {key: [segment idx]}} (only stated keys),
    or {} when any segment is not understood / platform-dependent."""
    if not isinstance(cell, str) or not cell.strip():
        return {}
    segs = [s.strip() for s in cell.split("^|^") if s.strip()]
    usbc, video, charge, tb, at = [], [], None, None, {}
    pd_in_seen = charge_clash = False
    for i, s in enumerate(segs):
        s1 = re.sub(r"\s+", " ", s)
        if PLATFORM.search(s1):
            return {}
        m = COUNT.match(s1)
        n, body = (int(m.group(1)), m.group(2)) if m else (1, s1)
        if USBC.search(body) and not re.search(r"power connector", body, re.I):
            it = _usbc(body)
            if it is None:
                return {}
            usbc += [dict(it) for _ in range(n)]
            at.setdefault("usbc_list", []).append(i)
            if "pd_in_w" in it or it.get("protocol") == "charging only":
                pd_in_seen = True
            t = TB.search(body)
            name = f"Thunderbolt {t.group(1)}" if t else ("USB4" if re.search(r"\bUSB4\b", body) else None)
            if name in RANKS and (tb is None or RANKS[name] > RANKS[tb]):
                tb = name
                at["tb_usb4"] = [i]
            continue
        kind = "proprietary" if re.search(r"slim tip.*power connector", body, re.I) else ("barrel" if re.search(r"round tip power connector", body, re.I) else None)
        if kind:
            if charge not in (None, kind):
                charge_clash = True
            charge = kind
            at.setdefault("charge_port", []).append(i)
            continue
        if VIDEO.match(body):
            video.append(s1)
            at.setdefault("video_out", []).append(i)
            continue
        if OTHER.match(body):
            continue
        return {}
    out = {}
    if usbc:
        out["usbc_list"] = usbc
    if tb:
        out["tb_usb4"] = tb
    if video:
        out["video_out"] = "; ".join(video)
    if charge_clash:                      # two different dedicated connectors named: which one this MTM charges from is not stated
        charge = None
        at.pop("charge_port", None)
    elif charge is None and pd_in_seen:
        charge = "usb-c"
        at["charge_port"] = at.get("usbc_list", [])
    if charge:
        out["charge_port"] = charge
    if out:
        out["segments"] = {k: v for k, v in at.items() if k in out}
    return out
