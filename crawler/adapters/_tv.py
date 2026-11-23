"""Shared, pure label-row mapper for the TV adapters (lg_tvs, samsung_tvs, tcl_tvs) -> research/tvs/spec-profile.yaml keys.

Rules (review 3 carried over from the start):
- Labelled rows only; never titles or marketing prose. Every claim keeps the literal 'label: value' in raw and the label in the locator.
- No negation-blind enums: an enum/bool comes from its OWN labelled row with an affirmative phrase; false only from a row whose whole value
  is No (or, for ATSC 3.0, a tuner row that names ATSC 1.0 and not 3.0). A missing row or a format missing from a list is unknown, never false.
- Explicit membership: hdmi.ports_4k120 only from an explicit port list, an 'Nx HDMI 2.1 (4K@N)' group statement, or LG's trailing port
  count ('4ea (supports 4K 120Hz, ... (2 port))' = 2); a generic 'supports 4K 120Hz, eARC, VRR' feature list without a port count does not
  say every port has every feature -> unresolved. Port figures are never summed across groups.
- Bases in conditions: power figures carry power_basis (maker_typical when the label says Typical, maker_unstated otherwise), peak brightness
  carries brightness_basis. Native refresh never comes from a motion/effective/marketing figure.
- Plausibility quarantines, it does not erase: dimensions that disagree with the printed size class (Samsung prints some sets in mm under an
  'inch' label) and numbers whose unit is not printed become status-unknown claims with the literal and the reason (preview evidence only).
"""
import html, re
import _contract as C

NOTRANS = dict.fromkeys(map(ord, "‎‏​﻿"), None)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(str(s or "")).translate(NOTRANS).replace("（", "(").replace("）", ")").replace("＜", "<")).strip()


class Unresolved:
    __slots__ = ("reason",)

    def __init__(self, reason):
        self.reason = reason


def fnum(s):
    m = re.search(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?", s or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", "") + (m.group(2) or ""))
    return int(v) if v == int(v) else v


YES = re.compile(r"^(yes|supported|support)\b", re.I)
NO = re.compile(r"^(no|not supported|none)\.?$", re.I)
MARKETING_HZ = re.compile(r"motion|effective|memc|index|trumotion|xcelerator|clear ?motion", re.I)
FMT_LABELS = (r"hdr \(high dynamic range\)", r"high dynamic range \(hdr\) format", r"high dynamic range format", r"hdr format support")


def yesno(v):
    if NO.match(v or ""):
        return False
    if YES.match(v or ""):
        return True
    return None


def find(rows, *pats):
    """First row whose label fully matches one of the regexes (case-insensitive), in pattern order; empty/dash/TBD cells skipped."""
    for p in pats:
        for k, v in rows.items():
            if re.fullmatch(p, k, re.I) and v not in ("", "-", "/", "N/A", "TBD"):
                return k, v
    return None, None


