#!/usr/bin/env python3
"""Ecovacs US robot-vacuum adapter v2 (contract ARCHITECTURE 15.5), category robot-vacuums. Source = www.ecovacs.com/us shop (Next.js).
v2: fingerprints.unmapped is a {label: example} map (v1 wrote a list, which import.py cannot read); claims unchanged.

discover : /us/shop/deebot-robotic-vacuum-cleaner?page=N (robots: '*/deebot-robotic-vacuum-cleaner?page=*' is explicitly allowed; every other
           '?page=' is disallowed). Each page's server-rendered __NEXT_DATA__ carries productData.list (12/page, page_data.total_page). Only
           goods_type 'main_goods' DEEBOT robots are kept (packages = robot + accessory kits, WINBOT bundles are dropped). Colour pages of one robot
           ('DEEBOT T90S OMNI Black') and the '... Care' plan page group into one model by the colour-stripped model name.
fetch    : bundle = every member's product page HTML (SSR __NEXT_DATA__ = the shop's product API response: base_info + spec_list).
parse    : pure. pageData.spec_list[0].spec_list = groups (' Navigation mode', ' DEEBOT Function', ' Station Function', ' SPEC',
           'Packaing&Accessories') of labelled rows (name, value). Read per (group, label): the same label ('clean water tank capacity') means the
           robot tank under DEEBOT Function and the station tank under Station Function. Units are in the label ('(L)', '(ml)', '(KG)', 'mm').
           Y/N cells -> bool. Runtime/noise rows name their mode in the label ('silent mode', 'standard mode'); only the vacuum-only ('sweep') rows
           are read.
Identity : Ecovacs prints no regulatory model code on the US shop: mfr_model = the product name's model head minus colour (DEEBOT T80 OMNI);
           base_info.sku (OZT80, the US channel code) and upc are configuration aliases of the model.
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _robovac as RV
import _run

ID, VERSION, SOURCE = "ecovacs_robovac", 3, "ecovacs-us-robovac"     # v3: review-3 strict enums / plausibility kept as preview
CATEGORIES = {"robot-vacuums"}
ADAPTER = f"{ID}@{VERSION}"
LIST = "https://www.ecovacs.com/us/shop/deebot-robotic-vacuum-cleaner"
PDP = LIST + "/{}"
COLOUR = re.compile(r"(?i)\s+(black|white|silver|grey|gray|care)$")
NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def next_data(h):
    m = NEXT.search(h or "")
    return json.loads(m[1]) if m else None


def model_name(title):
    """Model from the shop's own product name (base_info.name / list name): the 'model' field is unreliable (OZT3MXP, 'N8 PRO;D-AS01', T10OMNI).
    'Official Exclusive - DEEBOT T90S ULTRA OMNI Black Robot Vacuum & Mop (...)' -> 'DEEBOT T90S ULTRA OMNI'; '+' -> ' PLUS'; colour / 'Care'
    (care-plan page of the same robot) dropped."""
    t = RV.text(title or "")
    t = re.sub(r"(?i)^(official exclusive\s*-\s*)?(ecovacs\s+)?", "", t)
    t = re.split(r"(?i)\s+(?:robot|automated|auto-empty|self-empty|bagless|square)\b|\s+-\s|\s*[(（]", t)[0].strip()
    while COLOUR.search(t):
        t = COLOUR.sub("", t)
    t = re.sub(r"\s*\+(?=\s|$)", " PLUS", t.upper()).replace("OMNICYCLONE", "OmniCyclone")
    if not t.startswith("DEEBOT "):
        return None
    return t if re.search(r"\d", t) and len(t) <= 40 else None


def is_robot(p):
    m = (p.get("model") or "") + " " + (p.get("name") or "")
    return p.get("goods_type") == "main_goods" and not re.search(r"(?i)winbot|goat|airbot|accessor|refurb|\bkit\b", m)


class EcovacsRobovac:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        items, stop, page, total = [], None, 1, 1
        while page <= total and page <= 30:
            r = net.get(f"{LIST}?page={page}" if page > 1 else LIST, RV.DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                stop = f"list page {page}: {getattr(r, 'status_code', r)}"
                break
            pd = ((next_data(r.text) or {}).get("props", {}).get("pageProps", {}).get("productData") or {})
            total = int((pd.get("page_data") or {}).get("total_page") or 1)
            items += pd.get("list") or []
            page += 1
        groups = {}
        for p in items:
            name = model_name(p.get("name")) if is_robot(p) else None
            if name:
                groups.setdefault(name, []).append(p["alias"])
        refs = []
        for name, aliases in sorted(groups.items()):
            aliases = sorted({a for a in aliases if a}, key=lambda a: ("care" in a, len(a), a))
            key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            refs.append(C.Ref(SOURCE, key, PDP.format(aliases[0]), {"model": name, "handles": aliases}))
        return C.Discovery(refs, stop is None, stop, {"items": len(items), "main_goods": sum(map(is_robot, items)), "models": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        pages, missing, first = {}, [], None
        for a in ref.hints.get("handles") or [ref.url.rsplit("/", 1)[1]]:
            r = net.get(PDP.format(a), RV.DELAY)
            if hasattr(r, "status_code") and r.status_code == 200:
                pages[a] = r.text
                first = first or r
            else:
                missing.append(a)
        if not pages:
            s = C.Snapshot("sha256:", ref, "no member page", now, ref.url, {})
            self.store.append(s, ADAPTER, ".json.gz")
            return s
        blob = gzip.compress(json.dumps({"page_url": ref.url, "pages": pages, "missing": missing}, sort_keys=True).encode(), 6, mtime=0)
        s = C.Snapshot(self.store.put(blob, ".json.gz"), ref, 200, now, first.url, {"etag": None, "last_modified": None})
        self.store.append(s, ADAPTER, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, RV.read_bundle(blobs, snap))


def yn(v):
    t = (v or "").strip().upper()
    return True if re.match(r"^Y\b", t) else False if t in ("N", "NO") else None


def num(v):
    """A bare number, optionally followed by the label's own unit ('5.4(KG)', '5.5 (KG)'); '≈5kg' / '5.3±0.1' -> None."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:\(?\s*(?:kg|mm|ml|l|mah|pa|min)\s*\)?)?\s*", v or "", re.I)
    return float(m[1]) if m else None


