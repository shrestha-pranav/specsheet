"""Typed normalisation of claim values against a category profile (review P1-5). Pure; used by import.py BEFORE acceptance
(an auto-accept policy requires a clean normalisation) and by v1_publish.py.

Rules (never invent precision or drop qualifiers):
- claim `unit` is honoured: 1000 with unit g under a kg spec -> 1 (dimensional check via schemas/units.json + profile units.custom,
  affine offsets applied).
- integer specs reject fractional values (2.9 is not 2).
- qualifiers are preserved, never dropped: "starting at/from" -> qualifier "from" (a lower bound: base configuration),
  "approx./about/~" -> "approx", "up to" on a non-maximum spec -> "up_to" (on max/boost/peak/turbo specs "up to" IS the value).
  "min./at least/over/>/<" -> not normalised.
- "N x M unit" (1x 16GB, 2x 8GB) is an exact total (N*M); sums ("8GB + 8GB") and ranges are not normalised.
- unitless counts accept number words ("Two M.2 slots" -> 2).
- multi-quantity strings ("2x 8GB", "8GB + 8GB") and ranges ("3-25A") under a scalar spec -> not normalised.
- converted values are rounded to the significant digits of the source number (min 3): 3.5 lb -> 1.59 kg, never 1.5876.
- ranges must be {min,max} numbers with min <= max; objects must use the profile's `fields` when it declares them.
normalise(spec, claim, units) -> (ok, value, extra) where extra may carry {"display": "1 TB", "qualifier": "from"}
"""
import json, math, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_BUILTIN = json.loads((ROOT / "schemas" / "units.json").read_text())["units"]
UNIT_ALIAS = {"whrs": "Wh", "whr": "Wh", "wh": "Wh", '"': "in", "″": "in", "inch": "in", "inches": "in", "lbs": "lb", "pounds": "lb",
              "nits": "nit", "cd/m2": "nit", "cd/m²": "nit", "gb": "GB", "tb": "TB", "mb": "MB", "ghz": "GHz", "mhz": "MHz", "w": "W", "v": "V",
              "a": "A", "j": "J", "joules": "J", "kg": "kg", "g": "g", "mm": "mm", "cm": "cm", "ft": "ft", "feet": "ft", "foot": "ft", "m": "m",
              "hz": "Hz", "tops": "TOPS", "volts": "V", "amps": "A", "watts": "W", "oz": "oz"}
NUM = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-zµ\"″/²]*)")
BAD_QUAL = re.compile(r"^\s*(min\.?|minimum|at least|over|more than|less than|>|<)\s*", re.I)
QUALS = [(re.compile(r"^\s*(starting at|starts at|from)\s*", re.I), "from"), (re.compile(r"^\s*(approx\.?|approximately|about|around|~|≈)\s*", re.I), "approx")]
WORDS = {"zero": 0, "no": 0, "one": 1, "single": 1, "two": 2, "dual": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "ten": 10, "twelve": 12}
MULT = re.compile(r"^\s*(\d+)\s*x\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)\b", re.I)
UPTO = re.compile(r"^\s*up\s*to\s*", re.I)
MAXLIKE = re.compile(r"max|boost|peak|turbo|up to", re.I)
DISPLAY_SCALES = {"GB": [("TB", 1000)], "MB": [("GB", 1000)], "g": [("kg", 1000)], "mAh": [], "Hz": []}


def units(profile=None):
    u = dict(_BUILTIN)
    for c in ((profile or {}).get("units") or {}).get("custom") or []:
        cid = c.get("unit") or c.get("id")      # schema: `unit`; `id` is the legacy spelling
        if cid:
            u[cid] = {"base": c.get("base", cid), "factor": c.get("factor", 1), "offset": c.get("offset", 0)}
    # profile unit ids used but unregistered (nits, AWG): identity units, convertible only to themselves
    for s in (profile or {}).get("specs", []):
        if s.get("unit") and s["unit"] not in u:
            u[s["unit"]] = {"base": s["unit"], "factor": 1}
    if "nit" in u and "nits" in u:
        u["nits"] = u["nit"]
    return u


def unit_token(tok, U):
    if not tok:
        return ""
    if tok in U:
        return tok
    t = UNIT_ALIAS.get(tok.lower())
    if t in U:
        return t
    return next((k for k in U if k.lower() == tok.lower()), None)


