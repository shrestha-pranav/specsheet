#!/usr/bin/env python3
"""ASUS (US) monitors adapter v1 (contract ARCHITECTURE 15.5), category monitors.

discover : odinapi SeriesFilterResult ProductLevel1Code=displays-desktops&ProductLevel2Code=monitors, PageSize=300, pages 1-2
           (TotalCount 347 = 260 www.asus.com + 87 rog.asus.com). Accessories/non-monitor rows are kept as refs but parse() emits an
           absence when the page has no panel spec. ROG rows carry SalesModelName (XG27ACNS) + PartNo (orderable 90LM0E90-B013B1).
fetch    : www.asus.com -> <ProductURL>techspec/  (SSR: rowTable sections; cell = <p>Label : value<BR>...; one column per model code)
           rog.asus.com -> <ProductURL>spec/      (ProductSpecSingle h2 + descriptionItem/descriptionItemValue spans; JSON-LD ProductGroup
                                                   hasVariant[].sku = per-colour/region orderable part numbers)
           Stored gzip (.html.gz).
parse    : pure; identifiers mfr_model (page model code), mfr_sku (ROG PartNo / variant sku), claims with raw literal keyed to
           research/monitors/spec-profile.yaml; locator.model_code; unmapped sections in fingerprints.
Traps    : 'Response Time 1ms MPRT' is NOT GtG (left unmapped unless the literal says GTG); 'Refresh Rate (Max)' may include OC;
           'HDR Support: HDR10' is a marketing label, DisplayHDR tier only when the literal names it.
v2 (2026-11-24, preset fill): gen.size_class derived from 'Panel Size (inch)' (kind derived, round half up, _monports.DERIVATION; ASUS
           prints no size class). usb.usbc_inputs counted from the bare I/O port list (the maker's full input list): USB-C/Thunderbolt
           lines naming DP Alt Mode / Thunderbolt; 0 only as a complete enumeration (condition basis=complete_enumeration).
v3 (2026-11-25, A2-keys): usb.usbc_alt_dp from the one USB-C video-input I/O line that names DP (_monusb.alt_dp, raw = that line);
           usb.kvm from 'KVM Switch : Yes/No' or a '(For KVM Switch)' port row (_monusb.kvm_asus). Everything else byte-identical to v2.
v4 (2026-11-25, A2-mon r5): res.refresh_native only where the maker's own copy on this single-model page says 'native N Hz' explicitly
           ('Overclock to 260Hz (native 240Hz)', 'Native 144Hz refresh rate'); one distinct N on the page, N <= the stated Refresh Rate
           (Max). 'Refresh Rate (Max)' alone is up-to wording and never becomes native; multi-model pages write nothing.
v5 (2026-11-26, A2-ref r10): (1) the ROG label spelling 'Refresh Rate (max)' is read like 'Refresh Rate (Max)' (it was skipped, so those
           pages had no refresh_max). (2) fetch also stores the model's overview page (hints.pdp, the ProductURL without techspec/ or spec/)
           under ref '<KEY>#overview' (same store; discovery never lists it, so the importer never parses it as a model). (3)
           res.refresh_native = the 'Refresh Rate (Max)' figure when it is a plain 'N Hz' cell and the maker states no overclock for the
           model (plain_native): single-model page; the overview page is stored (none = nothing) and neither it nor the techspec page has
           an overclock word or 'OC' anywhere outside ASUS site boilerplate (OC_BOILER: motherboard / overclockers / 'fully overclocked GPU
           and CPU'); techspec title and spec rows carry no 'Dual Mode'/'Triple Mode'; no Hz figure above N in the spec rows (Digital Signal
           Frequency included, Analog excluded). Why both pages: the techspec page omits the OC note (TUF VG279QM techspec: 'Refresh Rate
           (Max) : 280Hz', no OC anywhere; its overview: 'Overclockable 280Hz'). Same meaning as aoc_monitors@1 'Max Refresh rate'. The v4
           explicit 'native N Hz' rule runs first and wins. Parse caches key on the techspec snapshot: after refetching overviews, import
           with --reparse. Every other claim byte-identical to v4.
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run
import _monports as MP
import _monusb as MU

ID, VERSION, SOURCE = "asus_monitors", 5, "asus-us-monitors"
CATEGORIES = {"monitors"}
API = ("https://odinapi.asus.com/recent-data/apiv2/SeriesFilterResult?SystemCode=asus&WebsiteCode=us&ProductLevel1Code=displays-desktops"
       "&ProductLevel2Code=monitors&PageSize=300&PageIndex={}&CategoryName=&SeparateType=1&LocalFlag=0")
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
LB = 0.45359237
T_ENUM = {"ips": "IPS", "fast ips": "Fast IPS", "ips black": "IPS Black", "fast ips black": "Fast IPS Black", "nano ips": "Nano IPS", "va": "VA",
          "fast va": "Fast VA", "tn": "TN", "wled": None, "qd-oled": "QD-OLED", "woled": "WOLED"}
NATIVE = re.compile(r"(?i)\bnative\s+(\d{2,3})\s?Hz\b")
OC_WORD = re.compile(r"(?i)over-?clock|\bO/?C\b")
OC_BOILER = re.compile(r"(?i)motherboards?\b|overclockers\b|overclocked GPU and CPU")    # ASUS site-wide footer / mega-menu copy
MULTI = re.compile(r"(?i)dual[- ]mode|triple[- ]mode")
OVERVIEW = "#overview"
HZ = re.compile(r"(?i)(?<![\d.])(\d{2,3})\s?Hz\b")
TXT = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def num(s):
    m = re.search(r"-?\d[\d,]*\.?\d*", s or "")
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    return int(v) if v == int(v) else v


def sections_www(t):
    """-> ({section: [cell lines]}, model codes). cell = list of 'Label : value' / bare lines."""
    secs, codes = {}, []
    for m in re.finditer(r'<div class="rowTableTitle">([^<]*)</div></div><div class="[^"]*rowTableItemViewBox[^"]*">(.*?)(?=<div class="[^"]*__rowTable___|$)', t, re.S):
        title = TXT(m.group(1))
        cells = []
        for blk in re.split(r'__rowTableItems___[^"]*"[^>]*>', m.group(2))[1:]:
            blk = re.split(r"<!--\]-->", blk)[0]
            lines = [TXT(x) for x in re.split(r"<br\s*/?>|</p>", blk, flags=re.I)]
            cells.append([l for l in lines if l])
        secs[title] = cells
    mm = re.search(r">Model</div>(.*?)(?=__rowTable___|$)", t, re.S)
    if mm:
        for c in re.findall(r">\s*([A-Z][A-Z0-9]{3,}[A-Z0-9-]*)\s*<", mm.group(1)):
            if c not in codes:
                codes.append(c)
    return secs, codes


def sections_rog(t):
    secs = {}
    for m in re.finditer(r'<h2 id="spec[^"]*" class="ProductSpecSingle__productSpecItemTitle[^"]*">([^<]*)</h2>(.*?)(?=<h2 id="spec|$)', t, re.S):
        lines = []
        for it in re.findall(r'<div class="ProductSpecSingle__productSpecListItem[^"]*">(.*?)</div>(?=<div class="ProductSpecSingle__productSpecListItem|</div>)', m.group(2), re.S):
            lab = re.search(r'descriptionItem__[^"]*"[^>]*>(.*?)</span>', it, re.S)
            val = re.search(r'descriptionItemValue__[^"]*"[^>]*>(.*?)</span>', it, re.S)
            lines.append((TXT(lab.group(1)) if lab else "") + (" " + TXT(val.group(1)) if val else ""))
        secs[TXT(m.group(1))] = [[l.strip() for l in lines if l.strip()]]
    return secs


def kv(lines):
    d, bare = {}, []
    for l in lines:
        m = re.match(r"^(.*?)\s:\s*(.*)$", l)
        if m:
            d.setdefault(m.group(1).strip(), m.group(2).strip())
        else:
            bare.append(l)
    return d, bare


def oc_stated(page):
    """v5: True when the page names an overclock anywhere outside the site boilerplate (each hit judged in a 60-char window)."""
    page = html.unescape(page)
    for m in OC_WORD.finditer(page):
        if not OC_BOILER.search(page[max(0, m.start() - 60): m.end() + 60]):
            return True
    return False


def plain_native(page, overview, F, title, ncodes):
    """v5: the 'Refresh Rate (Max)' figure as native when neither the techspec nor the overview page states an overclock
    -> (N, quote) or (None, reason)."""
    rr = F.get("Refresh Rate (Max)")
    if ncodes != 1 or not rr or not (m := re.fullmatch(r"\s*(\d{2,3})\s?Hz\s*", rr)):
        return None, "shape"
    if overview is None:
        return None, "no overview page stored"
    n = int(m[1])
    if oc_stated(page) or oc_stated(overview):
        return None, "overclock stated"
    spec = " ".join([title or ""] + [f"{k} {v}" for k, v in F.items() if not k.startswith("Analog")])
    if MULTI.search(spec) or "Dual Mode" in F or "Triple Mode" in F:
        return None, "multi-mode"
    if any(int(x) > n for x in HZ.findall(spec)):
        return None, "higher Hz in spec"
    dsf = F.get("Digital Signal Frequency")
    return n, f"Refresh Rate (Max): {rr}" + (f" | Digital Signal Frequency: {dsf}" if dsf else "") + " | no overclock stated on the spec or overview page"


class AsusMonitors:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        rows, total, p = [], None, 1
        while True:
            r = net.get(API.format(p), DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return Discovery([], False, f"list api page {p}: {getattr(r, 'status_code', r)}", checkpoint or {})
            res = r.json()["Result"]
            total = res["TotalCount"]
            rows += res["ProductList"]
            if len(rows) >= total or not res["ProductList"]:
                break
            p += 1
        refs, seen = [], set()
        for x in rows:
            u = x["ProductURL"]
            if u in seen or "/monitors/" not in u:
                continue
            seen.add(u)
            rog = "rog.asus.com" in u
            key = (x.get("SalesModelName") or x.get("PDWebPath") or u.rstrip("/").rsplit("/", 1)[1]).upper()
            refs.append(Ref(SOURCE, key, u + ("spec/" if rog else "techspec/"),
                            {"title": TXT(x["Name"]), "series": x.get("Level3Path"), "size_class": x.get("CategoryName"), "rog": rog,
                             "part_no": x.get("PartNo") or None, "sales_model": x.get("SalesModelName") or None, "pdp": u}))
        return Discovery(refs, total == len(rows) or len(refs) > 0, None, {"total": total, "listed": len(rows), "monitor_refs": len(refs)})

    def fetch(self, ref, prior, net):
        r = net.get(ref.url, DELAY)
        now = time.strftime("%FT%TZ", time.gmtime())
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz"); return s
        sha = self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz")
        s = C.Snapshot(sha, ref, 200, now, r.url, {})
        self.store.append(s, ADAPTER, ".html.gz")
        self.fetch_overview(ref, net)      # v5
        return s

    def fetch_overview(self, ref, net):
        """v5: the model's overview page (hints.pdp) -> stored under ref '<KEY>#overview' (gzip). Same politeness as fetch()."""
        u = (ref.hints or {}).get("pdp")
        if not u:
            return None
        oref = Ref(SOURCE, ref.key + OVERVIEW, u, {})
        r = net.get(u, DELAY)
        now = time.strftime("%FT%TZ", time.gmtime())
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", oref, st or "breaker", now, u, {})
        else:
            s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), oref, 200, now, r.url, {})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        t = gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace")
        return parse_html(snap, t, overview_of(blobs, snap.ref.key))


