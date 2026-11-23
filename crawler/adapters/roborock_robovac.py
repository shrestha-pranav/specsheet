#!/usr/bin/env python3
"""Roborock US robot-vacuum adapter v1 (contract ARCHITECTURE 15.5), category robot-vacuums. Source = us.roborock.com (Shopify, 'Roborock US Official Store').

discover : /products.json (2 pages) -> product_type 'Robot Vacuums' minus wet-dry (F25, Dyad, Flexi), stick (H60), refurbished, trade-in and
           anniversary-gift pages. Products sharing a variant SKU or a derived model name are one model (_robovac.group).
fetch    : bundle = canonical product page (SSR ~1.2 MB) + /products/<handle>.json of every member.
parse    : pure. Two blocks: (1) 'Specifications:' rows <span class="font-semibold">Label: </span>value (Robot Weight, Robot Dimensions incl. the dock,
           Battery Type '5200mAh lithium-ion battery'); (2) 'Key Features' <br/>-separated bullets ('-Industry-Leading 18500Pa HyperForce® Suction',
           '-167°F (75°C) Hot Water Re-Wash'). Suction comes from the Key Features bullet (else the page title), basis mfr_unstated: Roborock US pages print
           no test basis.
Identity : Roborock's US pages print no regulatory model code. mfr_model = the model name from the title (S8 MaxV Ultra). SKU RR-<Name><c>-M<n>: c = colour
           digit (0 white, 5 black), M/P = market batch; SKUs are configuration aliases. 'with Refill & Drainage System' pages are their own SKU
           (RR-...RDS-M1) and become '<model> RDS' (different dock hardware: plumbed refill/drain), never merged with the standard dock.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _robovac as RV
import _run

ID, VERSION, SOURCE = "roborock_robovac", 1, "roborock-us-robovac"
CATEGORIES = {"robot-vacuums"}
ADAPTER = f"{ID}@{VERSION}"
HOST = "us.roborock.com"
NOT_ROBOT = re.compile(r"(?i)\b(F25|H60|Dyad|Flexi|anniversary)\b")


def model_of(p):
    t = RV.text(p.get("title", ""))
    if p.get("product_type") != "Robot Vacuums" or not RV.skus(p) or RV.NOISE_TITLE.search(t) or NOT_ROBOT.search(t):
        return None
    rds = bool(re.search(r"(?i)refill\s*&\s*drainage", t)) or any(s.upper().endswith("RDS-M1") for s in RV.skus(p))
    t = re.sub(r"(?i)^\s*(roborock|rockrobo)\s+", "", t)
    t = re.sub(r"(?i)\s*(\s[-–]\s.*|\bwith\b.*|\brobot vacuum.*|\(.*|,.*)$", "", t).strip(" -–")
    t = re.sub(r"(?i)\s+roller mop$", "", re.sub(r"\s+", " ", t))
    if not re.search(r"\d|Qrevo|Saros", t, re.I) or len(t) > 40:
        return None
    return t + (" RDS" if rds else "")


def prefer(p):
    return 1 if re.search(r"(?i)\bset\b|-1$", p.get("handle", "") + " " + p.get("title", "")) else 0


class RoborockRobovac:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ps, stop = RV.catalogue(net, HOST)
        groups = RV.group(ps, model_of, prefer)
        refs = RV.refs_from_groups(SOURCE, HOST, groups)
        return C.Discovery(refs, stop is None, stop, {"products": len(ps), "models": len(refs)})

    def fetch(self, ref, prior, net):
        return RV.fetch_bundle(self.store, ADAPTER, ref, net)

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, RV.read_bundle(blobs, snap))


MAPPED = {"Battery Type", "Battery", "Battery Capacity", "Robot Dimensions", "Product Dimensions", "Dimensions: Robot", "Robot (W × D × H)",
          "Dock Dimensions", "Dock (W × D × H)", "Dimensions", "Robot Weight", "Net Weight: Robot", "Robot Net Weight", "Dock Weight"}
ROW = re.compile(r'<span class="font-semibold[^"]*">\s*(.*?)\s*</span>(.*?)</h3>', re.S)


def spec_rows(h):
    i = h.find("Specifications:")
    if i < 0:
        return {}
    seg = h[i: i + 20000]
    j = seg.find("User Manual")
    out = {}
    for a, b in ROW.findall(seg[: j if j > 0 else None]):
        la, va = RV.text(a).rstrip(":").strip(), RV.text(b)
        if la and va:
            out.setdefault(la, va)
    return out


def key_features(h):
    m = re.search(r'<h2 class="h5">Key Features</h2>\s*<div[^>]*>(.*?)</div>', h, re.S)
    if not m:
        return []
    return [RV.text(x).lstrip("-• ").strip() for x in re.split(r"<br\s*/?>", m[1]) if RV.text(x).strip("- ")]


def parse_bundle(snap, b):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "Roborock US product page " + snap.ref.key}]
    prods = b.get("products") or []
    canon = next((p for p in prods if snap.ref.url.endswith("/" + p.get("handle", ""))), prods[0] if prods else None)
    name = model_of(canon) if canon else None
    if not name:
        pr.absences.append({"key": "*", "reason": "no robot-vacuum product JSON in bundle", "source": "s1"})
        return pr
    fam = re.match(r"[A-Za-z]+", name)[0].upper()
    pr.identifiers.append(RV.ident("mfr_model", RV.plus(name), "model", "roborock", raw=name, series=fam))
    pr.aliases.append({"text": "Roborock " + name, "kind": "marketing_name"})
    RV.variant_idents(pr, prods, "roborock", RV.plus(name))
    h = b.get("html") or ""
    rows, kf = spec_rows(h), key_features(h)

    def add(k, v, raw, label, cond=None):
        RV.add(pr, ADAPTER, snap, name, k, v, raw, label, cond)
    title = RV.text(canon.get("title", ""))
    suc = next((f for f in kf if RV.pa(f)), None)
    if suc:
        add("clean.suction_pa", RV.pa(suc), suc, "Key Features", {"claim_basis": "mfr_unstated"})
    elif RV.pa(title):
        add("clean.suction_pa", RV.pa(title), title, "page title", {"claim_basis": "mfr_unstated"})
    hot = next((f for f in kf if re.search(r"hot water", f, re.I) and re.search(r"\d+\s*°?\s*[CF]", f)), None)
    if hot:
        add("dock.hot_water_wash", True, hot, "Key Features"); add("dock.mop_wash", True, hot, "Key Features")
        add("dock.wash_water_temp_c", RV.temp_c(hot), hot, "Key Features")
    if re.search(r"(?i)refill\s*&\s*drainage", title) or name.endswith(" RDS"):
        add("dock.plumbed_refill_drain", True, title, "page title")
    if re.search(r"(?i)auto-?empty", title):
        add("dock.self_empty", True, title, "page title")
    def row(*labels):
        for l in labels:
            if rows.get(l):
                return l, rows[l]
        return None, None
    bat = rows.get("Battery Type") or rows.get("Battery") or rows.get("Battery Capacity")
    if bat:
        add("bat.capacity_mah", RV.mah(bat), bat, "Battery Type")
    rl, rd = row("Robot Dimensions", "Product Dimensions", "Dimensions: Robot", "Robot (W × D × H)")
    dl, dd = row("Dock Dimensions", "Dock (W × D × H)")
    if dd:
        add("phys.dock_dimensions", RV.dims_mm(dd if re.search(r"(?i)in|mm|cm", dd) else dd + " inches"), dd, dl)
    bad = []
    if rd is None and rows.get("Dimensions"):
        rl, rd = "Dimensions", rows["Dimensions"]
    if rd:
        m = re.search(r"(?i)robot(?: dimensions)?\s*[:：]\s*([^;]*?)(?:;|dock|charging|$)", rd)
        part = m[1] if m else ("" if re.search(r"(?i)dock", rd.split("inch")[0]) else re.split(r"(?i)[,;]?\s*(?:auto-empty\s+)?dock\s*[:：]", rd)[0])
        d = RV.dims_mm(part if re.search(r"(?i)in|mm|cm", part) else part + " inches") if part else None
        if d and RV.plausible_robot(dims=d):
            add("phys.robot_dimensions", d, rd, rl); add("phys.robot_height_mm", d["height"], rd, rl)
        elif d:
            bad.append(("phys.robot_dimensions", rd))
        dm = re.search(r"(?i)dock(?: dimensions)?\s*[:：]\s*([^;]*)", rd)
        if dm and not dd:
            add("phys.dock_dimensions", RV.dims_mm(dm[1] if re.search(r"(?i)in|mm|cm", dm[1]) else dm[1] + " inches"), rd, rl)
    rw = rows.get("Robot Weight") or rows.get("Net Weight: Robot") or rows.get("Robot Net Weight")
    if rw:
        combined = re.match(r"(?i)\s*robot\s*(&|\+|and)", rw)
        m = re.search(r"(?i)robot\s*[:：]\s*([^,;]*)", rw)
        part = m[1] if m else re.split(r"(?i)dock", rw)[0]
        w = None if combined else RV.weight_g(part)
        if w and RV.plausible_robot(weight_g=w):
            add("phys.robot_weight_g", w, rw, "Robot Weight")
        elif w:
            bad.append(("phys.robot_weight_g", rw))
    dw = rows.get("Dock Weight")
    if dw:
        add("phys.dock_weight_g", RV.weight_g(dw), dw, "Dock Weight")
    pr.fingerprints = {"raw": snap.snapshot, "labels": sorted(rows), "key_features": kf[:12], "members": [p.get("handle") for p in prods],
                       "unmapped": {k: v[:100] for k, v in rows.items() if k not in MAPPED},
                       "implausible": bad}
    return pr


if __name__ == "__main__":
    _run.main(RoborockRobovac())
