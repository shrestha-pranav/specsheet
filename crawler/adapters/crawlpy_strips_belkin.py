#!/usr/bin/env python3
"""Belkin clamping voltage, as printed (A2 r7, coordinator ruling 2026-11-26). Extractor `crawlpy-strips-belkin@1`.

A *supplement* to crawlpy_strips (which is left byte-identical: rel/source-stated-hierarchy@10 pins its fingerprint for the Belkin
page-variant relations). iter_legacy("belkin") yields exactly what crawlpy_strips.iter_legacy yields, plus one `surge.clamping_v` claim
per page whose own 'Technical Specifications' block prints a clamping voltage. Those claims carry this extractor's tag, so a claim
policy can allowlist them separately and pin this module's fingerprint (registry.SUPPLEMENTS).

Rules (spec-profile surge.clamping_v):
  'Clamping Voltage 330V'                          -> 330
  'Clamping Voltage L-N: 400V, L-G: 500V, N-G: 500V' -> 500 (highest mode; raw keeps all three)
  'Clamping Voltage 340V(@50A)' / '340(@ 100A)'    -> nothing (stated at a test current: not comparable)
  'Clamping Voltage 330V No 400V No' (chart cell)  -> nothing
  'Clamping Voltage UL1449 1.2 KV'                 -> nothing (kV, no V figure; not read as a VPR either)
Never surge.vpr_*: no Belkin page says VPR / Voltage Protection Rating, and a bare clamping voltage is not the UL 1449 VPR.
"""
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C  # noqa: E402
import crawlpy_strips as S  # noqa: E402

ID, VERSION = "crawlpy-strips-belkin", 1
ADAPTER = f"{ID}@{VERSION}"

CLAMP = re.compile(r"Clamping Voltage\s*:?\s*(?:L-N:?\s*(\d{3,4})\s*V,?\s*L-G:?\s*(\d{3,4})\s*V,?\s*N-G:?\s*(\d{3,4})\s*V|(\d{3,4})\s*V\b(?!\s*\(@))"
                   r"(?!\s*(?:No|Yes)\b)")


def tech_block(d):
    pt = S.page_text(d)
    i = pt.find("Technical Specifications")
    if i < 0:
        return ""
    j = pt.find("Warranty and Support", i)
    return pt[i:j if j > i else i + 1200]


def clamping(tech):
    """-> (value, raw, quote) or None."""
    m = CLAMP.search(tech or "")
    if not m:
        return None
    v = max(int(x) for x in m.groups()[:3]) if m.group(1) else int(m.group(4))
    return v, m.group(0), tech[max(0, m.start() - 40):m.end() + 40]


def iter_legacy(source_id):
    for d, key, e, f, h in S.products(source_id):
        out, _ = S.build(source_id, key, d, e, f, h)
        if out is None:
            continue
        rec, pr, extra = out
        cl = clamping(tech_block(d)) if source_id == "belkin" else None
        if cl:
            v, raw, quote = cl
            c = C.claim(pr["fingerprints"]["model"], "surge.clamping_v", v, "V", raw, "s1", ADAPTER, "table", rec["fetched_at"],
                        {"where": "belkin.tech"}, quote)
            pr["claims"].append(c)
        yield rec, pr, extra
