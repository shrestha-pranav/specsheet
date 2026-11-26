"""Pure document parsers for the generic document stage (crawler/documents.py -> scripts/docattach.py). No network, deterministic.

Input = the derived text of one document (crawler/documents.py extract): pages [{n, text, blocks, method, ocr_conf, tokens?}]. `blocks`
are the column-local text blocks of `pdftotext -bbox-layout` (multi-column, multi-language manuals stay readable); a page without blocks
(OCR) is read line by line as one block. `tokens` (OCR pages, from the raw/_documents/ocr sidecar, attached by scripts/docattach.py) =
per line [[word, conf]]: every row/device entry read from an OCR page carries `tok_conf` = the lowest confidence of a digit-bearing word
it was read from (all words when none has a digit), None when the page has no token evidence (review 6: a high page mean must never
rescue an uncertain electrical digit).

power_output(doc) -- chargers + power banks. Reuses the page parsers' PDO model (_powerbank.pdos / _charger.norm_pdo), so a document port
row has the out.ports shape {fixed_pdos, pps, max_w}. Grammar, per block in reading order:
  - a port prefix 'USB-C1 / USB-C2 :' / 'USB-C1: 5V 3A ...' / 'USB-A1 QC3.0:' opens the named port(s); unprefixed PDO lines continue them
    ('20.0V 3.25A (65.0W Max)', 'PPS: 3.3V-16.0V 3.25A Max'); a new prefix, a header or the block end closes them;
  - mode headers: 'Use One Port' / 'Use 1 Port' / 'Single Port' -> single; 'Use Two Ports' / 'Multi Port' / 'N Ports in use' /
    'Simultaneous' -> multi. A '+' prefix ('USB-C1 + USB-C2 :') opens a combination context. docparse@2 (review 6 fix 2): mode and
    combination context are DOCUMENT scope: they survive block and page boundaries (a heading block followed by a row block, a table
    continued on the next page) and only an explicit mode heading changes them (single heading: closes the combination). Fail closed: a
    continuation after a combination is never read as a single port;
  - per-port rows are kept ONLY outside multi mode and outside a combination context (combination rows are reduced profiles, not the
    port's capability); 'Input' sections are skipped until an 'Output' heading; efficiency test points (a line with %) are never PDOs.
  - a PDO/PPS line that names no port is device-level evidence only (never a port).
Device-level facts: pps (a printed PPS/variable range in an output section, or an explicit 'Support(s) PPS' / protocol list naming PPS),
pps ranges, highest fixed voltage. Port rows keep their page, block text (quote) and the mode they were read in.

models(doc) -- every model-like token per page (identity is decided by scripts/docattach.py against the linking page's own identifiers).
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _powerbank as P  # noqa: E402
import _charger as CH  # noqa: E402

VERSION = 2
NAME = "docparse"

PNAME = r"(?:USB[- ]?[AC]\s?\d?|Type[- ]?C\s?\d?|C\d|A\d|[AC](?=\s*[:：/]))"
PREFIX = re.compile(r"^\s*(" + PNAME + r"(?:\s*(?:/|&|,|\+)\s*(?:USB[- ]?|Type[- ]?)?(?:[AC]\s?\d?|C\d|A\d|USB\d))*)\s*"
                    r"(?:(?:PD|PPS|QC\s*\d(?:\.\d)?|PD/PPS)\s*)*(?:Output|Port)?\s*[:：]\s*(.*)$", re.I)
PLUS_PREFIX = re.compile(r"^\s*(?:" + PNAME + r"|USB\d)(?:\s*\+\s*(?:" + PNAME + r"|USB\d))+\b", re.I)
SINGLE_H = re.compile(r"(?i)\buse\s*(?:one|1|a single)\s*ports?\b|\bsingle[- ]?port\b|\bone[- ]port\b|\b1[- ]port\s*(?:output|in use)\b|\b(?:one|1)\s*port\s*in\s*use\b")
MULTI_H = re.compile(r"(?i)\buse\s*(?:two|three|four|five|2|3|4|5)\s*ports?\b|\bmulti(?:ple)?[- ]?ports?\b|\b(?:two|three|four|2|3|4)\s*ports?\s*(?:in\s*use|output)\b|"
                     r"\bsimultaneous|\bdual[- ]port\s*output|\bcombined\s*output")
INPUT_H = re.compile(r"(?i)^\s*(?:input|eingang|entr[ée]e|entrada|ingresso)\b|\binput\s*(?:port)?\s*[:：]")
OUTPUT_H = re.compile(r"(?i)^\s*(?:output|outputs)\b|\boutput\s*[:：]|\boutput\s*interface")
PPS_NAMED = re.compile(r"(?i)\bsupports?\s*PPS\b|\bPPS\s*(?:support(?:ed)?|compatible)\b|(?:PD\s*3\.[01]|QC\s*\d(?:\.\d)?)[^.\n]{0,40}[,/]\s*PPS\b|\bPPS\s*[,/]\s*(?:PD|QC|AFC|SCP|FCP)")
EFFICIENCY = re.compile(r"\d\s*%|efficien", re.I)
# r10 (A2-pb): an IEC/EN/UL 62368-1 power-source class sentence ("USB-C port (20V/5A, 28V/5A) are classified as PS3 in IEC/EN/UL 62368-1")
# is safety boilerplate, often shared across a product family, never the product's PDO list: the line is skipped and closes any open row.
SAFETY_CLASS = re.compile(r"\bPS\s?[123]\b|62368")
MODEL_TOKEN = re.compile(r"(?<![A-Z0-9])([A-Z]{1,3}\d{3,5}[A-Z0-9]{0,4})(?![A-Z0-9])")


def word_conf(words):
    """[[word, conf]] of one OCR line -> the confidence that line's critical tokens carry: lowest digit-bearing word, else lowest word."""
    dig = [c for w, c in words if re.search(r"\d", w)]
    allc = [c for _, c in words]
    return min(dig) if dig else (min(allc) if allc else None)


