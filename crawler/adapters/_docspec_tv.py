"""Pure spec-table parser for TV spec sheets, r3 (2026-11-25): docspec-tv@1. No network, deterministic, text layer only.

Separate module (like _docspec / docspec@1) so pinned extractors never drift. Input = crawler/documents.py derived text
(pages [{n, text, blocks, method, ocr_conf}]).

Cells: `pdftotext -layout` prints two- and three-column spec sheets on one physical line ('Simplink (HDMI CEC)   •   HDMI   3 (HDCP 2.2)').
A line is split into segments at runs of 3+ spaces / tabs; a (label, value) pair is two adjacent segments whose first fully matches a
known label. A value that is followed by another segment the same rule would also read (per-size columns '4   4   4') is not a single
spanning cell and is never read. Affirmative only: nothing from silence, No, blank, or prose.

tv(doc) -> [{key, value, raw, quote, page, ocr, ocr_conf}]:
  hdmi.count       HDMI / HDMI In / HDMI Inputs / HDMI(R)/HDCP In row whose cell starts with the port count ('3 (HDCP 2.2)', '4x HDMI 2.1',
                   '4 HDMI (One with eARC)'). A cell holding a size qualifier ('98": TBD') is skipped.
  hdmi.earc        true when that HDMI cell names eARC.
  hdmi.has_4k120   true when that HDMI cell names HDMI 2.1 AND a 4K figure at 120 Hz or more ('4x HDMI 2.1 (4K@144HZ)'). HDMI 2.1 alone
                   does not prove 4K120 (bandwidth-limited 2.1 ports exist) and sets nothing.
  hdmi.ports_4k120 the leading count when the cell is '<N>x HDMI 2.1 (4K@120+)' and names no other HDMI version.
  refresh.native_hz 'Native (Panel) Refresh Rate' / 'Panel Refresh (Rate)' / 'Refresh Rate (Native)' = '<N>Hz'; LG's own label
                   'TruMotion 120 (Refresh Rate 60Hz)' states native 60 (TruMotion/MCI marketing numbers alone are never read).
  panel.backlight  Backlight (Type) cell: RGB Mini LED -> rgb_mini_led, Mini LED -> mini_led, Full Array / Direct -> direct_led,
                   Edge -> edge_led.
  panel.lcd_type   Panel (Type) cell naming IPS or VA as a word (TCL 'HVA' / 'WHVA' are brand names, not read); LG feature row
                   'IPS Panel' / 'IPS 4K Panel' marked Yes or a bullet -> ips.
  vrr.supported    VRR / Variable Refresh Rate / FreeSync (Premium (Pro)) row marked Yes or a bullet -> true.
"""
import re

VERSION = 1
NAME = "docspec-tv"

SEG = re.compile(r"\s{3,}|\t+")
YES = re.compile(r"(?i)^\s*(?:yes|•|●|✓)\s*$")


def segments(line):
    return [s.strip() for s in SEG.split(line.strip()) if s.strip()]


def pairs(line, label_rx):
    """(label, value) pairs on one physical line whose label fully matches label_rx (case-insensitive), with the next segment."""
    seg = segments(line)
    for i in range(len(seg) - 1):
        if re.fullmatch(label_rx, seg[i].rstrip(":："), re.I):
            yield seg[i], seg[i + 1], (seg[i + 2] if i + 2 < len(seg) else None)


def _hdmi(v):
    if re.search(r"[\"”]\s*:", v):
        return {}
    m = re.match(r"(?i)^\s*(\d)\s*(?:x\s*)?(?=$|\s|\(|HDMI)", v)
    if not m or not 1 <= int(m[1]) <= 8:
        return {}
    out = {"hdmi.count": int(m[1])}
    if re.search(r"(?i)\beARC\b", v):
        out["hdmi.earc"] = True
    k120 = re.search(r"(?i)\b4K\s*[@/ ]\s*(1[2-9]\d|2\d\d)\s*Hz", v)
    if k120 and re.search(r"(?i)HDMI\s*2\.1", v):
        out["hdmi.has_4k120"] = True
        if re.match(r"(?i)^\s*\d\s*x\s*HDMI\s*2\.1\s*\(\s*4K", v) and not re.search(r"(?i)HDMI\s*(?:1\.\d|2\.0)", v):
            out["hdmi.ports_4k120"] = int(m[1])
    return out


