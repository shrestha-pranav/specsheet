#!/usr/bin/env python3
"""Dreame US robot-vacuum adapter v1 (contract ARCHITECTURE 15.5), category robot-vacuums. Source = www.dreametech.com (Shopify, US store).

discover : /products.json (2 pages) -> product_type 'Robot Vacuums' / 'Robot Vacuum-1' or an untyped product whose title says 'Robot Vac', with at least
           one variant SKU (Dreame material code 010204AA000742; one per colour). Products sharing a SKU are one model (App Only / Live Only /
           Membership / Complete pages of the same robot): _robovac.group. SKU-less bundles, refurbished units, accessories are dropped.
fetch    : bundle = canonical product page (SSR, ~2.7 MB) + /products/<handle>.json of every member (titles, variant SKUs, colours).
parse    : pure. The page's 'Specifications' block is <li><span>label</span><span>value</span></li> pairs (common-spec section); its 'Disclaimers'
           lines ('*19,000Pa ...: Based on our in-house lab data', '*0 tangles: Certified by TÜV SÜD') give the claim basis of headline numbers.
           The multi-model 'Feature' comparison table is NOT read (columns are sibling models; mis-assignment risk).
Identity : Dreame prints no regulatory model code on US pages: mfr_model = the product model name (L40s Ultra), SKUs are configuration aliases.
Traps    : suction is 'Based on our in-house lab data' (no standard test); 'Dust Box Capacity ≥300ml' is a lower bound (not normalised);
           'Obstacle Crossing 1.57in (double-layer step), 0.87in (single-layer step)' -> the single-step figure is the comparable one.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _robovac as RV
import _run

ID, VERSION, SOURCE = "dreame_robovac", 2, "dreame-us-robovac"     # v2: review-3 strict enums / identity / plausibility
CATEGORIES = {"robot-vacuums"}
ADAPTER = f"{ID}@{VERSION}"
HOST = "www.dreametech.com"
TYPES = {"Robot Vacuums", "Robot Vacuum-1"}


def model_of(p):
    t = RV.text(p.get("title", ""))
    if not RV.skus(p) or RV.NOISE_TITLE.search(t) or "bundle" in t.lower() or "+" in t.replace("Plus", ""):
        return None
    if p.get("product_type") not in TYPES and not (p.get("product_type") in ("", None) and re.search(r"robot vac", t, re.I)):
        return None
    t = re.sub(r"【[^】]*】", "", t)
    t = re.sub(r"(?i)^\s*(\d+% off-)?\s*dreame(tech)?\s+", "", t)
    t = re.sub(r"(?i)\s*(robot(ic)? vac.*|[-–(]?\s*(app|live) only.*|-membership.*|\bwith\b.*|,.*|\(.*|-\s*for .*)$", "", t).strip(" -–")
    t = re.sub(r"(?i)\s+(white|black|grey|gray|silver)$", "", t)
    return t if 2 <= len(t) <= 40 and re.search(r"\d", t) else None


def prefer(p):
    t = p.get("title", "").lower()
    return sum(w in t for w in ("live only", "app only", "membership", "group buy", "complete", "off-"))


class DreameRobovac:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ps, stop = RV.catalogue(net, HOST)
        conflicts = []
        groups = RV.group(ps, model_of, prefer, conflicts)
        refs = RV.refs_from_groups(SOURCE, HOST, groups)
        return C.Discovery(refs, stop is None, stop, {"products": len(ps), "models": len(refs), "identity_conflicts": conflicts})

    def fetch(self, ref, prior, net):
        return RV.fetch_bundle(self.store, ADAPTER, ref, net)

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, RV.read_bundle(blobs, snap))


LI = re.compile(r"<li[^>]*>\s*<span[^>]*>(.*?)</span>\s*<span[^>]*>(.*?)</span>\s*</li>", re.S)
TR = re.compile(r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.S)
CFG = re.compile(r'<div class="cfg-spec__col-label">(.*?)</div>\s*<div class="cfg-spec__col-value">(.*?)</div>', re.S)
SPI = re.compile(r'<span class="spec-label">(.*?)</span>\s*<span class="spec-value">(.*?)</span>', re.S)
PAIRS = (LI, TR, CFG, SPI)      # four single-product templates seen on dreametech.com (li/span, table rows, cfg-spec rows, spec-item spans)


def spec_pairs(h):
    """label -> value from the product's own 'Specifications' block: label/value pairs (PAIRS templates) that follow a
    Specifications heading (first block with pairs wins; first occurrence of a label wins). Cut at the next 'Disclaimers'/'Feature' table."""
    for m in re.finditer(r">\s*Specifications\s*<", h):
        seg = h[m.end(): m.end() + 40000]
        cut = min([i for i in (seg.find("Disclaimers"), seg.find("group-item-"), seg.find(">Feature<")) if i > 0] or [len(seg)])
        out = {}
        for a, b in [x for rx in PAIRS for x in rx.findall(seg[:cut])]:
            la, va = RV.text(a).rstrip(":* "), RV.text(b)
            if la and va and len(la) < 70:
                out.setdefault(la, va)
        if len(out) >= 3:
            return out
    return {}


ITEM = re.compile(r'<div class="item-(\d+) item\s+group-item-(\d+)">(.*?)</div>\s*</div>\s*</div>', re.S)


def comparison_own_column(h, name):
    """Pages without an own Specifications block (X40/X50/L50 Ultra) carry a 2-model comparison (label | this product | older model).
    Column 2 is read ONLY when the header text just before the table names exactly this model ('New X50 Ultra' == 'X50 Ultra');
    any other header (L10s Pro Ultra page headed 'L10s Pro Ultra Heat') -> nothing."""
    i = h.find("group-item-")
    if i < 0:
        return {}
    heads = [re.sub(r"(?i)^new\s+", "", l) for l in RV.page_lines(h[max(0, i - 15000): i])
             if re.search(r"[A-Za-z]", l) and re.search(r"\d", l) and len(l) < 40 and "=" not in l and not l.startswith("<")]
    if len(heads) < 2 or RV.norm(heads[-2]) != RV.norm(name):
        return {}
    rows = {}
    for col, grp, body in ITEM.findall(h):
        rows.setdefault(int(grp), {})[int(col)] = RV.text(body)
    return {r[1]: r[2] for r in rows.values() if r.get(1) and r.get(2) and len(r[1]) < 70}


def disclaimers(h):
    ls = RV.page_lines(h)
    i = next((n for n, l in enumerate(ls) if l.strip().lower() == "disclaimers"), None)
    tail = ls[i + 1: i + 60] if i is not None else []
    return [l for l in tail if l.startswith("*")]


def parse_bundle(snap, b):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "Dreame US product page " + snap.ref.key}]
    prods = b.get("products") or []
    canon = next((p for p in prods if snap.ref.url.endswith("/" + p.get("handle", ""))), prods[0] if prods else None)
    name = model_of(canon) if canon else None
    if not name:
        pr.absences.append({"key": "*", "reason": "no robot-vacuum product JSON in bundle", "source": "s1"})
        return pr
    fam = re.match(r"[A-Za-z]+", name)[0].upper()
    pr.identifiers.append(RV.ident("mfr_model", RV.plus(name), "model", "dreame", raw=name, series=fam))
    pr.aliases.append({"text": "Dreame " + name, "kind": "marketing_name"})
    prods, quarantined = RV.corroborate(prods, canon, model_of)
    RV.variant_idents(pr, prods, "dreame", RV.plus(name))
    h = b.get("html") or ""
    rows = spec_pairs(h)
    table = "Specifications"
    if not rows:
        rows, table = comparison_own_column(h, name), "comparison column (header = this model)"
    disc = disclaimers(h)
    fill(pr, snap, name, rows, disc, ADAPTER)
    pr.fingerprints = {"raw": snap.snapshot, "table": table if rows else None, "labels": sorted(rows), "members": [p.get("handle") for p in prods], "disclaimers": len(disc),
                       "unmapped": {k: v[:100] for k, v in rows.items() if k not in MAPPED}, "quarantined_members": quarantined}
    return pr


MAPPED = set()


def fill(pr, snap, name, rows, disc, adapter):
    """Label-mapped claims shared by Dreame-template pages. Every claim keeps the literal cell in `raw`."""
    def add(k, v, raw, label, cond=None, quote=None):
        RV.add(pr, adapter, snap, name, k, v, raw, label, cond, quote)

    def get(*labels):
        for l in labels:
            for k, v in rows.items():
                if k.lower() == l.lower():
                    MAPPED.add(k)
                    return k, v
        return None, None
    MAPPED.add("Product Name")
    k, v = get("Maximum Suction (Pa)", "Maximum Suction", "Suction", "Suction Power", "Max Suction", "Max. Suction")
    if v and (x := RV.pa(v)):
        basis, q = RV.basis_for(re.search(r"\d[\d,]*", v)[0], disc)
        add("clean.suction_pa", x, v, k, {"claim_basis": basis}, q)
    k, v = get("Battery Capacity (mAh)", "Battery Capacity", "Battery")
    if v:
        add("bat.capacity_mah", RV.mah(v), v, k)
        add("bat.energy_wh", RV.wh(v), v, k)
    k, v = get("Dust Box Capacity", "Dustbin Capacity", "Dust Bin Capacity", "Dustbin Volume", "Dust Box Volume", "Dust Box Storage")
    if v:
        add("clean.dustbin_ml", RV.ml(v), v, k)
    k, v = get("Dust Bag Capacity", "Base Station Dust Bag Capacity", "Dust Bag Volume", "Dust Bag")
    if v:
        add("dock.dust_bag_ml", RV.ml(v), v, k)
    k, v = get("Clean/Used Water Box")
    if v:
        add("mop.robot_tank_ml", RV.tanks(v.replace("ml", "L") if "ml" in v.lower() else v)[0] and RV.ml(v.split("/")[0] + ("ml" if "ml" in v.lower() else "")), v, k)
    k, v = get("Clean Water Tank")
    if v:
        add("dock.clean_tank_ml", RV.ml(v), v, k)
    k, v = get("AI Recognition & Object Type Count")
    if v and (m := re.search(r"(\d+)\s*(\+)?", v)) and RV.yes(v):
        add("nav.ai_object_types", int(m[1]), v, k)
    k, v = get("Clean/Used Water Tank Capacity", "Clean/Dirty Water Tank Capacity", "Clean/Dirty Water Tank", "Water Tank Capacity (Clean/Dirty)")
    if v:
        c, d = RV.tanks(v)
        add("dock.clean_tank_ml", c, v, k); add("dock.dirty_tank_ml", d, v, k)
    k, v = get("Water Tank Capacity", "Robot Water Tank Capacity", "Water Tank", "Water Tank Volume", "Water Tank Storage")
    if v and "/" not in v:
        add("mop.robot_tank_ml", RV.ml(v), v, k)
    k, v = get("Robot Vacuum Dimensions", "Robot Dimensions", "Product Dimensions", "Robot Vacuum Product Dimensions", "Robot Vacuum Dimsensons")
    if v and (d := RV.dims_mm(v)):
        d = RV.robot_dims(d)
        add("phys.robot_dimensions", d, v, k); add("phys.robot_height_mm", RV.robot_height(d), v, k)
    k, v = get("Base Station Dimensions", "Dock Dimensions", "Base Station Product Dimensions", "Base Siation Dimensions", "Charging Dock Dimensions")
    if v:
        add("phys.dock_dimensions", RV.dims_mm(v), v, k)
    k, v = get("Robot Vacuum Weight", "Robot Weight")
    if v:
        w = RV.weight_g(v)
        add("phys.robot_weight_g", RV.robot_weight(w), v, k)
    k, v = get("Base Station Weight", "Dock Weight", "Charging Dock Weight")
    if v:
        add("phys.dock_weight_g", RV.weight_g(v), v, k)
    k, v = get("Obstacle Crossing Height", "Obstacle Crossing", "Climbing Height", "Obstacle Clearance Height", "Threshold Crossing")
    if v:
        single = re.search(r"([\d.]+\s*(?:in|mm|cm))\s*\((?:single|one)", v, re.I)
        many = len(re.findall(r"\d+(?:\.\d+)?\s*(?:in|mm|cm)\b", v)) > 1
        x = RV.length_mm(single[1]) if single else (None if many else RV.length_mm(v))
        add("nav.obstacle_crossing_mm", x, v, k)
    k, v = get("Navigation", "Navigation System", "Navigation & Obstacle Avoidance")
    if v:
        add("nav.type", RV.navigation(v), v, k)
    k, v = get("Obstacle Avoidance", "Obstacle Avoidance System", "Obstacle Recognition", "Navigation & Obstacle Avoidance")
    if v:
        add("nav.obstacle_sensors", RV.obstacle_sensors(v), v, k)
    k, v = get("Main Brush Type", "Main Brush")
    if v:
        add("clean.main_brush_type", v, v, k)
    for lab, key in (("Side Brush Lifting", "clean.side_brush_lifting"), ("Side Brush Extending", "clean.side_brush_extending"),
                     ("Main Brush Lifting", "clean.main_brush_lifting"), ("Mop Extending", "mop.extending"), ("Mop Removal", "mop.auto_removal"),
                     ("Mop Automatic Removal", "mop.auto_removal"), ("Hot Air Drying", "dock.hot_air_dry"), ("Auto Solution Adding", "dock.solution_dispense"),
                     ("Automatic Solution Adding", "dock.solution_dispense"), ("Auto Tank Water Refilling", "mop.auto_refill_from_dock"),
                     ("Auto Water Tank Refilling (from Dock to Robot)", "mop.auto_refill_from_dock"), ("Auto-Empty", "dock.self_empty"),
                     ("Auto Empty", "dock.self_empty"), ("Self-Cleaning Washboard", "dock.washboard_self_clean"),
                     ("Washboard Self-Cleaning", "dock.washboard_self_clean"), ("Auto Mop Cleaning with Hot Water", "dock.mop_wash"),
                     ("Mop Hot Water Washing", "dock.hot_water_wash"), ("Dirt Detection", "clean.dirt_detection"),
                     ("Auto Refill and Drain", "dock.plumbed_refill_drain"), ("Mop Lifting", "mop.lifting"), ("Mop Lifting Height", "mop.lifting"),
                     ("Brush Lifting", "clean.main_brush_lifting"), ("Liftable Side Brush", "clean.side_brush_lifting"),
                     ("Extendable Side Brush", "clean.side_brush_extending"), ("Extending Side Brush", "clean.side_brush_extending"),
                     ("Side Brush Extend", "clean.side_brush_extending"), ("Mop Extend", "mop.extending"), ("MopExtend™ RoboSwing", "mop.extending"),
                     ("MopExtend RoboSwing", "mop.extending"), ("Auto Mop Removal", "mop.auto_removal"), ("Auto Solution Refill", "dock.solution_dispense"),
                     ("Auto Tank Water Refill", "mop.auto_refill_from_dock"), ("AceClean™ DryBoard", "dock.washboard_self_clean"),
                     ("AceClean DryBoard", "dock.washboard_self_clean"), ("Mop Drying", "dock.mop_dry"), ("Auto Water Box Refilling", "mop.auto_refill_from_dock"), ("Auto Emptying", "dock.self_empty"),
                     ("Auto Solution Refilling", "dock.solution_dispense"), ("Matter Connectivity", "smart.matter"),
                     ("Dirt Detection/Mop Rewashing and Floor Remopping", "clean.dirt_detection")):
        k, v = get(lab)
        if v is None:
            continue
        y = RV.yes(v)
        if y is None and re.search(r"\d", v) and key in ("mop.lifting", "dock.mop_wash", "dock.hot_water_wash"):
            y = True                       # '10.5mm (0.41in)' / '✓ (167°F)' / '75°C (167℉)' state the feature with a figure
        add(key, y, v, k)
        if key == "dock.mop_dry" and y and re.search(r"(?i)hot", v):
            add("dock.hot_air_dry", True, v, k)
        if key == "mop.lifting" and re.search(r"\d", v):
            add("mop.lift_height_mm", RV.length_mm(v), v, k)
        if key in ("dock.mop_wash", "dock.hot_water_wash") and re.search(r"\d", v):
            add("dock.wash_water_temp_c", RV.temp_c(v), v, k)
            if key == "dock.mop_wash":
                add("dock.hot_water_wash", True, v, k)
        if key == "dock.hot_water_wash" and y:
            add("dock.mop_wash", True, v, k)
    k, v = get("Mop Type", "Mopping Type", "Mopping System", "Mops Type")
    if v:
        add("mop.type", RV.mop_type(v), v, k)
    k, v = get("Noise", "Noise Level", "Noise (dB)", "Lowest Noise")
    if v and (m := re.search(r"(\d+(?:\.\d+)?)\s*dB", v)):
        basis, q = RV.basis_for(m[0], disc)
        add("noise.db", float(m[1]), v, k, {"claim_basis": basis, "power_mode": RV.power_mode(v + " " + k)}, q)
    k, v = get("Runtime", "Run Time", "Running Time", "Battery Life", "Maximum Runtime")
    if v:
        add("bat.runtime_min", RV.minutes(v), v, k, {"power_mode": RV.power_mode(v + " " + k)})
    k, v = get("Voice Control", "Voice Assistant", "Third-Party Voice Control")
    if v:
        add("smart.voice_control", v, v, k)


if __name__ == "__main__":
    _run.main(DreameRobovac())
