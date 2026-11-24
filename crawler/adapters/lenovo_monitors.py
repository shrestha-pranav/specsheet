#!/usr/bin/env python3
"""Lenovo PSREF monitors adapter v2 (contract ARCHITECTURE 15.5), category monitors. Reuses the laptop adapter's transport.

PSREF 'Monitors' classification (ThinkVision + Lenovo/Legion lines, non-withdrawn, no ThinkCentre Tiny-in-One / LFD signage).
discover : /api/ph/ProductCategoryTree (same anonymous-JWT API as lenovo_psref.py; see that module's docstring)
fetch    : per ProductKey: GetInfoByKey + LoadSpecData (product-level spec tree) + ShowModel rows (per-MTM table) -> one gz blob
parse    : pure. Entity = product key (a model family, e.g. Legion_27_10_Monitor); identifiers mfr_model (key), mtm per row
           (US = suffix 'US'), gtin from EAN/UPC. Claims keyed to research/monitors/spec-profile.yaml with raw literal kept;
           a value is proposed only when the literal maps unambiguously. Everything else -> fingerprints.unmapped.
Traps recorded: 'Color Depth: 8-bit (6-bit+FRC)' is claimed as 6-bit+FRC (the parenthetical is the real panel); the single
'Refresh Rate' is a max (native vs overclock not stated); 'Brightness' typ/min basis not stated.
v2 (2026-11-24): usb.usbc_pd_w read per port line, upstream USB-C/TB/USB4 only; 'up to 90W PD' (number before PD) and 'USB PD 3.1 up to 140W' now parse.
v3 (2026-11-24, preset fill): usb.usbc_inputs from every '<side> Ports' list of the spec tree (Rear/Side/Left/Right/Front/Top/Bottom):
  USB-C/TB/USB4 lines that name DP Alt Mode / DisplayPort / Thunderbolt and are not downstream/out/data-only; a USB-C line of unknown role
  writes nothing; 0 only as a complete enumeration (condition basis=complete_enumeration, every port line kept as raw).
"""
import gzip, html, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _run
import lenovo_psref as LP
import _monports as MP

ID, VERSION, SOURCE = "lenovo_monitors", 3, "lenovo-psref-monitors"
ADAPTER = f"{ID}@{VERSION}"
SKIP = re.compile(r"LFD|Tiny|TIO|Collaboration", re.I)
PANEL = [(r"in-plane|\bIPS\b", "IPS"), (r"vertical alignment|\bVA\b", "VA"), (r"twisted|\bTN\b", "TN"), (r"QD-?OLED", "QD-OLED")]


def num(s):
    m = re.search(r"-?\d[\d,]*\.?\d*", s or "")
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    return int(v) if v == int(v) else v


UPSTREAM_PORT = re.compile(r"USB-?C|Thunderbolt|USB4", re.I)
PD_W = [re.compile(r"(\d{2,3})\s*W\s*(?:USB\s*)?(?:PD|Power Delivery)\b", re.I),               # 'up to 90W PD' (v2: number before PD)
        re.compile(r"(?:Power Delivery|\bPD)(?:\s*\d\.\d)?[^|\d]{0,25}?(\d{2,3})\s*W", re.I),     # 'USB PD 3.1 up to 140W' / 'PD 65W'
        re.compile(r"up to\s*(\d{2,3})\s*W\b", re.I)]                                           # 'Alt Mode, up to 75W' on an upstream USB-C port


def upstream_pd_w(seg):
    """Power a USB-C/Thunderbolt upstream port line states it delivers, or None. Downstream (charging-out) ports never count."""
    s = html.unescape(seg)
    if not UPSTREAM_PORT.search(s) or not re.search(r"upstream", s, re.I):
        return None
    if re.search(r"downstream", s, re.I) and not re.search(r"one USB upstream", s, re.I):
        return None
    for rx in PD_W:
        if (m := rx.search(s)):
            return float(m[1])
    return None


