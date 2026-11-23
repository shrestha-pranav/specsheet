#!/usr/bin/env python3
"""MOVA US robot-vacuum adapter v1 (contract ARCHITECTURE 15.5), category robot-vacuums. Source = us.mova.tech (Shopify; us.mova-tech.com redirects).

discover : /products.json -> product_type 'Robot Vacuum' with a variant SKU (Dreame-group material code 010204AA001237), minus refurbished /
           accessories; 'Live Only' / colour pages fold into one model by shared SKU (_robovac.group).
fetch    : bundle = product page + /products/<handle>.json per member (as Dreame/Roborock/Narwal) + the store's /pages/compare-robot-vacuum page
           (fetched once per run, embedded in every bundle so the parse is self-contained).
parse    : pure. The page's comparison section is rendered client-side from a server-rendered JSON island
           <script type="application/json" id="ProductData-...comparison...">{"products": [{title, url, specs: {slug: value}}]}</script>.
           The island lists sibling MOVA models AND competitors (Roborock Qrevo, url null): ONLY the entry whose url is one of this bundle's own
           member handles is read (no match -> no claims). Values: '√' / '×' / '-' cells, '19000Pa', '300ml', '√ 10.5mm', '4L/3.5L', '√ 75°C'.
           Compare page (s2): hidden <input class="...one-structre-item" value="{json}"> elements: row-group structures {title,
           structure_text_1..16} give the 48 row labels in order; product items {product: <handle>, column_data: 'v1 ## v2 ## ...'} give one
           column per handle. A column is read ONLY when its value count equals the label count (positional table; any drift -> nothing read)
           and its handle is one of this bundle's members. Own-page island values win over compare-page values for the same key.
           'TBC'/'TBD' and lower-bound ('>=') cells are not normalised.
Identity : mfr_model = model name (P50 Pro Ultra); SKUs are configuration aliases (no regulatory code on US pages).
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _robovac as RV
import _run

ID, VERSION, SOURCE = "mova_robovac", 2, "mova-us-robovac"     # v2: review-3 strict enums / identity
CATEGORIES = {"robot-vacuums"}
ADAPTER = f"{ID}@{VERSION}"
HOST = "us.mova.tech"
COMPARE = "https://us.mova.tech/pages/compare-robot-vacuum"
STRUCT = re.compile(r'one-structre-item"\s+hidden\s+value="(.*?)"\s*>', re.S)
ISLAND = re.compile(r'<script type="application/json" id="ProductData-[^"]*">(.*?)</script>', re.S)


def model_of(p):
    t = RV.text(p.get("title", ""))
    if p.get("product_type") != "Robot Vacuum" or not RV.skus(p) or RV.NOISE_TITLE.search(t) or re.search(r"(?i)refurb|accessor|\(100% off\)", t):
        return None
    t = re.sub(r"【[^】]*】", "", t)
    t = re.sub(r"(?i)^\s*(mova\s+)+", "", t)
    t = re.sub(r"(?i)\s*robot(ic)? vac.*$|\s*-\s*live only.*$", "", t).strip(" -–")
    t = re.sub(r"(?i)\s+(white|black|grey|gray|silver)$", "", t)
    t = re.sub(r"(?i)^mobius", "MOBIUS", t)
    return t if 2 <= len(t) <= 40 and re.search(r"\d", t) else None


def islands(h):
    """All comparison JSON islands -> [product dict]. Liquid leaves trailing commas: stripped before json.loads."""
    out = []
    for s in ISLAND.findall(h or ""):
        try:
            out += json.loads(re.sub(r",(\s*[}\]])", r"\1", s)).get("products") or []
        except ValueError:
            continue
    return out


def compare_columns(h):
    """-> ({handle: {label: value}}, n_labels, {handle: n_values}) from the compare page; only count-aligned columns are returned."""
    import html as H
    items = []
    for v in STRUCT.findall(h or ""):
        try:
            items.append(json.loads(H.unescape(v)))
        except ValueError:
            continue
    labels = [d[f"structure_text_{i}"].strip() for d in items if "title" in d for i in range(1, 17) if (d.get(f"structure_text_{i}") or "").strip()]
    cols, counts = {}, {}
    for d in items:
        if "product" in d and "column_data" in d:
            vals = re.split(r"\s*##\s*", d["column_data"].strip())
            counts[d["product"]] = len(vals)
            if len(vals) == len(labels):
                cols[d["product"]] = dict(zip(labels, (RV.text(x) for x in vals)))
    return cols, len(labels), counts


class MovaRobovac:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ps, stop = RV.catalogue(net, HOST)
        conflicts = []
        refs = RV.refs_from_groups(SOURCE, HOST, RV.group(ps, model_of, lambda p: ("live only" in p["title"].lower(), 0), conflicts))
        return C.Discovery(refs, stop is None, stop, {"products": len(ps), "models": len(refs), "identity_conflicts": conflicts})

    _compare = None

    def fetch(self, ref, prior, net):
        """_robovac.fetch_bundle's shape (page + member product JSON) plus the compare page; one snapshot record per model."""
        import gzip, time
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, RV.DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            s = C.Snapshot("sha256:", ref, getattr(r, "status_code", r) or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".json.gz")
            return s
        base = ref.url.split("/products/")[0]
        prods, missing = [], []
        for h in ref.hints.get("handles") or [ref.url.rsplit("/", 1)[1]]:
            j = net.get(f"{base}/products/{h}.json", RV.DELAY)
            try:
                prods.append(j.json()["product"]) if j.status_code == 200 else missing.append(h)
            except (AttributeError, ValueError, KeyError):
                missing.append(h)
        if MovaRobovac._compare is None:
            c = net.get(COMPARE, RV.DELAY)
            MovaRobovac._compare = c.text if hasattr(c, "status_code") and c.status_code == 200 else ""
        body = {"page_url": r.url, "html": r.text, "products": prods, "missing": missing, "compare_url": COMPARE, "compare_html": MovaRobovac._compare}
        blob = gzip.compress(json.dumps(body, sort_keys=True).encode(), 6, mtime=0)
        s = C.Snapshot(self.store.put(blob, ".json.gz"), ref, 200, now, r.url, {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, RV.read_bundle(blobs, snap))


def flag(v):
    """'√' / '✓' (optionally followed by a figure) -> True; '×' / 'x' / '-' -> False; '/' (not applicable) and free text -> None."""
    t = (v or "").strip()
    return True if t.startswith("√") or t.startswith("✓") else False if t in ("×", "-", "—", "x", "X") else None


def parse_bundle(snap, b):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "MOVA US product page + robot-vacuum comparison page " + snap.ref.key}]
    prods = b.get("products") or []
    canon = next((p for p in prods if snap.ref.url.endswith("/" + p.get("handle", ""))), prods[0] if prods else None)
    name = model_of(canon) if canon else None
    if not name:
        pr.absences.append({"key": "*", "reason": "no robot-vacuum product JSON in bundle", "source": "s1"})
        return pr
    pr.identifiers.append(RV.ident("mfr_model", RV.plus(name), "model", "mova", raw=name, series=re.match(r"[A-Za-z]+", name)[0].upper()))
    pr.aliases.append({"text": "MOVA " + name, "kind": "marketing_name"})
    prods, quarantined = RV.corroborate(prods, canon, model_of)
    RV.variant_idents(pr, prods, "mova", RV.plus(name))
    own = {p["handle"] for p in prods if p.get("handle")}
    entry = next((e for e in islands(b.get("html")) if (e.get("url") or "").split("?")[0] in {"/products/" + h for h in own}), None)
    cols, nlab, counts = compare_columns(b.get("compare_html"))
    col_h = next((h for h in sorted(own) if h in cols), None)
    if not entry and not col_h:
        pr.absences.append({"key": "*", "reason": "no comparison entry (product-page island or compare-page column) for this product's handles", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "members": sorted(own), "compare_labels": nlab, "compare_counts": {h: counts.get(h) for h in own}}
        return pr
    done = set()

    def add(k, v, raw, label, cond=None, src="s1"):     # one snapshot = one source (import.py); compare-page values carry locator.page
        if k in done or (not isinstance(v, RV.Unresolved) and v in (None, "", [], {})):
            return
        m = RV.plus(name)
        loc = {"model_code": m, "label": label, **({"page": "compare", "url": COMPARE} if src == "s2" else {})}
        if isinstance(v, RV.Unresolved):          # literal + reason kept as preview evidence; a later explicit cell for the key may still be read
            if (k, raw, src) in done:
                return
            done.add((k, raw, src))
            pr.claims.append(C.claim(m, k, None, None, raw, src, ADAPTER, "adapter", snap.fetched_at, locator=loc, quote=v.reason, conditions=cond, status="unknown"))
            return
        done.add(k)
        pr.claims.append(C.claim(m, k, v, None, raw, src, ADAPTER, "adapter", snap.fetched_at, locator=loc, conditions=cond))
    used = set()
    sp = {k: RV.text(str(v)) for k, v in ((entry or {}).get("specs") or {}).items()}
    for lab, v in sp.items():
        k0 = len(pr.claims)
        island_row(add, lab, v)
        if len(pr.claims) > k0:
            used.add(lab)
    cu = set()
    for lab, v in (cols.get(col_h) or {}).items():
        k0 = len(pr.claims)
        compare_row(lambda k, val, raw, label, cond=None: add(k, val, raw, label, cond, "s2"), lab, v)
        if len(pr.claims) > k0:
            cu.add(lab)
    pr.fingerprints = {"raw": snap.snapshot, "labels": sorted(sp), "members": sorted(own), "quarantined_members": quarantined, "entry": (entry or {}).get("title"),
                       "unmapped": {k: v[:80] for k, v in sp.items() if k not in used}, "compare_column": col_h, "compare_labels": nlab,
                       "compare_unmapped": sorted(set(cols.get(col_h) or {}) - cu)}
    return pr


def ok(v):
    return not re.search(r"(?i)tb[cd]|[≥>]|at least", v or "")


def island_row(add, lab, v):
    f = flag(v)
    if lab == "navigation":
        add("nav.type", RV.navigation(v), v, lab)
    elif lab == "obstacle-avoidance":
        add("nav.obstacle_sensors", RV.obstacle_sensors(v), v, lab)
    elif lab == "maximum-suction":
        add("clean.suction_pa", RV.pa(v), v, lab, {"claim_basis": "mfr_unstated"})
    elif lab == "extendable-side-brush":
        add("clean.side_brush_extending", f, v, lab)
    elif lab == "liftable-side-brush":
        add("clean.side_brush_lifting", f, v, lab)
    elif lab == "dust-box-capacity" and ok(v):
        add("clean.dustbin_ml", RV.ml(v), v, lab)
    elif lab == "obstacle-clearance-height" and not re.search(r"[/+]|double|two", v, re.I):
        add("nav.obstacle_crossing_mm", RV.length_mm(v), v, lab)
    elif lab == "mopping-type":
        add("mop.type", RV.mop_type(v), v, lab)
    elif lab == "mop-lifting":
        add("mop.lifting", f, v, lab)
        if f:
            add("mop.lift_height_mm", RV.length_mm(v), v, lab)
    elif lab == "robot-water-tank-volume" and ok(v):
        add("mop.robot_tank_ml", RV.ml(v), v, lab)
    elif lab == "mop-extend":
        add("mop.extending", f, v, lab)
    elif lab == "auto-detachable-mop":
        add("mop.auto_removal", f, v, lab)
    elif lab == "battery-capacity":
        add("bat.capacity_mah", RV.mah(v), v, lab)
    elif lab == "base-station-dust-bag-volume" and ok(v):
        add("dock.dust_bag_ml", RV.ml(v), v, lab)
    elif lab == "base-station-clean-waste-water-tank-volume" and ok(v):
        c, d = RV.tanks(v)
        add("dock.clean_tank_ml", c, v, lab); add("dock.dirty_tank_ml", d, v, lab)
    elif lab == "mop-drying":
        add("dock.mop_dry", f, v, lab)
    elif lab == "hot-water-mop-washing":
        add("dock.hot_water_wash", f, v, lab)
        if f:
            add("dock.wash_water_temp_c", RV.temp_c(v), v, lab)
    elif lab == "automatic-cleaning-solution-adding":
        add("dock.solution_dispense", f, v, lab)
    elif lab == "auto-refilling-and-draining-of-base-station-water-tank":
        add("dock.plumbed_refill_drain", f, v, lab)
    elif lab == "self-cleaning-washboard":
        add("dock.washboard_self_clean", f, v, lab)
    elif lab in ("realtime-ai-dirt-detetion", "realtime-ai-dirt-detection"):
        add("clean.dirt_detection", f, v, lab)


def compare_row(add, lab, v):
    f = flag(v)
    l = re.sub(r"\s+", " ", lab.lower())
    if l == "navigation":
        add("nav.type", RV.navigation(v), v, lab)
    elif l == "obstacle avoidance":
        add("nav.obstacle_sensors", RV.obstacle_sensors(v), v, lab)
    elif l.startswith("minimum robot's height") and re.fullmatch(r"\d+(\.\d+)?\s*mm", v):
        add("phys.robot_height_mm", RV.length_mm(v), v, lab)
    elif l.startswith("barrier crossing ability") and re.fullmatch(r"\d+(\.\d+)?\s*(cm|mm)", v):
        add("nav.obstacle_crossing_mm", RV.length_mm(v), v, lab)
    elif l == "suction (pa)" and ok(v):
        add("clean.suction_pa", RV.pa(v), v, lab, {"claim_basis": "mfr_unstated"})
    elif l.startswith("dust box volume") and ok(v):
        add("clean.dustbin_ml", RV.ml(v), v, lab)
    elif l == "auto main brush lift":
        add("clean.main_brush_lifting", f, v, lab)
    elif l == "side brush lift":
        add("clean.side_brush_lifting", f, v, lab)
    elif l == "side brush extend":
        add("clean.side_brush_extending", f, v, lab)
    elif l == "mop type":
        add("mop.type", RV.mop_type(v), v, lab)
    elif l == "mop extend":
        add("mop.extending", f, v, lab)
    elif l == "auto mop lift":
        add("mop.lifting", f, v, lab)
        if f:
            add("mop.lift_height_mm", RV.length_mm(v), v, lab)
    elif l == "auto mop detaching":
        add("mop.auto_removal", f, v, lab)
    elif l == "dust bag capacity" and ok(v):
        add("dock.dust_bag_ml", RV.ml(v), v, lab)
    elif l.startswith("station water tank capacity") and ok(v):
        c, d = RV.tanks(v)
        add("dock.clean_tank_ml", c, v, lab); add("dock.dirty_tank_ml", d, v, lab)
    elif l.startswith("hot water mop-washing"):
        hot = True if re.search(r"\d+\s*°C", v) else f
        add("dock.hot_water_wash", hot, v, lab)
        if hot:
            add("dock.wash_water_temp_c", RV.temp_c(v), v, lab)
    elif l.startswith("mop hot air drying"):
        add("dock.hot_air_dry", f, v, lab)
    elif l == "battery capacity":
        add("bat.capacity_mah", RV.mah(v), v, lab)
    elif l.startswith("water hookup kit"):
        add("dock.plumbed_refill_drain", f, v, lab)


if __name__ == "__main__":
    _run.main(MovaRobovac())
