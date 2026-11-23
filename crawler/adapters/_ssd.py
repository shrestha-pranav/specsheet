"""Shared pure helpers for the SSD adapters (samsung_ssd, sandisk_ssd, teamgroup_ssd). No network.

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
    m = re.search(r"PCIe\s*(?:Gen\s*)?(\d)(?:\.0)?\s*(?:x\s*(\d))?", s, re.I)
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


def dram(s):
    """-> list of (key, value). 'None'/'DRAM-less' = dramless; sizes/generations only when printed."""
    s = s or ""
    if re.search(r"dram[- ]?less|\bnone\b|^no$|not applicable|^n/?a$", s, re.I):
        return [("hw.dram_type", "dramless_none")] if re.search(r"dram[- ]?less|\bnone\b|^no$", s, re.I) and not re.search(r"hmb|host memory", s, re.I) else []
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


def temp_range(s):
    m = re.search(r"(-?\d+)\s*(?:°|˚|º|℃)?\s*C?\s*(?:to|~|-|–)\s*(\d+)\s*(?:°|˚|º|℃|C)", s or "")
    return {"min": int(m[1]), "max": int(m[2])} if m else None


# Rated sequential speeds are the maker's "up to" figures, measured with the SLC cache active: carry that as a claim condition
# (profile headline_condition cache_state=in_slc_cache) rather than a separate qualifier claim.
CACHED = {"perf.seq_read", "perf.seq_write"}


def add(pr, adapter, snap, key, value, raw, loc_kind, loc_val, label):
    import _lt as L
    n = len(pr.claims)
    L.add(pr, adapter, snap, key, value, raw, loc_kind, loc_val, label)
    if key in CACHED and len(pr.claims) > n:
        pr.claims[-1]["conditions"] = {"cache_state": "in_slc_cache"}