def _text_blocks(page):
    """-> list of blocks (list of (line, token conf)) in reading order. Token conf: None on a text-layer page (not OCR) and on an OCR page
    without token evidence."""
    if page.get("blocks"):
        return [[(l, None) for l in b["lines"]] for b in page["blocks"]]
    raw = page.get("text", "").split("\n")
    tok = page.get("tokens")
    if tok is not None and len(tok) != len(raw):
        tok = None
    return [[(l, word_conf(tok[i]) if tok is not None else None) for i, l in enumerate(raw) if l.strip()]]


def _clean(s):
    return CH.norm_pdo(P.clean(s))


def _pdo_bits(text):
    """P.pdos, minus mains ranges ('100-240V 1.4A' is an AC input rating, not PPS) and zero/garbled wattages."""
    fx, pps, mw, vmax = P.pdos(text)
    keep = []
    for r in (pps or "").split("; "):
        m = re.match(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)V ", r)
        if m and 3 <= float(m[1]) < float(m[2]) <= 48:
            keep.append(r)
    return fx, "; ".join(keep), (mw if mw and mw > 0 else None), vmax


def power_output(doc):
    ports, device, named = [], [], []
    mode, combo = None, False                 # document scope (docparse@2): survives block and page boundaries
    for page in doc.get("pages") or []:
        ocr = page.get("method") == "ocr"
        direction = None
        for blines in _text_blocks(page):
            lines = [l for l, _ in blines]
            block_text = " | ".join(lines)
            cur = None
            for raw, tconf in blines:
                ln = _clean(raw)
                if not ln:
                    continue
                if SAFETY_CLASS.search(ln):
                    cur = None
                    continue
                pg = dict(page, _tc=tconf)
                if PPS_NAMED.search(ln) and direction != "in":
                    named.append({"page": page["n"], "quote": ln[:200], "ocr": ocr, "ocr_conf": page.get("ocr_conf"), "tok_conf": tconf if ocr else None,
                                  "block": block_text[:600]})
                if SINGLE_H.search(ln):
                    mode, cur, combo = "single", None, False
                elif MULTI_H.search(ln):
                    mode, cur, combo = "multi", None, False
                if INPUT_H.search(ln) and not OUTPUT_H.search(ln):
                    direction, cur = "in", None
                    ln = re.sub(r"(?i)^\s*input\s*[:：]?\s*", "", ln)
                    continue
                if OUTPUT_H.search(ln):
                    direction = "out"
                    ln = re.sub(r"(?i)^\s*outputs?\s*(?:interface)?\s*[:：/]?\s*", "", ln).strip()
                    if not ln:
                        continue
                if direction == "in":
                    continue
                if EFFICIENCY.search(ln):
                    cur = None
                    continue
                if re.match(r"(?i)^\s*total\b", ln):
                    cur = None
                    continue
                if PLUS_PREFIX.match(ln):
                    combo, cur = True, None
                    _device(device, ln, pg, "multi", ocr, "port", block_text)
                    continue
                m = PREFIX.match(ln)
                if m:
                    name = re.sub(r"\s+", " ", m[1]).strip()
                    toks = [t for t in P.port_tokens(name) if t]
                    rest = m[2]
                    eff = "multi" if (mode == "multi" or combo) else (mode or "unstated")
                    if eff == "multi":
                        cur = None
                        _device(device, rest, pg, eff, ocr, "port", block_text)
                        continue
                    if not CH.has_pdo(rest) and rest.strip() and not re.search(r"\d\s*W", rest):
                        cur = None          # a protocol list / prose after a port name ('USB-C2: QC3.0 / PD3.0'), not a PDO table
                        continue
                    cur = {"name": name, "tokens": toks, "text": rest, "page": page["n"], "mode": eff, "ocr": ocr,
                           "ocr_conf": page.get("ocr_conf"), "tok_conf": tconf if ocr else None, "block": block_text[:600]}
                    ports.append(cur)
                    _device(device, rest, pg, eff, ocr, "port", block_text)
                    continue
                cont = cur is not None and (re.match(r"^\s*\d+(?:\.\d+)?\s*A\b", ln) or re.search(r"(?i)\d\s*W\s*Max", ln))
                if CH.has_pdo(ln) or re.match(r"(?i)^\s*PPS\b", ln) or cont:
                    eff = "multi" if (mode == "multi" or combo) else (mode or "unstated")
                    if cur is not None and eff != "multi":
                        # a PDO wrapped across lines ('... / 28.0V' + '5.0A, 140.0W (140.0W Max)') is re-joined with a space
                        sep = " " if re.search(r"\d\s*V\s*$", cur["text"]) else " / "
                        cur["text"] = (cur["text"] + sep + ln).strip(" /")
                        if ocr:
                            cur["tok_conf"] = _min_conf(cur["tok_conf"], tconf)
                            pg["_tc"] = cur["tok_conf"]
                        _device(device, cur["text"], pg, eff, ocr, "port", block_text)
                    else:
                        _device(device, ln, pg, eff, ocr, "out" if direction == "out" else None, block_text)
                    continue
                cur = None               # prose: the port row is over
    out_ports, by_tok = [], {}
    for p in ports:
        fx, pps, mw, vmax = _pdo_bits(p["text"])
        if not (fx or pps):
            continue
        out_ports.append({"name": p["name"], "tokens": p["tokens"], "fixed_pdos": fx or None, "pps": pps or None, "max_w": mw,
                          "vmax": vmax, "page": p["page"], "mode": p["mode"], "ocr": p["ocr"], "ocr_conf": p["ocr_conf"], "tok_conf": p["tok_conf"],
                          "quote": (p["name"] + ": " + p["text"])[:300], "block": p["block"]})
    # one document, one port, two different rows (repeated language sections OCR'd differently, a table we misread): that port is not
    # attributable from this document (device-level evidence only)
    for r in out_ports:
        for t in r["tokens"]:
            by_tok.setdefault(t, set()).add((r["fixed_pdos"], r["pps"], r["max_w"]))
    bad = {t for t, v in by_tok.items() if len(v) > 1}
    seen, uniq = set(), []
    for r in out_ports:
        if set(r["tokens"]) & bad:
            continue
        sig = (tuple(r["tokens"]), r["fixed_pdos"], r["pps"], r["max_w"])
        if sig not in seen:
            seen.add(sig); uniq.append(r)
    out_ports = uniq
    return {"ports": out_ports, "device": device, "pps_named": named}


