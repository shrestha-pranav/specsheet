#!/usr/bin/env python3
"""Dell US monitor adapter v1 (contract ARCHITECTURE 15.5), category monitors (A2-dell r6, 2026-11-25). Source = www.dell.com/en-us/shop/.../apd/.

discover : the server-rendered listing https://www.dell.com/en-us/shop/computer-monitors/ar/all-monitors?page=N (robots: '*' allows /ar/ listing
           pages; only comma-combined appliedRefinements queries are disallowed). Pages are read until one adds no new monitor (cap 15).
           Each tile links /en-us/shop/<monitors|computer-monitors>/apd/<slug>/<code>/- ; ref key = <code> (e.g. s2725qs_monitor).
fetch    : the /apd/ page (~1.6-2 MB, server-rendered), stored gzip. 1 req/s, crawler UA; a non-200 is recorded and the runner stops after 4.
parse    : pure. The '#accessoriesTechSpecs' block = spec__child__heading groups of spec__item (title + value; list values are <li>). Two
           markups seen (minified unquoted attributes, and pretty-printed quoted): both handled. One page = one model; mfr_model = the
           'Product Model' row (S2725QS), and it must equal the URL code (alphanumerics before any '_' suffix), else the page is skipped.
           'Manufacturer Part Number' (Dell part number, e.g. T4CNF) -> identifier x_dell_part_number (an alias on the model). A 'WOST'
           page ('Product Model: P2426H WOST', URL code p2426h_wost) is the same model sold without a stand: it resolves to the model
           (P2426H), its part number is an alias, and no stand-dependent key (height, weight with stand) is read from any page.
Traps    : the spec block is syndicated-style and sometimes contradicts itself (U5226KW: 'Number of DisplayPorts 0' beside 'Interface/Port
           Details: 2 DisplayPort 1.4 ... port/s'), so counts are cross-checked against the port-details list and dropped on disagreement.
           flk.pwm 'none' ONLY from the maker's explicit 'Flicker Free: Yes' row or a 'Flicker-free' item of the Features list (same meaning
           as BenQ 'Flicker-free Technology: Yes'); ComfortView, Eye Comfort star ratings, Low Blue Light and silence write nothing.
           res.refresh_native only from 'Standard Refresh Rate' as one plain 'N Hz' when no row/feature says overclock; res.refresh_max =
           'Maximum Refresh Rate' or the 'Maximum Preset Resolution ... at N Hz' figure. usb.usbc_pd_w only from an upstream-side
           'USB Type-C (Power Delivery)' / 'Thunderbolt ... Power Delivery' row with one W figure; 'Downstream' rows never count.
           usb.kvm True only from 'KVM Switch' in the 'Built-in Devices' row or a 'KVM Switch: Yes' row; never False from absence.
           v2 (same round, after @1 was locked by the round's first import): usb.usbc_inputs 0 (basis complete_enumeration) only when the port-details list is cross-checked complete: its USB-C lines add up
           to 'Total Number of USB Type-C Ports', or (no USB-C/Thunderbolt row or line anywhere) its USB lines add up to 'Number of USB Ports'.
"""
import gzip, html, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _run
import _monports as MP
import _monusb as MU

ID, VERSION, SOURCE = "dell_monitors", 2, "dell-us-monitors"
CATEGORIES = {"monitors"}
ADAPTER = f"{ID}@{VERSION}"
LISTING = "https://www.dell.com/en-us/shop/computer-monitors/ar/all-monitors"
MAX_PAGES = 15
DELAY = 1.0
TILE = re.compile(r'href="(https://www\.dell\.com/en-us/shop/(?:monitors|computer-monitors)/apd/([a-z0-9-]+)/([a-z0-9_]+)/-)"')
ITEM = re.compile(r'<div class="?spec__child__heading"?>(.*?)</div>|<div class="?spec__item"?>\s*<div class="?spec__item__title"?>(.*?)</div>(.*?)</div>', re.S)
INCH = re.compile(r'\s*(\d{2}(?:\.\d{1,2})?)\s*(?:"|inch(?:es)?|in\.?)\s*', re.I)


def txt(s):
    s = re.sub(r"<sup>.*?</sup>", "", s or "", flags=re.S | re.I)
    s = re.sub(r"(?i)</li>\s*<li[^>]*>", " | ", s)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).replace("\xa0", " ").replace("™", "").replace("®", "").strip(" |")


def items(s):
    """A value cell -> list of its <li> items (or the one text value)."""
    li = re.findall(r"<li[^>]*>(.*?)</li>", s or "", re.S)
    return [txt(x) for x in li if txt(x)] if li else ([txt(s)] if txt(s) else [])


