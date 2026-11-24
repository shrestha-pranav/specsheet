#!/usr/bin/env python3
"""LG US monitors adapter v1 (contract ARCHITECTURE 15.5), category monitors.

discover : https://www.lg.com/us/sitemap.xml (1.4 MB, one request) -> /us/monitors/lg-<slug> product pages (category/landing pages
           without the 'lg-' prefix are dropped). robots.txt Allow: / for generic agents; 1 req/s.
fetch    : the SSR product page (~1.8 MB); stored gzip-compressed (.html.gz, ~10x smaller). Embedded data used:
           __NEXT_DATA__ props.pageProps.productData.product {sku = model number e.g. 22MP410-B, modelCode = LG material code,
           productIdentifier = UPC, modelStatus} and .allInfo[].tableData[] = [{term, description, attributeOrder}] spec table.
parse    : pure over the blob. Identifiers mfr_model (sku), gtin (UPC), x_lg_material_code; claims keyed to
           research/monitors/spec-profile.yaml with raw literal (term: description); weights lb->kg are derived (raw kept).
Traps    : 'Screen Size' is the viewable diagonal (21.45") -> gen.viewable_diag; 'Color Depth 16.7M' does not say 8-bit vs 6+FRC (left
           unmapped); 'Response Time (GTG)' basis text is kept in raw ('5ms (GtG at Faster)').
v2 (2026-11-24, preset fill): gen.size_class from 'Screen Size Class (diagonal)' ('22" Class (21.5" diagonal)' -> 22, stated); where only a
           diagonal is printed (that row without 'Class', or 'Screen Size') the class is derived (kind derived, round half up,
           _monports.DERIVATION). usb.usbc_inputs from the Input/Output group, see lg_usbc_inputs().
"""
import gzip, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run
import _monports as MP

ID, VERSION, SOURCE = "lg_us", 2, "lg-us"
CATEGORIES = {"monitors"}
SITEMAP = "https://www.lg.com/us/sitemap.xml"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
LB = 0.45359237


def num(s):
    m = re.search(r"-?\d[\d,]*\.?\d*", s or "")
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    return int(v) if v == int(v) else v


def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


