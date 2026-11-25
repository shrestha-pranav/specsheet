"""Pure spec-table parsers for linked documents, r2 (2026-11-24): SSD datasheets / spec sheets. No network, deterministic.

Separate module (docspec@1) so docparse@1 / docattach@1 -- pinned by claim/document-power-pdo@1 -- never drift.

Input = the derived text of one document (crawler/documents.py extract): pages [{n, text, blocks, method, ocr_conf}]. Only text-layer
lines of the form '<LABEL><2+ spaces><VALUE>' (pdftotext -layout table rows) or '<LABEL>: <VALUE>' are read. A value cell that is split
into several columns (2+ runs of 3+ spaces: one value per capacity) is not a single spanning value and is never read.

ssd(doc) -> [{key, value, raw, quote, page, ocr, ocr_conf}], affirmative only:
  if.protocol  'usb' (or 'usb_uasp' when the cell says UASP) from an INTERFACE row naming USB 2.0 / USB 3.x. Coordinator ruling 4: a cell
               naming Thunderbolt or USB4 (PCIe may be tunnelled) or only a connector ('USB Type-C') sets nothing.
  hw.dram_type DRAM / DRAM CACHE / Cache Memory row: Yes or a DRAM part ('2GB LPDDR4 DRAM') -> dram; HMB / Host Memory Buffer -> dramless_hmb;
               No / None / DRAM-less -> dramless (ruling 5; HMB stays unknown). A cell naming two products ('G70 PRO (Yes) / G70 (NO)') -> nothing.
  hw.nand_type NAND / NAND Type / Flash Type / NAND Flash row naming exactly one of SLC/MLC/TLC/QLC; Samsung's '3-bit MLC' = tlc, '4-bit MLC'
               = qlc (the maker's own synonym). '3D NAND' alone says nothing.
  hw.controller Controller row with a part-like token (letters + digits, e.g. 'Phison E18'); 'In-House' alone sets nothing.

monitor(doc) -> same shape, affirmative only:
  flk.pwm      'none' from a 'Flicker Safe' / 'Flicker-free (Technology)' cell reading Yes or a bullet (the maker's declaration, same meaning as
               the page label rules lg/asus flicker_free); No, blank or silence sets nothing. Prose mentions never count.
  usb.usbc_pd_w the upstream USB-C power figure of 'USB Type-C(TM) with 90W Power Delivery' (the monitor's own USB-C input charging the
               host). A line naming downstream / USB-A / charging port is skipped; a figure without 'W' ('with 65 PD') is not read.
"""
import re

VERSION = 1
NAME = "docspec"

ROW = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /&().-]{1,40}?)\d?(?:\s*[:：]\s*|\s{2,})(\S.*?)\s*$")
SPLIT = re.compile(r"\S\s{3,}\S")


def _cell(label_rx, line):
    m = ROW.match(line)
    if not m or not re.fullmatch(label_rx, m[1].strip(), re.I):
        return None
    val = m[2].strip()
    if SPLIT.search(val):
        return None             # one value per column: not a single spanning cell
    return val


def _protocol(v):
    if re.search(r"(?i)thunderbolt|usb\s*4|usb4|pcie|nvme|sata", v):
        return None
    if re.search(r"(?i)\bUSB\s*(?:2\.0|3\.[0-2])\b|\bUSB\s*3\b", v):
        return "usb_uasp" if re.search(r"(?i)\buasp\b", v) else "usb"
    return None


def _dram(v):
    if re.search(r"(?i)\(\s*(?:yes|no)\s*\)", v) or re.search(r"(?i)\byes\b.*\bno\b|\bno\b.*\byes\b", v):
        return None
    if re.search(r"(?i)\bHMB\b|host\s*memory\s*buffer", v):
        return "dramless_hmb"
    if re.fullmatch(r"(?i)\s*(?:no|none|n/a|dram[- ]?less)\s*", v):
        return "dramless"
    if re.fullmatch(r"(?i)\s*yes\s*", v) or re.search(r"(?i)\b\d+\s*(?:GB|MB)\s*(?:LP)?DDR\d", v):
        return "dram"
    return None


def _nand(v):
    v2 = re.sub(r"(?i)\b3[- ]?bit\s*MLC\b", "TLC", v)
    v2 = re.sub(r"(?i)\b4[- ]?bit\s*MLC\b", "QLC", v2)
    hits = {t.lower() for t in re.findall(r"(?i)\b(SLC|MLC|TLC|QLC|PLC)\b", v2)}
    return hits.pop() if len(hits) == 1 else None


def _controller(v):
    if not re.search(r"(?i)\b[A-Z]{1,6}\d{2,5}[A-Z0-9]*\b", v):
        return None
    return re.sub(r"(?i)\s*controller\s*$", "", v).strip()[:60] or None


RULES = [
    ("if.protocol", r"interface", _protocol),
    ("hw.dram_type", r"dram(?: cache)?|cache memory|dram buffer", _dram),
    ("hw.nand_type", r"nand(?: flash)?(?: type)?|flash(?: memory)? type|nand flash memory", _nand),
    ("hw.controller", r"controller", _controller),
]


def ssd(doc):
    out = []
    for page in doc.get("pages") or []:
        if page.get("method") != "text_layer":
            continue                # text layer only this round (no OCR claims)
        for raw in page.get("text", "").splitlines():
            for key, lrx, fn in RULES:
                v = _cell(lrx, raw)
                if v is None:
                    continue
                val = fn(v)
                if val is not None:
                    out.append({"key": key, "value": val, "raw": v[:200], "quote": " ".join(raw.split())[:200], "page": page["n"],
                                "ocr": False, "ocr_conf": None})
    return _single(out)     # one key, two different values in one document (per-variant table we misread): not read from it


FLICKER = re.compile(r"(?i)\bflicker[- ]?(?:safe|free)\s*(?:®|\(R\))?(?:\s*technology)?\s*[:：]?\s+(yes\b|•)")
PD_W = re.compile(r"(?i)\bUSB[- ]?(?:Type[- ]?)?C(?:™|\(TM\))?\s*(?:\(?upstream\)?\s*)?with\s+(\d{2,3})\s*W\s+(?:USB\s*)?Power\s*Delivery\b")


def monitor(doc):
    out = []
    for page in doc.get("pages") or []:
        if page.get("method") != "text_layer":
            continue
        for raw in page.get("text", "").splitlines():
            ln = " ".join(raw.split())
            m = FLICKER.search(ln)
            if m:
                out.append({"key": "flk.pwm", "value": "none", "raw": m[0][:200], "quote": ln[:200], "page": page["n"], "ocr": False, "ocr_conf": None})
            m = PD_W.search(ln)
            if m and not re.search(r"(?i)downstream|usb[- ]?a\b|charging port", ln):
                out.append({"key": "usb.usbc_pd_w", "value": float(m[1]), "raw": m[0][:200], "quote": ln[:200], "page": page["n"], "ocr": False, "ocr_conf": None})
    return _single(out)


def _single(out):
    vals = {}
    for f in out:
        vals.setdefault(f["key"], set()).add(f["value"])
    seen, uniq = set(), []
    for f in out:
        if len(vals[f["key"]]) > 1 or f["key"] in seen:
            continue
        seen.add(f["key"]); uniq.append(f)
    return uniq

