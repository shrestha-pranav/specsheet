"""Pure parser: Lenovo PSREF multi-target laptop cells -> typed sub-values (research/laptops/psref-mapping.yaml maps_to lists).
Used by scripts/import.py (`import.py+psref-split@1`, derived_from = the literal claim) the way _cpu.py backs cpu-split.

Only what the cell states literally is returned; a missing field means "not stated or ambiguous" and nothing is inferred
(no 60 Hz default for a cell that prints no refresh rate, no "soldered" for an LPDDR cell that does not say so).

  Display       '14" WUXGA (1920x1200) OLED 600nits (peak) / 400nits (typical) Glossy, 100% DCI-P3, 60Hz, Touch'
                -> panel_type OLED, nits_sdr 400 (the typical figure; a peak figure is never taken as SDR), refresh {max: 60},
                   resolution 1920x1200. Two refresh figures ('240Hz / 440Hz' dual-mode) -> no refresh.
  Memory Slots  'Memory soldered to systemboard, no slots' -> slots {total: 0}, soldered 'soldered'
                'One memory soldered to systemboard, one DDR5 SODIMM slot, ...' -> {total: 1}, 'mixed'
                'Two DDR5 SODIMM / CSODIMM slots' -> {total: 2}, 'socketed'; 'One LPCAMM2 connector' -> {total: 1}, 'socketed'
                A single platform prefix ('Arrow Lake: two ...') is the only statement the MTM row carries, so it applies.
                'Unified memory, 16-channel' states neither -> nothing.
  Memory        '16GB Soldered LPDDR5X-7500' -> type LPDDR5X-7500 (literal token), soldered_hint 'soldered' (used only as a
                consistency check against Memory Slots: a contradiction drops mem.soldered for that MTM).
"""
import re

WORDS = {"no": 0, "one": 1, "two": 2, "three": 3, "four": 4}
PANELS = ("Tandem OLED", "POLED", "OLED", "Mini LED", "Mini-LED", "IPS", "TN", "VA", "WVA")


def _multi(s):
    return isinstance(s, str) and ("\n" in s or "^|^" in s)     # PSREF joins several statements with ^|^: ambiguous for one MTM


def _clean(s):
    return re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else ""


def display(text):
    s = _clean(text)
    out = {}
    if not s or _multi(text) or ";" in s:
        return out
    m = re.search(r"\((\d{3,4})\s*x\s*(\d{3,4})\)", s)
    if not m:
        return out
    out["resolution"] = f"{m.group(1)}x{m.group(2)}"
    tail = s[m.end():]
    pm = re.match(r"\s*(" + "|".join(re.escape(p) for p in PANELS) + r")\b", tail)
    if pm:
        out["panel_type"] = pm.group(1)
    nits = re.findall(r"(\d{2,4})\s*nits(?:\s*\((typical|peak)\))?", tail)
    typ = [int(n) for n, q in nits if q == "typical"]
    plain = [int(n) for n, q in nits if not q]
    if len(typ) == 1:
        out["nits_sdr"] = typ[0]
    elif not typ and len(plain) == 1 and not any(q == "peak" for _, q in nits):
        out["nits_sdr"] = plain[0]
    hz = re.findall(r"(\d{2,3})\s*Hz\b", tail)
    if len(hz) == 1:
        out["refresh"] = {"max": int(hz[0])}
    return out


def slots(text):
    s = _clean(text)
    if not s or _multi(text) or ";" in s:
        return {}
    pre = re.match(r"^[A-Z][A-Za-z0-9 ,]+?(?: and [A-Za-z0-9 ]+)?:\s*", s)
    if pre:
        s = s[pre.end():]
    ls = s.lower()
    sold = "soldered to systemboard" in ls
    if re.match(r"^memory soldered to systemboard, no slots\b", ls):
        return {"total": 0, "soldered": "soldered"}
    m = re.match(r"^one memory soldered to systemboard, (one|two) [a-z0-9 /]*?\b(?:sodimm|csodimm|so-dimm)\b[a-z0-9 /]*?slots?\b", ls)
    if m:
        return {"total": WORDS[m.group(1)], "soldered": "mixed"}
    m = re.match(r"^(one|two|three|four) (?:ddr\d[a-z]?\s+)?(?:sodimm|csodimm|so-dimm)(?:\s*/\s*csodimm)? slots?\b", ls)
    if m and not sold:
        return {"total": WORDS[m.group(1)], "soldered": "socketed"}
    m = re.match(r"^(one|two) lpcamm2 (?:connector|memory module|slot)s?\b", ls)
    if m and not sold:
        return {"total": WORDS[m.group(1)], "soldered": "socketed"}
    return {}


def memory(text):
    s = _clean(text)
    out = {}
    if not s or _multi(text):
        return out
    types = re.findall(r"\b((?:LP)?DDR\d[Xx]?(?:-\d{4})?)\b", s)
    if len(set(t.upper() for t in types)) == 1:
        out["type"] = types[0]
    ls = s.lower()
    if "soldered" in ls and re.search(r"\b(c?sodimm|so-dimm|lpcamm2?)\b", ls):
        out["soldered_hint"] = "mixed"
    elif "soldered" in ls:
        out["soldered_hint"] = "soldered"
    elif re.search(r"\b(c?sodimm|so-dimm|lpcamm2?)\b", ls):
        out["soldered_hint"] = "socketed"
    return out