def flat_features(plat):
    """LoadSpecData -> {feature name: [value strings]} (product level; Lenovo keeps option labels such as 'Lowest Position' as items)."""
    out = {}
    try:
        gs = json.loads(plat["GeneralSpecData"][0]["GeneralSpecJson"])["data"]["SpecData"]
    except (TypeError, KeyError, IndexError, ValueError):
        return out
    for l1 in gs:
        for l2 in l1["L2"]:
            for f in l2["Features"]:
                vals = [html.unescape(it["AttV"]).strip() for v in f["FVs"] for g in v["FVGs"] for it in g["FVGItem"] if it.get("AttV")]
                if vals:
                    out[f["FName"]] = vals
    return out


def after(vals, label):
    """value following an option label ('Monitor with stand' -> next item)."""
    for i, v in enumerate(vals):
        if v.lower().startswith(label.lower()) and i + 1 < len(vals):
            return vals[i + 1]


class LenovoMonitors(LP.LenovoPsref):
    id, version, source_id, categories = ID, VERSION, SOURCE, {"monitors"}

    def discover(self, checkpoint, net):
        r = net.get(LP.BASE + "/api/ph/ProductCategoryTree", LP.DELAY, headers=LP.HDR)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"tree http {getattr(r, 'status_code', r)}", checkpoint or {})
        refs, total, wd = [], 0, 0
        for cl in r.json()["data"]["ProductClassificationList"]:
            if cl["ClassificationName"] != "Monitors":
                continue
            for pl in cl["ProductLineList"]:
                for se in pl["ProductSeriesList"]:
                    for p in se["ProductList"]:
                        total += 1
                        if p["Withdraw"]:
                            wd += 1; continue
                        if SKIP.search(p["ProductName"]) or SKIP.search(pl["ProductLine"]):
                            continue
                        refs.append(C.Ref(SOURCE, p["ProductKey"], f"{LP.BASE}/product/{p['ProductID']}",
                                          {"title": p["ProductName"], "line": pl["ProductLine"], "series": se["SeriesName"], "product_id": p["ProductID"]}))
        return C.Discovery(refs, True, None, {"monitors_total": total, "withdrawn_skipped": wd})

    def parse(self, snap, blobs, profile):
        b = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        obs, key = snap.fetched_at, b["product_key"]
        pr = C.ParseResult(sources=[{"id": "s1", "url": snap.ref.url, "label": "Lenovo PSREF " + key, "source_id": "lenovo-psref",
                                     "tier": "manufacturer", "retrieved_at": obs, "snapshot": snap.snapshot}])
        name = (b.get("info") or {}).get("ProductName") or snap.ref.hints.get("title", key)
        pr.aliases.append({"text": name, "kind": "marketing_name", "source": "s1", "observed_at": obs})
        pr.identifiers.append({"scheme": "mfr_model", "value": key, "value_raw": key, "issuer": "lenovo", "market": None,
                               "package_level": "model", "role": "key", "sources": ["s1"]})
        rows = b.get("models") or []
        for m in rows:
            mtm = m.get("Model", "")
            if not re.fullmatch(r"[0-9A-Z]{10}", mtm):
                continue
            pr.identifiers.append({"scheme": "mtm", "value": mtm, "value_raw": mtm, "issuer": "lenovo", "market": "US" if mtm.endswith("US") else None,
                                   "package_level": "package", "role": "key", "sources": ["s1"]})
            seen = set()
            for tok in re.split(r"\s*/\s*", m.get("EAN / UPC / JAN", "") or ""):   # '0199273182657 / 199273182657 / None' = EAN-13 / UPC-A / JAN
                d = re.sub(r"\D", "", tok)
                if 12 <= len(d) <= 14 and d.zfill(14) not in seen:
                    seen.add(d.zfill(14))
                    pr.identifiers.append({"scheme": "gtin", "value": d.zfill(14), "value_raw": tok, "issuer": "GS1",
                                           "package_level": "package", "role": "alias", "sources": ["s1"]})
        F = flat_features(b.get("platform_spec"))
        basis = "platform_spec"
        if not F and rows:                 # old products: no spec tree, use the first row's columns (same labels)
            F = {k: [v] for k, v in rows[0].items() if isinstance(v, str) and v.strip() and v.strip() != "None"}
            basis = "first_row"
        used = set()

        def add(k, v, unit, label, raw=None):
            raw = raw if raw is not None else " | ".join(F[label])
            pr.claims.append(C.claim(key, k, v, unit, raw, "s1", ADAPTER, "psref_json", obs, {"label": label, "basis": basis}, f"{label}  {raw}"))
            used.add(label)

        def txt(l):
            return " | ".join(F.get(l, []))
        if "Panel" in F:
            for rx, v in PANEL:
                if re.search(rx, txt("Panel"), re.I):
                    add("panel.technology", v, None, "Panel"); break
        if "Display Size" in F and num(txt("Display Size")):
            add("gen.size_class", num(txt("Display Size")), "in", "Display Size")
        if "Resolution" in F and (m := re.search(r"(\d{3,5})\s*[x×]\s*(\d{3,5})", txt("Resolution"))):
            add("res.native", f"{m[1]}x{m[2]}", None, "Resolution")
            add("res.width_px", int(m[1]), "px", "Resolution"); add("res.height_px", int(m[2]), "px", "Resolution")
        if "Aspect Ratio" in F and txt("Aspect Ratio") in ("16:9", "16:10", "3:2", "21:9", "32:9", "4:3"):
            add("res.aspect", txt("Aspect Ratio"), None, "Aspect Ratio")
        if "Dot / Pixel Per Inch" in F and num(txt("Dot / Pixel Per Inch")):
            add("res.ppi", num(txt("Dot / Pixel Per Inch")), "ppi", "Dot / Pixel Per Inch")
        if "Refresh Rate" in F and re.search(r"\d\s*Hz", txt("Refresh Rate"), re.I):
            add("res.refresh_max", num(txt("Refresh Rate")), "Hz", "Refresh Rate")
        if "Brightness" in F and num(txt("Brightness")):
            add("hdr.sdr_typ", num(txt("Brightness")), "nit", "Brightness")
        if "Contrast Ratio" in F and (m := re.search(r"(?<![\d:])(\d[\d,]*):1", txt("Contrast Ratio"))):
            add("hdr.contrast_static", f"{m[1].replace(',', '')}:1", None, "Contrast Ratio")
        if "Color Depth" in F:
            cd = txt("Color Depth")
            m = re.search(r"\((\d+-bit\+?FRC)\)", cd)
            v = m[1] if m else ("10-bit" if re.fullmatch(r"10-bit.*", cd) and "FRC" not in cd else None)
            if v in ("6-bit+FRC", "8-bit+FRC", "10-bit"):
                add("panel.bit_depth", v, None, "Color Depth")
        g = txt("Color Gamut")
        for k, rx in (("color.srgb", r"(\d+(?:\.\d+)?)\s*%\s*sRGB"), ("color.dci_p3", r"(\d+(?:\.\d+)?)\s*%\s*DCI-?P3")):
            if (m := re.search(rx, g)):
                add(k, float(m[1]), "%", "Color Gamut")
        if "Screen Surface Treatment" in F:
            add("panel.surface", "matte" if re.search(r"anti-?glare", txt("Screen Surface Treatment"), re.I) else "unspecified", None, "Screen Surface Treatment") \
                if re.search(r"anti-?glare", txt("Screen Surface Treatment"), re.I) else None
        if "Curvature" in F:
            add("gen.curvature", txt("Curvature"), None, "Curvature")
        pw = txt("Power Consumption")
        if (m := re.search(r"Typical\s*/\s*Max[^:]*:\s*([\d.]+)\s*W\s*/\s*([\d.]+)\s*W", pw)) or (m := re.search(r"([\d.]+)\s*W\s*/\s*([\d.]+)\s*W", pw)):
            add("pwr.typical", float(m[1]), "W", "Power Consumption"); add("pwr.max", float(m[2]), "W", "Power Consumption")
        if "Mounting" in F and (m := re.search(r"(\d+)\s*x\s*(\d+)", txt("Mounting"))):
            v = f"{m[1]}x{m[2]}"
            if v in ("75x75", "100x100", "200x100", "200x200", "400x400"):
                add("ergo.vesa", v, None, "Mounting")
        if "Weight" in F:
            w = F["Weight"]
            for lbl, k in (("Monitor with stand", "ergo.weight"), ("Monitor head only", "ergo.weight_panel")):
                v = after(w, lbl)
                if v and (m := re.search(r"([\d.]+)\s*kg", v)):
                    add(k, float(m[1]), "kg", "Weight", f"{lbl}: {v}")
            if "Monitor with stand" not in " ".join(w) and (m := re.search(r"([\d.]+)\s*kg", w[0])) and len(w) == 1:
                add("ergo.weight", float(m[1]), "kg", "Weight", w[0])
        if "Base Warranty" in F and (m := re.search(r"(\d+)[- ]year", txt("Base Warranty"), re.I)):
            add("sup.warranty_years", int(m[1]), "year", "Base Warranty")
        ports = F.get("Rear Ports", []) + F.get("Side Ports", []) + F.get("Left Ports", [])
        if ports:
            pt = " | ".join(ports)
            pr.claims.append(C.claim(key, "vin.ports", ports, None, pt, "s1", ADAPTER, "psref_json", obs, {"label": "Ports", "basis": basis}, pt))
            used.add("Rear Ports")
            pr.claims.append(C.claim(key, "vin.hdmi_count", sum(int(m[1] or 1) for m in re.finditer(r"(?:(\d+)x\s*)?HDMI", pt, re.I)), None, pt, "s1", ADAPTER,
                                     "psref_json", obs, {"label": "Ports", "basis": basis}, pt))
            pr.claims.append(C.claim(key, "vin.dp_count", sum(int(m[1] or 1) for m in re.finditer(r"(?:(\d+)x\s*)?Display ?Port", html.unescape(pt), re.I)), None, pt,
                                     "s1", ADAPTER, "psref_json", obs, {"label": "Ports", "basis": basis}, pt))
            pdw = {}
            for seg in ports:                       # v2: one port line at a time; only the USB-C upstream port's power counts (profile: upstream PD)
                if (w := upstream_pd_w(seg)) is not None:
                    pdw.setdefault(w, seg)
            if len(pdw) == 1:                       # two upstream ports with different wattages: ambiguous, nothing written
                (w, seg), = pdw.items()
                pr.claims.append(C.claim(key, "usb.usbc_pd_w", w, "W", seg, "s1", ADAPTER, "psref_json", obs, {"label": "Ports", "basis": basis}, seg))
        allports = [x for lab in sorted(F) if re.fullmatch(r"(Rear|Side|Left|Right|Front|Top|Bottom) Ports", lab) for x in F[lab]]
        if allports:
            n, zero = MP.count_inputs([html.unescape(x) for x in allports])
            others = [l for l, v in F.items() if not l.endswith(" Ports") and MP.CPORT.search(l + " " + " ".join(v))]
            if zero and others:             # USB-C named outside the port lists: not provably complete
                n, zero = None, False
            if n is not None:
                apt = " | ".join(allports)
                pr.claims.append(C.claim(key, "usb.usbc_inputs", n, None, apt, "s1", ADAPTER, "psref_json", obs, {"label": "Ports", "basis": basis}, apt,
                                         conditions={"basis": "complete_enumeration"} if zero else None))
        sf = txt("Special Features")
        if (m := re.search(r"DisplayHDR\s*(True Black\s*)?(\d{3,4})", sf, re.I)):
            tier = f"DisplayHDR {'True Black ' if m[1] else ''}{m[2]}"
            add("hdr.vesa_tier", tier, None, "Special Features")
        vrr = [n for n, rx in (("FreeSync", r"FreeSync"), ("G-Sync Compatible", r"G-SYNC"), ("Adaptive-Sync", r"Adaptive.?Sync")) if re.search(rx, sf, re.I)]
        if vrr:
            add("res.vrr_types", vrr, None, "Special Features")
        if re.search(r"\bHDR\b|HDR10", sf):
            add("hdr.marketed_label", next(x for x in re.split(r" \| ", sf) if "HDR" in x)[:80], None, "Special Features")
        if "Case Color" in F:
            add("gen.color", txt("Case Color"), None, "Case Color")
        pr.fingerprints = {"raw": snap.snapshot, "basis": basis, "models": len(rows), "us": sum(m.get("Model", "").endswith("US") for m in rows),
                           "unmapped": {k: v for k, v in F.items() if k not in used}}
        return pr


if __name__ == "__main__":
    _run.main(LenovoMonitors())