def overview_of(blobs, key):
    """v5: (text, snapshot id, url) of the latest stored 200 overview page of this ref, or None (fail closed)."""
    rec = blobs.latest().get(key + OVERVIEW) if hasattr(blobs, "latest") else None
    if not rec:
        return None
    return gzip.decompress(blobs.read_rec(rec)).decode("utf-8", "replace"), rec["snapshot"], rec["url"]


def parse_html(snap, t, overview=None):
    pr, obs, h = ParseResult(), snap.fetched_at, snap.ref.hints
    rog = bool(h.get("rog")) or "rog.asus.com" in snap.ref.url
    if rog:
        secs = sections_rog(t)
        codes = [h.get("sales_model") or snap.ref.key]
        skus = []
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
        if m:
            try:
                skus = [v["sku"] for v in json.loads(m.group(1)).get("hasVariant", []) if v.get("sku")]
            except ValueError:
                pass
    else:
        secs, codes = sections_www(t)
        skus = []
        if not codes:   # no 'Model' row: take a model-looking token from the title, never the long URL slug
            tt = [x.strip(",") for x in (h.get("title") or "").split() if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+-]{2,23}", x.strip(","))
                  and re.search(r"\d", x) and re.search(r"[A-Za-z]", x)]
            codes = [tt[-1].upper()] if tt else [re.sub(r"[^A-Z0-9]+", "-", snap.ref.key.upper()).strip("-")[:32]]
    pr.sources = [{"id": "s1", "url": snap.ref.url, "label": "ASUS US spec page " + snap.ref.key, "source_id": "asus-us-monitors", "tier": "manufacturer",
                   "retrieved_at": obs, "snapshot": snap.snapshot}]
    if not any("Panel Type" in kv(c)[0] or "Panel Size (inch)" in kv(c)[0] for cells in secs.values() for c in cells):
        pr.absences.append({"key": "*", "reason": "no panel spec table on page (accessory or empty spec)", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "sections": list(secs)}
        return pr
    if h.get("title"):
        pr.aliases.append({"text": h["title"], "kind": "marketing_name", "source": "s1", "observed_at": obs})
    for c in codes:
        pr.identifiers.append({"scheme": "mfr_model", "value": c, "value_raw": c, "issuer": "asus", "market": "US", "package_level": "model", "role": "key", "sources": ["s1"]})
    for sku in dict.fromkeys(([h["part_no"]] if h.get("part_no") else []) + skus):
        pr.identifiers.append({"scheme": "mfr_sku", "value": sku, "value_raw": sku, "issuer": "asus", "market": "US", "package_level": "package", "role": "alias", "sources": ["s1"]})
    unmapped = {}
    ncols = max((len(c) for c in secs.values()), default=1)
    for ci, code in enumerate(codes):
        F, bare = {}, []
        for sec, cells in secs.items():
            cell = cells[ci] if len(cells) == len(codes) and len(codes) > 1 else cells[0] if cells else []
            d, b = kv(cell)
            for k, v in d.items():
                F.setdefault("Refresh Rate (Max)" if k == "Refresh Rate (max)" else k, v)      # v5: ROG spelling
            if sec.lower().startswith("i/o"):
                bare += [l for l in cell if " : " not in l]
        used = set()

        def add(k, v, unit, label, raw=None):
            raw = f"{label}: {raw if raw is not None else F.get(label, '')}"
            pr.claims.append(claim(code, k, v, unit, raw, "s1", ADAPTER, "spec_html", obs, {"label": label, "model_code": code}, raw))
            used.add(label)
        g = F.get
        if (v := g("Panel Size (inch)")) and num(v):
            add("gen.viewable_diag", num(v), "in", "Panel Size (inch)")   # ASUS states panel/viewable diagonal; marketed class may differ
            pr.claims.append(claim(code, "gen.size_class", MP.size_class(num(v)), "in", f"Panel Size (inch): {v}", "s1", ADAPTER, "spec_html", obs,
                                   {"label": "Panel Size (inch)", "model_code": code, "derivation": MP.DERIVATION}, f"Panel Size (inch): {v}"))
            pr.claims[-1]["kind"] = "derived"
        if (v := g("Aspect Ratio")) in ("16:9", "16:10", "3:2", "21:9", "32:9", "4:3"):
            add("res.aspect", v, None, "Aspect Ratio")
        if (v := g("Panel Type")) is not None and T_ENUM.get(v.lower().strip()):
            add("panel.technology", T_ENUM[v.lower().strip()], None, "Panel Type")
        if (v := g("Resolution")) and (m := re.search(r"(\d{3,5})\s*[x×]\s*(\d{3,5})", v)):
            add("res.native", f"{m[1]}x{m[2]}", None, "Resolution"); add("res.width_px", int(m[1]), "px", "Resolution"); add("res.height_px", int(m[2]), "px", "Resolution")
        if (v := g("Display Surface")):
            add("panel.surface", "matte" if re.search(r"anti-?glare|matte", v, re.I) else "glossy" if re.search(r"glossy", v, re.I) else "unspecified", None, "Display Surface")
        for lab, k in (("Color Space (sRGB)", "color.srgb"), ("Color Space (DCI-P3)", "color.dci_p3")):
            if (v := g(lab)) and re.search(r"\d\s*%", v):
                add(k, num(v), "%", lab)
        if (v := g("Brightness (Typ.)")) and num(v):
            add("hdr.sdr_typ", num(v), "nit", "Brightness (Typ.)")
        if (v := g("Brightness (HDR, Peak)")) and num(v):
            add("hdr.peak_marketed", num(v), "nit", "Brightness (HDR, Peak)")
        if (v := g("Contrast Ratio (Typ.)")) and (m := re.search(r"(\d[\d,]*):1", v)):
            add("hdr.contrast_static", f"{m[1].replace(',', '')}:1", None, "Contrast Ratio (Typ.)")
        if (v := g("Response Time")) and re.search(r"gtg", v, re.I) and (m := re.search(r"([\d.]+)\s*ms\s*\(?\s*GTG", v, re.I)):
            add("motion.gtg_marketed", float(m[1]), "ms", "Response Time")
        if (v := g("Refresh Rate (Max)")) and num(v):
            add("res.refresh_max", num(v), "Hz", "Refresh Rate (Max)")
            nat = {}
            for m in NATIVE.finditer(t):
                nat.setdefault(int(m[1]), TXT(t[max(0, m.start() - 90): m.end() + 30].replace("\\u003C", "<").replace("\\u003E", ">").replace("\\n", " ")).split('"')[-1].strip())
            if len(codes) == 1 and len(nat) == 1 and next(iter(nat)) <= num(v):
                (n, q), = nat.items()
                pr.claims.append(claim(code, "res.refresh_native", n, "Hz", q, "s1", ADAPTER, "spec_html", obs,
                                       {"label": "maker copy 'native N Hz'", "model_code": code}, q))      # v4
            elif (pn := plain_native(t, overview[0] if overview else None, F, h.get("title"), len(codes)))[0]:
                pr.claims.append(claim(code, "res.refresh_native", pn[0], "Hz", pn[1], "s1", ADAPTER, "spec_html", obs,
                                       {"label": "Refresh Rate (Max)", "model_code": code, "rule": "no overclock stated on the spec or overview page",
                                        "overview_url": overview[2], "overview_snapshot": overview[1]}, pn[1]))   # v5
        hd = g("HDR (High Dynamic Range) Support") or g("HDR Support") or ""
        if (m := re.search(r"DisplayHDR\s*(True Black\s*)?(\d{3,4})", hd, re.I)):
            add("hdr.vesa_tier", f"DisplayHDR {'True Black ' if m[1] else ''}{m[2]}", None, "HDR (High Dynamic Range) Support" if g("HDR (High Dynamic Range) Support") else "HDR Support")
        elif hd and hd.lower() not in ("no", "none"):
            add("hdr.marketed_label", hd[:80], None, "HDR (High Dynamic Range) Support" if g("HDR (High Dynamic Range) Support") else "HDR Support")
        vr = g("VRR Technology") or ""
        vrr = [n for n, rx in (("FreeSync", r"FreeSync"), ("G-Sync Compatible", r"G-?SYNC"), ("Adaptive-Sync", r"Adaptive.?Sync")) if re.search(rx, vr, re.I)]
        if vrr:
            add("res.vrr_types", vrr, None, "VRR Technology")
        if (v := g("VESA Wall Mounting")) and (m := re.search(r"(\d+)\s*x\s*(\d+)", v)) and f"{m[1]}x{m[2]}" in ("75x75", "100x100", "200x100", "200x200", "400x400"):
            add("ergo.vesa", f"{m[1]}x{m[2]}", None, "VESA Wall Mounting")
        for lab, k in (("Net Weight", "ergo.weight"), ("Net Weight without Stand", "ergo.weight_panel")):
            if (v := g(lab)) and (m := re.search(r"([\d.]+)\s*kg", v)):
                add(k, float(m[1]), "kg", lab)
        if (v := g("Power Consumption")) and re.search(r"\d\s*W", v):
            add("pwr.typical", num(v), "W", "Power Consumption")
        adj = [n for n in ("Tilt", "Swivel", "Pivot", "Height Adjustment") if (g(n) or "").lower().startswith("yes")]
        if any(g(n) for n in ("Tilt", "Swivel", "Pivot", "Height Adjustment")):
            add("ergo.adjust", [a.split()[0].lower() for a in adj], None, "Tilt", "; ".join(f"{n}={g(n)}" for n in ("Tilt", "Swivel", "Pivot", "Height Adjustment") if g(n)))
        if bare:
            pt = " | ".join(bare)
            pr.claims.append(claim(code, "vin.ports", bare, None, pt, "s1", ADAPTER, "spec_html", obs, {"label": "I/O Ports", "model_code": code}, pt))
            def cnt(rx):
                n = 0
                for l in bare:
                    if re.search(rx, l, re.I):
                        m = re.search(r"x\s*(\d+)", l)
                        n += int(m[1]) if m else 1
                return n
            pr.claims.append(claim(code, "vin.hdmi_count", cnt(r"^HDMI"), None, pt, "s1", ADAPTER, "spec_html", obs, {"label": "I/O Ports", "model_code": code}, pt))
            pr.claims.append(claim(code, "vin.dp_count", cnt(r"^Display ?Port|^DP\b"), None, pt, "s1", ADAPTER, "spec_html", obs, {"label": "I/O Ports", "model_code": code}, pt))
            other_c = [f"{k} : {v}" for k, v in F.items() if MP.CPORT.search(f"{k} {v}") and not re.search(r"hub|power delivery", k, re.I)]
            n, zero = MP.count_inputs(bare)
            if zero and other_c:            # USB-C named elsewhere on the page (accessory cable, a 'USB-C' row): the list is not provably complete
                n, zero = None, False
            if n is not None:
                pr.claims.append(claim(code, "usb.usbc_inputs", n, None, f"I/O Ports: {pt}", "s1", ADAPTER, "spec_html", obs, {"label": "I/O Ports", "model_code": code},
                                       pt, conditions={"basis": "complete_enumeration"} if zero else None))
            v, line = MU.alt_dp(bare)
            if v:
                pr.claims.append(claim(code, "usb.usbc_alt_dp", v, None, f"I/O Ports: {line}", "s1", ADAPTER, "spec_html", obs, {"label": "I/O Ports", "model_code": code}, line))
            pdl = next((f"{k}: {v}" for k, v in F.items() if re.search(r"Power Delivery|\bPD\b", k) and re.search(r"\d\s*W", v)), None)
            if pdl and (m := re.search(r"(\d{2,3})\s*W", pdl)):
                pr.claims.append(claim(code, "usb.usbc_pd_w", float(m[1]), "W", pdl, "s1", ADAPTER, "spec_html", obs, {"label": pdl.split(":")[0], "model_code": code}, pdl))
                used.add(pdl.split(":")[0])
            elif (m := re.search(r"USB[^|]*?(?:PD|Power Delivery)[^|\d]{0,12}(\d{2,3})\s*W", pt, re.I)):
                pr.claims.append(claim(code, "usb.usbc_pd_w", float(m[1]), "W", pt, "s1", ADAPTER, "spec_html", obs, {"label": "I/O Ports", "model_code": code}, pt))
        kv_, kraw = MU.kvm_asus(F)
        if kv_ is not None:
            pr.claims.append(claim(code, "usb.kvm", kv_, None, kraw, "s1", ADAPTER, "spec_html", obs, {"label": kraw.split(":")[0], "model_code": code}, kraw))
        unmapped[code] = {k: v for k, v in F.items() if k not in used}
    pr.fingerprints = {"raw": snap.snapshot, "overview": overview[1] if overview else None, "rog": rog, "models": codes, "columns": ncols, "sections": list(secs), "unmapped": unmapped}
    return pr


if __name__ == "__main__":
    _run.main(AsusMonitors())
