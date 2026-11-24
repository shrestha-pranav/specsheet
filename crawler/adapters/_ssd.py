"""Shared pure helpers for the SSD adapters (samsung_ssd, sandisk_ssd, teamgroup_ssd, kingston_ssd). No network.

Keys follow research/ssds/spec-profile.yaml. Capacity is DECIMAL GB as makers print it (1TB = 1000 GB); a value the source did not state is
never invented (the caller passes None -> no claim). `raw` always keeps the source literal.
"""
import html, re

_NUM = r"(\d[\d,]*\.?\d*)"


def n(x):
    v = float(x.replace(",", ""))
    return int(v) if v == int(v) else v


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def capacity_gb(s):
    m = re.search(_NUM + r"\s*(TB|GB)\b", s or "", re.I)
    return n(m[1]) * (1000 if m[2].upper() == "TB" else 1) if m else None


def speed_mbs(s):
    m = re.search(_NUM + r"\s*(GB|MB)\s*/\s*s", s or "", re.I)
    return n(m[1]) * (1000 if m[2].upper() == "GB" else 1) if m else None


def iops(s):
    m = re.search(_NUM + r"\s*(K|M)?\s*IOPS", s or "", re.I)
    if not m:
        return None
    v = n(m[1]) * {"K": 1000, "M": 1000000}.get((m[2] or "").upper(), 1)
    return int(v)


def tbw(s):
    m = re.search(_NUM + r"\s*(?:TBW|TB\b|units)?", s or "", re.I)
    return n(m[1]) if m else None


def years(s):
    m = re.search(r"(\d+)[- ]*year", s or "", re.I)
    return int(m[1]) if m else None


def form_factor(s):
    s = s or ""
    m = re.search(r"M\.?2\W{0,3}(2230|2242|2260|2280|22110)", s, re.I)
    if m:
        return "m2_" + m[1]
    if re.search(r"2\.5", s):
        return "sata_2_5"
    if re.search(r"portable|external", s, re.I):
        return "portable"
    return None


def interface(s):
    """-> list of (key, value) from an interface string. Only what the string states."""
    out = []
    s = s or ""
    m = re.search(r"PCIe\s*[®™]?\s*(?:Gen\s*)?(\d)(?:\.0)?\s*(?:x\s*(\d))?", s, re.I)   # preset fill: 'PCIe® 5.0 x4' (Samsung 9100 PRO)
    if m:
        out += [("if.protocol", "nvme"), ("if.pcie_gen", int(m[1]))]
        if m[2]:
            out.append(("if.pcie_lanes", int(m[2])))
        else:
            m2 = re.search(r"[x×](\d)\b", s)
            if m2:
                out.append(("if.pcie_lanes", int(m2[1])))
    elif re.search(r"\bSATA\b", s, re.I):
        out.append(("if.protocol", "sata_ahci"))
    mv = re.search(r"NVMe\s*(\d\.\d)", s, re.I)
    if mv:
        out.append(("if.nvme_version", mv[1]))
    return out


def usb(s):
    s = s or ""
    if re.search(r"USB\s*4|USB4", s, re.I):
        return "usb4"
    if re.search(r"thunderbolt\s*4", s, re.I):
        return "thunderbolt4"
    if re.search(r"thunderbolt\s*3", s, re.I):
        return "thunderbolt3"
    if re.search(r"Gen\s*2\s*[x×]\s*2|20\s*Gb", s, re.I):
        return "usb_3_2_gen2x2"
    if re.search(r"Gen\s*2|10\s*Gb|3\.1\s*Gen\s*2", s, re.I):
        return "usb_3_2_gen2"
    if re.search(r"Gen\s*1|5\s*Gb|USB\s*3\.[012]|USB\s*3\b", s, re.I):
        return "usb_3_2_gen1"
    return None


def nand_type(s):
    s = s or ""
    if re.search(r"\bQLC\b|4[- ]?bit", s, re.I):
        return "qlc"
    if re.search(r"\bTLC\b|3[- ]?bit", s, re.I):
        return "tlc"      # Samsung prints '3-bit MLC' for TLC: the raw literal is kept on the claim
    if re.search(r"\bMLC\b|2[- ]?bit", s, re.I):
        return "mlc"
    return None


