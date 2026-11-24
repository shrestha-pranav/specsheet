"""Pure helper: explicit affirmative SSD silicon statements in a maker's own product-page prose (sandisk_ssd@3, teamgroup_ssd@3). No network.

Only three facts, and only when the page states them about the drive itself:
  hw.nand_type (+ hw.nand_vendor when the same sentence names SanDisk/BiCS)   'built with ... BiCS TLC 3D CBA NAND', '3D QLC NAND flash'
  hw.controller / hw.controller_vendor                                      'PHISON PS5027-E27T control chip', 'IG5666 controller chip from InnoGrit',
                                                                            'in-house controller', 'SMI controller'
  hw.dram_type = dramless_hmb (HMB stated) | dram ('equipped with DRAM Cache') | dramless (a bare 'DRAM-less': HMB unstated, never assumed)
Rules: the quote (the sentence) is kept as the claim's raw literal; a hedged or comparative sentence ('by default', 'whereas', 'previous generation',
two models in one sentence, cache-mix descriptions such as 'SLC ... and TLC flash blocks') says nothing; two different values for one key on the page
= conflict, nothing written for that key (listed in the result's `conflicts`); silence writes nothing. A bare 'DRAM-less' (no HMB in the same
sentence) = `dramless` (A1 answer, coverage r3): it says neither dramless_hmb nor dramless_none, so hw.hmb_support stays unknown. A page that
says 'DRAM-less' in one sentence and 'HMB' in another yields dramless_hmb only through the HMB sentence; the two values conflict -> nothing.
"""
import html, re

HEDGE = re.compile(r"by default|whereas|previous gen|compared|\bvs\.?\s|\bor\b[^.]{0,20}\b(?:TLC|QLC)\b|combination of|test system|configuration:|"
                   r"supported controller|\b\w+ Pro\s*/\s*\w+", re.I)
NAND = re.compile(r"\b(TLC|QLC)\b(?:\s*\((?:triple|quad)[- ]level cell\))?[^.]{0,25}?\b(?:NAND|flash)\b(?!\s*blocks)", re.I)
CTRL = [(re.compile(r"\bPHISON\s+((?:PS\d{4}-)?E\d{2}T?)\b", re.I), lambda m: f"Phison {m[1].upper()}", "phison"),
        (re.compile(r"\b(IG\d{4})\b[^.]{0,30}\bInnoGrit\b|\bInnoGrit\s+(IG\d{4})\b", re.I), lambda m: f"InnoGrit {(m[1] or m[2]).upper()}", "innogrit"),
        (re.compile(r"\bInnoGrit\s+controller", re.I), None, "innogrit"),
        (re.compile(r"\bPHISON\s+controller", re.I), None, "phison"),
        (re.compile(r"\b(?:SMI|Silicon Motion)\s+controller", re.I), None, "silicon_motion"),
        (re.compile(r"\bMaxio\s+controller", re.I), None, "maxio"),
        (re.compile(r"\bin-house controller", re.I), None, "in_house")]
HMB = re.compile(r"\bHost Memory Buffer\b|\bHMB\b")
DRAM_YES = re.compile(r"\bequipped with (?:a )?DRAM cache\b", re.I)
DRAMLESS = re.compile(r"\bDRAM[- ]?less\b", re.I)
SELF_DRAMLESS = re.compile(r"\bthis DRAM[- ]?less (?:drive|SSD)\b", re.I)


def page_text(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", h or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).replace("\xa0", " ").strip()


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if 20 <= len(s.strip()) <= 600]


def extract(h):
    """-> {"claims": {key: (value, quote)}, "conflicts": [key, ...]} for one product page."""
    found = {}
    for s in sentences(page_text(h)):
        if HEDGE.search(s):
            # the one exception: 'this DRAM-less drive ...' names the drive itself; the sentence's comparison ('over the previous generation')
            # is about another attribute, so only the DRAM-less self-description is read from it (and only if HMB is not mentioned)
            if SELF_DRAMLESS.search(s) and not HMB.search(s):
                found.setdefault("hw.dram_type", {}).setdefault("dramless", s[:300])
            continue
        q = s[:300]
        for m in NAND.finditer(s):
            found.setdefault("hw.nand_type", {}).setdefault(m[1].lower(), q)
            if re.search(r"(?:\bSan[Dd]isk|SANDISK)(?:['’]s)?\s+(?:[\w-]+\s+){0,5}$|\bBiCS\d*\s+(?:\d+L\s+)?$", s[max(0, m.start() - 70):m.start()]):   # vendor named IN the NAND phrase
                found.setdefault("hw.nand_vendor", {}).setdefault("sandisk", q)
        for rx, name, vendor in CTRL:
            if (m := rx.search(s)):
                found.setdefault("hw.controller_vendor", {}).setdefault(vendor, q)
                if name:
                    found.setdefault("hw.controller", {}).setdefault(name(m), q)
        if HMB.search(s) and re.search(r"\bsupports?\b|\buses?\b|\bwith\b", s, re.I):
            found.setdefault("hw.dram_type", {}).setdefault("dramless_hmb", q)
        elif DRAM_YES.search(s):
            found.setdefault("hw.dram_type", {}).setdefault("dram", q)
        elif DRAMLESS.search(s):
            found.setdefault("hw.dram_type", {}).setdefault("dramless", q)
    out, conflicts = {}, []
    for k, vals in found.items():
        if len(vals) == 1:
            (v, q), = vals.items()
            out[k] = (v, q)
        else:
            conflicts.append(k)
    return {"claims": out, "conflicts": sorted(conflicts)}
