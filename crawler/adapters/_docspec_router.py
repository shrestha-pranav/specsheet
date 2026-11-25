"""Pure spec-table parser for router datasheets / spec sheets, r3 (2026-11-25): docspec-router@1. No network, deterministic, text layer only.

Same cell model as _docspec_tv (segments split at 3+ spaces, adjacent (label, value) pair, a value repeated in the next column is not a
spanning cell, one key with two values in a document reads nothing). Affirmative only.

router(doc) -> [{key, value, raw, quote, page, ocr, ocr_conf}]:
  wifi.generation  WiFi / Wireless Standard / Technology cell: Wi-Fi 7 / 802.11be -> wifi7; Wi-Fi 6E -> wifi6e; Wi-Fi 6 / 802.11ax (no 6E,
                   no 6 GHz) -> wifi6; Wi-Fi 5 / 802.11ac (nothing newer) -> wifi5. 802.11ax + 6 GHz in one cell is NOT promoted to 6E.
  wifi.band_count  Bands / Frequency / Radio cell: Dual-band 2, Tri-band 3, Quad-band 4 (the maker's word, not a count of listed radios).
  wifi.has_6ghz    true when a Bands / Frequency / Radio / WiFi cell names 6 GHz (never false: silence is not a negative).
  port.lan_count   LAN Port(s) / Ethernet LAN cell starting with the count ('4 x 1G Ethernet', '3x Gigabit').
  port.wan_speed_mbps WAN / Internet Port cell with one speed: 10G / 10 Gigabit / 2.5G / 2.5 Gbps / Gigabit / 10/100/1000 (-> 1000).
"""
import re

import _docspec_tv as T

VERSION = 1
NAME = "docspec-router"


def _gen(v):
    if re.search(r"(?i)wi-?fi\s*7\b|802\.11\s*be\b", v):
        return {"wifi.generation": "wifi7"}
    if re.search(r"(?i)wi-?fi\s*6E\b", v):
        return {"wifi.generation": "wifi6e"}
    if re.search(r"(?i)wi-?fi\s*6\b|802\.11\s*ax\b", v):
        return {} if re.search(r"(?i)6\s*GHz", v) else {"wifi.generation": "wifi6"}
    if re.search(r"(?i)wi-?fi\s*5\b|802\.11\s*ac\b", v):
        return {"wifi.generation": "wifi5"}
    return {}


def _bands(v):
    out = {}
    m = re.search(r"(?i)\b(dual|tri|quad)[- ]band\b", v)
    if m:
        out["wifi.band_count"] = {"dual": 2, "tri": 3, "quad": 4}[m[1].lower()]
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
                    out += [{"key": k, "value": x, "raw": val[:200], "quote": " ".join(raw.split())[:200], "page": page["n"], "ocr": False,
                             "ocr_conf": None} for k, x in got.items()]
    return T.single(out)