def inches3(label, v):
    """'57.0" x 32.8" x 1.8"' / '56.9 x 32.7 x 1.6 inch' / '48.2*27.9*2.7' under an '(inches)' label -> (w, h, d) | Unresolved | None."""
    if re.search(r"\(mm\)|\bmm\b", label + " " + v, re.I):
        return None                                   # the mm duplicate row of a TCL box: the inch row is read instead
    t = v.replace("×", "x").replace("*", "x").replace("”", '"').replace("″", '"').replace("“", '"')
    m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*"?\s*x\s*(\d+(?:\.\d+)?)\s*"?\s*x\s*(\d+(?:\.\d+)?)\s*("|inch(?:es)?|in\.?)?\s*', t, re.I)
    if not m:
        return Unresolved("dimension cell is not three numbers")
    if not (m.group(4) or '"' in t or re.search(r"inch|\(in\)", label, re.I)):
        return Unresolved("no unit printed")
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def model_size(model):
    m = re.search(r"(?<!\d)(\d{2,3})(?!\d)", model)
    return int(m.group(1)) if m and 19 <= int(m.group(1)) <= 120 else None


def hdmi_4k120(v):
    """-> int count of HDMI inputs stated to accept 4K at >= 120 Hz, an Unresolved, or None (no 4K figure in the cell)."""
    t = clean(v).replace("HZ", "Hz").replace("hz", "Hz")
    if not re.search(r"4K\s*@?\s*\d{2,3}\s*Hz", t, re.I):
        return None
    ports = {}
    for rate, plist in re.findall(r"4K\s*(\d{2,3})\s*Hz\s*\(for HDMI\s*([\d/ ,&]+)\)", t, re.I):          # Samsung '4K 144Hz (for HDMI 1/2/3/4)'
        for p in re.findall(r"\d", plist):
            ports[p] = max(ports.get(p, 0), int(rate))
    for a, b, rate in re.findall(r"HDMI\s*(\d)\s*[-–]\s*(\d)\s*:\s*4K\s*@\s*(\d{2,3})", t, re.I):         # TCL 'HDMI 1-2: 4K@144Hz'
        for p in range(int(a), int(b) + 1):
            ports[str(p)] = max(ports.get(str(p), 0), int(rate))
    if not ports:                                                                                   # TCL '1/2-4K@144Hz, 3/4-4K@60Hz'
        for plist, rate in re.findall(r"((?:\d\s*[/ ,&]\s*)*\d)\s*[-–]\s*4K\s*@\s*(\d{2,3})", t, re.I):
            for p in re.findall(r"\d", plist):
                ports[p] = max(ports.get(p, 0), int(rate))
    if ports:
        return sum(1 for r in ports.values() if r >= 120)
    m = re.match(r"^\s*(\d)\s*ea\s*\(supports 4K\s*(\d{2,3})\s*Hz\b.*\((\d)\s*ports?\)\)\s*$", t, re.I)    # LG '4ea (supports 4K 120Hz, ... (2 port))'
    if m and int(m.group(3)) <= int(m.group(1)) and len(re.findall(r"4K\s*@?\s*\d{2,3}", t, re.I)) == 1:
        return int(m.group(3)) if int(m.group(2)) >= 120 else 0
    m = re.match(r"^\s*(\d)\s*[x*]\s*HDMI\s*2\.1\s*\(\s*4K\s*@\s*(\d{2,3})\s*Hz\s*\)", t, re.I)       # '4x HDMI 2.1 (4K@144HZ)': one group, one rate
    if m and len(re.findall(r"4K\s*@?\s*\d{2,3}", t, re.I)) == 1:
        return int(m.group(1)) if int(m.group(2)) >= 120 else 0
    return Unresolved("4K figure without an explicit port list")


def hdmi_count(v):
    t = clean(v)
    m = re.match(r"^\s*(\d)\s*(?:ea\b|x\b|\*|HDMI\b|\(|$)", t, re.I) or re.match(r"^\s*HDMI\s*2\.1\s*[x*]\s*(\d)\b", t, re.I)
    if not m:
        return None
    if re.search(r"\)\s*/\s*\d", t):          # '1 (Side) / 2 (Rear)': two groups -> not one count
        return Unresolved("several HDMI groups")
    return int(m.group(1))


HDR_TOKENS = [("dolby_vision", r"dolby\s*vis(?:i)?on"), ("hdr10plus", r"hdr\s*10\s*(?:\+|plus)"), ("hdr10", r"hdr\s*10(?!\s*(?:\+|plus))"),
              ("hlg", r"\bhlg\b"), ("advanced_hdr", r"advanced\s*hdr")]
FREESYNC = {"freesync": "freesync", "compatible": "freesync", "yes": "freesync", "freesync premium": "freesync_premium",
            "freesync premium pro": "freesync_premium_pro"}


def emit(pr, brand, model, rows, adapter, stage, obs):
    used, keys = set(), set()

    def add(key, value, label, unit=None, cond=None, raw=None):
        lit = f"{label}: {raw if raw is not None else rows[label]}"
        used.add(label)
        if isinstance(value, Unresolved):
            keys.add(key)
            pr.claims.append(C.claim(model, key, None, None, lit, "s1", adapter, stage, obs, {"model_code": model, "label": label}, value.reason,
                                     conditions=cond, status="unknown"))
        elif value not in (None, "", []):
            keys.add(key)
            pr.claims.append(C.claim(model, key, value, unit, lit, "s1", adapter, stage, obs, {"model_code": model, "label": label}, lit, conditions=cond))

    # ---- size
    size = None
    for pat in (r"size", r"screen size", r"screen class", r"screen size class(?: \(diagonal\))?", r"diagonal class"):
        k, v = find(rows, pat)
        if k and (m := re.match(r'^\s*(\d{2,3})(?:\.\d)?\s*("|”|“|inch(?:es)?|in\b|-inch| class)', v, re.I)):
            size = int(m.group(1))
            ms = model_size(model)
            add("gen.size_class", size if ms in (None, size) else Unresolved(f"size {size} disagrees with model number {model}"), k, "in")
            if ms not in (None, size):
                size = None
            break
    k, v = find(rows, r"diagonal", r"real inch", r"viewable display size", r"diagonal size", r"screen size diagonal", r"diagonal screen size(?: \(inch\))?")
    if k and (x := fnum(v)) and 15 < x < 130:
        add("gen.viewable_diag", x, k, "in")
    else:
        k, v = find(rows, r"screen size class \(diagonal\)")
        if k and (m := re.search(r"\(([\d.]+)\"?\s*diagonal\)", v)):
            add("gen.viewable_diag", float(m.group(1)), k, "in")
    k, v = find(rows, r"series")
    if k and brand == "lg" and re.fullmatch(r"[A-Z0-9]{3,12}", v):
        add("gen.series", v, k)

    # ---- panel
    tech = None
    k, v = find(rows, r"display type", r"product type", r"display technology")
    if k and not re.search(r"\d,?\d{3}\s*x", v):           # a resolution in the type row = shifted row (Samsung): ignored
        lv = v.lower()
        if re.search(r"\bmicro ?led\b", lv) and "rgb" not in lv:
            tech = "micro_led"
        elif "oled" in lv:
            tech = "oled"
        elif re.search(r"\b(lcd|led|(neo ?)?qled|qned|nanocell|mini ?-?led|micro ?rgb)\b", lv):
            tech = "lcd"
        add("panel.display_tech", tech, k)
        add("panel.marketing_class", v[:60], k)
    k, v = find(rows, r"screen", r"panel type")
    if k and tech != "oled":
        add("panel.lcd_type", "va" if re.search(r"\b(w?hva|va)\b", v, re.I) else "ips" if re.search(r"\b(ips|ads)\b", v, re.I) else None, k)
    for k, v in rows.items():
        if re.fullmatch(r"backlight type|mini-led / local dimming type|led technology|contrast|display technology", k, re.I):
            lv = v.lower()
            b = ("rgb_mini_led" if re.search(r"rgb", lv) and re.search(r"mini|micro", lv) else "mini_led" if re.search(r"mini ?-?led", lv)
                 else "edge_led" if re.search(r"\bedge\b", lv) else "direct_led" if re.search(r"^direct\b|\bdirect led\b", lv) else None)
            if b and "panel.backlight" not in keys:
                add("panel.backlight", b, k)
    for k, v in rows.items():
        if re.fullmatch(r"led technology|display technology|mini-led / local dimming type", k, re.I) and re.search(r"quantum|\bqd\b|\bqd-|^s?qd", v, re.I):
            add("panel.quantum_dot", True, k)
            break
    k, v = find(rows, r"panel \+ tcon bit-depth")
    if k:
        add("panel.bit_depth", v[:80], k)

    # ---- resolution
    k, v = find(rows, r"display resolution", r"panel resolution", r"resolution", r"native resolution")
    if k and (m := re.search(r"(\d[\d,]{2,5})\s*[x*×X]\s*(\d[\d,]{2,5})", v)):
        w, h = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
        if w > h:
            add("res.native", f"{w}x{h}", k); add("res.width_px", w, k, "px"); add("res.height_px", h, k, "px")
            add("res.class", {1024: "hd", 1280: "hd", 1366: "hd", 1920: "fhd", 3840: "4k", 7680: "8k"}.get(w), k)

    # ---- refresh
    k, v = find(rows, r"refresh rate", r"panel refresh", r"panel refresh rate")
    if k:
        if MARKETING_HZ.search(v):
            add("refresh.marketing", v[:80], k)
            if (m := re.search(r"(\d{2,3})\s*Hz\s*Native", v, re.I)):          # LG 'TruMotion 120 (60Hz Native)'
                add("refresh.native_hz", int(m.group(1)), k, "Hz")
        elif (hz := [int(x) for x in re.findall(r"(\d{2,3})\s*Hz", v, re.I)]):
            add("refresh.native_hz", hz[0], k, "Hz")
            if (dlg := re.search(r"DLG\s*(\d{2,3})", v, re.I)):
                add("refresh.dlg_hz", int(dlg.group(1)), k, "Hz")
            up = [int(x) for x in re.findall(r"(?:up to|vrr)\s*(?:4K\s*)?(\d{2,3})\s*Hz", v, re.I)] + [int(x) for x in re.findall(r"/\s*4K\s*(\d{2,3})\s*Hz", v, re.I)]
            if up:
                add("refresh.max_hz", max(up), k, "Hz")
    k, v = find(rows, r"variable refresh rate \(vrr\)", r"vrr \(variable refresh rate\)", r"vrr")
    if k:
        if NO.match(v):
            add("vrr.supported", False, k)
        elif YES.match(v) or re.match(r"^up to \d", v, re.I):
            add("vrr.supported", True, k)
            if "refresh.max_hz" not in keys and (m := re.search(r"(?:up to\s*|4K2K@\d+~)(\d{2,3})\s*Hz", v, re.I)):
                add("refresh.max_hz", int(m.group(1)), k, "Hz")
    for k, v in rows.items():
        if re.fullmatch(r"motion technology|motion rate|motion enhancement technology|motion enhancement rate|clear motion index|trumotion.*", k, re.I):
            if "refresh.marketing" not in keys:
                add("refresh.marketing", f"{k}: {v}"[:80], k)

    # ---- HDR
    fmts = []
    k, v = find(rows, *FMT_LABELS)
    fk = k
    if k:
        fmts = [f for f, rx in HDR_TOKENS if re.search(rx, v, re.I)]
        add("hdr.formats", fmts, k)
    k, v = find(rows, r"dolby vision", r"dolby vision mode")
    if k and (yesno(v) is not None or re.match(r"^dolby vision", v, re.I)):
        add("hdr.dolby_vision", not NO.match(v), k)
    elif "dolby_vision" in fmts:
        add("hdr.dolby_vision", True, fk)
    k, v = find(rows, r"hdr ?10\+", r"compatible with hdr 10\+")
    if k and yesno(v) is not None:
        add("hdr.hdr10plus", yesno(v), k)
    elif "hdr10plus" in fmts:
        add("hdr.hdr10plus", True, fk)
    k, v = find(rows, r"contrast control zones \(local dimming zones\)", r"local dimming")
    if k and yesno(v) is not None:
        add("hdr.local_dimming", yesno(v), k)
    k, v = find(rows, r"dimming zones")
    if k and (m := re.search(r"(?:(up to)\s*)?(\d[\d,]*)\s*(\+)?\s*(?:discrete\s*)?(?:dimming\s*)?zones", v, re.I)):
        add("hdr.dimming_zones", Unresolved("'N+' is a lower bound") if m.group(3) else (f"Up to {m.group(2)}" if m.group(1) else int(m.group(2).replace(",", ""))), k)
        if not m.group(3) and "hdr.local_dimming" not in keys:
            add("hdr.local_dimming", True, k)
    k, v = find(rows, r"system brightness [–-] peak\(uhda test method typical\)")
    if k and re.search(r"\d", v) and (x := fnum(v)):
        add("hdr.peak_nits", x, k, "nit", {"brightness_basis": "uhda_typical"})
    k, v = find(rows, r"peak brightness \(nits\)", r"display brightness")
    if k and (m := re.search(r"(up to\s*)?(\d[\d,]*)\s*(?:peak\s*)?nits", v, re.I)):
        add("hdr.peak_nits", (f"Up to {m.group(2)}" if m.group(1) else fnum(m.group(2))), k, "nit", {"brightness_basis": "maker_peak_unstated"})

    # ---- HDMI & gaming
    k, v = find(rows, r"hdmi", r"hdmi input", r"hdmi connections", r"hdmi™/hdcp input", r"hdmi®", r"hdmi port\(s\)", r"no\. of hdmi ports")
    if k:
        add("hdmi.count", hdmi_count(v), k)
    for lab in ("HDMI Maximum Input Rate", "HDMI 2.1", "HDMI", "HDMI Input"):
        kk, vv = find(rows, re.escape(lab))
        if kk and (n := hdmi_4k120(vv)) is not None:
            add("hdmi.ports_4k120", n, kk)
            break
    k, v = find(rows, r"hdmi maximum input rate")
    if k:
        add("hdmi.max_input", v[:60], k)
    for k, v in rows.items():
        if re.fullmatch(r"hdmi audio return channel(?: \(arc\))?|hdmi|hdmi input|hdmi 2\.1|hdmi a / return ch\. support", k, re.I) and re.search(r"\beARC\b", v, re.I):
            add("hdmi.earc", True, k)
            break
    vf, vl = [], []
    for k, v in rows.items():
        lk = k.lower().replace("™", "").replace("-", "").replace(" ", "")
        if lk in ("freesync", "freesynccertification"):
            t = re.sub(r"free-?sync", "freesync", v.lower()).strip()
            if t in FREESYNC:
                vf.append(FREESYNC[t]); vl.append(k)
        elif lk in ("freesyncpremium", "freesyncpremiumpro") and YES.match(v):
            vf.append("freesync_premium_pro" if lk.endswith("pro") else "freesync_premium"); vl.append(k)
        elif lk in ("gsync", "gsynccompatible(nvidia)", "gsynccompatible") and YES.match(v):
            vf.append("gsync_compatible"); vl.append(k)
    if vf:
        add("vrr.formats", sorted(set(vf)), vl[0], raw="; ".join(f"{lab}={rows[lab]}" for lab in vl))
        used.update(vl)
    for key, pats in (("game.allm", (r"auto game mode \(allm\)", r"allm \(auto low latency mode\)")), ("game.hgig", (r"hgig", r"hgig mode")),
                      ("audio.dolby_atmos", (r"dolby atmos", r"dolby atmos®"))):
        k, v = find(rows, *pats)
        if k and yesno(v) is not None:
            add(key, yesno(v), k)

    # ---- smart
    k, v = find(rows, r"operating system \(os\)", r"operating system", r"smart tv operating system", r"smart platform")
    if k:
        lv = v.lower()
        add("os.platform", "webos" if "webos" in lv else "tizen" if "tizen" in lv else "google_tv" if "google tv" in lv else "android_tv" if "android tv" in lv
            else "roku_tv" if re.search(r"\broku\b", lv) else "fire_tv" if re.search(r"fire (tv|os)", lv) else "vidaa" if "vidaa" in lv else None, k)
        if (m := re.search(r"webOS\s*\d[\d.]*", v)):
            add("os.version", m.group(0), k)

    # ---- audio
    k, v = find(rows, r"sound output \(rms\)", r"audio output", r"audio power \(watts\)", r"output power")
    if k and (m := re.match(r"^\s*(\d+(?:\.\d+)?)\s*W\b\s*(?:\(|:|$)", v)):
        add("audio.output_w", fnum(m.group(1)), k, "W")

    # ---- connectivity
    k, v = find(rows, r"tuner type", r"tv tuner", r"digital broadcasting")
    if k:
        add("conn.atsc3", True if re.search(r"ATSC\s*3\.0", v, re.I) else False if re.search(r"ATSC\s*1\.0", v, re.I) else None, k)
    k, v = find(rows, r"usb input", r"usb")
    if k and (m := re.match(r"^\s*(\d)\s*(?:ea\b|x\b|usb|\(|$)", v, re.I)):
        add("conn.usb_count", Unresolved("several USB groups") if len(re.findall(r"\d\s*x\s*USB", v, re.I)) > 1 else int(m.group(1)), k)
    k, v = find(rows, r"wi-fi standard", r"wi-fi")
    if k and re.search(r"wi-?fi|802\.11", v, re.I):
        add("conn.wifi", v[:60], k)
    k, v = find(rows, r"ethernet input", r"ethernet \(lan\)", r"ethernet")
    if k:
        n = fnum(v)
        add("conn.ethernet", True if (n and n >= 1) or YES.match(v) else False if (n == 0 or NO.match(v)) else None, k)

    # ---- power
    def watts(v):
        if re.search(r"under|<|less than", v, re.I):
            return Unresolved("a bound, not a value")
        x = fnum(v)
        return x if x is not None and not re.search(r"\d\s*(?:/|~)\s*\d", v) else None
    k, v = find(rows, r"power consumption \(typical\)", r"typical power consumption")
    if k:
        add("pwr.on_mode_w", watts(v), k, "W", {"power_basis": "maker_typical"})
    else:
        k, v = find(rows, r"power consumption", r"power consumption \(watts\)")
        if k and not re.search(r"kwh", v, re.I):
            add("pwr.on_mode_w", watts(v), k, "W", {"power_basis": "maker_unstated"})
    k, v = find(rows, r"power consumption \(max\)(?: \(w\))?", r"maximum power consumption")
    if k:
        add("pwr.max_w", watts(v), k, "W")
    k, v = find(rows, r"power consumption \(stand-by\)(?: \(w\))?", r"standby power consumption", r"standby power(?: \(watts\))?")
    if k:
        add("pwr.standby_w", watts(v), k, "W", {"power_basis": "maker_unstated"})
    k, v = find(rows, r"annual power consumption", r"power consumption \(annual, kwh\)", r"power consumption \(kwh/yr\)", r"power consumption \(kwh\)")
    if k and (x := fnum(v)) is not None:
        add("pwr.annual_kwh", x, k, "kWh", {"power_basis": "maker_unstated"})

    # ---- physical
    for k, v in rows.items():
        lk = k.lower()
        if "weight" not in lk or re.search(r"package|shipping|packaging|pallet|^stand weight|\(kg\)", lk):
            continue
        key = "phys.weight_no_stand" if re.search(r"without stand|w/o stand", lk) else "phys.weight_with_stand" if re.search(r"with stand|^w stand", lk) else None
        if not key or key in keys:
            continue
        x = fnum(v)
        if x and re.search(r"\blbs?\b|pounds", lk + " " + v, re.I):
            add(key, x, k, "lb")
        elif x:
            add(key, Unresolved("no unit printed"), k)
    for k, v in rows.items():
        lk = k.lower()
        if not re.search(r"dimension|size", lk) or re.search(r"package|shipping|packaging|pallet|stand size|stand \(basic\)|screen|container", lk):
            continue
        part = "no_stand" if re.search(r"without stand|w/o stand", lk) else "with_stand" if re.search(r"with stand", lk) else None
        if not part or f"phys.width_{part}" in keys:
            continue
        d = inches3(k, v)
        if d is None:
            continue
        if not isinstance(d, Unresolved) and size:
            w, h, dd = d
            if not (0.80 * size <= w <= (1.1 if part == "with_stand" else 0.98) * size and 0.40 * size <= h <= 0.80 * size and dd <= 0.45 * size):
                d = Unresolved(f"{w:g} x {h:g} x {dd:g} disagrees with the {size}\" class (unit mislabelled?)")
        for ax, x in zip(("width", "height", "depth"), d if not isinstance(d, Unresolved) else (d, d, d)):
            add(f"phys.{ax}_{part}", x, k, "in")
    k, v = find(rows, r"vesa mounting \(wxh\)", r"vesa spec", r"vesa hole pattern", r"vesa® size \(mm\)")
    if k and (m := re.fullmatch(r"\s*(\d{2,4})\s*[xX*]\s*(\d{2,4})\s*(mm)?\s*", v)):
        add("phys.vesa", f"{m.group(1)}x{m.group(2)}", k)
    k, v = find(rows, r"limited warranty", r"warranty")
    if k and re.search(r"year|yr", v, re.I):
        add("sup.warranty", v[:60], k)
    return used