class LgUs:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        urls = sorted(set(re.findall(r"<loc>(https://www\.lg\.com/us/monitors/lg-[^<]+)</loc>", r.text)))
        refs = [Ref(SOURCE, u.rsplit("/", 1)[1], u, {"slug": u.rsplit("/", 1)[1]}) for u in urls]
        return Discovery(refs, True, None, {"monitor_urls": len(refs)})

    def fetch(self, ref, prior, net):
        import time
        r = net.get(ref.url, DELAY)
        now = time.strftime("%FT%TZ", time.gmtime())
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        sha = self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz")
        s = C.Snapshot(sha, ref, 200, now, r.url, {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        html = gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace")
        return parse_html(snap, html)


def parse_html(snap, html):
    pr, obs = ParseResult(), snap.fetched_at
    nd = next_data(html)
    try:
        pd = nd["props"]["pageProps"]["productData"]
        p = pd["product"]
        model = p["sku"].strip()
    except (TypeError, KeyError):
        pr.absences.append({"key": "*", "reason": "no __NEXT_DATA__ productData/sku (not a product page)", "source": "s1"})
        return pr
    pr.sources = [{"id": "s1", "url": snap.ref.url, "label": "LG US product page " + model, "source_id": "lg-us", "tier": "manufacturer",
                   "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "lg", "market": "US", "package_level": "model", "role": "key", "sources": ["s1"]})
    if p.get("modelCode"):
        pr.identifiers.append({"scheme": "x_lg_material_code", "value": p["modelCode"], "value_raw": p["modelCode"], "issuer": "lg", "sources": ["s1"]})
    pi = p.get("productIdentifier") or {}
    if pi.get("type") == "UPC" and re.fullmatch(r"\d{11,14}", pi.get("value") or ""):
        pr.identifiers.append({"scheme": "gtin", "value": pi["value"].zfill(14), "value_raw": pi["value"], "issuer": "GS1", "package_level": "package", "role": "alias", "sources": ["s1"]})
    if p.get("title"):
        pr.aliases.append({"text": p["title"], "kind": "marketing_name", "source": "s1", "observed_at": obs})
    T = {}                                         # term -> description (first wins; terms repeat across groups, e.g. 'Type')
    for g in pd.get("allInfo") or []:
        for row in g.get("tableData") or []:
            T.setdefault(row["term"], str(row["description"]).strip())
    used = set()

    def add(k, v, unit, term, raw=None):
        raw = f"{term}: {raw if raw is not None else T[term]}"
        pr.claims.append(claim(model, k, v, unit, raw, "s1", ADAPTER, "next_data", obs, {"term": term}, raw))
        used.add(term)
    g = T.get
    if (v := g("Native Resolution") or g("Resolution")) and (m := re.search(r"(\d{3,5})\s*x\s*(\d{3,5})", v)):
        t = "Native Resolution" if g("Native Resolution") else "Resolution"
        add("res.native", f"{m[1]}x{m[2]}", None, t); add("res.width_px", int(m[1]), "px", t); add("res.height_px", int(m[2]), "px", t)
    if (v := g("Aspect Ratio")) in ("16:9", "16:10", "3:2", "21:9", "32:9", "4:3"):
        add("res.aspect", v, None, "Aspect Ratio")
    dt = g("Display Type") or ""
    for rx, val in ((r"^nano ips$", "Nano IPS"), (r"^ips black$", "IPS Black"), (r"^ips", "IPS"), (r"^(va|tn)\b", dt.upper()[:2]), (r"^woled$", "WOLED")):
        if re.search(rx, dt, re.I):
            add("panel.technology", val, None, "Display Type"); break
    if (v := g("Screen Size")) and num(v):
        add("gen.viewable_diag", num(v), "in", "Screen Size")
    sc = g("Screen Size Class (diagonal)") or ""
    if (m := re.search(r"(\d{2}(?:\.\d+)?)\s*(?:\"|”|''|-inch|inch)?\s*Class\b", sc, re.I)) or (m := re.fullmatch(r"\s*(\d{2})(?:\.0)?\s*(?:\"|”|inch)\s*(?:Flat|Curved)?\s*", sc, re.I)):
        add("gen.size_class", int(float(m[1])), "in", "Screen Size Class (diagonal)")
    else:
        t = "Screen Size Class (diagonal)" if re.fullmatch(r"\s*\d{2}\.\d+\s*(?:\"|”|inch)\s*(?:Flat|Curved)?\s*", sc, re.I) else "Screen Size"
        if (d := re.search(r"(\d{2}(?:\.\d+)?)\s*(?:\"|”|inch)", g(t) or "")):
            add("gen.size_class", MP.size_class(d[1]), "in", t)
            pr.claims[-1]["kind"] = "derived"
            pr.claims[-1]["locator"]["derivation"] = MP.DERIVATION
    if (v := g("Refresh Rate")) and re.search(r"\d\s*Hz", v):
        add("res.refresh_max", num(v), "Hz", "Refresh Rate")
    if (v := g("Response Time (GTG)")) and num(v) is not None:
        add("motion.gtg_marketed", num(v), "ms", "Response Time (GTG)")
    b = g("Brightness (Typical, Minimum)") or g("Brightness (Typical)") or g("Brightness")
    if b and num(b):
        t = next(k for k in T if T[k] == b and k.startswith("Brightness"))
        add("hdr.sdr_typ", num(b), "nit", t)
    if (v := g("Contrast Ratio")) and (m := re.search(r"(\d[\d,]*):1", v)):
        add("hdr.contrast_static", f"{m[1].replace(',', '')}:1", None, "Contrast Ratio")
    for term, v in T.items():
        if term.startswith("Color Gamut"):
            for k, rx in (("color.srgb", r"sRGB\s*(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%\s*sRGB"), ("color.dci_p3", r"DCI-?P3\s*(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%\s*DCI-?P3")):
                if (m := re.search(rx, v, re.I)):
                    add(k, float(m[1] or m[2]), "%", term)
            break
    if (v := g("Surface Treatment")):
        if re.search(r"anti-?glare|matte|hard coating", v, re.I):
            add("panel.surface", "matte", None, "Surface Treatment")
        elif re.search(r"glossy|glare", v, re.I):
            add("panel.surface", "glossy", None, "Surface Treatment")
    for term, k in (("Power Consumption (Typ.)", "pwr.typical"), ("Power Consumption (Max.)", "pwr.max")):
        if (v := g(term)) and num(v) is not None and re.search(r"\d\s*W", v):
            add(k, num(v), "W", term)
    if (v := g("Type")) and re.search(r"external|internal", v, re.I) and "Power" in v:
        add("pwr.external_adapter", bool(re.search(r"external", v, re.I)), None, "Type")
    if (v := g("Wall Mount Size (mm)")) and (m := re.search(r"(\d+)\s*x\s*(\d+)", v)) and f"{m[1]}x{m[2]}" in ("75x75", "100x100", "200x100", "200x200", "400x400"):
        add("ergo.vesa", f"{m[1]}x{m[2]}", None, "Wall Mount Size (mm)")
    for term, k in (("With Stand Weight", "ergo.weight"), ("Without Stand Weight", "ergo.weight_panel")):
        if (v := g(term)) and (m := re.search(r"([\d.]+)\s*lbs?", v)):
            add(k, round(float(m[1]) * LB, 2), "kg", term)
    if (v := g("Limited Warranty")) and (m := re.search(r"(\d+)\s*Year", v, re.I)):
        add("sup.warranty_years", int(m[1]), "year", "Limited Warranty")
    if (v := g("HDMI")) and num(v) is not None and "HDMI" not in used:
        add("vin.hdmi_count", int(num(v)), None, "HDMI")
    if (v := g("DisplayPort")) and num(v) is not None:
        add("vin.dp_count", int(num(v)), None, "DisplayPort")
    for term, v in T.items():
        if "DisplayHDR" in term + " " + v and (m := re.search(r"DisplayHDR\s*(True Black\s*)?(\d{3,4})", term + " " + v, re.I)):
            add("hdr.vesa_tier", f"DisplayHDR {'True Black ' if m[1] else ''}{m[2]}", None, term, v); break
    blob = " ".join(f"{t} {v}" for t, v in T.items() if re.search(r"sync", t + v, re.I))
    vrr = [n for n, rx in (("FreeSync", r"FreeSync"), ("G-Sync Compatible", r"G-?SYNC")) if re.search(rx, blob, re.I)]
    if not vrr and re.search(r"adaptive.?sync", blob, re.I):
        vrr = ["Adaptive-Sync"]
    if vrr:
        add("res.vrr_types", vrr, None, next(t for t in T if re.search("sync", t + T[t], re.I)), blob[:200])
    adj = [n for n in ("Tilt", "Swivel", "Pivot", "Height") if T.get(n) == "Yes"]
    if any(T.get(n) in ("Yes", "No") for n in ("Tilt", "Swivel", "Pivot", "Height")):
        add("ergo.adjust", [a.lower() for a in adj], None, "Tilt", f"Tilt={T.get('Tilt')} Swivel={T.get('Swivel')} Pivot={T.get('Pivot')} Height={T.get('Height')}")
    for term in T:
        if re.search(r"USB.?C|Type-C", term, re.I) and re.search(r"power|PD", term + T[term], re.I) and (m := re.search(r"(\d{2,3})\s*W", term + " " + T[term])):
            add("usb.usbc_pd_w", float(m[1]), "W", term); break
    io = [(r["term"], str(r["description"]).strip()) for grp in pd.get("allInfo") or [] if re.search(r"input|output|connect", grp.get("subtitle") or "", re.I)
          for r in grp.get("tableData") or []]
    rest = [(r["term"], str(r["description"]).strip()) for grp in pd.get("allInfo") or [] if not re.search(r"input|output|connect", grp.get("subtitle") or "", re.I)
            for r in grp.get("tableData") or []]
    n, zero, rawio = lg_usbc_inputs(io, rest)
    if n is not None:
        pr.claims.append(claim(model, "usb.usbc_inputs", n, None, rawio, "s1", ADAPTER, "next_data", obs, {"term": "Input/Output"}, rawio,
                               conditions={"basis": "complete_enumeration"} if zero else None))
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "status": p.get("modelStatus"), "terms": len(T),
                       "unmapped": {k: v for k, v in T.items() if k not in used}}
    return pr


NOT = re.compile(r"^\s*(no|none|-|n/a)\s*$", re.I)
LG_C = re.compile(r"USB[- ]?C|Type[- ]?C|Thunderbolt|USB ?4", re.I)


def lg_usbc_inputs(io, rest):
    """LG Input/Output group rows -> (count, complete_zero, raw) or (None, False, raw).
    LG prints one row per port type, often redundantly ('USB Type-C: 1', 'USB-C: Yes', 'USB-C (Power Delivery): 65 W', 'USB Up-stream: YES (USB-C, 1ea)').
    Count: an explicit upstream count ('Yes (1 Up / 2 Down)', 'USB Up-stream: YES (USB-C, 1ea)', 'via Thunderbolt/1ea, via USB-C/1ea'), else the
    USB-C row's own count minus USB-C ports the Down-stream row names. A count is written only with video evidence on the page (DP Alternate
    Mode: Yes, a USB-C/Thunderbolt power-delivery or max-resolution row, Thunderbolt); 'DP Alternate Mode: No' with no Thunderbolt = 0.
    0 from absence only as a complete enumeration: the group names a video input (HDMI/DisplayPort/D-Sub/DVI) and no row anywhere on the
    page names USB-C / Type-C / Thunderbolt except as 'No'."""
    raw = "Input/Output: " + " | ".join(f"{t}: {v}" for t, v in io)
    if not io:
        return None, False, raw
    c_rows = [(t, v) for t, v in io + rest if LG_C.search(f"{t} {v}") and not NOT.match(v)]
    if not c_rows:
        if any(re.search(r"HDMI|Display ?Port|D-Sub|DVI|\bDP\b", t, re.I) and not NOT.match(v) for t, v in io):
            return 0, True, raw
        return None, False, raw
    T = dict(reversed(io))
    def cnt(v):
        m = re.search(r"(\d+)\s*(?:ea|x)\b|x\s*(\d+)\b|\((\d+)\)|^\s*(\d+)\s*$", v, re.I)
        return int(next(x for x in m.groups() if x)) if m else None
    up = None
    for t, v in io:
        if re.search(r"Type-?C|USB-?C", t) and (m := re.search(r"(\d+)\s*Up\b", v, re.I)):
            up = int(m[1])
    for t, v in io:
        if re.search(r"USB\s*Up", t, re.I) and LG_C.search(v):
            parts = re.findall(r"(?:thunderbolt|usb-?c)[^,/)]*?/?\s*(\d+)\s*ea|(\d+)\s*ea[^,)]*?(?:usb-?c|thunderbolt)|usb-?c\s*,\s*(\d+)\s*ea", v, re.I)
            if parts:
                up = sum(int(next(x for x in p if x)) for p in parts)
    tb = [(t, v) for t, v in io if re.search(r"thunderbolt", t, re.I) and not re.search(r"cable|power", t, re.I)]
    video = bool(tb) or any((re.search(r"DP Alt", t, re.I) and re.match(r"(?i)\s*yes", v)) or re.search(r"\(Power Delivery\)|Max\. Resolution", t, re.I)
                            or re.search(r"DP Alt|Alt\.? Mode", v, re.I) for t, v in c_rows)
    alt_no = any(re.search(r"DP Alt", t, re.I) and NOT.match(v) for t, v in io)
    if alt_no and not tb and not video:
        return 0, False, raw                               # the maker states the USB-C port carries no DisplayPort
    if not video:
        return None, False, raw
    if up is None:
        tot = [cnt(v) for t, v in io if re.fullmatch(r"USB Type-?C|USB-?C", t.strip(), re.I)]
        tot = [x for x in tot if x is not None]
        if not tot or len(set(tot)) != 1:
            return None, False, raw
        down = 0
        for t, v in io:
            if re.search(r"down", t, re.I) and (m := re.search(r"USB-?C[^0-9]{0,4}(\d+)\s*ea", v, re.I)):
                down += int(m[1])
        up = tot[0] - down
    return (up, False, raw) if up >= 1 else (None, False, raw)


if __name__ == "__main__":
    _run.main(LgUs())