def convert(x, frm, to, U):
    if frm == to:
        return x
    a, b = U.get(frm), U.get(to)
    if not a or not b or a["base"] != b["base"]:
        if {frm, to} <= {"nit", "nits"}:
            return x
        return None
    base = x * a["factor"] + a.get("offset", 0)
    return (base - b.get("offset", 0)) / b["factor"]


def sig_round(x, digits):
    if x == 0:
        return 0
    return round(x, max(0, digits - 1 - int(math.floor(math.log10(abs(x))))))


def _sig(numstr):
    s = numstr.replace(".", "").lstrip("0")
    return max(len(s), 1)


def to_number(spec, v, claim_unit, U, q=None):
    """-> number in spec unit or None. q (dict) receives {"qualifier": ...} when the source qualified the number."""
    q = q if q is not None else {}
    unit = spec.get("unit")
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if claim_unit and unit and claim_unit != unit:
            fu, tu = unit_token(claim_unit, U), unit_token(unit, U)
            if not fu or not tu:
                return None
            c = convert(float(v), fu, tu, U)
            return None if c is None else sig_round(c, max(3, _sig(repr(float(v)).rstrip("0").rstrip("."))))
        return v
    if not isinstance(v, str):
        return None
    s = v.strip()
    if BAD_QUAL.match(s):
        return None
    for rx, name in QUALS:
        m = rx.match(s)
        if m:
            q["qualifier"] = name; s = s[m.end():]
            break
    m = UPTO.match(s)
    if m:
        if not MAXLIKE.search(spec["key"] + " " + spec.get("label", "")):
            q["qualifier"] = "up_to"
        s = s[m.end():]
    if not unit:
        w = re.match(r"^\s*([A-Za-z]+)\b", s)
        if w and w.group(1).lower() in WORDS:
            return WORDS[w.group(1).lower()]
    mm = MULT.match(s)
    if mm:
        t = unit_token(mm.group(3), U)
        tu = unit_token(unit, U) if unit else None
        if t and tu and not re.search(r"(\+|\band\b|&)\s*\d", s[mm.end():].split("(")[0], re.I):
            c = convert(int(mm.group(1)) * float(mm.group(2)), t, tu, U)
            return None if c is None else (c if t == tu else sig_round(c, max(3, _sig(mm.group(2)))))
        return None
    if re.match(r"^\s*\d{1,3}(,\d{3})+(\.\d+)?\b", s):
        s = s.replace(",", "", s.count(","))
    m = NUM.match(s)
    if not m:
        return None
    rest = s[m.end():].strip()
    if re.match(r"^(x|\+|/|-|–|to)\s*\d", rest, re.I) or re.search(r"\d\s*(?:x|\+|-|–)\s*\d", s[:m.end() + 4]):
        return None   # multi-quantity / range under a scalar spec
    if re.search(r"(\+|\band\b|&)\s*\d", rest.split("(")[0], re.I):
        return None   # "16GB soldered + 16GB SO-DIMM": a sum we would have to invent
    num, tok = m.group(1), m.group(2)
    x = float(num)
    t = unit_token(tok, U) if tok else (unit_token(claim_unit, U) if claim_unit else "")
    if not unit:
        return x if not t else None     # unitless spec: a noun suffix ("12 outlets") is fine, a unit token is not
    if t is None:
        return None
    if t == "":
        return x                        # bare number: the adapter states it in the spec's unit
    tu = unit_token(unit, U) or unit
    c = convert(x, t, tu, U)
    if c is None:
        return None
    return c if t == tu else sig_round(c, max(3, _sig(num)))


def display_hint(spec, value, raw):
    """Display string in a larger unit when it is exact (1000 GB -> '1 TB'), or when the source itself used that unit (1.5TB)."""
    unit = spec.get("unit")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or unit not in DISPLAY_SCALES:
        return None
    stated = {m.group(1) for m in re.finditer(r"[0-9.]\s*(TB|GB|MB|kg|g)\b", raw or "")}
    for big, f in DISPLAY_SCALES[unit]:
        if value >= f and (value % f == 0 or (big in stated and round(value / f, 3) == value / f)):
            return f"{value / f:g} {big}"
    return None