def dims(v):
    """'353*351.5*98' (label says wide/depth/height mm) -> {length,width,height} in printed order."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[*x×]\s*(\d+(?:\.\d+)?)\s*[*x×]\s*(\d+(?:\.\d+)?)\s*(mm)?\s*", v or "")
    return {"length": float(m[1]), "width": float(m[2]), "height": float(m[3])} if m else None


def rows_of(info):
    out = []
    for g in ((info.get("spec_list") or [{}])[0].get("spec_list") or []):
        for s in g.get("son_list") or []:
            out.append((RV.text(g.get("name")).lower(), RV.text(s.get("name")), RV.text(str(s.get("value") or ""))))
    return out


def L(lab):
    """Normalised label: lower case, full-width brackets -> ASCII, spaces squeezed."""
    t = lab.lower().replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", " ", t).strip()


def parse_bundle(snap, b):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "Ecovacs US shop product page " + snap.ref.key}]
    infos = {}
    for a, h in sorted((b.get("pages") or {}).items()):
        pd = ((next_data(h) or {}).get("props", {}).get("pageProps", {}).get("pageData") or {})
        if pd.get("base_info"):
            infos[a] = pd
    canon_alias = snap.ref.url.rsplit("/", 1)[1]
    canon = infos.get(canon_alias) or next(iter(infos.values()), None)
    name = model_name((canon or {}).get("base_info", {}).get("name"))
    if not canon or not name:
        pr.absences.append({"key": "*", "reason": "no product __NEXT_DATA__ with a model in bundle", "source": "s1"})
        return pr
    pr.identifiers.append(RV.ident("mfr_model", name, "model", "ecovacs", raw=RV.text(canon["base_info"]["name"]), series=name.split()[1][:1]))
    pr.aliases.append({"text": "ECOVACS " + name, "kind": "marketing_name"})
    seen = set()
    for a, pd in infos.items():
        bi = pd["base_info"]
        if model_name(bi.get("name")) != name:
            continue
        sku = (bi.get("sku") or "").strip()
        if sku and sku not in seen:
            seen.add(sku)
            colour = (COLOUR.search(RV.text(bi.get("model"))) or [None, None])[1]  # model field keeps the colour word
            pr.identifiers.append(RV.ident("mfr_sku", sku, "configuration", "ecovacs", role="alias", parent=name, option=colour))
        upc = re.sub(r"\D", "", bi.get("upc") or "")
        if len(upc) in (12, 13) and upc not in seen:
            seen.add(upc)
            pr.identifiers.append(RV.ident("gtin", upc, "configuration", "ecovacs", role="alias", parent=name))
        if bi.get("name"):
            pr.aliases.append({"text": RV.text(bi["name"]), "kind": "retail_title"})
    rows = rows_of(canon)

    def add(k, v, raw, label, cond=None):
        RV.add(pr, ADAPTER, snap, name, k, v, raw, label, cond)
    if not rows:
        pr.absences.append({"key": "*", "reason": "spec_list empty on the product page", "source": "s1"})
    used, done = set(), set()
    for grp, lab, v in rows:
        l = L(lab)
        if not v or v in ("/", "-") or (grp, l) in done:
            continue
        done.add((grp, l))
        k0 = len(pr.claims)
        station = "station" in grp
        if l.startswith("vacuum level") and "pa" in l:
            add("clean.suction_pa", RV.pa(v if re.search(r"[a-z]", v, re.I) else v + "Pa"), v, lab, {"claim_basis": "mfr_unstated"})
        elif l.startswith("battery capacity") and "mah" in l:
            add("bat.capacity_mah", RV.mah(v if re.search(r"[a-z]", v, re.I) else v + "mAh"), v, lab)
        elif l.startswith("dust box capacity") and "(l)" in l and num(v):
            add("clean.dustbin_ml", round(num(v) * 1000), v, lab)
        elif l == "navigation type":
            add("nav.type", RV.navigation(v), v, lab)
        elif l == "obstacle avoidance":
            add("nav.obstacle_sensors", RV.obstacle_sensors(v), v, lab)
        elif l == "mopping type":
            add("mop.type", RV.mop_type(v), v, lab)
        elif (l.startswith("clean water tank capacity") or (l.startswith("water tank capacity") and not station)) and num(v):
            unit = 1000 if "(l)" in l else 1 if "(ml)" in l else None
            if unit:
                add("dock.clean_tank_ml" if station else "mop.robot_tank_ml", round(num(v) * unit), v, lab)
        elif l.startswith("dirty water tank capacity") and num(v) and station:
            unit = 1000 if "(l)" in l else 1 if "(ml)" in l else None
            if unit:
                add("dock.dirty_tank_ml", round(num(v) * unit), v, lab)
        elif l == "auto refill (station to deebot)":
            add("mop.auto_refill_from_dock", yn(v), v, lab)
        elif l.startswith("barrier crossing ability (mm)") and num(v):
            add("nav.obstacle_crossing_mm", num(v), v, lab)
        elif l.startswith("automatic mop lifting"):
            if num(v):
                add("mop.lifting", True, v, lab); add("mop.lift_height_mm", num(v), v, lab)
            elif yn(v) is not None:
                add("mop.lifting", yn(v), v, lab)
        elif l == "auto dust collection":
            add("dock.self_empty", yn(v), v, lab)
        elif l.startswith("dust bag capacity") and "(l)" in l and num(v):
            add("dock.dust_bag_ml", round(num(v) * 1000), v, lab)
        elif l == "automatic mop cleaning" and station:
            add("dock.mop_wash", yn(v), v, lab)
        elif l in ("warm water mop cleaning", "warm water mop cleaning(y/n)"):
            add("dock.hot_water_wash", yn(v), v, lab)
            if yn(v):
                add("dock.wash_water_temp_c", RV.temp_c(v.replace("℃", "°C")), v, lab)
        elif l == "hot air dry":
            add("dock.hot_air_dry", yn(v), v, lab)
        elif l == "auto detergent dispenser":
            add("dock.solution_dispense", yn(v), v, lab)
        elif l in ("compatible with automatic upper and lower water system", "auto refill and drain"):
            add("dock.plumbed_refill_drain", yn(v), v, lab)
        elif l.startswith("noise-standard mode -sweep") or l.startswith("noise-standard mode-sweep ("):
            add("noise.db", num(v), v, lab, {"claim_basis": "mfr_unstated", "power_mode": "standard"})
        elif re.match(r"working time on hard floor-(silent|standard) mode\(sweep\)", l) and num(v):
            add("bat.runtime_min", int(num(v)), v, lab, {"claim_basis": "mfr_unstated", "power_mode": RV.power_mode(l)})
        elif l.startswith("deebot dimension") and "mm" in l and (d := dims(v)):
            d = RV.robot_dims(d)
            add("phys.robot_dimensions", d, v, lab); add("phys.robot_height_mm", RV.robot_height(d), v, lab)
        elif l.startswith("deebot net weight (kg)") and num(v):
            add("phys.robot_weight_g", RV.robot_weight(round(num(v) * 1000)), v, lab)
        elif l.startswith("station net weight(kg)") and num(v):
            add("phys.dock_weight_g", round(num(v) * 1000), v, lab)
        elif l.startswith("station dimension") and "without base" not in l and (d := dims(v)) and all(100 <= x <= 800 for x in d.values()):
            if "(with base)" in l or not any(L(r[1]).startswith("station dimension") and "(with base)" in L(r[1]) for r in rows):
                add("phys.dock_dimensions", d, v, lab)
        elif l.startswith("integrated voice control"):
            add("smart.voice_control", {True: "integrated", False: "none"}.get(yn(v)), v, lab)
        if len(pr.claims) > k0:
            used.add(lab)
    pr.fingerprints = {"raw": snap.snapshot, "labels": sorted({r[1] for r in rows}), "members": sorted(infos),
                       "unmapped": {r[1]: r[2][:80] for r in rows if r[1] not in used}}
    return pr


if __name__ == "__main__":
    _run.main(EcovacsRobovac())