def _hz(v):
    m = re.fullmatch(r"(?i)\s*(\d{2,3})\s*Hz\s*", v)
    return {"refresh.native_hz": int(m[1])} if m and 24 <= int(m[1]) <= 480 else {}


def _backlight(v):
    if re.search(r"(?i)\bRGB\s*Mini\s*LED", v):
        return {"panel.backlight": "rgb_mini_led"}
    if re.search(r"(?i)Mini[- ]?LED", v):
        return {"panel.backlight": "mini_led"}
    if re.search(r"(?i)\bfull[- ]array\b|\bdirect(?:[- ]lit)?\b", v) and not re.search(r"(?i)\bedge\b", v):
        return {"panel.backlight": "direct_led"}
    if re.search(r"(?i)\bedge(?:[- ]lit)?\b", v) and not re.search(r"(?i)\bdirect|full[- ]array", v):
        return {"panel.backlight": "edge_led"}
    return {}


def _lcd(v):
    hits = {t.lower() for t in re.findall(r"\b(IPS|VA)\b", v)}
    return {"panel.lcd_type": hits.pop()} if len(hits) == 1 else {}


def _yes(key, value):
    return lambda v: {key: value} if YES.match(v) else {}


RULES = [   # (label regex, cell -> {key: value})
    (r"HDMI(?:®|\(R\))?(?:\s*/\s*HDCP)?(?:\s*(?:In|Inputs?|Ports?|Connections?))?", _hdmi),
    (r"(?:Native\s+(?:Panel\s+)?Refresh\s+Rate|Panel\s+Refresh(?:\s+Rate)?|Refresh\s+Rate\s*\(Native\))", _hz),
    (r"Backlight(?:ing)?(?:\s+Type)?", _backlight),
    (r"Panel(?:\s+Type)?", _lcd),
    (r"IPS(?:\s+4K)?\s+Panel", _yes("panel.lcd_type", "ips")),
    (r"(?:VRR|Variable\s+Refresh\s+Rate(?:\s*\(VRR\))?|(?:AMD\s+)?FreeSync(?:™|®)?(?:\s+Premium(?:\s+Pro)?)?)", _yes("vrr.supported", True)),
]
TRUMOTION = re.compile(r"(?i)^TruMotion\s+\d{2,3}\s*\(Refresh\s+Rate\s+(\d{2,3})\s*Hz\)$")


def _facts_of_line(raw):
    out = []
    for lrx, fn in RULES:
        for lab, val, nxt in pairs(raw, lrx):
            got = fn(val)
            if not got or (nxt is not None and fn(nxt)):
                continue                    # nothing, or one value per column: not a single spanning cell
            out += [(k, v, val) for k, v in got.items()]
    for lab, val, nxt in pairs(raw, r"TruMotion\s+\d{2,3}\s*\(Refresh\s+Rate\s+\d{2,3}\s*Hz\)"):
        if YES.match(val):
            out.append(("refresh.native_hz", int(TRUMOTION.match(lab)[1]), lab))
    return out


def tv(doc):
    out = []
    for page in doc.get("pages") or []:
        if page.get("method") != "text_layer":
            continue
        for raw in page.get("text", "").splitlines():
            for k, v, cell in _facts_of_line(raw):
                out.append({"key": k, "value": v, "raw": cell[:200], "quote": " ".join(raw.split())[:200], "page": page["n"], "ocr": False,
                            "ocr_conf": None})
    return single(out)


def single(out):
    """One key, two different values in one document (a per-variant table we misread): that key is not read from it."""
    vals = {}
    for f in out:
        vals.setdefault(f["key"], set()).add(f["value"])
    seen, uniq = set(), []
    for f in out:
        if len(vals[f["key"]]) > 1 or f["key"] in seen:
            continue
        seen.add(f["key"]); uniq.append(f)
    return uniq