DIM = re.compile(r"^\s*([0-9.]+)\s*x\s*([0-9.]+)\s*x\s*([0-9.]+)\s*(mm|cm)\b")


def special(spec, v):
    """Deterministic Lenovo/ASUS cell parsers kept from v1 (moved out of the publisher). -> (ok, value) or None (no opinion)."""
    k = spec["key"]
    if not isinstance(v, str):
        return None
    lv = v.strip().lower()
    if k == "disp.touch":
        if lv in ("none", "no", "non-touch"):
            return True, False
        if "multi-touch" in lv or lv.startswith("touch"):
            return True, True
    if k == "in.fingerprint":
        if lv.startswith("no fingerprint") or lv == "none":
            return True, False
        if "match-on" in lv or lv.startswith(("fingerprint", "touch style")):
            return True, True
    if k == "cpu.npu_tops":
        m = re.search(r"up to ([0-9.]+) tops", lv)
        if m:
            return True, float(m.group(1)) if "." in m.group(1) else int(m.group(1))
    if k == "phys.dimensions" and spec.get("unit") == "mm":
        m = DIM.match(v)
        if m and "~" not in v.split("(")[0]:
            f = 10 if m.group(4) == "cm" else 1
            return True, {"w": round(float(m.group(1)) * f, 2), "d": round(float(m.group(2)) * f, 2), "h": round(float(m.group(3)) * f, 2), "unit": "mm"}
    return None


def normalise(spec, claim, U):
    """-> (ok, value, display). Failure keeps the raw literal at the call site (spec publishes not_yet_extracted)."""
    t, v = spec["type"], claim.get("value")
    if claim.get("status") != "known":
        return False, None, {}
    sp = special(spec, v)
    if sp is not None:
        return sp[0], sp[1], {}
    if t in ("number", "integer"):
        q = {}
        x = to_number(spec, v, claim.get("unit"), U, q)
        if x is None:
            return False, None, {}
        if t == "integer":
            if float(x) != int(x):
                return False, None, {}
            x = int(x)
        elif float(x).is_integer():
            x = int(x)
        d = display_hint(spec, x, claim.get("raw") if isinstance(claim.get("raw"), str) else (v if isinstance(v, str) else None))
        if d:
            q["display"] = d
        return True, x, q
    if t == "bool":
        if isinstance(v, bool):
            return True, v, {}
        if isinstance(v, str) and v.strip().lower() in ("yes", "true"):
            return True, True, {}
        if isinstance(v, str) and v.strip().lower() in ("no", "false"):
            return True, False, {}
        return False, None, {}
    if t == "enum":
        if not isinstance(v, str):
            return False, None, {}
        if spec.get("enum"):
            hit = next((e for e in spec["enum"] if str(e).lower() == v.strip().lower()), None)
            return (True, hit, {}) if hit is not None else (False, None, {})
        return True, v.strip(), {}
    if t == "text":
        if isinstance(v, str):
            return (True, v.strip(), {}) if v.strip() else (False, None, {})
        if isinstance(v, list) and all(isinstance(x, (str, int, float)) for x in v):
            return True, "; ".join(map(str, v)), {}
        return (True, str(v), {}) if isinstance(v, (int, float)) and not isinstance(v, bool) else (False, None, {})
    if t == "list":
        if isinstance(v, list):
            return True, v, {}
        return (True, [v], {}) if isinstance(v, str) and v.strip() else (False, None, {})
    if t == "range":
        if isinstance(v, dict) and set(v) <= {"min", "max", "unit"} and ("min" in v or "max" in v):
            lo, hi = v.get("min"), v.get("max")
            if all(x is None or (isinstance(x, (int, float)) and not isinstance(x, bool)) for x in (lo, hi)) and (lo is None or hi is None or lo <= hi):
                return True, {k: v[k] for k in ("min", "max") if k in v}, {}
        return False, None, {}
    if t == "object":
        if not isinstance(v, dict):
            return False, None, {}
        fields = spec.get("fields")
        if fields:
            names = {f["key"] if isinstance(f, dict) else f for f in fields}
            if not set(v) <= names | {"unit"}:
                return False, None, {}
        return True, v, {}
    if t == "date":
        return (True, v, {}) if isinstance(v, str) and re.match(r"\d{4}(-\d{2}(-\d{2})?)?$", v) else (False, None, {})
    return False, None, {}
