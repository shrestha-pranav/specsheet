"""Pure parser: a manufacturer's processor cell -> {model, cores, threads, base_clock, boost_clock, cache, cores_threads}.
Only fields the text states unambiguously are returned (missing = not stated / ambiguous). Used by scripts/import.py to emit
derived claims (`import.py+cpu-split@1`, derived_from = the literal claim) until each adapter emits these keys itself.

Handles: PSREF Intel   "Intel Core Ultra 5 225U, 12C (2P + 8E + 2LPE) / 14T, Max Turbo up to 4.8GHz, 12MB Intel Smart Cache"
         PSREF Intel   "Intel Core 5 210H, 8C (4P + 4E) / 12T, P-core 2.2 / 4.8GHz, E-core 1.6 / 3.6GHz, 12MB Intel Smart Cache"
         PSREF AMD     "AMD Ryzen AI 5 430 (4C / 8T, 2.0 / 4.5GHz, 4MB L2 / 8MB L3)"
         PSREF Arm     "Snapdragon X X1-26-100, 8C, Max Turbo up to 3.0GHz, 30MB" / "MediaTek Kompanio 520 (8C, 2x A76 @2.05GHz + ...)"
         ASUS/Dell     "Intel® Core™ Ultra 7 Processor 255H 2.0 GHz (24MB Cache, up to 5.1 GHz, 16 cores, 16 Threads); ..."
         Apple list    ["Apple M2 Pro chip", "10-core CPU with 6 performance cores and 4 efficiency cores", ...]
"""
import re

TM = re.compile(r"\s*[®™]|\((?:R|TM)\)", re.I)


def _f(x):
    v = float(x)
    return int(v) if v.is_integer() else v


def parse_apple(items):
    chips = []
    for s in items:
        m = re.match(r"^\s*Apple (M\d+(?: Pro| Max| Ultra)?) chip\s*$", str(s))
        if m and m.group(1) not in chips:
            chips.append(m.group(1))
    if not chips:
        return {}
    out = {"model": " / ".join("Apple " + c for c in chips)}
    if len(chips) == 1:
        cores = {int(m.group(1)) for s in items for m in [re.match(r"^\s*(\d+)-core CPU\b", str(s))] if m}
        if len(cores) == 1:
            out["cores"] = cores.pop()
    return out


def parse(text):
    if isinstance(text, list):
        return parse_apple(text)
    if not isinstance(text, str) or not text.strip():
        return {}
    s = TM.sub("", text.split(";")[0]).strip()
    s = re.sub(r"\s+", " ", s)
    out = {}
    # ---- model name: up to the first spec token
    cut = re.search(r"\s*(?:,\s*\d+C\b|\((?!Series)|\s\d+(?:\.\d+)?\s?GHz| with )", s)
    name = s[:cut.start()] if cut else s
    name = re.sub(r"(?<!Intel )\b(Mobile )?Processor\b", "", name)
    name = re.sub(r"\bprocessor\b", "", name)
    name = re.sub(r"\s+", " ", name).strip(" ,")
    if name and name != s or cut is None and len(s) <= 60:
        out["model"] = name
    # ---- cores / threads
    m = re.search(r"\b(\d+)C\b(?:\s*\(([^)]*)\))?(?:\s*/\s*(\d+)T\b)?", s)
    if m:
        out["cores"] = int(m.group(1))
        if m.group(3):
            out["threads"] = int(m.group(3))
        out["cores_threads"] = m.group(0).strip()
    else:
        m = re.search(r"\b(\d+)[ -]core CPU\b", s, re.I) or re.search(r"\b(\d+)[ -]cores?\b(?! ?GPU)", s, re.I)
        if m:
            out["cores"] = int(m.group(1))
        m = re.search(r"\b(\d+)[ -]threads?\b", s, re.I)
        if m:
            out["threads"] = int(m.group(1))
        if "cores" in out:
            out["cores_threads"] = f"{out['cores']}C" + (f" / {out['threads']}T" if "threads" in out else "")
    # ---- clocks (P-core when split by core type; never from per-cluster '@x GHz' lists)
    if "@" not in s:
        m = re.search(r"(?:P-core\s+|\b)(\d+(?:\.\d+)?)\s*(?:/|to|GHz to|GHz Base\s*/)\s*(\d+(?:\.\d+)?)\s*GHz", s, re.I)
        if m:
            out["base_clock"], out["boost_clock"] = _f(m.group(1)), _f(m.group(2))
        else:
            m = re.search(r"(?:Max Turbo |P-core )?up to (\d+(?:\.\d+)?)\s*GHz", s, re.I) or re.search(r"(\d+(?:\.\d+)?)\s*GHz Max (?:Turbo|boost)", s, re.I)
            if m:
                out["boost_clock"] = _f(m.group(1))   # "up to X GHz (single-core)" is the max boost
            m = re.search(r"(?<!up to )(?<!/ )(?<![\d./])(\d+(?:\.\d+)?)\s?GHz\s*(?:,|\((?!single|multi))", s)
            if m:
                out["base_clock"] = _f(m.group(1))
    # ---- cache literal
    m = re.search(r"(\d+MB L2\s*/\s*\d+MB L3)", s) or re.search(r"(\d+MB) Intel Smart Cache", s) or re.search(r"\((\d+)\s?M?B? Cache\b", s) \
        or re.search(r"(\d+MB L3) cache", s, re.I) or re.search(r"(\d+)\s?MB\s*cache", s, re.I) or re.search(r",\s*(\d+MB)\s*\)?$", s)
    if m:
        c = m.group(1)
        out["cache"] = c if "MB" in c else c.rstrip("MB") + "MB"
    return out