def nand_vendor(s):
    s = (s or "").lower()
    for k, v in (("samsung", "samsung"), ("kioxia", "kioxia"), ("toshiba", "kioxia"), ("sandisk", "sandisk"), ("micron", "micron"),
                 ("hynix", "sk_hynix"), ("ymtc", "ymtc"), ("solidigm", "intel_solidigm")):
        if k in s:
            return v
    return None


HMB_ANY = re.compile(r"\bHMB\b|host memory buffer", re.I)
HMB_DENIED = re.compile(r"\b(?:no|without|not\s+support(?:ed|s)?)\s+(?:an?\s+)?(?:HMB|host memory buffer)\b|\b(?:HMB|host memory buffer)\s*[:\-]?\s*(?:no|none|not supported|n/?a)\b", re.I)


def dram(s):
    """-> list of (key, value) from a DRAM / cache cell. Ruling 5 (coordinator, preset fill 2026-11-24): a cell that says the drive has no DRAM
    ('DRAM-less', 'None', 'No') = `dramless` (HMB unknown); `dramless_none` ONLY when the same cell explicitly denies HMB; `dramless_hmb` when the
    cell names HMB affirmatively (incl. a cache cell that is just 'HMB (Host Memory Buffer)'). Sizes/generations only when printed."""
    s = s or ""
    if re.search(r"not applicable|^n/?a$", s, re.I):
        return []
    if re.search(r"dram[- ]?less|\bnone\b|^no$", s, re.I) or (HMB_ANY.search(s) and not re.search(r"DDR|DRAM", s, re.I)):
        if HMB_DENIED.search(s):
            return [("hw.dram_type", "dramless_none")]
        return [("hw.dram_type", "dramless_hmb" if HMB_ANY.search(s) else "dramless")]
    out = []
    if re.search(r"DDR|DRAM", s, re.I):
        out.append(("hw.dram_type", "dram"))
        m = re.search(_NUM + r"\s*(GB|MB)", s, re.I)
        if m:
            out.append(("hw.dram_size", n(m[1]) if m[2].upper() == "GB" else n(m[1]) / 1024))
        g = re.search(r"LPDDR4X|LPDDR5|LPDDR4|DDR4|DDR3", s, re.I)
        if g:
            out.append(("hw.dram_gen", g[0].lower()))
    return out


def usb_protocol(s):
    """if.protocol for a USB-attached (portable) drive, AFFIRMATIVE ONLY (ruling 4, preset fill 2026-11-24): `usb_uasp` when the interface cell
    names UASP, `usb` when it names a USB 2/3.x interface. Thunderbolt or USB4 in the cell (PCIe can be tunnelled: the host may see NVMe) = None,
    a connector-only cell ('USB Type-C') = None, silence = None. Never not_applicable."""
    s = s or ""
    if re.search(r"thunderbolt|USB\s*4", s, re.I):
        return None
    if re.search(r"\bUASP\b", s, re.I):
        return "usb_uasp"
    if re.search(r"USB\s*(?:2\.0|3(?:\.\d)?)\b|SuperSpeed USB", s, re.I):
        return "usb"
    return None


def temp_range(s):
    m = re.search(r"(-?\d+)\s*(?:°|˚|º|℃)?\s*C?\s*(?:to|~|-|–)\s*(\d+)\s*(?:°|˚|º|℃|C)", s or "")
    return {"min": int(m[1]), "max": int(m[2])} if m else None


# Rated sequential speeds are the maker's "up to" figures. "Up to" alone does NOT say the SLC cache was active (review 2 risk 2): the
# claim keeps the literal (normalize.py turns a leading "up to" into qualifier up_to) and gets the cache_state condition ONLY when its own
# text evidences it (Samsung "Measured with Intelligent TurboWrite technology being activated", "SLC cache", WD "nCache"). cache_state is a
# BASIS condition in the profile (basis_conditions): it qualifies the assertion without splitting the headline.
CACHED = {"perf.seq_read", "perf.seq_write"}
CACHE_EVIDENCE = re.compile(r"\bSLC\b|TurboWrite|nCache|\bcache\b", re.I)


def add(pr, adapter, snap, key, value, raw, loc_kind, loc_val, label):
    import _lt as L
    n = len(pr.claims)
    L.add(pr, adapter, snap, key, value, raw, loc_kind, loc_val, label)
    if key in CACHED and len(pr.claims) > n and CACHE_EVIDENCE.search(" ".join(str(x) for x in (raw, label) if x)):
        pr.claims[-1]["conditions"] = {"cache_state": "in_slc_cache"}