def _device(device, text, page, mode, ocr, ctx=None, block=""):
    """ctx: 'port' (read from a named output port row), 'out' (unnamed line inside an Output section), None (no output context: never
    used for a device-level value, since it may be an input or a wireless rating)."""
    fx, pps, mw, vmax = _pdo_bits(text)
    if fx or pps:
        device.append({"page": page["n"], "mode": mode, "ctx": ctx, "fixed": fx, "pps": pps, "vmax": vmax, "ocr": ocr, "ocr_conf": page.get("ocr_conf"),
                       "tok_conf": page.get("_tc") if ocr else None, "quote": P.clean(text)[:200], "block": block[:600]})


def _min_conf(a, b):
    """Lowest of two token confidences; None (no token evidence) wins: uncertainty is never averaged away."""
    return None if a is None or b is None else min(a, b)


def models(doc):
    """-> {page_no: set(model-like tokens)} (upper-cased, e.g. A2667, A2669211, S140U)."""
    out = {}
    for page in doc.get("pages") or []:
        out[page["n"]] = set(MODEL_TOKEN.findall(page.get("text", "").upper()))
    return out


def full_text(doc):
    return "\n".join(p.get("text", "") for p in doc.get("pages") or [])


def mentions(text, value):
    """Exact identifier mention: the value bounded by non-alphanumerics (A2667 matches 'Product Number: A2667', not 'A26671')."""
    v = re.escape(str(value).upper())
    return re.search(r"(?<![A-Z0-9])" + v + r"(?![A-Z0-9])", text.upper()) is not None
