"""Pure spec-table parser for laptop spec sheets / datasheets, r3 (2026-11-25): docspec-laptop@1. No network, deterministic, text layer only.

Same cell model as _docspec_tv. Affirmative only; a negative placement needs a complete enumeration with its basis, so:
  mem.soldered  Memory cell: 'soldered' / 'on board' / 'onboard' / 'on package' AND a SO-DIMM slot named -> mixed; soldered-type words and
                an explicit 'no slots' / '0 slots' / 'not upgradable' basis -> soldered; only SO-DIMM slots named and no soldered word -> socketed.
                Soldered words alone (no slot statement) set nothing (the ASUS trap: a free slot is possible).
  mem.slots     Memory Slots cell: 'Two DDR5 SO-DIMM slots' / '2 x SO-DIMM' -> {total: 2}; 'None' / 'No slots' / 'soldered, no slots' -> {total: 0}.
  mem.max       Max Memory / Maximum Memory cell 'Up to 64GB' with exactly one figure (platform-labelled multi-figure cells set nothing).
  pwr.max_pd_in USB-C / Power Delivery charging cell 'USB-C PD up to 100W' (input); a cell naming output / reverse charging is skipped.
"""
import re

import _docspec_tv as T

VERSION = 1
NAME = "docspec-laptop"
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "single": 1, "dual": 2}
SOLDERED = re.compile(r"(?i)\bsoldered\b|\bon[- ]?board\b|\bon[- ]package\b|\bLPDDR\d")
SLOT = re.compile(r"(?i)SO-?DIMM|\bslots?\b")
NOSLOT = re.compile(r"(?i)\bno\s+(?:SO-?DIMM\s+)?slots?\b|\b0\s+slots?\b|\bnot\s+upgrad(?:e)?able\b")


def _slots(v):
    if NOSLOT.search(v) or re.fullmatch(r"(?i)\s*none\s*", v):
        return {"mem.slots": {"total": 0}}
    m = re.match(r"(?i)^\s*(\d|one|two|three|four|single|dual)\b\s*(?:x\s*)?(?:DDR\d\w*\s*)?SO-?DIMM", v)
    if m:
        n = WORDS.get(m[1].lower()) or int(m[1])
        return {"mem.slots": {"total": n}}
    return {}


def _memory(v):
    sold, slot = bool(SOLDERED.search(v)), bool(re.search(r"(?i)SO-?DIMM", v))
    out = {}
    if sold and slot and not NOSLOT.search(v):
        out["mem.soldered"] = "mixed"
    elif sold and NOSLOT.search(v):
        out["mem.soldered"] = "soldered"
    elif slot and not sold:
        out["mem.soldered"] = "socketed"
    return out


def _max(v):
    figs = re.findall(r"(?i)(\d{1,3})\s*GB", v)
    if len(figs) != 1 or ":" in v:
        return {}
    return {"mem.max": float(figs[0])} if re.search(r"(?i)\bup\s+to\b|\bmax", v) or re.fullmatch(r"(?i)\s*\d{1,3}\s*GB\s*", v) else {}


def _pd(v):
    if re.search(r"(?i)\bout(?:put)?\b|reverse|charges?\s+(?:your\s+)?(?:phone|devices?)", v):
        return {}
    m = re.search(r"(?i)USB[- ]?C.*?(?:PD|Power\s+Delivery).*?(?:up\s+to\s+)?(\d{2,3})\s*W\b", v)
    return {"pwr.max_pd_in": float(m[1])} if m else {}


RULES = [
    (r"Memory\s+Slots?|(?:SO-?DIMM\s+)?Slots", _slots),
    (r"Memory(?:\s+Type)?|System\s+Memory|RAM", _memory),
    (r"Max(?:imum)?\.?\s+Memory|Memory\s+Max(?:imum)?", _max),
    (r"(?:Power\s+Delivery|USB-?C\s+Charging|Charging|Power\s+Adapter|Power\s+Input)", _pd),
]


def laptop(doc):
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
    return _single(out)


def _single(out):
    vals = {}
    for f in out:
        vals.setdefault(f["key"], set()).add(repr(f["value"]))
    seen, uniq = set(), []
    for f in out:
        if len(vals[f["key"]]) > 1 or f["key"] in seen:
            continue
        seen.add(f["key"]); uniq.append(f)
    return uniq