class DellMonitors:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        seen, pages, stop = {}, 0, None
        for p in range(1, MAX_PAGES + 1):
            r = net.get(LISTING if p == 1 else f"{LISTING}?page={p}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                stop = f"listing page {p}: {getattr(r, 'status_code', r)}"
                break
            pages = p
            new = 0
            for url, slug, code in TILE.findall(r.text):
                if code not in seen:
                    seen[code] = {"url": url, "slug": slug}; new += 1
            if not new:
                break
        refs = [C.Ref(SOURCE, k, d["url"], {"slug": d["slug"]}) for k, d in sorted(seen.items())]
        return C.Discovery(refs, stop is None, stop, {"models": len(refs), "pages": pages})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            if st in (403, 429):
                raise _run.StopCrawl(f"{st} on {ref.url}: stop, no workaround")
            return s
        s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_html(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


def spec_rows(h):
    """-> list of (group, label, raw value html) in page order, from the Tech Specs block only."""
    i = h.find("accessoriesTechSpecs")
    if i < 0:
        return []
    out, grp = [], ""
    for m in ITEM.finditer(h[i:]):
        if m[1] is not None:
            grp = txt(m[1])
        else:
            out.append((grp, txt(m[2]), m[3]))
    return out


PANEL = [(r"In-plane Switching \(IPS\) Black", "IPS Black"), (r"Fast IPS", "Fast IPS"), (r"In-plane Switching \(IPS\)", "IPS"),
         (r"Quantum Dot OLED|QD-OLED", "QD-OLED"), (r"Vertical Alignment \(VA\)", "VA"), (r"Twisted nematic \(TN\)", "TN")]   # bare 'OLED': nothing
UP_PD = re.compile(r"^(?:USB Type-C \(Power Delivery\)(?: Upstream| Extended Power Range \(EPR\))?|Thunderbolt \(Power Delivery\) Upstream(?: \(Rear\))?)$", re.I)
GLUE = re.compile(r"(port/s|ports?)(?=\d+\s*(?:x\s*)?(?:USB|HDMI|Display|DP|Thunderbolt))", re.I)


def count(line):
    """'2 USB-C ...' / '2 x USB-C' / '2x USB' -> 2; default 1."""
    m = re.match(r"\s*(\d+)\s*(?:x\s*)?(?=[A-Za-z])", line)
    return int(m[1]) if m else 1


def port_lines(v_html):
    """'Interface/Port Details' cell -> one line per port type (glued '...port/s1 USB-C ...' split)."""
    out = []
    for x in items(v_html):
        out += [y.strip() for y in GLUE.sub(r"\1\n", x).split("\n") if y.strip()]
    return out


def parse_html(snap, h):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "Dell US product page " + snap.ref.key}]
    rows = spec_rows(h)
    by, grp = {}, {}
    for g, l, v in rows:
        by.setdefault(l, v); grp.setdefault(l, g)
    get = lambda l: txt(by[l]) if l in by else None
    model = (get("Product Model") or "").strip().upper()
    wost = bool(re.fullmatch(r"\S+ WOST", model))      # 'P2426H WOST' = the same model sold without its stand (a package of P2426H)
    model = re.sub(r" WOST$", "", model)
    code = re.sub(r"[^A-Z0-9].*$", "", snap.ref.key.upper())
    if not rows or not re.fullmatch(r"[A-Z]{1,3}\d{3,4}[A-Z0-9]{0,5}", model):
        pr.absences.append({"key": "*", "reason": "no Tech Specs block / Product Model row (not a monitor spec page)", "source": "s1"})
        return pr
    if model != code:
        pr.absences.append({"key": "*", "reason": f"Product Model {model!r} is not the page's URL code {code!r}", "source": "s1"})
        return pr
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "dell", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"], "series": get("Product Line") or get("Product Series")})
    pn = get("Manufacturer Part Number")
    if pn and re.fullmatch(r"[A-Z0-9]{5,7}", pn):
        pr.identifiers.append({"scheme": "x_dell_part_number", "value": pn, "value_raw": pn, "issuer": "dell", "market": "US", "sources": ["s1"],
                               **({"note": "without-stand package"} if wost else {})})
    name = get("Product Name")
    pr.aliases.append({"text": f"Dell {name}" if name and not name.lower().startswith(("dell", "alienware")) else (name or f"Dell {model}"), "kind": "marketing_name"})

    def add(k, v, label, quote=None, kind=None, extra=None):
        if v in (None, "", []):
            return
        raw = f"{label}: {get(label)}" if label in by else label
        c = C.claim(model, k, v, None, raw, "s1", ADAPTER, "adapter", snap.fetched_at,
                    locator=dict({"model_code": model, "label": f"{grp.get(label, 'Tech Specs')} > {label}"}, **(extra or {})), quote=quote or raw)
        if kind:
            c["kind"] = kind
        pr.claims.append(c)

    # ---- size / panel / resolution -------------------------------------------------------------------------------------------------
    if (sz := get("Screen Size Class")) and (m := INCH.fullmatch(sz)):
        if "." in m[1] and not re.fullmatch(r"\d+\.0+", m[1]):
            add("gen.size_class", MP.size_class(m[1]), "Screen Size Class", kind="derived", extra={"derivation": MP.DERIVATION})
        else:
            add("gen.size_class", int(float(m[1])), "Screen Size Class")
    if (vd := get("Viewable Screen Size")) and (m := INCH.fullmatch(vd)):
        add("gen.viewable_diag", float(m[1]) if "." in m[1] else int(m[1]), "Viewable Screen Size")
    if pt := get("Panel Technology"):
        hit = next((v for rx, v in PANEL if re.search(rx, pt, re.I)), None)
        add("panel.technology", hit, "Panel Technology")
    w = hgt = None
    if (r := get("Maximum Resolution")) and (m := re.fullmatch(r"\s*(\d{3,4})\s*x\s*(\d{3,4})\s*", r)):
        w, hgt = int(m[1]), int(m[2])
        add("res.native", f"{w}x{hgt}", "Maximum Resolution"); add("res.width_px", w, "Maximum Resolution"); add("res.height_px", hgt, "Maximum Resolution")
    std = get("Standard Refresh Rate")
    std_hz = int(m[1]) if std and (m := re.fullmatch(r"\s*(\d{2,3})\s*Hz\s*", std)) else None
    preset = items(by.get("Maximum Preset Resolution"))
    at_native = [int(m[3]) for x in preset if (m := re.match(r"\s*(\d{3,4})\s*x\s*(\d{3,4})\s*(?:at|@)\s*(\d{2,3})\s*Hz", x, re.I))
                 and w and (int(m[1]), int(m[2])) == (w, hgt)]
    oc = any(re.search(r"(?i)overclock|\bOC\b", f"{l} {txt(v)}") for _, l, v in rows)
    if std_hz and at_native and max(at_native) == std_hz and not oc:
        # native = two rows agree (the 'Standard' rate is the overclock rate on some pages: AW2524HF 500 Hz vs 480 Hz preset)
        add("res.refresh_native", std_hz, "Standard Refresh Rate", quote=f"Standard Refresh Rate: {std} | Maximum Preset Resolution: {' | '.join(preset)}")
    mx = [x for x in ([std_hz] if std_hz else []) + at_native]
    if mx:
        add("res.refresh_max", max(mx), "Standard Refresh Rate" if std_hz == max(mx) else "Maximum Preset Resolution")
    # ---- flicker ---------------------------------------------------------------------------------------------------------------------
    ff = get("Flicker Free")
    feats = items(by.get("Features"))
    if ff is not None and re.fullmatch(r"(?i)\s*yes\s*", ff):
        add("flk.pwm", "none", "Flicker Free", quote=f"Flicker Free: {ff}")
    elif ff is None and any(re.fullmatch(r"(?i)flicker[- ]free", x) for x in feats):
        add("flk.pwm", "none", "Features", quote="Features: Flicker-free")
    # ---- ports -----------------------------------------------------------------------------------------------------------------------
    lines = port_lines(by.get("Interface/Port Details"))
    yes = lambda *ls: any(re.fullmatch(r"(?i)yes", get(l) or "") for l in ls)
    no = lambda *ls: any(re.fullmatch(r"(?i)no", get(l) or "") for l in ls)
    tot_c = get("Total Number of USB Type-C Ports")
    tot_c = int(tot_c) if tot_c and tot_c.isdigit() else None
    # v2: '2 HDMI ports' -> '2 x HDMI ports' so _monports' video-input test reads Dell's count style (local transform; _monports untouched)
    n_in, _ = MP.count_inputs([re.sub(r"^\s*(\d+)\s+(?!x\b)", r"\1 x ", l) for l in lines], count) if lines else (None, False)
    raw_ports = "Interface/Port Details: " + " | ".join(lines)
    tot_usb = get("Number of USB Ports")
    any_c = any(MP.CPORT.search(l) for l in lines) or any(re.search(r"(?i)type-c|thunderbolt", l) and not re.fullmatch(r"(?i)no|0", txt(v))
                                                         for l, v in by.items())
    if n_in is not None and n_in > 0:
        add("usb.usbc_inputs", n_in, "Interface/Port Details", quote=raw_ports)
    elif no("USB Type-C", "USB Type-C<SUP></SUP>") and not yes("Thunderbolt", "Thunderbolt<SUP></SUP>", "Thunderbolt 4") and not tot_c \
            and not any(MP.CPORT.search(l) for l in lines):
        add("usb.usbc_inputs", 0, "USB Type-C", quote=f"USB Type-C: No")            # the maker's own 'USB Type-C: No' row: no USB-C port at all
    elif n_in == 0 and (tot_c and tot_c == sum(count(l) for l in lines if MP.CPORT.search(l))
                        or not any_c and tot_usb and tot_usb.isdigit() and int(tot_usb) == sum(count(l) for l in lines if re.search(r"\bUSB\b", l))):
        # complete enumeration, cross-checked: every USB-C port the 'Total Number of USB Type-C Ports' row counts is listed and none takes
        # video, or (no USB-C/Thunderbolt row or line at all) every USB port 'Number of USB Ports' counts is listed
        pr.claims.append(C.claim(model, "usb.usbc_inputs", 0, None, raw_ports, "s1", ADAPTER, "adapter", snap.fetched_at,
                                 locator={"model_code": model, "label": "Interfaces/Ports > Interface/Port Details"}, quote=raw_ports,
                                 conditions={"basis": "complete_enumeration"}))
    alt, aline = MU.alt_dp(lines)
    if alt:
        add("usb.usbc_alt_dp", alt, "Interface/Port Details", quote=aline)
    pd = {}
    for l, v in by.items():
        if UP_PD.match(l) and (ws := re.findall(r"(\d{2,3})\s*W\b", txt(v))):
            for x in ws:
                pd.setdefault(int(x), l)
    if not pd:
        for l in lines:
            if MP.classify(l) == "input" and (m := re.findall(r"(?:Power Delivery|PD)[^,;)]*?(\d{2,3})\s*W", l, re.I)):
                for x in m:
                    pd.setdefault(int(x), "Interface/Port Details")
    if len(pd) == 1:
        (wv, lab), = pd.items()
        add("usb.usbc_pd_w", wv, lab, quote=(f"{lab}: {get(lab)}" if lab in by and lab != "Interface/Port Details" else raw_ports))
    if any(re.fullmatch(r"(?i)KVM Switch", x) for x in items(by.get("Built-in Devices"))):
        add("usb.kvm", True, "Built-in Devices")
    elif (k := get("KVM Switch")) and re.fullmatch(r"(?i)yes", k):
        add("usb.kvm", True, "KVM Switch")
    hd = get("Total Number of HDMI Ports")
    hd_d = [count(l) for l in lines if re.match(r"\s*(?:\d+\s*x?\s*)?HDMI", l, re.I)]
    if hd and hd.isdigit() and (not hd_d or sum(hd_d) == int(hd)):
        add("vin.hdmi_count", int(hd), "Total Number of HDMI Ports")
    dp_d = [count(l) for l in lines if re.match(r"\s*(?:\d+\s*x?\s*)?(?:DisplayPort|DP\b|Mini ?DisplayPort)", l, re.I)
            and not re.search(r"(?i)\bout(put)?\b|daisy|\bMST\b", l)]
    dpn = get("Number of DisplayPorts")
    if lines and dpn and dpn.isdigit() and sum(dp_d) == int(dpn) and not yes("DisplayPort Output"):
        add("vin.dp_count", int(dpn), "Number of DisplayPorts", quote=f"Number of DisplayPorts: {dpn} | {raw_ports}")
    if (hv := get("HDMI Version")) and (m := re.fullmatch(r"\s*(\d\.\d)\s*(?:\((?:FRL|TMDS)\))?\s*", hv)):
        add("vin.hdmi_version", m[1], "HDMI Version")
    if (pm := get("Maximum Power Consumption")) and (m := re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*W\s*", pm)):
        add("pwr.max", C_num(m[1]), "Maximum Power Consumption")
    vs = items(by.get("VESA Mount Standard"))
    if len(vs) == 1 and (m := re.fullmatch(r"\s*(\d{2,3})\s*x\s*(\d{2,3})\s*(?:mm)?\s*", vs[0])) and f"{m[1]}x{m[2]}" in ("75x75", "100x100", "200x100", "200x200", "400x400"):
        add("ergo.vesa", f"{m[1]}x{m[2]}", "VESA Mount Standard")
    pr.fingerprints = {"raw": snap.snapshot, "labels": [f"{g} > {l}" for g, l, _ in rows][:300], "ports": lines[:20]}
    return pr


def C_num(x):
    v = float(x)
    return int(v) if v == int(v) else v


if __name__ == "__main__":
    _run.main(DellMonitors())
