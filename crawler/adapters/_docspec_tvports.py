"""Pure per-port HDMI rate parser for TV quick start guides, r7 (2026-11-26, A2-st): docspec-tv-ports@1. No network, deterministic, text layer.

Separate module (like _docspec_tv / docspec-tv@1) so the pinned r3 extractors never drift. Input = crawler/documents.py derived text
(pages [{n, text, blocks, method, ocr_conf}]); only pages with method == text_layer are read.

What it reads: the maker's own per-port statement in the connections section of a TCL quick start guide:
    'HDMI port 1: Supports up to 4K/144Hz' / 'HDMI port 2: Supports up to 4K/120Hz' / 'HDMI ports 3 & 4: Supports up to 4K/60Hz'
Each line names its port(s) and the 4K rate that port takes. tv(doc) ->
  hdmi.ports_4k120  number of ports whose stated 4K rate is >= 120 Hz (0 is written when every stated port is below 120: an explicit
                    per-port statement, not silence).
  hdmi.has_4k120    true when that count is >= 1 (never false).
Rules (affirmative only, all must hold or nothing is read):
  - every port number 1..N appears in some line (a gap = an incomplete list), and no port is given two different rates;
  - at least two port statements, so a single "HDMI port 1" sentence about eARC alone never counts as the full list;
  - the document carries no size-qualified rate footnote ('120Hz is only supported for 65"/75"'): a multi-size guide whose rate differs by
    size says nothing per model;
  - generic 'HDMI 2.1' / 'supports 4K 120Hz' prose and the 'Input Signal Compatibility' format table are not read.
"""
import re

VERSION = 1
NAME = "docspec-tv-ports"

PORT = re.compile(r"HDMI\s+ports?\s+((?:\d\s*(?:,|&|and|/)?\s*)+?)\s*:\s*Supports\s+up\s+to\s+4K\s*/\s*(\d{2,3})\s*Hz", re.I)
SIZE_FOOTNOTE = re.compile(r"only\s+(?:be\s+)?(?:supported|available)\s+(?:on|for|with)\s+[^\n]{0,40}\d{2,3}\s*(?:\"|”|''|-?inch)", re.I)


def tv(doc):
    pages = [p for p in doc.get("pages") or [] if p.get("method") == "text_layer"]
    text = "\n".join(p.get("text", "") for p in pages)
    if SIZE_FOOTNOTE.search(text):
        return []
    rates, quotes, first_page = {}, [], None
    for p in pages:
        for m in PORT.finditer(p.get("text", "")):
            q = re.sub(r"\s+", " ", m.group(0)).strip()
            for port in re.findall(r"\d", m.group(1)):
                r = int(m.group(2))
                if rates.setdefault(int(port), r) != r:
                    return []                       # one port, two rates: nothing
            if q not in quotes:
                quotes.append(q)
            first_page = first_page or p.get("n")
    if len(quotes) < 2 or not rates or sorted(rates) != list(range(1, max(rates) + 1)):
        return []
    n = sum(1 for r in rates.values() if r >= 120)
    raw = " | ".join(quotes)
    out = [{"key": "hdmi.ports_4k120", "value": n, "raw": raw, "quote": raw, "page": first_page, "ocr": False, "ocr_conf": None}]
    if n >= 1:
        out.append({"key": "hdmi.has_4k120", "value": True, "raw": raw, "quote": raw, "page": first_page, "ocr": False, "ocr_conf": None})
    return out
